from __future__ import annotations

import argparse
import json
import math
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
START_READING_TEXT = "开始阅读"
UPDATE_BUTTON_TEXT = "更新"
SEARCH_BOOK_TEXT = "搜索图书"
RECENT_READING_TEXT = "最近阅读"
PROGRESS_PREFIX = "进度:"
EXCLUDED_COLLECTION_CATEGORIES = {"重点图书"}
GENERIC_BOOK_LABELS = {"书香理工", "人文理工", "校图书读书工程", "重点图书"}


DETAIL_PAGE_HINT_TEXTS = (
    "\u4f5c\u8005",
    "\u51fa\u7248\u793e",
    "\u603b\u5b57\u6570",
    "\u7b80\u4ecb",
    "\u6e29\u99a8\u63d0\u793a",
)
HOME_ENTRY_UPDATE_ROUNDS = 3
RETURNED_DETAIL_SYNC_ROUNDS = 3


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


def clean_book_title_candidate(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    normalized = " ".join(str(title).split()).strip()
    if not normalized or normalized in {"•", "<unknown>"}:
        return None
    if normalized in GENERIC_BOOK_LABELS:
        return None
    return normalized


def expand_bounds(
    bounds: tuple[int, int, int, int],
    pad_left: int,
    pad_top: int,
    pad_right: int,
    pad_bottom: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bounds
    return (
        max(0, x1 - pad_left),
        max(0, y1 - pad_top),
        x2 + pad_right,
        y2 + pad_bottom,
    )


def union_bounds(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    return (
        min(left[0], right[0]),
        min(left[1], right[1]),
        max(left[2], right[2]),
        max(left[3], right[3]),
    )


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
    duration_ms: tuple[int, int]
    duration_jitter_ms: int
    settle_ms: int
    pause_ms: tuple[int, int]


@dataclass
class PageTurnConfig:
    action: str
    start: Optional[tuple[float, float]]
    end: Optional[tuple[float, float]]
    start_jitter: tuple[float, float]
    end_jitter: tuple[float, float]
    tap: Optional[tuple[float, float]]
    duration_ms: tuple[int, int]
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
    selection_blacklist_file: Optional[str]
    completion_verify_attempts: int


@dataclass
class MotionConfig:
    trajectory_points: tuple[int, int]
    path_jitter: tuple[float, float]
    lateral_chance: float
    lateral_distance_ratio: tuple[float, float]
    lateral_duration_ms: tuple[int, int]
    downward_chance: float
    downward_distance_ratio: tuple[float, float]
    downward_duration_ms: tuple[int, int]
    micro_settle_ms: tuple[int, int]


@dataclass
class ReaderConfig:
    serial: Optional[str]
    package: str
    navigation: NavigationConfig
    scroll: SwipeConfig
    page_turn: PageTurnConfig
    analysis: AnalysisConfig
    runtime: RuntimeConfig
    motion: MotionConfig


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


def parse_int_range(value: object, name: str) -> tuple[int, int]:
    if isinstance(value, (int, float)):
        parsed = int(value)
        if parsed < 0:
            raise ConfigError(f"{name} must be >= 0")
        return parsed, parsed

    if isinstance(value, (list, tuple)) and len(value) == 2:
        start = int(value[0])
        end = int(value[1])
        low = min(start, end)
        high = max(start, end)
        if low < 0:
            raise ConfigError(f"{name} values must be >= 0")
        return low, high

    raise ConfigError(f"{name} must be an integer or a 2-item range")


def parse_float_range(value: object, name: str) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        parsed = float(value)
        if parsed < 0:
            raise ConfigError(f"{name} must be >= 0")
        return parsed, parsed

    if isinstance(value, (list, tuple)) and len(value) == 2:
        start = float(value[0])
        end = float(value[1])
        low = min(start, end)
        high = max(start, end)
        if low < 0:
            raise ConfigError(f"{name} values must be >= 0")
        return low, high

    raise ConfigError(f"{name} must be a number or a 2-item range")


def load_config(path: Path) -> ReaderConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    navigation = raw["navigation"]
    scroll = raw["scroll"]
    page_turn = raw["page_turn"]
    analysis = raw["analysis"]
    runtime = raw["runtime"]
    motion = raw.get("motion", {})

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
            duration_ms=parse_int_range(scroll["duration_ms"], "scroll.duration_ms"),
            duration_jitter_ms=int(scroll.get("duration_jitter_ms", 0)),
            settle_ms=int(scroll["settle_ms"]),
            pause_ms=parse_int_range(scroll.get("pause_ms", 0), "scroll.pause_ms"),
        ),
        page_turn=PageTurnConfig(
            action=str(page_turn.get("action", "swipe")),
            start=tuple(page_turn["start"]) if page_turn.get("start") else None,
            end=tuple(page_turn["end"]) if page_turn.get("end") else None,
            start_jitter=tuple(page_turn.get("start_jitter", [0.0, 0.0])),
            end_jitter=tuple(page_turn.get("end_jitter", [0.0, 0.0])),
            tap=tuple(page_turn["tap"]) if page_turn.get("tap") else None,
            duration_ms=parse_int_range(
                page_turn.get("duration_ms", 300),
                "page_turn.duration_ms",
            ),
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
            selection_blacklist_file=runtime.get(
                "selection_blacklist_file",
                "selection_blacklist.json",
            ),
            completion_verify_attempts=max(
                1, int(runtime.get("completion_verify_attempts", 2))
            ),
        ),
        motion=MotionConfig(
            trajectory_points=parse_int_range(
                motion.get("trajectory_points", [3, 4]),
                "motion.trajectory_points",
            ),
            path_jitter=parse_float_range(
                motion.get("path_jitter", [0.012, 0.018]),
                "motion.path_jitter",
            ),
            lateral_chance=max(0.0, min(1.0, float(motion.get("lateral_chance", 0.04)))),
            lateral_distance_ratio=parse_float_range(
                motion.get("lateral_distance_ratio", [0.06, 0.10]),
                "motion.lateral_distance_ratio",
            ),
            lateral_duration_ms=parse_int_range(
                motion.get("lateral_duration_ms", [70, 110]),
                "motion.lateral_duration_ms",
            ),
            downward_chance=max(
                0.0, min(1.0, float(motion.get("downward_chance", 0.08)))
            ),
            downward_distance_ratio=parse_float_range(
                motion.get("downward_distance_ratio", [0.10, 0.18]),
                "motion.downward_distance_ratio",
            ),
            downward_duration_ms=parse_int_range(
                motion.get("downward_duration_ms", [110, 180]),
                "motion.downward_duration_ms",
            ),
            micro_settle_ms=parse_int_range(
                motion.get("micro_settle_ms", [350, 900]),
                "motion.micro_settle_ms",
            ),
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

    def motionevent(self, action: str, x: int, y: int) -> None:
        self.run("shell", "input", "motionevent", action, str(x), str(y))

    def gesture(
        self,
        points: list[tuple[int, int]],
        duration_ms: int,
    ) -> None:
        cleaned: list[tuple[int, int]] = []
        for point in points:
            if not cleaned or point != cleaned[-1]:
                cleaned.append(point)

        if len(cleaned) < 2:
            return

        interval_count = max(1, len(cleaned) - 1)
        base_delay = max(1, duration_ms // interval_count)
        remainder = max(0, duration_ms - base_delay * interval_count)

        try:
            self.motionevent("DOWN", cleaned[0][0], cleaned[0][1])
            for index, point in enumerate(cleaned[1:], start=1):
                delay_ms = base_delay + (1 if index <= remainder else 0)
                time.sleep(delay_ms / 1000)
                action = "UP" if index == len(cleaned) - 1 else "MOVE"
                self.motionevent(action, point[0], point[1])
        except subprocess.CalledProcessError:
            self.swipe(cleaned[0], cleaned[-1], duration_ms)

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
        return clean_book_title_candidate(best_text)

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

    def find_text_prefix_bounds(
        self,
        root: ET.Element,
        prefix: str,
    ) -> Optional[tuple[str, tuple[int, int, int, int]]]:
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text.startswith(prefix) or not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            return text, bounds
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
        return clean_book_title_candidate(best_text)

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
                candidate_title = clean_book_title_candidate(text)
                if candidate_title and not title:
                    title = candidate_title

            title = clean_book_title_candidate(title) or ""

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

        text_candidates: list[tuple[int, int, int, int]] = []
        image_candidates: list[tuple[int, int, int, int]] = []
        for node in iter_nodes(subtree):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) <= 0 or bounds[1] >= 1100:
                continue

            if text == "书香理工":
                text_candidates.append(bounds)
                continue

            class_name = node.attrib.get("class", "")
            if "Image" in class_name and area(bounds) >= 8000:
                image_candidates.append(bounds)

        if not text_candidates:
            return None

        text_bounds = min(text_candidates, key=lambda item: (item[1], item[0]))
        tap_bounds = expand_bounds(text_bounds, 24, 180, 24, 24)
        text_center = center(text_bounds)
        best_image: Optional[tuple[int, int, int, int]] = None
        best_score: Optional[int] = None

        for image_bounds in image_candidates:
            image_center = center(image_bounds)
            horizontal_distance = abs(image_center[0] - text_center[0])
            vertical_gap = text_bounds[1] - image_bounds[3]
            if horizontal_distance > 220:
                continue
            if vertical_gap < -80 or vertical_gap > 260:
                continue
            score = horizontal_distance * 4 + abs(vertical_gap)
            if best_score is None or score < best_score:
                best_score = score
                best_image = image_bounds

        if best_image is not None:
            return expand_bounds(best_image, 18, 18, 18, 18)

        return tap_bounds

    def current_collection_category(self, root: ET.Element) -> Optional[str]:
        subtree = self._page_subtree(root, "collection")
        if subtree is None:
            return None

        found = self.find_text_prefix_bounds(subtree, "分类：")
        if not found:
            return None
        text, _ = found
        return text.removeprefix("分类：").strip()

    def find_collection_category_trigger(
        self,
        root: ET.Element,
    ) -> Optional[tuple[int, int, int, int]]:
        subtree = self._page_subtree(root, "collection")
        if subtree is None:
            return None

        found = self.find_text_prefix_bounds(subtree, "分类：")
        if not found:
            return None
        _, bounds = found
        x1, y1, x2, y2 = bounds
        return max(0, x1 - 64), max(0, y1 - 20), x2 + 48, y2 + 20

    def list_collection_categories(
        self,
        root: ET.Element,
    ) -> list[tuple[str, tuple[int, int, int, int]]]:
        subtree = self._page_subtree(root, "collection")
        if subtree is None:
            return []

        categories: list[tuple[str, tuple[int, int, int, int]]] = []
        seen: set[str] = set()
        current = self.current_collection_category(root)
        for node in iter_nodes(subtree):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) == 0:
                continue
            if not (660 <= bounds[1] <= 1860):
                continue
            if not (180 <= bounds[2] - bounds[0] <= 360):
                continue
            if not (100 <= bounds[3] - bounds[1] <= 140):
                continue
            if text == current or text in seen:
                continue
            categories.append((text, bounds))
            seen.add(text)
        return categories

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

            title = clean_book_title_candidate(title) or ""
            if not title:
                for child in direct_children:
                    candidate_title = clean_book_title_candidate(
                        (child.attrib.get("text") or "").strip()
                    )
                    if candidate_title:
                        title = candidate_title
                        break
            if not progress_text or (not title and not image_key):
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
        self.completed_book_titles: set[str] = set()
        self.incomplete_completion_verifications: dict[str, int] = {}
        self.debug_dir = (
            Path(config.runtime.debug_dir).resolve()
            if config.runtime.debug_dir
            else None
        )
        self.selection_blacklist_path = (
            Path(config.runtime.selection_blacklist_file).resolve()
            if config.runtime.selection_blacklist_file
            else None
        )
        self.selection_blacklist_titles: set[str] = set()
        self.selection_blacklist_keys: set[str] = set()
        self._load_selection_blacklist()

    def _normalize_book_title(self, title: Optional[str]) -> Optional[str]:
        normalized = clean_book_title_candidate(title)
        if not normalized or normalized.startswith("collection-slot-"):
            return None
        return normalized
        if not title:
            return None
        normalized = " ".join(title.split()).strip()
        if (
            not normalized
            or normalized in {"•", "<unknown>"}
            or normalized.startswith("collection-slot-")
        ):
            return None
        return normalized

    def _selection_blacklist_key(self, book: RecentBook) -> Optional[str]:
        if not book.image_key:
            return None
        normalized = book.image_key.strip()
        return normalized or None

    def _completion_verification_key(self, book: RecentBook) -> str:
        key = self._selection_blacklist_key(book)
        if key:
            return f"key:{key}"

        title = self._normalize_book_title(book.title)
        if title:
            return f"title:{title}"

        return f"raw:{book.key}"

    def _mark_book_completed(self, book: RecentBook) -> None:
        title = self._normalize_book_title(book.title)
        if title:
            self.completed_book_titles.add(title)
        self.completed_book_keys.add(book.key)
        self.incomplete_completion_verifications.pop(
            self._completion_verification_key(book),
            None,
        )

    def _is_marked_completed(self, book: RecentBook) -> bool:
        title = self._normalize_book_title(book.title)
        if title and title in self.completed_book_titles:
            return True
        return book.key in self.completed_book_keys

    def _same_book(self, left: Optional[RecentBook], right: Optional[RecentBook]) -> bool:
        if not left or not right:
            return False
        left_key = self._selection_blacklist_key(left)
        right_key = self._selection_blacklist_key(right)
        if left_key and right_key and left_key == right_key:
            return True
        left_title = self._normalize_book_title(left.title)
        right_title = self._normalize_book_title(right.title)
        return bool(left_title and right_title and left_title == right_title)

    def _load_selection_blacklist(self) -> None:
        if not self.selection_blacklist_path or not self.selection_blacklist_path.exists():
            return
        try:
            payload = json.loads(
                self.selection_blacklist_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            log(f"failed to load selection blacklist file: {exc}")
            return

        if not isinstance(payload, dict):
            return

        for value in payload.get("titles", []):
            normalized = self._normalize_book_title(str(value))
            if normalized:
                self.selection_blacklist_titles.add(normalized)

        for value in payload.get("keys", []):
            normalized = str(value).strip()
            if normalized:
                self.selection_blacklist_keys.add(normalized)

    def _save_selection_blacklist(self) -> None:
        if not self.selection_blacklist_path:
            return

        payload = {
            "titles": sorted(self.selection_blacklist_titles),
            "keys": sorted(self.selection_blacklist_keys),
        }
        try:
            self.selection_blacklist_path.parent.mkdir(parents=True, exist_ok=True)
            self.selection_blacklist_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            log(f"failed to save selection blacklist file: {exc}")

    def _selection_blacklist_contains(self, book: RecentBook) -> bool:
        title = self._normalize_book_title(book.title)
        if title and title in self.selection_blacklist_titles:
            return True

        key = self._selection_blacklist_key(book)
        if key and key in self.selection_blacklist_keys:
            return True

        return False

    def _remember_selected_for_collection(self, book: RecentBook) -> None:
        changed = False

        title = self._normalize_book_title(book.title)
        if title and title not in self.selection_blacklist_titles:
            self.selection_blacklist_titles.add(title)
            changed = True

        key = self._selection_blacklist_key(book)
        if key and key not in self.selection_blacklist_keys:
            self.selection_blacklist_keys.add(key)
            changed = True

        if changed:
            self._save_selection_blacklist()

    def _resolve_collection_book(
        self,
        candidate_root: ET.Element,
        fallback_book: RecentBook,
    ) -> RecentBook:
        title = (
            self.navigator.report_title(candidate_root)
            or self.navigator.detail_title(candidate_root)
            or clean_book_title_candidate(fallback_book.title)
            or ""
        )
        progress = self.navigator.report_progress(candidate_root)
        if progress is None:
            progress = self.navigator.detail_progress(candidate_root)
        if progress is None:
            progress = fallback_book.progress_percent

        progress_text = (
            f"进度:{progress:.2f}%"
            if progress is not None
            else (fallback_book.progress_text or "进度:unknown")
        )
        return RecentBook(
            title=title,
            image_key=fallback_book.image_key,
            progress_text=progress_text,
            progress_percent=progress,
            bounds=fallback_book.bounds,
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

    def _randomized_duration(
        self,
        duration_ms: tuple[int, int],
        jitter_ms: int,
    ) -> int:
        low, high = duration_ms
        base_duration = low if low == high else random.randint(low, high)
        if jitter_ms <= 0:
            return base_duration
        return max(1, base_duration + random.randint(-jitter_ms, jitter_ms))

    def _random_int_between(self, value_range: tuple[int, int]) -> int:
        low, high = value_range
        return low if low == high else random.randint(low, high)

    def _random_float_between(self, value_range: tuple[float, float]) -> float:
        low, high = value_range
        return low if math.isclose(low, high) else random.uniform(low, high)

    def _build_trajectory_points(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> list[tuple[int, int]]:
        point_count = max(2, self._random_int_between(self.config.motion.trajectory_points))
        if point_count <= 2:
            return [start, end]

        if self.screen_size == (0, 0):
            self.screen_size = self.device.wm_size()
        width, height = self.screen_size
        jitter_x = width * self.config.motion.path_jitter[0]
        jitter_y = height * self.config.motion.path_jitter[1]

        points: list[tuple[int, int]] = []
        for index in range(point_count):
            t = index / (point_count - 1)
            base_x = start[0] + (end[0] - start[0]) * t
            base_y = start[1] + (end[1] - start[1]) * t
            curve = math.sin(math.pi * t)
            offset_x = random.uniform(-jitter_x, jitter_x) * curve
            offset_y = random.uniform(-jitter_y, jitter_y) * curve
            point = self._clamp_point(
                (int(round(base_x + offset_x)), int(round(base_y + offset_y)))
            )
            if not points or point != points[-1]:
                points.append(point)

        if len(points) < 2:
            return [start, end]

        points[0] = start
        points[-1] = end
        return points

    def _perform_gesture(
        self,
        label: str,
        start: tuple[int, int],
        end: tuple[int, int],
        duration_ms: int,
    ) -> None:
        points = self._build_trajectory_points(start, end)
        log(
            "{0}: start=({1},{2}) end=({3},{4}) duration={5}ms track_points={6}".format(
                label,
                start[0],
                start[1],
                end[0],
                end[1],
                duration_ms,
                len(points),
            )
        )
        self.device.gesture(points, duration_ms)

    def _perform_direct_swipe(
        self,
        label: str,
        start: tuple[int, int],
        end: tuple[int, int],
        duration_ms: int,
    ) -> None:
        log(
            "{0}: start=({1},{2}) end=({3},{4}) duration={5}ms".format(
                label,
                start[0],
                start[1],
                end[0],
                end[1],
                duration_ms,
            )
        )
        self.device.swipe(start, end, duration_ms)

    def _pause_ratio(self, pause_ms: int) -> float:
        low, high = self.config.scroll.pause_ms
        if high <= low:
            return 0.5
        ratio = (pause_ms - low) / (high - low)
        return max(0.0, min(1.0, ratio))

    def _perform_lateral_drift(self) -> int:
        distance_ratio = self._random_float_between(
            self.config.motion.lateral_distance_ratio
        )
        duration_ms = self._random_int_between(self.config.motion.lateral_duration_ms)
        center_x = random.uniform(0.40, 0.66)
        center_y = random.uniform(0.40, 0.74)
        half_distance = distance_ratio / 2
        start_ratio = (
            min(0.92, center_x + half_distance),
            center_y + random.uniform(-0.015, 0.015),
        )
        end_ratio = (
            max(0.08, center_x - half_distance),
            center_y + random.uniform(-0.015, 0.015),
        )
        start = self._clamp_point(self._ratio_to_abs(start_ratio))
        end = self._clamp_point(self._ratio_to_abs(end_ratio))
        self._perform_direct_swipe("lateral drift swipe", start, end, duration_ms)
        return duration_ms

    def _perform_downward_review(self, pause_ms: int) -> int:
        pause_ratio = self._pause_ratio(pause_ms)
        low_distance, high_distance = self.config.motion.downward_distance_ratio
        distance_ratio = low_distance + (high_distance - low_distance) * pause_ratio
        distance_ratio *= random.uniform(0.92, 1.08)
        distance_ratio = max(low_distance, min(high_distance, distance_ratio))
        duration_ms = self._random_int_between(self.config.motion.downward_duration_ms)
        start_ratio = (
            random.uniform(0.24, 0.76),
            random.uniform(0.28, 0.44),
        )
        end_ratio = (
            start_ratio[0] + random.uniform(-0.02, 0.02),
            min(0.86, start_ratio[1] + distance_ratio),
        )
        start = self._clamp_point(self._ratio_to_abs(start_ratio))
        end = self._clamp_point(self._ratio_to_abs(end_ratio))
        log(
            "downward review swipe: pause_ratio={0:.2f}, distance_ratio={1:.3f}".format(
                pause_ratio,
                distance_ratio,
            )
        )
        self._perform_direct_swipe("downward review swipe", start, end, duration_ms)
        return duration_ms

    def _perform_pause_actions(
        self,
        label: str,
        pause_ms: int,
    ) -> None:
        if pause_ms <= 0:
            return

        actions: list[str] = []
        if random.random() < self.config.motion.lateral_chance:
            actions.append("lateral")
        if random.random() < self.config.motion.downward_chance:
            actions.append("downward")

        if not actions:
            self._sleep_ms(pause_ms)
            return

        action = random.choice(actions)
        remaining_ms = pause_ms

        wait_min = min(remaining_ms, int(pause_ms * 0.2))
        wait_max = min(remaining_ms, max(wait_min, int(pause_ms * 0.7)))
        if wait_max > 0:
            wait_ms = wait_min if wait_min == wait_max else random.randint(wait_min, wait_max)
            self._sleep_ms(wait_ms)
            remaining_ms = max(0, remaining_ms - wait_ms)

        used_ms = (
            self._perform_lateral_drift()
            if action == "lateral"
            else self._perform_downward_review(pause_ms)
        )
        remaining_ms = max(0, remaining_ms - used_ms)

        settle_ms = min(
            remaining_ms,
            self._random_int_between(self.config.motion.micro_settle_ms),
        )
        if settle_ms > 0:
            self._sleep_ms(settle_ms)
            remaining_ms -= settle_ms

        if remaining_ms > 0:
            self._sleep_ms(remaining_ms)

    def _sleep_ms(self, delay_ms: int) -> None:
        if delay_ms <= 0:
            return
        time.sleep(delay_ms / 1000)

    def _random_pause_ms(self) -> int:
        low, high = self.config.scroll.pause_ms
        if high <= 0:
            return 0
        if low == high:
            return low
        return random.randint(low, high)

    def _sleep_scroll_pause(self, label: str) -> None:
        pause_ms = self._random_pause_ms()
        if pause_ms <= 0:
            return

        low, high = self.config.scroll.pause_ms
        if low == high:
            log(f"{label}: waiting {pause_ms}ms before next upward swipe")
        else:
            log(
                f"{label}: waiting {pause_ms}ms before next upward swipe "
                f"(random in {low}-{high}ms)"
            )
        self._perform_pause_actions(label, pause_ms)

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
        title = self._normalize_book_title(book.title) or self._selection_blacklist_key(book)
        if title and book.progress_text:
            return f"{title} ({book.progress_text})"
        if title:
            return title
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

    def _tap_detail_update_if_present(
        self,
        root: Optional[ET.Element] = None,
    ) -> ET.Element:
        updated_root, _ = self._tap_detail_update_once(root)
        return updated_root

    def _tap_detail_update_once(
        self,
        root: Optional[ET.Element] = None,
    ) -> tuple[ET.Element, bool]:
        if root is None:
            root = self.device.dump_ui()

        current_root = root
        for _ in range(4):
            exact_candidates: list[tuple[int, int, int, int]] = []
            row_fallback: Optional[tuple[int, int, int, int]] = None

            for node in iter_nodes(current_root):
                text = (node.attrib.get("text") or "").strip()
                bounds_text = node.attrib.get("bounds")
                if not text or not bounds_text:
                    continue
                bounds = parse_bounds(bounds_text)
                if area(bounds) <= 0:
                    continue
                if text == UPDATE_BUTTON_TEXT:
                    exact_candidates.append(bounds)
                    continue
                if UPDATE_BUTTON_TEXT in text and 760 <= bounds[1] <= 1100:
                    row_fallback = bounds

            if exact_candidates:
                exact_candidates.sort(
                    key=lambda bounds: (area(bounds), -(bounds[2] - bounds[0]))
                )
                x, y = center(exact_candidates[0])
                log(f"found '{UPDATE_BUTTON_TEXT}', tapping {x},{y}")
                self.device.tap(x, y)
                self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1200))
                return self.device.dump_ui(), True

            if row_fallback:
                x1, y1, x2, y2 = row_fallback
                target_x = max(x1, x2 - max(72, int((x2 - x1) * 0.12)))
                target_y = (y1 + y2) // 2
                log(
                    f"found '{UPDATE_BUTTON_TEXT}' row fallback, "
                    f"tapping {target_x},{target_y}"
                )
                self.device.tap(target_x, target_y)
                self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1200))
                return self.device.dump_ui(), True

            self._sleep_ms(350)
            current_root = self.device.dump_ui()

        return current_root, False

    def _tap_detail_update_repeatedly(
        self,
        root: Optional[ET.Element] = None,
        rounds: int = HOME_ENTRY_UPDATE_ROUNDS,
        context_label: str = "detail update",
    ) -> ET.Element:
        if root is None:
            root = self.device.dump_ui()

        current_root = root
        for round_index in range(max(0, rounds)):
            log(
                f"{context_label}: checking '{UPDATE_BUTTON_TEXT}' "
                f"{round_index + 1}/{rounds}"
            )
            current_root, tapped = self._tap_detail_update_once(current_root)
            if not tapped:
                break
        return current_root

    def _tap_start_reading_if_present(self, root: Optional[ET.Element] = None) -> bool:
        if root is None:
            root = self.device.dump_ui()
        button = self.navigator.find_text_bounds(root, START_READING_TEXT)
        if not button:
            return False
        x, y = center(button)
        log(f"found '{START_READING_TEXT}', tapping {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        return True

    def _open_recent_book(self, book: RecentBook) -> str:
        x, y = center(book.bounds)
        log(f"opening recent book: {self._describe_book(book)} at {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        root = self.device.dump_ui()
        root = self._tap_detail_update_repeatedly(
            root,
            rounds=HOME_ENTRY_UPDATE_ROUNDS,
            context_label="home recent entry sync",
        )
        self.current_book = self._resolve_collection_book(root, book)
        if self._tap_continue_if_present(root):
            return "open_recent_then_continue"
        if self._tap_start_reading_if_present(root):
            return "open_recent_then_start"
        return "open_recent"

    def _refresh_recent_home(self) -> None:
        log("refreshing home page to sync reading progress")
        self._swipe_ratio((0.5, 0.34), (0.5, 0.78), 650)
        self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 2500))

    def _refresh_current_book_page(self) -> ET.Element:
        log("refreshing current page to sync reading progress")
        self._swipe_ratio((0.5, 0.34), (0.5, 0.78), 650)
        self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 2500))
        return self.device.dump_ui()

    def _looks_like_refreshable_book_page(self, root: ET.Element) -> bool:
        page_name = self.navigator._current_page_name(root)
        if page_name in {"home", "report"}:
            return False
        if self.navigator.find_text_bounds(root, UPDATE_BUTTON_TEXT):
            return False
        if self.navigator.find_text_bounds(root, SEARCH_BOOK_TEXT):
            return True

        progress_like_count = 0
        for node in iter_nodes(root):
            text = (node.attrib.get("text") or "").strip()
            bounds_text = node.attrib.get("bounds")
            if not text or not bounds_text:
                continue
            bounds = parse_bounds(bounds_text)
            if area(bounds) <= 0:
                continue
            if "进度" in text or "%" in text:
                progress_like_count += 1
                if progress_like_count >= 2:
                    return True
        return False

    def _sync_page_after_back(self, root: ET.Element) -> ET.Element:
        updated_root = self._tap_detail_update_if_present(root)
        if self._looks_like_refreshable_book_page(updated_root):
            return self._refresh_current_book_page()
        return updated_root

    def _looks_like_returned_book_entry_page(
        self,
        root: ET.Element,
    ) -> bool:
        page_name = self.navigator._current_page_name(root)
        if page_name == "home":
            return False
        if page_name == "report":
            return False
        if not self.navigator.find_text_bounds(root, START_READING_TEXT):
            return False

        hint_count = 0
        for hint_text in DETAIL_PAGE_HINT_TEXTS:
            if self.navigator.find_text_bounds(root, hint_text):
                hint_count += 1
                if hint_count >= 2:
                    return True

        return (
            self.navigator.detail_title(root) is not None
            or self.navigator.detail_progress(root) is not None
        )

    def _sync_page_after_back_once(
        self,
        root: ET.Element,
    ) -> tuple[ET.Element, bool]:
        current_root = root

        if self._looks_like_returned_book_entry_page(current_root):
            log(
                "returned to the collection detail page after reading, "
                f"refreshing it {RETURNED_DETAIL_SYNC_ROUNDS} time(s) before leaving"
            )
            for round_index in range(RETURNED_DETAIL_SYNC_ROUNDS):
                log(
                    f"collection detail refresh "
                    f"{round_index + 1}/{RETURNED_DETAIL_SYNC_ROUNDS}"
                )
                current_root = self._refresh_current_book_page()
            return current_root, True

        did_sync = False
        if self.navigator.find_text_bounds(current_root, UPDATE_BUTTON_TEXT):
            current_root = self._tap_detail_update_if_present(current_root)
            did_sync = True

        return current_root, did_sync

    def _open_collection_book(self, book: RecentBook) -> str:
        x, y = center(book.bounds)
        log(f"opening collection book: {self._describe_book(book)} at {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(self.config.navigation.prepare_wait_ms)
        candidate_root = self.device.dump_ui()
        if (
            self.navigator._current_page_name(candidate_root) == "collection"
            and not self._looks_like_returned_book_entry_page(candidate_root)
            and not self.navigator.find_clickable_text(candidate_root, CONTINUE_READING_TEXT)
        ):
            log("collection card tap did not leave the collection page")
            return "open_collection_miss"

        candidate_root = self._tap_detail_update_if_present(candidate_root)

        selected_book = self._resolve_collection_book(candidate_root, book)
        if self._selection_blacklist_contains(selected_book):
            self._remember_selected_for_collection(selected_book)
            log("selected collection book is already in selection blacklist, going back")
            self.device.back()
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
            return "open_collection_blacklisted"

        self.current_book = selected_book
        self._remember_selected_for_collection(selected_book)
        if self._tap_continue_if_present(candidate_root):
            return "open_collection_then_continue"
        if self._tap_start_reading_if_present(candidate_root):
            return "open_collection_then_start"
        return "open_collection"

    def _open_home_collection_page(self, root: ET.Element) -> Optional[ET.Element]:
        current_root = root
        for attempt in range(3):
            if self.navigator._current_page_name(current_root) == "collection":
                return current_root

            bounds = self.navigator.find_home_collection_entry(current_root)
            if not bounds:
                self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1200))
                current_root = self.device.dump_ui()
                continue

            x, y = center(bounds)
            log(f"opening collection entry at {x},{y} (attempt {attempt + 1})")
            self.device.tap(x, y)
            for _ in range(4):
                self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1500))
                current_root = self.device.dump_ui()
                if self.navigator._current_page_name(current_root) == "collection":
                    return current_root

            log("collection entry tap stayed on home, trying to clear the loading overlay")
            self.device.back()
            self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1200))
            current_root = self.device.dump_ui()
            if (
                self.navigator._current_page_name(current_root) == "home"
                and self.navigator.list_recent_books(current_root)
            ):
                log("home page became interactive again after back")
            else:
                log("back left the home page while recovering, relaunching app")
                if self.config.navigation.launch_app:
                    log(f"launching {self.config.package}")
                    self.device.launch_app()
                    self._sleep_ms(self.config.navigation.prepare_wait_ms)
                current_root = self._return_to_recent_home()
                if current_root is None:
                    return None

            log("collection entry tap did not leave home, retrying")

        return None

    def _pick_next_book_from_collection_root(
        self,
        collection_root: ET.Element,
    ) -> str:
        collection_root = self._choose_random_collection_category(collection_root)
        collection_root = self._randomize_collection_start(collection_root)

        for _ in range(4):
            next_book = self._find_next_collection_book(collection_root)
            if not next_book:
                break

            action = self._open_collection_book(next_book)
            if action == "open_collection_blacklisted":
                collection_root = self.device.dump_ui()
                continue
            if action == "open_collection_miss":
                log("parsed collection card did not open, falling back to visible slot scanning")
                break

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

    def _open_collection_category_picker(
        self,
        root: ET.Element,
    ) -> Optional[ET.Element]:
        bounds = self.navigator.find_collection_category_trigger(root)
        if not bounds:
            return None
        x, y = center(bounds)
        log(f"opening collection category picker at {x},{y}")
        self.device.tap(x, y)
        self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 1500))
        return self.device.dump_ui()

    def _close_collection_category_picker(self) -> ET.Element:
        self.device.tap(*self._ratio_to_abs((0.92, 0.28)))
        self._sleep_ms(1000)
        return self.device.dump_ui()

    def _choose_random_collection_category(
        self,
        root: ET.Element,
    ) -> ET.Element:
        current_category = self.navigator.current_collection_category(root)
        popup_root = self._open_collection_category_picker(root)
        if popup_root is None:
            log("collection category picker was not found, keeping current category")
            return root

        categories = self.navigator.list_collection_categories(popup_root)
        allowed = [
            item
            for item in categories
            if item[0] not in EXCLUDED_COLLECTION_CATEGORIES
        ]

        if not allowed:
            if current_category in EXCLUDED_COLLECTION_CATEGORIES:
                log("no allowed collection category was found after excluding 重点图书")
            else:
                log("no alternative collection category was found, keeping current category")
            return self._close_collection_category_picker()

        chosen_name, chosen_bounds = random.choice(allowed)
        x, y = center(chosen_bounds)
        log(
            f"switching collection category from "
            f"{current_category or '<unknown>'} to {chosen_name}"
        )
        self.device.tap(x, y)
        self._sleep_ms(max(self.config.navigation.prepare_wait_ms, 2000))
        updated_root = self.device.dump_ui()
        updated_category = self.navigator.current_collection_category(updated_root)
        if updated_category:
            log(f"current collection category: {updated_category}")
        return updated_root

    def _scroll_collection_page(self) -> ET.Element:
        log("scrolling collection page to look for more books")
        self._swipe_ratio((0.5, 0.82), (0.5, 0.3), 650)
        self._sleep_ms(self.config.page_turn.settle_ms)
        return self.device.dump_ui()

    def _randomize_collection_start(
        self,
        root: ET.Element,
        max_random_scrolls: int = 3,
    ) -> ET.Element:
        scrolls = random.randint(0, max_random_scrolls)
        if scrolls <= 0:
            return root

        log(
            f"randomizing collection start page: scrolling {scrolls} screen(s) before selecting"
        )
        current_root = root
        for _ in range(scrolls):
            current_root = self._scroll_collection_page()
        return current_root

    def _should_skip_collection_book(self, book: RecentBook) -> bool:
        if self._is_marked_completed(book):
            return True
        if book.is_complete():
            return True
        if self._selection_blacklist_contains(book):
            return True
        if self._same_book(self.current_book, book):
            return True
        return False

    def _open_next_book_from_collection(self, root: ET.Element) -> str:
        collection_root = self._open_home_collection_page(root)
        if collection_root is None:
            log("home collection entry was not found, cannot choose the next book")
            return "stop"
        return self._pick_next_book_from_collection_root(collection_root)

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

            candidates = [
                book for book in books if not self._should_skip_collection_book(book)
            ]
            if candidates:
                chosen = random.choice(candidates)
                log(
                    f"randomly selected one visible collection book from "
                    f"{len(candidates)} candidate(s): {self._describe_book(chosen)}"
                )
                return chosen

            if attempt == max_scrolls:
                break

            log("no selectable visible collection book yet, moving to another collection screen")
            root = self._scroll_collection_page()

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
            slot_candidates = list(enumerate(self._collection_slot_points(), start=1))
            random.shuffle(slot_candidates)
            for slot_index, point in slot_candidates:
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

                candidate_root = self._tap_detail_update_if_present(candidate_root)
                report_progress = self.navigator.report_progress(candidate_root)
                detail_progress = self.navigator.detail_progress(candidate_root)
                continue_bounds = self.navigator.find_clickable_text(
                    candidate_root,
                    CONTINUE_READING_TEXT,
                )
                start_bounds = self.navigator.find_text_bounds(
                    candidate_root,
                    START_READING_TEXT,
                )

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
                selected_book = RecentBook(
                    title=title,
                    image_key=None,
                    progress_text=progress_text,
                    progress_percent=progress,
                    bounds=(0, 0, 0, 0),
                )
                log(
                    f"collection candidate opened: {title}, progress={progress_text}"
                )

                if self._same_book(self.current_book, selected_book):
                    log("candidate book matches the current book, going back to try another one")
                    self.device.back()
                    self._sleep_ms(self.config.navigation.prepare_wait_ms)
                    root = self.device.dump_ui()
                    continue

                if self._selection_blacklist_contains(selected_book):
                    self._remember_selected_for_collection(selected_book)
                    log("candidate book is already in selection blacklist, going back")
                    self.device.back()
                    self._sleep_ms(self.config.navigation.prepare_wait_ms)
                    root = self.device.dump_ui()
                    continue

                if progress is not None and progress >= 99.9:
                    log("candidate book is already complete, going back to collection page")
                    self.device.back()
                    self._sleep_ms(self.config.navigation.prepare_wait_ms)
                    root = self.device.dump_ui()
                    continue

                self.current_book = selected_book
                self._remember_selected_for_collection(selected_book)
                if self._tap_continue_if_present(candidate_root):
                    return "open_collection_then_continue"
                if self._tap_start_reading_if_present(candidate_root):
                    return "open_collection_then_start"
                return "open_collection"

            if page_index == max_pages - 1:
                break

            root = self._scroll_collection_page()

        return "all_done"

    def _prepare_reading_page(self) -> str:
        root = self.device.dump_ui()
        page_name = self.navigator._current_page_name(root)
        if page_name == "report" or self.navigator.find_clickable_text(root, CONTINUE_READING_TEXT):
            root = self._tap_detail_update_repeatedly(
                root,
                rounds=HOME_ENTRY_UPDATE_ROUNDS,
                context_label="home entry sync",
            )
            page_name = self.navigator._current_page_name(root)
        else:
            root = self._tap_detail_update_if_present(root)
            page_name = self.navigator._current_page_name(root)

        if page_name == "collection":
            log("already on collection page during prepare, choosing a book from current collection")
            return self._pick_next_book_from_collection_root(root)

        if self._tap_continue_if_present(root):
            return "continue"
        if self._tap_start_reading_if_present(root):
            return "start"

        items = self.navigator.list_recent_books(root)
        if items:
            first_recent = items[0]
            if first_recent.is_complete() or self._is_marked_completed(first_recent):
                self._mark_book_completed(first_recent)
                if first_recent.is_complete():
                    log(
                        "first recent book is already complete, "
                        "opening collection page to choose a new book"
                    )
                else:
                    log(
                        "first recent book has already been verified as done for this run, "
                        "opening collection page to choose a new book"
                    )
                result = self._open_next_book_from_collection(root)
                if result == "opened_next":
                    return "first_recent_complete_then_opened_next"
                return result

        if self.config.navigation.open_recent_index and self.config.navigation.open_recent_index > 0:
            if items and len(items) >= self.config.navigation.open_recent_index:
                return self._open_recent_book(
                    items[self.config.navigation.open_recent_index - 1]
                )

        return "noop"

    def _return_to_recent_home(
        self,
        max_back_steps: int = 4,
    ) -> Optional[ET.Element]:
        back_steps = 0
        synced_since_last_back = False

        while back_steps <= max_back_steps:
            root = self.device.dump_ui()
            books = self.navigator.list_recent_books(root)
            if books:
                log(f"recent reading page ready with {len(books)} visible books")
                return root

            if not synced_since_last_back:
                root, did_sync = self._sync_page_after_back_once(root)
                if did_sync:
                    synced_since_last_back = True
                    books = self.navigator.list_recent_books(root)
                    if books:
                        log(f"recent reading page ready with {len(books)} visible books")
                        return root
                    continue

            if back_steps == max_back_steps:
                break
            log("recent reading not visible yet, pressing back")
            self.device.back()
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
            back_steps += 1
            synced_since_last_back = False
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

    def _handle_incomplete_completion_verification(
        self,
        root: ET.Element,
        current_on_home: RecentBook,
    ) -> str:
        verify_key = self._completion_verification_key(current_on_home)
        verification_count = (
            self.incomplete_completion_verifications.get(verify_key, 0) + 1
        )
        self.incomplete_completion_verifications[verify_key] = verification_count
        max_attempts = max(1, self.config.runtime.completion_verify_attempts)

        if verification_count < max_attempts:
            log(
                "suspected end of book reached, but current book progress is still "
                f"{current_on_home.progress_text}; verification "
                f"{verification_count}/{max_attempts}, reopening the same book "
                "to confirm before skipping"
            )
            reopen_result = self._open_recent_book(current_on_home)
            log(
                "reopened current book after incomplete completion verification, "
                f"action={reopen_result}"
            )
            return "reopen_current"

        log(
            "current book still has progress "
            f"{current_on_home.progress_text} after "
            f"{verification_count}/{max_attempts} end-of-book verifications; "
            "marking it as done for this run and moving on"
        )
        self._mark_book_completed(current_on_home)
        return self._open_next_book_from_collection(root)

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
            return self._handle_incomplete_completion_verification(
                root,
                current_on_home,
            )

        self._mark_book_completed(current_on_home)
        log(f"book completed: {self._describe_book(current_on_home)}")
        return self._open_next_book_from_collection(root)

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

    def prepare(self, skip_prepare: bool = False) -> str:
        self.device.ensure_ready()
        self.screen_size = self.device.wm_size()
        result = "noop"
        if self.config.navigation.launch_app:
            log(f"launching {self.config.package}")
            self.device.launch_app()
            self._sleep_ms(self.config.navigation.prepare_wait_ms)
        if not skip_prepare:
            result = self._prepare_reading_page()
            log(f"prepare result: {result}")
        return result

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
        self._perform_direct_swipe("scroll swipe", start, end, duration_ms)

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
        start = self._clamp_point(self._ratio_to_abs(self.config.page_turn.start))
        end = self._clamp_point(self._ratio_to_abs(self.config.page_turn.end))
        low, high = self.config.page_turn.duration_ms
        duration_ms = max(120, (low + high) // 2)
        self._perform_direct_swipe("page-turn swipe", start, end, duration_ms)

    def run(
        self,
        skip_prepare: bool = False,
        max_page_turns_override: Optional[int] = None,
    ) -> int:
        prepare_result = self.prepare(skip_prepare=skip_prepare)
        if prepare_result == "all_done":
            log("no unread book found during prepare, stopping")
            return 0
        if prepare_result == "stop":
            log("prepare step did not reach a safe reading page, stopping")
            return 2

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
                    if switch_result in {"opened_next", "reopen_current"}:
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
                self._sleep_scroll_pause("scroll pause")

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

            if pause_after_page_turn:
                self._sleep_scroll_pause("page-turn pause")

            if pause_after_book_switch:
                self._sleep_scroll_pause("book-switch pause")

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
