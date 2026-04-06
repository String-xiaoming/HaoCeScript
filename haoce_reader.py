from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import cv2
import numpy as np


CONTINUE_READING_TEXT = "继续阅读"
RECENT_READING_TEXT = "最近阅读"
PROGRESS_PREFIX = "进度:"


def log(message: str) -> None:
    now = time.strftime("%H:%M:%S")
    line = f"[{now}] {message}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_line = line.encode(encoding, errors="backslashreplace").decode(encoding)
        print(safe_line, flush=True)


def parse_bounds(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", value)
    if not match:
        raise ValueError(f"invalid bounds: {value}")
    x1, y1, x2, y2 = map(int, match.groups())
    return x1, y1, x2, y2


def center(bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bounds
    return (x1 + x2) // 2, (y1 + y2) // 2


def area(bounds: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bounds
    return max(0, x2 - x1) * max(0, y2 - y1)


def iter_nodes(node: ET.Element) -> Iterator[ET.Element]:
    yield node
    for child in node:
        yield from iter_nodes(child)


@dataclass
class SwipeConfig:
    start: tuple[float, float]
    end: tuple[float, float]
    start_jitter: tuple[float, float]
    end_jitter: tuple[float, float]
    duration_ms: int
    duration_jitter_ms: int
    settle_ms: int
    pause_ms: int


@dataclass
class PageTurnConfig:
    action: str
    start: Optional[tuple[float, float]]
    end: Optional[tuple[float, float]]
    start_jitter: tuple[float, float]
    end_jitter: tuple[float, float]
    tap: Optional[tuple[float, float]]
    duration_ms: int
    duration_jitter_ms: int
    settle_ms: int


@dataclass
class NavigationConfig:
    launch_app: bool
    open_recent_index: Optional[int]
    auto_continue_from_report: bool
    prepare_wait_ms: int


@dataclass
class AnalysisConfig:
    crop: tuple[float, float, float, float]
    pixel_diff_threshold: int
    stuck_mean_diff_max: float
    stuck_changed_ratio_max: float
    page_turn_mean_diff_min: float
    page_turn_changed_ratio_min: float
    bottom_confirmations: int


@dataclass
class RuntimeConfig:
    loop_sleep_ms: int
    max_page_turns: int
    max_minutes: int
    debug_dir: Optional[str]


@dataclass
class ReaderConfig:
    serial: Optional[str]
    package: str
    navigation: NavigationConfig
    scroll: SwipeConfig
    page_turn: PageTurnConfig
    analysis: AnalysisConfig
    runtime: RuntimeConfig


@dataclass
class DiffMetrics:
    mean_diff: float
    changed_ratio: float


@dataclass(frozen=True)
class RecentBook:
    title: str
    image_key: Optional[str]
    progress_text: str
    progress_percent: Optional[float]
    bounds: tuple[int, int, int, int]

    @property
    def key(self) -> str:
        if self.image_key:
            return self.image_key
        return f"{self.title}:{self.bounds}"

    def is_complete(self, threshold: float = 99.9) -> bool:
        return self.progress_percent is not None and self.progress_percent >= threshold


class ConfigError(RuntimeError):
    pass


def parse_progress_percent(value: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", value)
    if not match:
        return None
    return float(match.group(1))


def load_config(path: Path) -> ReaderConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    navigation = raw["navigation"]
    scroll = raw["scroll"]
    page_turn = raw["page_turn"]
    analysis = raw["analysis"]
    runtime = raw["runtime"]

    return ReaderConfig(
        serial=raw.get("serial"),
        package=raw.get("package", "app.haoce.com"),
        navigation=NavigationConfig(
            launch_app=bool(navigation.get("launch_app", True)),
            open_recent_index=navigation.get("open_recent_index"),
            auto_continue_from_report=bool(
                navigation.get("auto_continue_from_report", True)
            ),
            prepare_wait_ms=int(navigation.get("prepare_wait_ms", 2000)),
        ),
        scroll=SwipeConfig(
            start=tuple(scroll["start"]),
            end=tuple(scroll["end"]),
            start_jitter=tuple(scroll.get("start_jitter", [0.0, 0.0])),
            end_jitter=tuple(scroll.get("end_jitter", [0.0, 0.0])),
            duration_ms=int(scroll["duration_ms"]),
            duration_jitter_ms=int(scroll.get("duration_jitter_ms", 0)),
            settle_ms=int(scroll["settle_ms"]),
            pause_ms=int(scroll.get("pause_ms", 0)),
        ),
        page_turn=PageTurnConfig(
            action=str(page_turn.get("action", "swipe")),
            start=tuple(page_turn["start"]) if page_turn.get("start") else None,
            end=tuple(page_turn["end"]) if page_turn.get("end") else None,
            start_jitter=tuple(page_turn.get("start_jitter", [0.0, 0.0])),
            end_jitter=tuple(page_turn.get("end_jitter", [0.0, 0.0])),
            tap=tuple(page_turn["tap"]) if page_turn.get("tap") else None,
            duration_ms=int(page_turn.get("duration_ms", 300)),
            duration_jitter_ms=int(page_turn.get("duration_jitter_ms", 0)),
            settle_ms=int(page_turn.get("settle_ms", 1500)),
        ),
        analysis=AnalysisConfig(
            crop=tuple(analysis["crop"]),
            pixel_diff_threshold=int(analysis.get("pixel_diff_threshold", 12)),
            stuck_mean_diff_max=float(analysis.get("stuck_mean_diff_max", 2.0)),
            stuck_changed_ratio_max=float(
                analysis.get("stuck_changed_ratio_max", 0.015)
            ),
            page_turn_mean_diff_min=float(
                analysis.get("page_turn_mean_diff_min", 8.0)
            ),
            page_turn_changed_ratio_min=float(
                analysis.get("page_turn_changed_ratio_min", 0.08)
            ),
            bottom_confirmations=int(analysis.get("bottom_confirmations", 2)),
        ),
        runtime=RuntimeConfig(
            loop_sleep_ms=int(runtime.get("loop_sleep_ms", 250)),
            max_page_turns=int(runtime.get("max_page_turns", 30)),
            max_minutes=int(runtime.get("max_minutes", 0)),
            debug_dir=runtime.get("debug_dir"),
        ),
    )


class AdbDevice:
    def __init__(self, serial: Optional[str], package: str) -> None:
        self.serial = serial
        self.package = package

    def _base(self) -> list[str]:
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def run(
        self,
        *args: str,
        capture_output: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [*self._base(), *args],
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            check=check,
        )

    def shell(self, *args: str, check: bool = True) -> str:
        result = self.run("shell", *args, check=check)
        return result.stdout.decode("utf-8", errors="ignore").strip()

    def ensure_ready(self) -> None:
        state = self.run("get-state").stdout.decode("utf-8", errors="ignore").strip()
        if state != "device":
            raise RuntimeError(f"adb device state is {state!r}, expected 'device'")

        package_path = self.shell("pm", "path", self.package)
        if self.package not in package_path:
            raise RuntimeError(f"package not found: {self.package}")

    def wm_size(self) -> tuple[int, int]:
        output = self.shell("wm", "size")
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        if not match:
            raise RuntimeError(f"unable to parse wm size: {output}")
        return int(match.group(1)), int(match.group(2))

    def launch_app(self) -> None:
        self.run(
            "shell",
            "monkey",
            "-p",
            self.package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        )

    def tap(self, x: int, y: int) -> None:
        self.run("shell", "input", "tap", str(x), str(y))

    def back(self) -> None:
        self.run("shell", "input", "keyevent", "4")

    def swipe(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        duration_ms: int,
    ) -> None:
        self.run(
            "shell",
            "input",
            "swipe",
            str(start[0]),
            str(start[1]),
            str(end[0]),
            str(end[1]),
            str(duration_ms),
        )

    def capture(self) -> np.ndarray:
        result = self.run("exec-out", "screencap", "-p")
        buffer = np.frombuffer(result.stdout, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("failed to decode screenshot")
        return image

    def dump_ui(self) -> ET.Element:
        remote_path = "/sdcard/__haoce_ui_dump.xml"
        last_error: Optional[subprocess.CalledProcessError] = None
        for attempt in range(3):
            try:
                self.run("shell", "uiautomator", "dump", remote_path)
                time.sleep(0.3)
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
                time.sleep(0.5)
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("uiautomator dump failed without an error")
        with tempfile.NamedTemporaryFile(
            prefix="haoce_ui_", suffix=".xml", delete=False
        ) as handle:
            local_path = Path(handle.name)
        try:
            self.run("pull", remote_path, str(local_path))
            content = local_path.read_text(encoding="utf-8", errors="ignore")
            return ET.fromstring(content)
        finally:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.run("shell", "rm", "-f", remote_path, check=False)


class PageAnalyzer:
    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config

    def _crop_gray(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        left, top, right, bottom = self.config.crop
        x1 = max(0, min(width - 1, int(width * left)))
        y1 = max(0, min(height - 1, int(height * top)))
        x2 = max(x1 + 1, min(width, int(width * right)))
        y2 = max(y1 + 1, min(height, int(height * bottom)))
        cropped = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, (360, 800), interpolation=cv2.INTER_AREA)

    def diff(self, before: np.ndarray, after: np.ndarray) -> DiffMetrics:
        a = self._crop_gray(before)
        b = self._crop_gray(after)
        delta = cv2.absdiff(a, b)
        mean_diff = float(delta.mean())
        changed_ratio = float((delta > self.config.pixel_diff_threshold).mean())
        return DiffMetrics(mean_diff=mean_diff, changed_ratio=changed_ratio)

    def looks_stuck(self, metrics: DiffMetrics) -> bool:
        return (
            metrics.mean_diff <= self.config.stuck_mean_diff_max
            and metrics.changed_ratio <= self.config.stuck_changed_ratio_max
        )

    def page_turn_confirmed(self, metrics: DiffMetrics) -> bool:
        return (
            metrics.mean_diff >= self.config.page_turn_mean_diff_min
            or metrics.changed_ratio >= self.config.page_turn_changed_ratio_min
        )


class UiNavigator:
    def __init__(self, device: AdbDevice) -> None:
        self.device = device

    def _current_page_name(self, root: ET.Element) -> Optional[str]:
        anchors = {
            "校图书读书工程": "collection",
            "首页": "home",
            "成绩": "report",
        }
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            page_name = anchors.get(text)
            if page_name:
                return page_name
        return None

    def _page_subtree(self, root: ET.Element, page_name: str) -> Optional[ET.Element]:
        if self._current_page_name(root) != page_name:
            return None

        anchors = {
            "collection": "校图书读书工程",
            "home": "首页",
            "report": "成绩",
        }
        target = anchors[page_name]
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            if text == target:
                return node
        return None

    def report_title(self, root: ET.Element) -> Optional[str]:
        subtree = self._page_subtree(root, "report")
        if subtree is None:
            return None

        best_text = None
        best_y = None
        for node in iter_nodes(subtree):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text or text in {"返回", "读书报告", "继续阅读", "成绩"}:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            if bounds[1] > 260:
                continue
            if best_y is None or bounds[1] < best_y:
                best_text = text
                best_y = bounds[1]
        return best_text

    def report_progress(self, root: ET.Element) -> Optional[float]:
        subtree = self._page_subtree(root, "report")
        if subtree is None:
            return None

        best = None
        best_y = None
        for node in iter_nodes(subtree):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text or "%" not in text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            if not (300 <= bounds[1] <= 700):
                continue
            if bounds[0] > 650:
                continue
            value = parse_progress_percent(text)
            if value is None:
                continue
            if best_y is None or bounds[1] < best_y:
                best = value
                best_y = bounds[1]
        return best

    def find_text_bounds(
        self,
        root: ET.Element,
        target: str,
    ) -> Optional[tuple[int, int, int, int]]:
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if text != target or not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            return bounds
        return None

    def detail_title(self, root: ET.Element) -> Optional[str]:
        start_bounds = self.find_text_bounds(root, "开始阅读")
        if not start_bounds:
            return None

        best_text = None
        best_area = -1
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text or text in {"返回", "书香理工", "开始阅读"}:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            if not (220 <= bounds[1] <= 500):
                continue
            current_area = area(bounds)
            if current_area > best_area:
                best_text = text
                best_area = current_area
        return best_text

    def detail_progress(self, root: ET.Element) -> Optional[float]:
        start_bounds = self.find_text_bounds(root, "开始阅读")
        if not start_bounds:
            return None

        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text or "%" not in text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            if not (1100 <= bounds[1] <= 1450):
                continue
            value = parse_progress_percent(text)
            if value is not None:
                return value
        return None

    def find_clickable_text(
        self, root: ET.Element, target: str
    ) -> Optional[tuple[int, int, int, int]]:
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            if target not in text:
                continue
            bounds = node.attrib.get("bounds")
            clickable = node.attrib.get("clickable") == "true"
            enabled = node.attrib.get("enabled") == "true"
            if bounds and enabled and (clickable or node.attrib.get("class", "").endswith("Button")):
                return parse_bounds(bounds)
        return None

    def list_recent_books(self, root: ET.Element) -> list[RecentBook]:
        items: list[RecentBook] = []
        seen: set[tuple[int, int, int, int]] = set()
        subtree = self._page_subtree(root, "home")
        if subtree is None:
            return []

        for node in iter_nodes(subtree):
            bounds_text = node.attrib.get("bounds")
            if not bounds_text:
                continue
            direct_children = list(node)
            if not direct_children:
                continue
            progress_text = None
            title = ""
            image_key = None
            for child in direct_children:
                text = (child.attrib.get("text") or "").strip()
                if not text:
                    continue
                if text.startswith(PROGRESS_PREFIX):
                    progress_text = text
                    continue
                child_class = child.attrib.get("class", "")
                if "Image" in child_class and image_key is None:
                    image_key = text
                    continue
                if not title:
                    title = text

            if not progress_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) < 15000:
                continue
            if bounds not in seen:
                items.append(
                    RecentBook(
                        title=title,
                        image_key=image_key,
                        progress_text=progress_text,
                        progress_percent=parse_progress_percent(progress_text),
                        bounds=bounds,
                    )
                )
                seen.add(bounds)
        items.sort(key=lambda item: (item.bounds[1], item.bounds[0]))
        return items

    def list_recent_item_bounds(self, root: ET.Element) -> list[tuple[int, int, int, int]]:
        return [item.bounds for item in self.list_recent_books(root)]

    def find_recent_book_by_key(
        self,
        root: ET.Element,
        key: str,
    ) -> Optional[RecentBook]:
        for item in self.list_recent_books(root):
            if item.key == key:
                return item
        return None

    def first_unfinished_recent_book(
        self,
        root: ET.Element,
        exclude_keys: Optional[set[str]] = None,
    ) -> Optional[RecentBook]:
        excluded = exclude_keys or set()
        for item in self.list_recent_books(root):
            if item.key in excluded:
                continue
            if not item.is_complete():
                return item
        return None

    def find_home_collection_entry(self, root: ET.Element) -> Optional[tuple[int, int, int, int]]:
        subtree = self._page_subtree(root, "home")
        if subtree is None:
            return None

        candidates: list[tuple[int, int, int, int]] = []
        for node in iter_nodes(subtree):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if text != "书香理工" or not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if bounds[1] < 1100:
                candidates.append(bounds)

        if not candidates:
            return None

        x1, y1, x2, y2 = min(candidates, key=lambda item: (item[1], item[0]))
        return max(0, x1 - 24), max(0, y1 - 180), x2 + 24, y2 + 24

    def list_collection_books(self, root: ET.Element) -> list[RecentBook]:
        items: list[RecentBook] = []
        seen: set[tuple[int, int, int, int]] = set()
        subtree = self._page_subtree(root, "collection")
        if subtree is None:
            return []

        for node in iter_nodes(subtree):
            bounds_text = node.attrib.get("bounds")
            if not bounds_text:
                continue
            direct_children = list(node)
            if not direct_children:
                continue

            progress_text = None
            title = ""
            image_key = None
            for child in direct_children:
                text = (child.attrib.get("text") or "").strip()
                if not text:
                    continue
                if "进度" in text or "讲度" in text:
                    progress_text = text
                    continue
                child_class = child.attrib.get("class", "")
                if "Image" in child_class and image_key is None:
                    image_key = text
                    continue
                if text != "• " and not title:
                    title = text

            if not progress_text or not title:
                continue

            bounds = parse_bounds(bounds_text)
            if area(bounds) < 60000:
                continue

            if bounds not in seen:
                items.append(
                    RecentBook(
                        title=title,
                        image_key=image_key,
                        progress_text=progress_text,
                        progress_percent=parse_progress_percent(progress_text),
                        bounds=bounds,
                    )
                )
                seen.add(bounds)

        items.sort(key=lambda item: (item.bounds[1], item.bounds[0]))
        return items

    def inspect(self) -> dict[str, object]:
        root = self.device.dump_ui()
        texts = [(node.attrib.get("text") or "").strip() for node in iter_nodes(root)]
        return {
            "has_continue_button": self.find_clickable_text(root, CONTINUE_READING_TEXT)
            is not None,
            "has_recent_reading": RECENT_READING_TEXT in texts,
            "recent_items": len(self.list_recent_item_bounds(root)),
        }

    def prepare_reading_page(self, config: NavigationConfig) -> str:
        root = self.device.dump_ui()

        if config.auto_continue_from_report:
            button = self.find_clickable_text(root, CONTINUE_READING_TEXT)
            if button:
                x, y = center(button)
                log(f"found '{CONTINUE_READING_TEXT}', tapping {x},{y}")
                self.device.tap(x, y)
                return "continue"

        if config.open_recent_index and config.open_recent_index > 0:
            items = self.list_recent_books(root)
            if items and len(items) >= config.open_recent_index:
                book = items[config.open_recent_index - 1]
                x, y = center(book.bounds)
                log(
                    f"opening recent book #{config.open_recent_index} at {x},{y}"
                )
                self.device.tap(x, y)
                time.sleep(config.prepare_wait_ms / 1000)

                if config.auto_continue_from_report:
                    root = self.device.dump_ui()
                    button = self.find_clickable_text(root, CONTINUE_READING_TEXT)
                    if button:
                        x, y = center(button)
                        log(f"found '{CONTINUE_READING_TEXT}', tapping {x},{y}")
                        self.device.tap(x, y)
                        return "open_recent_then_continue"
                return "open_recent"

        return "noop"


class HaoceReader:
    def __init__(self, config: ReaderConfig) -> None:
        self.config = config
        self.device = AdbDevice(config.serial, config.package)
        self.navigator = UiNavigator(self.device)
        self.analyzer = PageAnalyzer(config.analysis)
        self.screen_size = (0, 0)
        self.current_book: Optional[RecentBook] = None
        self.completed_book_keys: set[str] = set()
        self.debug_dir = (
            Path(config.runtime.debug_dir).resolve()
            if config.runtime.debug_dir
            else None
        )

    def _ratio_to_abs(self, point: tuple[float, float]) -> tuple[int, int]:
        if self.screen_size == (0, 0):
            self.screen_size = self.device.wm_size()
        width, height = self.screen_size
        return int(width * point[0]), int(height * point[1])

    def _clamp_point(self, point: tuple[int, int]) -> tuple[int, int]:
        if self.screen_size == (0, 0):
            self.screen_size = self.device.wm_size()
        width, height = self.screen_size
        x = max(0, min(width - 1, point[0]))
        y = max(0, min(height - 1, point[1]))
        return x, y

    def _randomized_point(
        self,
        point: tuple[float, float],
        jitter: tuple[float, float],
    ) -> tuple[int, int]:
        x = point[0] + random.uniform(-jitter[0], jitter[0])
        y = point[1] + random.uniform(-jitter[1], jitter[1])
        return self._clamp_point(self._ratio_to_abs((x, y)))

    def _randomized_duration(self, duration_ms: int, jitter_ms: int) -> int:
        if jitter_ms <= 0:
            return duration_ms
        return max(1, duration_ms + random.randint(-jitter_ms, jitter_ms))

    def _sleep_ms(self, delay_ms: int) -> None:
        if delay_ms <= 0:
            return
        time.sleep(delay_ms / 1000)

    def _swipe_ratio(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        duration_ms: int,
    ) -> None:
        self.device.swipe(
            self._ratio_to_abs(start),
            self._ratio_to_abs(end),
            duration_ms,
        )

    def _describe_book(self, book: Optional[RecentBook]) -> str:
        if not book:
            return "<unknown>"
        if book.title and book.progress_text:
            return f"{book.title} ({book.progress_text})"
        if book.title:
            return book.title
        if book.progress_text:
            return book.progress_text
        return book.key

    def _save_debug(self, name: str, image: np.ndarray) -> None:
        if not self.debug_dir:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / name
        cv2.imwrite(str(path), image)

    def _tap_continue_if_present(self, root: Optional[ET.Element] = None) -> bool:
        if not self.config.navigation.auto_continue_from_report:
            return False
        if root is None:
            root = self.device.dump_ui()
        button = self.navigator.find_clickable_text(root, CONTINUE_READING_TEXT)
        if not button:
            return False
        x, y = center(button)
        log(f"found '{CONTINUE_READING_TEXT}', tapping {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        return True

    def _tap_start_reading_if_present(self, root: Optional[ET.Element] = None) -> bool:
        if root is None:
            root = self.device.dump_ui()
        button = self.navigator.find_text_bounds(root, "开始阅读")
        if not button:
            return False
        x, y = center(button)
        log(f"found '开始阅读', tapping {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        return True

    def _open_recent_book(self, book: RecentBook) -> str:
        x, y = center(book.bounds)
        log(f"opening recent book: {self._describe_book(book)} at {x},{y}")
        self.device.tap(x, y)
        self.current_book = book
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        if self._tap_continue_if_present():
            return "open_recent_then_continue"
        return "open_recent"

    def _refresh_recent_home(self) -> None:
        log("refreshing home page to sync reading progress")
        self._swipe_ratio((0.5, 0.34), (0.5, 0.78), 650)
        self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 2500))

    def _open_collection_book(self, book: RecentBook) -> str:
        x, y = center(book.bounds)
        log(f"opening collection book: {self._describe_book(book)} at {x},{y}")
        self.device.tap(x, y)
        self.current_book = book
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        candidate_root = self.device.dump_ui()
        if self._tap_continue_if_present(candidate_root):
            return "open_collection_then_continue"
        if self._tap_start_reading_if_present(candidate_root):
            return "open_collection_then_start"
        if self.navigator._current_page_name(candidate_root) == "collection":
            log("collection card tap did not leave the collection page")
            return "open_collection_miss"
        return "open_collection"

    def _open_home_collection_page(self, root: ET.Element) -> Optional[ET.Element]:
        bounds = self.navigator.find_home_collection_entry(root)
        if not bounds:
            return None
        x, y = center(bounds)
        log(f"opening collection entry at {x},{y}")
        self.device.tap(x, y)
        for _ in range(4):
            self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1500))
            current_root = self.device.dump_ui()
            if self.navigator._current_page_name(current_root) == "collection":
                return current_root
        return None

    def _find_next_collection_book(
        self,
        root: ET.Element,
        max_scrolls: int = 12,
    ) -> Optional[RecentBook]:
        seen_signatures: set[tuple[str, ...]] = set()

        for attempt in range(max_scrolls + 1):
            books = self.navigator.list_collection_books(root)
            signature = tuple(book.key for book in books)
            if signature in seen_signatures:
                break
            seen_signatures.add(signature)

            for book in books:
                if book.key in self.completed_book_keys:
                    continue
                if not book.is_complete():
                    return book

            if attempt == max_scrolls:
                break

            log("no unfinished visible collection book yet, scrolling collection list")
            self._swipe_ratio((0.5, 0.8), (0.5, 0.34), 550)
            self._sleep_ms(self.config.page_turn.settle_ms)
            root = self.device.dump_ui()

        return None

    def _collection_slot_points(self) -> list[tuple[int, int]]:
        return [
            self._ratio_to_abs((0.17, 0.41)),
            self._ratio_to_abs((0.50, 0.41)),
            self._ratio_to_abs((0.83, 0.41)),
            self._ratio_to_abs((0.17, 0.63)),
            self._ratio_to_abs((0.50, 0.63)),
            self._ratio_to_abs((0.83, 0.63)),
        ]

    def _open_next_collection_book_by_slots(
        self,
        root: ET.Element,
        max_pages: int = 8,
    ) -> str:
        tried_slots: set[tuple[int, int, int]] = set()

        for page_index in range(max_pages):
            for slot_index, point in enumerate(self._collection_slot_points()):
                slot_key = (page_index, point[0], point[1])
                if slot_key in tried_slots:
                    continue
                tried_slots.add(slot_key)

                log(
                    f"trying collection slot page={page_index + 1} slot={slot_index + 1} at {point[0]},{point[1]}"
                )
                self.device.tap(point[0], point[1])
                self._sleep_ms(self.config.navigation.prepare_wait_ms + 1000)
                candidate_root = self.device.dump_ui()
                report_progress = self.navigator.report_progress(candidate_root)
                detail_progress = self.navigator.detail_progress(candidate_root)
                continue_bounds = self.navigator.find_clickable_text(
                    candidate_root,
                    CONTINUE_READING_TEXT,
                )
                start_bounds = self.navigator.find_text_bounds(candidate_root, "开始阅读")
                opened_book = (
                    continue_bounds is not None
                    or start_bounds is not None
                    or report_progress is not None
                    or detail_progress is not None
                )

                if not opened_book:
                    continue

                title = (
                    self.navigator.report_title(candidate_root)
                    or self.navigator.detail_title(candidate_root)
                    or f"collection-slot-{page_index + 1}-{slot_index + 1}"
                )
                progress = (
                    report_progress
                    if report_progress is not None
                    else detail_progress
                )
                progress_text = (
                    f"进度:{progress:.2f}%"
                    if progress is not None
                    else "进度:unknown"
                )
                log(
                    f"collection candidate opened: {title}, progress={progress_text}"
                )

                if progress is not None and progress >= 99.9:
                    log("candidate book is already complete, going back to collection page")
                    self.device.back()
                    self._sleep_ms(self.config.navigation.prepare_wait_ms)
                    root = self.device.dump_ui()
                    continue

                self.current_book = RecentBook(
                    title=title,
                    image_key=None,
                    progress_text=progress_text,
                    progress_percent=progress,
                    bounds=(0, 0, 0, 0),
                )
                if self._tap_continue_if_present(candidate_root):
                    return "open_collection_then_continue"
                if self._tap_start_reading_if_present(candidate_root):
                    return "open_collection_then_start"
                return "open_collection"

            if page_index == max_pages - 1:
                break

            log("scrolling collection page to look for more books")
            self._swipe_ratio((0.5, 0.82), (0.5, 0.3), 650)
            self._sleep_ms(self.config.page_turn.settle_ms)
            root = self.device.dump_ui()

        return "all_done"

    def _prepare_reading_page(self) -> str:
        root = self.device.dump_ui()

        if self._tap_continue_if_present(root):
            return "continue"

        if self.config.navigation.open_recent_index and self.config.navigation.open_recent_index > 0:
            items = self.navigator.list_recent_books(root)
            if items and len(items) >= self.config.navigation.open_recent_index:
                return self._open_recent_book(
                    items[self.config.navigation.open_recent_index - 1]
                )

        return "noop"

    def _return_to_recent_home(
        self,
        max_back_steps: int = 4,
    ) -> Optional[ET.Element]:
        for step in range(max_back_steps + 1):
            root = self.device.dump_ui()
            books = self.navigator.list_recent_books(root)
            if books:
                log(f"recent reading page ready with {len(books)} visible books")
                return root
            if step == max_back_steps:
                break
            log("recent reading not visible yet, pressing back")
            self.device.back()
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
        return None

    def _find_current_book_on_home(
        self,
        root: ET.Element,
    ) -> Optional[RecentBook]:
        if not self.current_book:
            return None
        if self.current_book.image_key:
            found = self.navigator.find_recent_book_by_key(root, self.current_book.key)
            if found:
                return found
        books = self.navigator.list_recent_books(root)
        if not books:
            return None
        return books[0]

    def _wait_for_home_progress_refresh(
        self,
        attempts: int = 3,
    ) -> tuple[Optional[ET.Element], Optional[RecentBook]]:
        root = self._return_to_recent_home()
        if root is None:
            return None, None

        self._refresh_recent_home()
        root = self.device.dump_ui()
        current = self._find_current_book_on_home(root)
        for attempt in range(attempts):
            if current and current.is_complete():
                return root, current
            if attempt == attempts - 1:
                break
            log("current book is not shown as completed yet, waiting for home progress refresh")
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
            self._refresh_recent_home()
            root = self.device.dump_ui()
            current = self._find_current_book_on_home(root)
        return root, current

    def _switch_to_next_book(self) -> str:
        if not self.current_book:
            log("current book is unknown, cannot safely switch to the next book")
            return "stop"

        root, current_on_home = self._wait_for_home_progress_refresh()
        if root is None:
            log("failed to return to recent reading page")
            return "stop"

        if current_on_home is None:
            log(
                f"current book {self._describe_book(self.current_book)} was not found in visible recent books"
            )
            return "stop"

        if not current_on_home.is_complete():
            log(
                "page turn was not confirmed, but current book progress is still "
                f"{current_on_home.progress_text}; stopping to avoid switching books by mistake"
            )
            return "stop"

        self.completed_book_keys.add(current_on_home.key)
        log(f"book completed: {self._describe_book(current_on_home)}")

        collection_root = self._open_home_collection_page(root)
        if collection_root is None:
            log("home collection entry was not found, cannot choose the next book")
            return "stop"

        next_book = self._find_next_collection_book(collection_root)
        if next_book:
            action = self._open_collection_book(next_book)
            if action == "open_collection_miss":
                log("parsed collection card did not open, falling back to visible slot scanning")
            else:
                log(f"switched to next book: {self._describe_book(next_book)}, action={action}")
                return "opened_next"

        log("collection page UI did not expose book cards, falling back to visible slot scanning")
        action = self._open_next_collection_book_by_slots(collection_root)
        if action in {
            "open_collection",
            "open_collection_then_continue",
            "open_collection_then_start",
        }:
            log(f"switched to next book by slot fallback, action={action}")
            return "opened_next"

        self.current_book = None
        log("no unfinished book found in the collection page, stopping")
        return "all_done"

    def doctor(self) -> int:
        self.device.ensure_ready()
        self.screen_size = self.device.wm_size()
        info = self.navigator.inspect()
        print(
            json.dumps(
                {
                    "serial": self.config.serial,
                    "package": self.config.package,
                    "screen_size": {
                        "width": self.screen_size[0],
                        "height": self.screen_size[1],
                    },
                    "ui": info,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    def dump_ui(self, output: Path) -> int:
        root = self.device.dump_ui()
        output.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
        log(f"ui dump saved to {output}")
        return 0

    def capture(self, output: Path) -> int:
        self.device.ensure_ready()
        image = self.device.capture()
        cv2.imwrite(str(output), image)
        log(f"screenshot saved to {output}")
        return 0

    def prepare(self, skip_prepare: bool = False) -> None:
        self.device.ensure_ready()
        self.screen_size = self.device.wm_size()
        if self.config.navigation.launch_app:
            log(f"launching {self.config.package}")
            self.device.launch_app()
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
        if not skip_prepare:
            result = self._prepare_reading_page()
            log(f"prepare result: {result}")

    def perform_scroll(self) -> None:
        start = self._randomized_point(
            self.config.scroll.start,
            self.config.scroll.start_jitter,
        )
        end = self._randomized_point(
            self.config.scroll.end,
            self.config.scroll.end_jitter,
        )
        duration_ms = self._randomized_duration(
            self.config.scroll.duration_ms,
            self.config.scroll.duration_jitter_ms,
        )
        log(
            "scroll swipe: start=({0},{1}) end=({2},{3}) duration={4}ms".format(
                start[0], start[1], end[0], end[1], duration_ms
            )
        )
        self.device.swipe(start, end, duration_ms)

    def perform_page_turn(self) -> None:
        action = self.config.page_turn.action.lower()
        if action == "tap":
            if not self.config.page_turn.tap:
                raise ConfigError("page_turn.tap is required when action='tap'")
            x, y = self._ratio_to_abs(self.config.page_turn.tap)
            self.device.tap(x, y)
            return

        if action != "swipe":
            raise ConfigError(f"unsupported page_turn.action: {self.config.page_turn.action}")
        if not self.config.page_turn.start or not self.config.page_turn.end:
            raise ConfigError("page_turn.start/end are required when action='swipe'")
        start = self._randomized_point(
            self.config.page_turn.start,
            self.config.page_turn.start_jitter,
        )
        end = self._randomized_point(
            self.config.page_turn.end,
            self.config.page_turn.end_jitter,
        )
        duration_ms = self._randomized_duration(
            self.config.page_turn.duration_ms,
            self.config.page_turn.duration_jitter_ms,
        )
        log(
            "page-turn swipe: start=({0},{1}) end=({2},{3}) duration={4}ms".format(
                start[0], start[1], end[0], end[1], duration_ms
            )
        )
        self.device.swipe(start, end, duration_ms)

    def run(
        self,
        skip_prepare: bool = False,
        max_page_turns_override: Optional[int] = None,
    ) -> int:
        self.prepare(skip_prepare=skip_prepare)

        max_page_turns = (
            max_page_turns_override
            if max_page_turns_override is not None
            else self.config.runtime.max_page_turns
        )
        start_time = time.monotonic()
        page_turns = 0
        stuck_count = 0
        iteration = 0

        log("reader loop started")
        while True:
            iteration += 1
            pause_after_page_turn = False
            pause_after_book_switch = False
            before = self.device.capture()
            self.perform_scroll()
            self._sleep_ms(self.config.scroll.settle_ms)
            after = self.device.capture()

            metrics = self.analyzer.diff(before, after)
            log(
                "scroll #{0}: mean_diff={1:.3f}, changed_ratio={2:.4f}".format(
                    iteration, metrics.mean_diff, metrics.changed_ratio
                )
            )

            if self.analyzer.looks_stuck(metrics):
                stuck_count += 1
                log(
                    f"bottom-like state {stuck_count}/{self.config.analysis.bottom_confirmations}"
                )
                if stuck_count < self.config.analysis.bottom_confirmations:
                    self._sleep_ms(self.config.runtime.loop_sleep_ms)
                    continue

                before_turn = self.device.capture()
                self.perform_page_turn()
                self._sleep_ms(self.config.page_turn.settle_ms)
                after_turn = self.device.capture()

                turn_metrics = self.analyzer.diff(before_turn, after_turn)
                log(
                    "page-turn check: mean_diff={0:.3f}, changed_ratio={1:.4f}".format(
                        turn_metrics.mean_diff,
                        turn_metrics.changed_ratio,
                    )
                )

                if self.analyzer.page_turn_confirmed(turn_metrics):
                    page_turns += 1
                    stuck_count = 0
                    pause_after_page_turn = True
                    log(f"moved to next section, total page turns: {page_turns}")
                else:
                    switch_result = self._switch_to_next_book()
                    if switch_result == "opened_next":
                        stuck_count = 0
                        pause_after_book_switch = True
                    elif switch_result == "all_done":
                        return 0
                    else:
                        self._save_debug("turn_before.png", before_turn)
                        self._save_debug("turn_after.png", after_turn)
                        log("page turn not confirmed, stopping to avoid misfire")
                        return 2
            else:
                stuck_count = 0
                if self.config.scroll.pause_ms > 0:
                    log(
                        f"scroll pause: waiting {self.config.scroll.pause_ms}ms before next upward swipe"
                    )
                self._sleep_ms(self.config.scroll.pause_ms)

            if max_page_turns > 0 and page_turns >= max_page_turns:
                log(f"reached max_page_turns={max_page_turns}, stopping")
                return 0

            if self.config.runtime.max_minutes > 0:
                elapsed_minutes = (time.monotonic() - start_time) / 60
                if elapsed_minutes >= self.config.runtime.max_minutes:
                    log(
                        f"reached max_minutes={self.config.runtime.max_minutes}, stopping"
                    )
                    return 0

            if pause_after_page_turn and self.config.scroll.pause_ms > 0:
                log(
                    f"page-turn pause: waiting {self.config.scroll.pause_ms}ms before next upward swipe"
                )
                self._sleep_ms(self.config.scroll.pause_ms)

            if pause_after_book_switch and self.config.scroll.pause_ms > 0:
                log(
                    f"book-switch pause: waiting {self.config.scroll.pause_ms}ms before next upward swipe"
                )
                self._sleep_ms(self.config.scroll.pause_ms)

            self._sleep_ms(self.config.runtime.loop_sleep_ms)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ADB-based Haoce reader with bottom detection and auto page turn."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to JSON config file. Default: config.json",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check ADB/device/package/UI state.")

    dump_ui = subparsers.add_parser("dump-ui", help="Dump current UI XML.")
    dump_ui.add_argument("output", help="Output XML file path.")

    capture = subparsers.add_parser("capture", help="Save current screenshot.")
    capture.add_argument("output", help="Output PNG file path.")

    run_parser = subparsers.add_parser("run", help="Start auto reading loop.")
    run_parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip home/report-page navigation and start from current page.",
    )
    run_parser.add_argument(
        "--max-page-turns",
        type=int,
        default=None,
        help="Override max_page_turns from config. Use 0 for unlimited.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config(Path(args.config))
    reader = HaoceReader(config)

    if args.command == "doctor":
        return reader.doctor()
    if args.command == "dump-ui":
        return reader.dump_ui(Path(args.output))
    if args.command == "capture":
        return reader.capture(Path(args.output))
    if args.command == "run":
        return reader.run(
            skip_prepare=args.skip_prepare,
            max_page_turns_override=args.max_page_turns,
        )

    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("stopped by user")
        raise SystemExit(130)
