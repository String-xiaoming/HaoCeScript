var SCRIPT_DIR = (function () {
  try {
    var engine = engines.myEngine();
    if (engine && typeof engine.cwd === "function") {
      return engine.cwd();
    }
  } catch (error) {
  }
  return files.cwd();
}());

// Optional external config. If absent, the script uses built-in defaults.
var DEFAULT_CONFIG_PATH = files.join(SCRIPT_DIR, "config.json");
var KNOWN_COLLECTION_CATEGORIES = [
  "\u91cd\u70b9\u56fe\u4e66",
  "\u653f\u6cbb\u519b\u4e8b",
  "\u6559\u80b2\u6559\u5b66",
  "\u6210\u529f\u52b1\u5fd7",
  "\u54f2\u5b66\u601d\u60f3",
  "\u6cd5\u5f8b\u6cd5\u89c4",
  "\u5c0f\u8bf4\u4f20\u8bb0",
  "\u81ea\u7136\u79d1\u5b66",
  "\u5a5a\u604b\u60c5\u611f",
  "\u6587\u5316\u4f53\u80b2",
  "\u6587\u5b66\u827a\u672f",
  "\u52a8\u6f2b\u7ed8\u672c",
  "\u793e\u4f1a\u79d1\u5b66",
  "\u7eaa\u5b9e\u5386\u53f2",
  "\u7ecf\u7ba1\u7406\u8d22",
  "\u57f9\u8bad\u8003\u8bd5",
  "\u4ea4\u901a\u8fd0\u8f93",
  "\u519c\u6797\u7267\u6e14",
  "\u533b\u7597\u4fdd\u5065",
  "\u5bb6\u5c45\u751f\u6d3b",
  "\u5c11\u513f\u8bfb\u7269",
  "\u5de5\u4e1a\u6280\u672f",
  "\u5efa\u7b51\u8bbe\u8ba1",
  "\u65c5\u6e38\u5730\u7406",
  "\u6c11\u65cf\u6587\u5316",
  "\u65f6\u5c1a\u5a31\u4e50",
  "\u70f9\u996a\u7f8e\u98df",
  "\u7535\u8111\u7f51\u7edc"
];

var TEXT_CONTINUE = "\u7ee7\u7eed\u9605\u8bfb";
var TEXT_START = "\u5f00\u59cb\u9605\u8bfb";
var TEXT_UPDATE = "\u66f4\u65b0";
var TEXT_RECENT = "\u6700\u8fd1\u9605\u8bfb";
var TEXT_COLLECTION = "\u4e66\u9999\u7406\u5de5";
var TEXT_COLLECTION_ROOT = "\u6821\u56fe\u4e66\u8bfb\u4e66\u5de5\u7a0b";
var TEXT_CATEGORY_PREFIX = "\u5206\u7c7b\uff1a";
var TEXT_HOME = "\u9996\u9875";
var TEXT_SCORE = "\u6210\u7ee9";
var TEXT_LAST_CHAPTER = "\u5df2\u662f\u6700\u540e\u4e00\u7ae0!";
var TEXT_REPORT = "\u8bfb\u4e66\u62a5\u544a";
var TEXT_BACK = "\u8fd4\u56de";
var TEXT_SEARCH = "\u641c\u7d22";
var GENERIC_BOOK_LABELS = {
  "\u4e66\u9999\u7406\u5de5": true,
  "\u4eba\u6587\u7406\u5de5": true,
  "\u6821\u56fe\u4e66\u8bfb\u4e66\u5de5\u7a0b": true,
  "\u91cd\u70b9\u56fe\u4e66": true
};
var DETAIL_PAGE_HINT_TEXTS = [
  "\u4f5c\u8005",
  "\u51fa\u7248\u793e",
  "\u603b\u5b57\u6570",
  "\u7b80\u4ecb",
  "\u6e29\u99a8\u63d0\u793a"
];
var HOME_ENTRY_UPDATE_ROUNDS = 3;
var RETURNED_DETAIL_SYNC_ROUNDS = 3;

function log(message) {
  var now = new Date();
  var hh = ("0" + now.getHours()).slice(-2);
  var mm = ("0" + now.getMinutes()).slice(-2);
  var ss = ("0" + now.getSeconds()).slice(-2);
  console.log("[" + hh + ":" + mm + ":" + ss + "] " + message);
}

function sleepMs(value) {
  if (value > 0) {
    sleep(value);
  }
}

function singleTap(x, y) {
  var tapX = Math.floor(x);
  var tapY = Math.floor(y);
  if (typeof click === "function") {
    try {
      return click(tapX, tapY);
    } catch (error) {
    }
  }
  if (typeof press === "function") {
    try {
      return press(tapX, tapY, 1);
    } catch (error) {
    }
  }
  return false;
}

function choose(value, fallbackValue) {
  return value === undefined || value === null ? fallbackValue : value;
}

function randomInt(minValue, maxValue) {
  var low = Math.min(minValue, maxValue);
  var high = Math.max(minValue, maxValue);
  if (low === high) {
    return low;
  }
  return low + Math.floor(Math.random() * (high - low + 1));
}

function randomFloat(minValue, maxValue) {
  var low = Math.min(minValue, maxValue);
  var high = Math.max(minValue, maxValue);
  if (Math.abs(low - high) < 1e-9) {
    return low;
  }
  return low + Math.random() * (high - low);
}

function shuffleArray(items) {
  for (var i = items.length - 1; i > 0; i -= 1) {
    var j = Math.floor(Math.random() * (i + 1));
    var temp = items[i];
    items[i] = items[j];
    items[j] = temp;
  }
  return items;
}

function parseRange(value, fallbackLow, fallbackHigh) {
  if (typeof value === "number") {
    return [value, value];
  }
  if (Array.isArray(value) && value.length === 2) {
    var first = Number(value[0]);
    var second = Number(value[1]);
    if (!isNaN(first) && !isNaN(second)) {
      return [Math.min(first, second), Math.max(first, second)];
    }
  }
  return [fallbackLow, fallbackHigh];
}

function midRange(rangeValue) {
  return Math.floor((rangeValue[0] + rangeValue[1]) / 2);
}

function parsePercent(textValue) {
  if (!textValue) {
    return null;
  }
  var match = String(textValue).match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? parseFloat(match[1]) : null;
}

function normalizeTitle(title) {
  if (!title) {
    return null;
  }
  var normalized = String(title).replace(/\s+/g, " ").trim();
  if (!normalized || normalized === "\u2022" || normalized === "\u2022 ") {
    return null;
  }
  if (GENERIC_BOOK_LABELS[normalized]) {
    return null;
  }
  if (normalized.indexOf("collection-slot-") === 0) {
    return normalized;
  }
  return normalized;
}

function readJson(path, fallbackValue) {
  try {
    if (!files.exists(path)) {
      return fallbackValue;
    }
    return JSON.parse(files.read(path));
  } catch (error) {
    log("read json failed: " + error);
    return fallbackValue;
  }
}

function writeJson(path, value) {
  try {
    var normalizedPath = String(path || "").replace(/\\/g, "/");
    var index = normalizedPath.lastIndexOf("/");
    var parent = index > 0 ? normalizedPath.slice(0, index) : null;
    if (parent && !files.exists(parent)) {
      files.createWithDirs(files.join(parent, ".keep"));
      files.remove(files.join(parent, ".keep"));
    }
    files.write(path, JSON.stringify(value, null, 2));
    return true;
  } catch (error) {
    log("write json failed: " + error);
    return false;
  }
}

function setHas(map, value) {
  return !!map[value];
}

function setAdd(map, value) {
  if (!value) {
    return false;
  }
  if (map[value]) {
    return false;
  }
  map[value] = true;
  return true;
}

function setKeys(map) {
  return Object.keys(map).sort();
}

function rectFromBounds(bounds) {
  if (!bounds) {
    return null;
  }
  var left = Number(bounds.left);
  var top = Number(bounds.top);
  var right = Number(bounds.right);
  var bottom = Number(bounds.bottom);
  if (isNaN(left) || isNaN(top) || isNaN(right) || isNaN(bottom)) {
    return null;
  }
  return {
    left: left,
    top: top,
    right: right,
    bottom: bottom
  };
}

function rectWidth(rect) {
  return rect ? Math.max(0, rect.right - rect.left) : 0;
}

function rectHeight(rect) {
  return rect ? Math.max(0, rect.bottom - rect.top) : 0;
}

function rectArea(rect) {
  return rectWidth(rect) * rectHeight(rect);
}

function rectCenter(rect) {
  return [
    Math.floor((rect.left + rect.right) / 2),
    Math.floor((rect.top + rect.bottom) / 2)
  ];
}

function rectSignature(rect) {
  return [rect.left, rect.top, rect.right, rect.bottom].join(",");
}

function rectExpanded(rect, padLeft, padTop, padRight, padBottom) {
  return {
    left: Math.max(0, rect.left - padLeft),
    top: Math.max(0, rect.top - padTop),
    right: Math.min(device.width, rect.right + padRight),
    bottom: Math.min(device.height, rect.bottom + padBottom)
  };
}

function rectUnion(leftRect, rightRect) {
  if (!leftRect) {
    return rightRect || null;
  }
  if (!rightRect) {
    return leftRect;
  }
  return {
    left: Math.min(leftRect.left, rightRect.left),
    top: Math.min(leftRect.top, rightRect.top),
    right: Math.max(leftRect.right, rightRect.right),
    bottom: Math.max(leftRect.bottom, rightRect.bottom)
  };
}

function progressTextOf(value) {
  if (typeof value !== "number" || isNaN(value)) {
    return "\u8fdb\u5ea6:unknown";
  }
  return "\u8fdb\u5ea6:" + value.toFixed(2) + "%";
}

function buildConfig(raw) {
  raw = raw || {};
  raw.navigation = raw.navigation || {};
  raw.scroll = raw.scroll || {};
  raw.page_turn = raw.page_turn || {};
  raw.analysis = raw.analysis || {};
  raw.runtime = raw.runtime || {};
  raw.collection = raw.collection || {};
  raw.motion = raw.motion || {};

  return {
    packageName: choose(raw.package, "app.haoce.com"),
    navigation: {
      launchApp: raw.navigation.launch_app !== false,
      openRecentIndex: choose(raw.navigation.open_recent_index, 1),
      prepareWaitMs: choose(raw.navigation.prepare_wait_ms, 2000),
      maxBackStepsHome: choose(raw.navigation.max_back_steps_home, 4)
    },
    scroll: {
      start: choose(raw.scroll.start, [0.5, 0.8]),
      end: choose(raw.scroll.end, [0.5, 0.28]),
      startJitter: choose(raw.scroll.start_jitter, [0.03, 0.025]),
      endJitter: choose(raw.scroll.end_jitter, [0.03, 0.025]),
      durationMs: parseRange(raw.scroll.duration_ms, 450, 650),
      durationJitterMs: choose(raw.scroll.duration_jitter_ms, 0),
      settleMs: choose(raw.scroll.settle_ms, 1200),
      pauseMs: parseRange(raw.scroll.pause_ms, 10000, 15000)
    },
    pageTurn: {
      action: choose(raw.page_turn.action, "swipe"),
      start: choose(raw.page_turn.start, [0.83, 0.58]),
      end: choose(raw.page_turn.end, [0.17, 0.58]),
      startJitter: choose(raw.page_turn.start_jitter, [0.0, 0.0]),
      endJitter: choose(raw.page_turn.end_jitter, [0.0, 0.0]),
      tap: choose(raw.page_turn.tap, null),
      durationMs: parseRange(raw.page_turn.duration_ms, 320, 320),
      durationJitterMs: choose(raw.page_turn.duration_jitter_ms, 0),
      settleMs: choose(raw.page_turn.settle_ms, 1500)
    },
    motion: {
      trajectoryPoints: parseRange(raw.motion && raw.motion.trajectory_points, 3, 4),
      pathJitter: choose(raw.motion && raw.motion.path_jitter, [0.012, 0.018]),
      lateralChance: choose(raw.motion && raw.motion.lateral_chance, 0.04),
      lateralDistanceRatio: parseRange(raw.motion && raw.motion.lateral_distance_ratio, 0.06, 0.10),
      lateralDurationMs: parseRange(raw.motion && raw.motion.lateral_duration_ms, 70, 110),
      downwardChance: choose(raw.motion && raw.motion.downward_chance, 0.08),
      downwardDistanceRatio: parseRange(raw.motion && raw.motion.downward_distance_ratio, 0.10, 0.18),
      downwardDurationMs: parseRange(raw.motion && raw.motion.downward_duration_ms, 110, 180),
      microSettleMs: parseRange(raw.motion && raw.motion.micro_settle_ms, 350, 900)
    },
    analysis: {
      crop: choose(raw.analysis.crop, [0.06, 0.12, 0.94, 0.92]),
      pixelDiffThreshold: choose(raw.analysis.pixel_diff_threshold, 12),
      stuckMeanDiffMax: choose(raw.analysis.stuck_mean_diff_max, 2.0),
      stuckChangedRatioMax: choose(raw.analysis.stuck_changed_ratio_max, 0.015),
      pageTurnMeanDiffMin: choose(raw.analysis.page_turn_mean_diff_min, 8.0),
      pageTurnChangedRatioMin: choose(raw.analysis.page_turn_changed_ratio_min, 0.08),
      bottomConfirmations: choose(raw.analysis.bottom_confirmations, 2),
      diffGridX: choose(raw.analysis.diff_grid_x, 8),
      diffGridY: choose(raw.analysis.diff_grid_y, 14)
    },
    runtime: {
      loopSleepMs: choose(raw.runtime.loop_sleep_ms, 250),
      maxPageTurns: choose(raw.runtime.max_page_turns, 0),
      maxMinutes: choose(raw.runtime.max_minutes, 0),
      selectionBlacklistFile: choose(raw.runtime.selection_blacklist_file, "selection_blacklist.json"),
      completionVerifyAttempts: Math.max(1, choose(raw.runtime.completion_verify_attempts, 2))
    },
    collection: {
      excludedCategories: choose(raw.collection.excluded_categories, ["\u91cd\u70b9\u56fe\u4e66"]),
      randomStartScrolls: parseRange(raw.collection.random_start_scrolls, 0, 3),
      slotScanPages: choose(raw.collection.slot_scan_pages, 8),
      slotPoints: choose(raw.collection.slot_points, [
        [0.17, 0.41],
        [0.50, 0.41],
        [0.83, 0.41],
        [0.17, 0.63],
        [0.50, 0.63],
        [0.83, 0.63]
      ])
    }
  };
}

function HaoceReader(config) {
  this.config = config;
  this.currentBook = null;
  this.completedBookKeys = {};
  this.completedBookTitles = {};
  this.incompleteCompletionVerifications = {};
  this.selectionBlacklistPath = files.join(SCRIPT_DIR, config.runtime.selectionBlacklistFile);
  this.selectionBlacklistTitles = {};
  this.selectionBlacklistKeys = {};
  this.loadSelectionBlacklist();
}

HaoceReader.prototype.safeText = function (node) {
  try {
    var value = node.text();
    if (value === null || value === undefined) {
      return "";
    }
    return String(value).trim();
  } catch (error) {
    return "";
  }
};

HaoceReader.prototype.safeDesc = function (node) {
  try {
    var value = node.desc();
    if (value === null || value === undefined) {
      return "";
    }
    return String(value).trim();
  } catch (error) {
    return "";
  }
};

HaoceReader.prototype.safeClassName = function (node) {
  try {
    var value = node.className();
    if (value === null || value === undefined) {
      return "";
    }
    return String(value);
  } catch (error) {
    return "";
  }
};

HaoceReader.prototype.safeBounds = function (node) {
  try {
    return rectFromBounds(node.bounds());
  } catch (error) {
    return null;
  }
};

HaoceReader.prototype.directChildren = function (node) {
  var result = [];
  var count = 0;
  try {
    count = node.childCount();
  } catch (error) {
    return result;
  }

  for (var i = 0; i < count; i += 1) {
    var child;
    try {
      child = node.child(i);
    } catch (error) {
      child = null;
    }
    if (!child) {
      continue;
    }
    result.push({
      node: child,
      text: this.safeText(child),
      desc: this.safeDesc(child),
      className: this.safeClassName(child),
      bounds: this.safeBounds(child)
    });
  }
  return result;
};

HaoceReader.prototype.allNodes = function () {
  var result = [];
  var nodes;
  try {
    nodes = packageName(this.config.packageName).find();
  } catch (error) {
    return result;
  }
  if (!nodes) {
    return result;
  }
  for (var i = 0; i < nodes.size(); i += 1) {
    var node = nodes.get(i);
    if (!node) {
      continue;
    }
    result.push(node);
  }
  return result;
};

HaoceReader.prototype.loadSelectionBlacklist = function () {
  var payload = readJson(this.selectionBlacklistPath, { titles: [], keys: [] });
  var i;
  for (i = 0; i < (payload.titles || []).length; i += 1) {
    var normalizedTitle = normalizeTitle(payload.titles[i]);
    if (normalizedTitle) {
      this.selectionBlacklistTitles[normalizedTitle] = true;
    }
  }
  for (i = 0; i < (payload.keys || []).length; i += 1) {
    var key = String(payload.keys[i] || "").trim();
    if (key) {
      this.selectionBlacklistKeys[key] = true;
    }
  }
};

HaoceReader.prototype.saveSelectionBlacklist = function () {
  writeJson(this.selectionBlacklistPath, {
    titles: setKeys(this.selectionBlacklistTitles),
    keys: setKeys(this.selectionBlacklistKeys)
  });
};

HaoceReader.prototype.selectionBlacklistContains = function (book) {
  var title = normalizeTitle(book && book.title);
  if (title && setHas(this.selectionBlacklistTitles, title)) {
    return true;
  }
  var key = book && book.key ? String(book.key).trim() : null;
  if (key && setHas(this.selectionBlacklistKeys, key)) {
    return true;
  }
  return false;
};

HaoceReader.prototype.rememberSelectedForCollection = function (book) {
  var changed = false;
  var title = normalizeTitle(book && book.title);
  var key = book && book.key ? String(book.key).trim() : null;
  if (title) {
    changed = setAdd(this.selectionBlacklistTitles, title) || changed;
  }
  if (key) {
    changed = setAdd(this.selectionBlacklistKeys, key) || changed;
  }
  if (changed) {
    this.saveSelectionBlacklist();
  }
};

HaoceReader.prototype.markCompleted = function (book) {
  var title = normalizeTitle(book && book.title);
  var key = book && book.key ? String(book.key).trim() : null;
  var verificationKey = this.completionVerificationKey(book);
  if (title) {
    this.completedBookTitles[title] = true;
  }
  if (key) {
    this.completedBookKeys[key] = true;
  }
  if (verificationKey) {
    delete this.incompleteCompletionVerifications[verificationKey];
  }
};

HaoceReader.prototype.isCompleted = function (book) {
  var title = normalizeTitle(book && book.title);
  var key = book && book.key ? String(book.key).trim() : null;
  if (title && this.completedBookTitles[title]) {
    return true;
  }
  if (key && this.completedBookKeys[key]) {
    return true;
  }
  return false;
};

HaoceReader.prototype.completionVerificationKey = function (book) {
  var key = book && book.key ? String(book.key).trim() : null;
  var title = normalizeTitle(book && book.title);
  if (key) {
    return "key:" + key;
  }
  if (title) {
    return "title:" + title;
  }
  return null;
};

HaoceReader.prototype.describeBook = function (book) {
  if (!book) {
    return "<unknown>";
  }
  var title = normalizeTitle(book.title) || (book.key ? String(book.key).trim() : null) || "<untitled>";
  return title + " (" + (book.progressText || "\u8fdb\u5ea6:unknown") + ")";
};

HaoceReader.prototype.ratioToAbs = function (point) {
  return [
    Math.max(0, Math.min(device.width - 1, Math.floor(device.width * point[0]))),
    Math.max(0, Math.min(device.height - 1, Math.floor(device.height * point[1])))
  ];
};

HaoceReader.prototype.randomizedPoint = function (point, jitter) {
  var xRatio = point[0] + (Math.random() * 2 - 1) * jitter[0];
  var yRatio = point[1] + (Math.random() * 2 - 1) * jitter[1];
  return this.ratioToAbs([xRatio, yRatio]);
};

HaoceReader.prototype.randomizedDuration = function (rangeValue, jitterMs) {
  var base = randomInt(rangeValue[0], rangeValue[1]);
  if (jitterMs <= 0) {
    return base;
  }
  return Math.max(1, base + randomInt(-jitterMs, jitterMs));
};

HaoceReader.prototype.randomFloatBetween = function (rangeValue) {
  return randomFloat(rangeValue[0], rangeValue[1]);
};

HaoceReader.prototype.buildTrajectoryPoints = function (start, end) {
  var pointCount = Math.max(2, randomInt(
    this.config.motion.trajectoryPoints[0],
    this.config.motion.trajectoryPoints[1]
  ));
  if (pointCount <= 2) {
    return [start, end];
  }

  var jitterX = device.width * this.config.motion.pathJitter[0];
  var jitterY = device.height * this.config.motion.pathJitter[1];
  var points = [];

  for (var index = 0; index < pointCount; index += 1) {
    var t = index / (pointCount - 1);
    var baseX = start[0] + (end[0] - start[0]) * t;
    var baseY = start[1] + (end[1] - start[1]) * t;
    var curve = Math.sin(Math.PI * t);
    var point = [
      Math.max(0, Math.min(device.width - 1, Math.round(baseX + randomFloat(-jitterX, jitterX) * curve))),
      Math.max(0, Math.min(device.height - 1, Math.round(baseY + randomFloat(-jitterY, jitterY) * curve)))
    ];
    if (!points.length || point[0] !== points[points.length - 1][0] || point[1] !== points[points.length - 1][1]) {
      points.push(point);
    }
  }

  if (points.length < 2) {
    return [start, end];
  }
  points[0] = start;
  points[points.length - 1] = end;
  return points;
};

HaoceReader.prototype.performGesturePath = function (label, start, end, duration) {
  var points = this.buildTrajectoryPoints(start, end);
  log(
    label + ": start=(" + start[0] + "," + start[1] + ") end=(" + end[0] + "," + end[1] +
    ") duration=" + duration + "ms track_points=" + points.length
  );
  if (typeof gesture === "function" && points.length >= 2) {
    var args = [duration];
    for (var i = 0; i < points.length; i += 1) {
      args.push(points[i]);
    }
    gesture.apply(null, args);
    return;
  }
  swipe(start[0], start[1], end[0], end[1], duration);
};

HaoceReader.prototype.performDirectSwipe = function (label, start, end, duration) {
  log(
    label + ": start=(" + start[0] + "," + start[1] + ") end=(" + end[0] + "," + end[1] +
    ") duration=" + duration + "ms"
  );
  swipe(start[0], start[1], end[0], end[1], duration);
};

HaoceReader.prototype.pauseRatio = function (pauseMs) {
  var low = this.config.scroll.pauseMs[0];
  var high = this.config.scroll.pauseMs[1];
  if (high <= low) {
    return 0.5;
  }
  return Math.max(0, Math.min(1, (pauseMs - low) / (high - low)));
};

HaoceReader.prototype.performLateralDrift = function () {
  var distanceRatio = this.randomFloatBetween(this.config.motion.lateralDistanceRatio);
  var duration = randomInt(
    this.config.motion.lateralDurationMs[0],
    this.config.motion.lateralDurationMs[1]
  );
  var centerX = randomFloat(0.40, 0.66);
  var centerY = randomFloat(0.40, 0.74);
  var halfDistance = distanceRatio / 2;
  var start = this.ratioToAbs([
    Math.min(0.92, centerX + halfDistance),
    centerY + randomFloat(-0.015, 0.015)
  ]);
  var end = this.ratioToAbs([
    Math.max(0.08, centerX - halfDistance),
    centerY + randomFloat(-0.015, 0.015)
  ]);
  this.performDirectSwipe("lateral drift swipe", start, end, duration);
  return duration;
};

HaoceReader.prototype.performDownwardReview = function (pauseMs) {
  var pauseRatio = this.pauseRatio(pauseMs);
  var lowDistance = this.config.motion.downwardDistanceRatio[0];
  var highDistance = this.config.motion.downwardDistanceRatio[1];
  var distanceRatio = lowDistance + (highDistance - lowDistance) * pauseRatio;
  distanceRatio = Math.max(lowDistance, Math.min(highDistance, distanceRatio * randomFloat(0.92, 1.08)));
  var duration = randomInt(
    this.config.motion.downwardDurationMs[0],
    this.config.motion.downwardDurationMs[1]
  );
  var startRatio = [
    randomFloat(0.24, 0.76),
    randomFloat(0.28, 0.44)
  ];
  var endRatio = [
    startRatio[0] + randomFloat(-0.02, 0.02),
    Math.min(0.86, startRatio[1] + distanceRatio)
  ];
  log(
    "downward review swipe: pause_ratio=" + pauseRatio.toFixed(2) +
    ", distance_ratio=" + distanceRatio.toFixed(3)
  );
  this.performDirectSwipe(
    "downward review swipe",
    this.ratioToAbs(startRatio),
    this.ratioToAbs(endRatio),
    duration
  );
  return duration;
};

HaoceReader.prototype.performPauseActions = function (label, pauseMs) {
  if (pauseMs <= 0) {
    return;
  }

  var actions = [];
  if (Math.random() < this.config.motion.lateralChance) {
    actions.push("lateral");
  }
  if (Math.random() < this.config.motion.downwardChance) {
    actions.push("downward");
  }

  if (!actions.length) {
    sleepMs(pauseMs);
    return;
  }

  var action = actions[randomInt(0, actions.length - 1)];
  var remainingMs = pauseMs;
  var waitMin = Math.min(remainingMs, Math.floor(pauseMs * 0.2));
  var waitMax = Math.min(remainingMs, Math.max(waitMin, Math.floor(pauseMs * 0.7)));
  if (waitMax > 0) {
    var waitMs = waitMin === waitMax ? waitMin : randomInt(waitMin, waitMax);
    sleepMs(waitMs);
    remainingMs = Math.max(0, remainingMs - waitMs);
  }

  var usedMs = action === "lateral" ?
    this.performLateralDrift() :
    this.performDownwardReview(pauseMs);
  remainingMs = Math.max(0, remainingMs - usedMs);

  var settleMs = Math.min(
    remainingMs,
    randomInt(this.config.motion.microSettleMs[0], this.config.motion.microSettleMs[1])
  );
  if (settleMs > 0) {
    sleepMs(settleMs);
    remainingMs -= settleMs;
  }

  if (remainingMs > 0) {
    sleepMs(remainingMs);
  }
};

HaoceReader.prototype.randomPauseMs = function () {
  return randomInt(this.config.scroll.pauseMs[0], this.config.scroll.pauseMs[1]);
};

HaoceReader.prototype.sleepScrollPause = function (label) {
  var pauseMs = this.randomPauseMs();
  if (pauseMs <= 0) {
    return;
  }
  var low = this.config.scroll.pauseMs[0];
  var high = this.config.scroll.pauseMs[1];
  if (low === high) {
    log(label + ": waiting " + pauseMs + "ms before next upward swipe");
  } else {
    log(label + ": waiting " + pauseMs + "ms before next upward swipe (random in " + low + "-" + high + "ms)");
  }
  this.performPauseActions(label, pauseMs);
};

HaoceReader.prototype.launchApp = function () {
  log("launching " + this.config.packageName);
  app.launchPackage(this.config.packageName);
  sleepMs(this.config.navigation.prepareWaitMs + 1500);
};

HaoceReader.prototype.performScroll = function () {
  var start = this.randomizedPoint(this.config.scroll.start, this.config.scroll.startJitter);
  var end = this.randomizedPoint(this.config.scroll.end, this.config.scroll.endJitter);
  var duration = this.randomizedDuration(this.config.scroll.durationMs, this.config.scroll.durationJitterMs);
  this.performDirectSwipe("scroll swipe", start, end, duration);
};

HaoceReader.prototype.performPageTurn = function () {
  if (this.config.pageTurn.action === "tap" && this.config.pageTurn.tap) {
    var tapPoint = this.ratioToAbs(this.config.pageTurn.tap);
    singleTap(tapPoint[0], tapPoint[1]);
    return;
  }
  var start = this.ratioToAbs(this.config.pageTurn.start);
  var end = this.ratioToAbs(this.config.pageTurn.end);
  var duration = Math.max(120, midRange(this.config.pageTurn.durationMs));
  this.performDirectSwipe("page-turn swipe", start, end, duration);
};

HaoceReader.prototype.capture = function () {
  var image = captureScreen();
  if (!image) {
    throw new Error("captureScreen returned null");
  }

  if (images && typeof images.copy === "function") {
    var copied = images.copy(image);
    if (copied) {
      this.recycleImage(image);
      return copied;
    }
  }

  return image;
};

HaoceReader.prototype.recycleImage = function (image) {
  if (image && typeof image.recycle === "function") {
    try {
      image.recycle();
    } catch (error) {
    }
  }
};

HaoceReader.prototype.grayValue = function (colorValue) {
  return (colors.red(colorValue) + colors.green(colorValue) + colors.blue(colorValue)) / 3;
};

HaoceReader.prototype.diffImages = function (beforeImage, afterImage) {
  var width = beforeImage.getWidth();
  var height = beforeImage.getHeight();
  var crop = this.config.analysis.crop;
  var xStart = Math.floor(width * crop[0]);
  var yStart = Math.floor(height * crop[1]);
  var xEnd = Math.floor(width * crop[2]);
  var yEnd = Math.floor(height * crop[3]);
  var xSteps = this.config.analysis.diffGridX;
  var ySteps = this.config.analysis.diffGridY;
  var total = 0;
  var changed = 0;
  var sum = 0;

  for (var yi = 0; yi < ySteps; yi += 1) {
    for (var xi = 0; xi < xSteps; xi += 1) {
      var x = xStart + Math.floor((xEnd - xStart) * (xi + 0.5) / xSteps);
      var y = yStart + Math.floor((yEnd - yStart) * (yi + 0.5) / ySteps);
      var grayA = this.grayValue(images.pixel(beforeImage, x, y));
      var grayB = this.grayValue(images.pixel(afterImage, x, y));
      var delta = Math.abs(grayA - grayB);
      sum += delta;
      if (delta > this.config.analysis.pixelDiffThreshold) {
        changed += 1;
      }
      total += 1;
    }
  }

  return {
    meanDiff: total > 0 ? sum / total : 0,
    changedRatio: total > 0 ? changed / total : 0
  };
};

HaoceReader.prototype.looksStuck = function (metrics) {
  return metrics.meanDiff <= this.config.analysis.stuckMeanDiffMax &&
    metrics.changedRatio <= this.config.analysis.stuckChangedRatioMax;
};

HaoceReader.prototype.pageTurnConfirmed = function (metrics) {
  return metrics.meanDiff >= this.config.analysis.pageTurnMeanDiffMin ||
    metrics.changedRatio >= this.config.analysis.pageTurnChangedRatioMin;
};

HaoceReader.prototype.pageName = function () {
  if (textContains(TEXT_CONTINUE).exists() || text(TEXT_SCORE).exists()) {
    return "report";
  }
  if (textContains(TEXT_START).exists()) {
    return "detail";
  }
  if (textStartsWith(TEXT_CATEGORY_PREFIX).exists() || text(TEXT_COLLECTION_ROOT).exists()) {
    return "collection";
  }
  if (text(TEXT_RECENT).exists() || text(TEXT_HOME).exists()) {
    return "home";
  }
  return null;
};

HaoceReader.prototype.findTextNodePrefix = function (prefix) {
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    if (textValue.indexOf(prefix) === 0) {
      var bounds = this.safeBounds(nodes[i]);
      if (bounds && rectArea(bounds) > 0) {
        return {
          node: nodes[i],
          text: textValue,
          bounds: bounds
        };
      }
    }
  }
  return null;
};

HaoceReader.prototype.findClickableTextNode = function (target) {
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var node = nodes[i];
    var textValue = this.safeText(node);
    if (textValue.indexOf(target) < 0) {
      continue;
    }
    var bounds = this.safeBounds(node);
    if (!bounds || rectArea(bounds) <= 0) {
      continue;
    }
    return {
      node: node,
      text: textValue,
      bounds: bounds
    };
  }
  return null;
};

HaoceReader.prototype.reportTitle = function () {
  if (this.pageName() !== "report") {
    return null;
  }

  var bestText = null;
  var bestTop = null;
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!textValue || !bounds) {
      continue;
    }
    if (textValue === TEXT_BACK || textValue === TEXT_REPORT || textValue === TEXT_CONTINUE || textValue === TEXT_SCORE) {
      continue;
    }
    if (bounds.top > 260 || rectArea(bounds) <= 0) {
      continue;
    }
    if (bestTop === null || bounds.top < bestTop) {
      bestText = textValue;
      bestTop = bounds.top;
    }
  }
  return normalizeTitle(bestText);
};

HaoceReader.prototype.reportProgress = function () {
  if (this.pageName() !== "report") {
    return null;
  }

  var bestValue = null;
  var bestTop = null;
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!textValue || !bounds || textValue.indexOf("%") < 0) {
      continue;
    }
    if (rectArea(bounds) <= 0 || bounds.top < 300 || bounds.top > 700 || bounds.left > 650) {
      continue;
    }
    var progress = parsePercent(textValue);
    if (progress === null) {
      continue;
    }
    if (bestTop === null || bounds.top < bestTop) {
      bestValue = progress;
      bestTop = bounds.top;
    }
  }
  return bestValue;
};

HaoceReader.prototype.detailTitle = function () {
  if (this.pageName() !== "detail") {
    return null;
  }
  if (!textContains(TEXT_START).exists()) {
    return null;
  }

  var bestText = null;
  var bestArea = -1;
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!textValue || !bounds) {
      continue;
    }
    if (textValue === TEXT_BACK || textValue === TEXT_COLLECTION || textValue === TEXT_START) {
      continue;
    }
    if (bounds.top < 220 || bounds.top > 500) {
      continue;
    }
    var currentArea = rectArea(bounds);
    if (currentArea > bestArea) {
      bestText = textValue;
      bestArea = currentArea;
    }
  }
  return normalizeTitle(bestText);
};

HaoceReader.prototype.detailProgress = function () {
  if (this.pageName() !== "detail") {
    return null;
  }
  if (!textContains(TEXT_START).exists()) {
    return null;
  }

  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!textValue || !bounds || textValue.indexOf("%") < 0) {
      continue;
    }
    if (bounds.top < 1100 || bounds.top > 1450) {
      continue;
    }
    var progress = parsePercent(textValue);
    if (progress !== null) {
      return progress;
    }
  }
  return null;
};

HaoceReader.prototype.resolveOpenedBook = function (fallbackBook) {
  var title = this.reportTitle() || this.detailTitle() || normalizeTitle(fallbackBook ? fallbackBook.title : null) || "";
  var progress = this.reportProgress();
  if (progress === null) {
    progress = this.detailProgress();
  }
  if (progress === null && fallbackBook) {
    progress = fallbackBook.progressPercent;
  }
  return {
    title: title,
    key: fallbackBook ? fallbackBook.key : null,
    progressText: progressTextOf(progress),
    progressPercent: progress,
    bounds: fallbackBook ? fallbackBook.bounds : null
  };
};

HaoceReader.prototype.isProgressText = function (textValue) {
  return /^\u8fdb\u5ea6[:\uff1a]/.test(textValue) || (textValue.indexOf("\u8fdb\u5ea6") >= 0 && textValue.indexOf("%") >= 0);
};

HaoceReader.prototype.listRecentBooks = function () {
  if (this.pageName() !== "home") {
    return [];
  }

  var items = [];
  var seen = {};
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var node = nodes[i];
    var bounds = this.safeBounds(node);
    if (!bounds) {
      continue;
    }
    var children = this.directChildren(node);
    if (!children.length) {
      continue;
    }

    var progressText = null;
    var title = "";
    var imageKey = null;
    for (var j = 0; j < children.length; j += 1) {
      var child = children[j];
      if (!child.text) {
        continue;
      }
      if (this.isProgressText(child.text)) {
        progressText = child.text;
        continue;
      }
      if (child.className.indexOf("Image") >= 0 && !imageKey) {
        imageKey = child.text;
        continue;
      }
      var candidateTitle = normalizeTitle(child.text);
      if (!title && candidateTitle) {
        title = candidateTitle;
      }
    }

    if (!progressText) {
      continue;
    }
    if (rectArea(bounds) < 15000) {
      continue;
    }

    var signature = rectSignature(bounds);
    if (seen[signature]) {
      continue;
    }
    seen[signature] = true;
    items.push({
      title: title,
      key: imageKey,
      progressText: progressText,
      progressPercent: parsePercent(progressText),
      bounds: bounds
    });
  }

  items.sort(function (a, b) {
    if (a.bounds.top !== b.bounds.top) {
      return a.bounds.top - b.bounds.top;
    }
    return a.bounds.left - b.bounds.left;
  });
  return items;
};

HaoceReader.prototype.findRecentBookByKey = function (key) {
  var items = this.listRecentBooks();
  for (var i = 0; i < items.length; i += 1) {
    if (items[i].key && items[i].key === key) {
      return items[i];
    }
  }
  return null;
};

HaoceReader.prototype.findHomeCollectionEntryPoint = function () {
  if (this.pageName() !== "home") {
    return null;
  }

  var candidates = [];
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (textValue !== TEXT_COLLECTION || !bounds) {
      continue;
    }
    if (bounds.top < 1100) {
      candidates.push(bounds);
    }
  }

  if (!candidates.length) {
    return null;
  }

  candidates.sort(function (a, b) {
    if (a.top !== b.top) {
      return a.top - b.top;
    }
    return a.left - b.left;
  });
  return rectExpanded(candidates[0], 24, 180, 24, 24);
};

HaoceReader.prototype.findHomeCollectionEntryCandidate = function () {
  if (this.pageName() !== "home") {
    return null;
  }

  var textCandidates = [];
  var imageCandidates = [];
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!bounds || bounds.top >= 1100) {
      continue;
    }

    if (textValue === TEXT_COLLECTION) {
      textCandidates.push({
        node: nodes[i],
        bounds: bounds
      });
      continue;
    }

    if (String(nodes[i].className || "").indexOf("Image") >= 0 && rectArea(bounds) >= 8000) {
      imageCandidates.push(bounds);
    }
  }

  if (!textCandidates.length) {
    return null;
  }

  textCandidates.sort(function (a, b) {
    if (a.bounds.top !== b.bounds.top) {
      return a.bounds.top - b.bounds.top;
    }
    return a.bounds.left - b.bounds.left;
  });

  var chosen = textCandidates[0];
  var tapBounds = rectExpanded(chosen.bounds, 24, 180, 24, 24);
  var mergedBounds = tapBounds;
  var bestImage = null;
  var bestScore = Number.MAX_SAFE_INTEGER;
  var textCenter = rectCenter(chosen.bounds);

  for (var j = 0; j < imageCandidates.length; j += 1) {
    var imageBounds = imageCandidates[j];
    var imageCenter = rectCenter(imageBounds);
    var horizontalDistance = Math.abs(imageCenter[0] - textCenter[0]);
    var verticalGap = chosen.bounds.top - imageBounds.bottom;
    if (horizontalDistance > 220) {
      continue;
    }
    if (verticalGap < -80 || verticalGap > 260) {
      continue;
    }
    var score = horizontalDistance * 4 + Math.abs(verticalGap);
    if (score < bestScore) {
      bestScore = score;
      bestImage = imageBounds;
    }
  }

  if (bestImage) {
    tapBounds = rectExpanded(bestImage, 18, 18, 18, 18);
    mergedBounds = rectUnion(bestImage, chosen.bounds);
  }

  return {
    node: chosen.node,
    bounds: mergedBounds,
    tapBounds: tapBounds
  };
};

HaoceReader.prototype.clickNodeOrAncestor = function (node, maxLevels) {
  var current = node;
  var levels = choose(maxLevels, 4);

  for (var i = 0; i <= levels; i += 1) {
    if (!current) {
      break;
    }

    try {
      if (current.clickable && current.clickable() && current.enabled && current.enabled()) {
        if (current.click()) {
          return true;
        }
      }
    } catch (error) {
    }

    try {
      current = current.parent ? current.parent() : null;
    } catch (error) {
      current = null;
    }
  }

  return false;
};

HaoceReader.prototype.recoverHomeAfterCollectionTapMiss = function () {
  if (this.pageName() !== "home") {
    return true;
  }

  log("collection entry tap stayed on home, trying to clear the loading overlay");
  back();
  sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1200));

  if (this.pageName() === "home" && this.listRecentBooks().length) {
    log("home page became interactive again after back");
    return true;
  }

  log("back left the home page while recovering, relaunching app");
  if (this.config.navigation.launchApp) {
    this.launchApp();
  }
  if (this.returnToRecentHome()) {
    log("returned to recent home after recovery relaunch");
    return true;
  }
  return false;
};

HaoceReader.prototype.openHomeCollectionPage = function () {
  for (var attempt = 0; attempt < 3; attempt += 1) {
    if (this.pageName() === "collection") {
      return true;
    }

    var candidate = this.findHomeCollectionEntryCandidate();
    if (!candidate) {
      sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1200));
      continue;
    }

    var tapBounds = candidate.tapBounds || candidate.bounds;
    var point = rectCenter(tapBounds);
    log("opening collection entry at " + point[0] + "," + point[1] + " (attempt " + (attempt + 1) + ")");
    singleTap(point[0], point[1]);

    for (var i = 0; i < 4; i += 1) {
      sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1500));
      if (this.pageName() === "collection") {
        return true;
      }
    }

    if (!this.recoverHomeAfterCollectionTapMiss()) {
      return false;
    }
    log("collection entry tap did not leave home, retrying");
  }
  return false;
};

HaoceReader.prototype.currentCollectionCategory = function () {
  if (this.pageName() !== "collection") {
    return null;
  }
  var found = this.findTextNodePrefix(TEXT_CATEGORY_PREFIX);
  if (!found) {
    return null;
  }
  return found.text.replace(TEXT_CATEGORY_PREFIX, "").trim();
};

HaoceReader.prototype.findCollectionCategoryTrigger = function () {
  var found = this.findTextNodePrefix(TEXT_CATEGORY_PREFIX);
  if (!found) {
    return null;
  }
  return rectExpanded(found.bounds, 64, 20, 48, 20);
};

HaoceReader.prototype.openCollectionCategoryPicker = function () {
  var bounds = this.findCollectionCategoryTrigger();
  if (!bounds) {
    return false;
  }
  var point = rectCenter(bounds);
  log("opening collection category picker at " + point[0] + "," + point[1]);
  singleTap(point[0], point[1]);
  sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1500));
  return true;
};

HaoceReader.prototype.closeCollectionCategoryPicker = function () {
  var point = this.ratioToAbs([0.92, 0.28]);
  singleTap(point[0], point[1]);
  sleepMs(1000);
};

HaoceReader.prototype.listCollectionCategories = function () {
  var categories = [];
  var seen = {};
  var current = this.currentCollectionCategory();
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var textValue = this.safeText(nodes[i]);
    var bounds = this.safeBounds(nodes[i]);
    if (!textValue || !bounds) {
      continue;
    }
    if (KNOWN_COLLECTION_CATEGORIES.indexOf(textValue) < 0) {
      continue;
    }
    if (textValue === current || seen[textValue]) {
      continue;
    }
    if (rectArea(bounds) <= 0) {
      continue;
    }
    if (bounds.top < 660 || bounds.top > 1860) {
      continue;
    }
    if (rectWidth(bounds) < 180 || rectWidth(bounds) > 360) {
      continue;
    }
    if (rectHeight(bounds) < 100 || rectHeight(bounds) > 160) {
      continue;
    }
    categories.push({
      name: textValue,
      bounds: bounds
    });
    seen[textValue] = true;
  }
  return categories;
};

HaoceReader.prototype.chooseRandomCollectionCategory = function () {
  var currentCategory = this.currentCollectionCategory();
  if (!this.openCollectionCategoryPicker()) {
    log("collection category picker was not found, keeping current category");
    return false;
  }

  var categories = this.listCollectionCategories();
  var allowed = [];
  for (var i = 0; i < categories.length; i += 1) {
    if (this.config.collection.excludedCategories.indexOf(categories[i].name) >= 0) {
      continue;
    }
    allowed.push(categories[i]);
  }

  if (!allowed.length) {
    if (currentCategory && this.config.collection.excludedCategories.indexOf(currentCategory) >= 0) {
      log("no allowed collection category was found after excluding " + "\u91cd\u70b9\u56fe\u4e66");
    } else {
      log("no alternative collection category was found, keeping current category");
    }
    this.closeCollectionCategoryPicker();
    return false;
  }

  var chosen = allowed[randomInt(0, allowed.length - 1)];
  var point = rectCenter(chosen.bounds);
  log("switching collection category from " + (currentCategory || "<unknown>") + " to " + chosen.name);
  singleTap(point[0], point[1]);
  sleepMs(Math.max(this.config.navigation.prepareWaitMs, 2000));
  var updatedCategory = this.currentCollectionCategory();
  if (updatedCategory) {
    log("current collection category: " + updatedCategory);
  }
  return true;
};

HaoceReader.prototype.scrollCollectionPage = function () {
  log("scrolling collection page to look for more books");
  var start = this.ratioToAbs([0.5, 0.82]);
  var end = this.ratioToAbs([0.5, 0.30]);
  swipe(start[0], start[1], end[0], end[1], 650);
  sleepMs(this.config.pageTurn.settleMs);
};

HaoceReader.prototype.randomizeCollectionStart = function () {
  var scrolls = randomInt(this.config.collection.randomStartScrolls[0], this.config.collection.randomStartScrolls[1]);
  if (scrolls <= 0) {
    return;
  }
  log("randomizing collection start page: scrolling " + scrolls + " screen(s) before selecting");
  for (var i = 0; i < scrolls; i += 1) {
    this.scrollCollectionPage();
  }
};

HaoceReader.prototype.listCollectionBooks = function () {
  if (this.pageName() !== "collection") {
    return [];
  }

  var items = [];
  var seen = {};
  var nodes = this.allNodes();
  for (var i = 0; i < nodes.length; i += 1) {
    var node = nodes[i];
    var bounds = this.safeBounds(node);
    if (!bounds) {
      continue;
    }
    var children = this.directChildren(node);
    if (!children.length) {
      continue;
    }

    var progressText = null;
    var title = "";
    var imageKey = null;
    for (var j = 0; j < children.length; j += 1) {
      var child = children[j];
      if (!child.text) {
        continue;
      }
      if (this.isProgressText(child.text)) {
        progressText = child.text;
        continue;
      }
      if (child.className.indexOf("Image") >= 0 && !imageKey) {
        imageKey = child.text;
        continue;
      }
      var candidateTitle = normalizeTitle(child.text);
      if (!title && candidateTitle) {
        title = candidateTitle;
      }
    }

    if (!progressText || (!title && !imageKey)) {
      continue;
    }
    if (rectArea(bounds) < 60000) {
      continue;
    }

    var signature = rectSignature(bounds);
    if (seen[signature]) {
      continue;
    }
    seen[signature] = true;
    items.push({
      title: title,
      key: imageKey,
      progressText: progressText,
      progressPercent: parsePercent(progressText),
      bounds: bounds
    });
  }

  items.sort(function (a, b) {
    if (a.bounds.top !== b.bounds.top) {
      return a.bounds.top - b.bounds.top;
    }
    return a.bounds.left - b.bounds.left;
  });
  return items;
};

HaoceReader.prototype.sameBook = function (leftBook, rightBook) {
  if (!leftBook || !rightBook) {
    return false;
  }
  if (leftBook.key && rightBook.key && leftBook.key === rightBook.key) {
    return true;
  }
  var leftTitle = normalizeTitle(leftBook.title);
  var rightTitle = normalizeTitle(rightBook.title);
  return !!leftTitle && !!rightTitle && leftTitle === rightTitle;
};

HaoceReader.prototype.shouldSkipCollectionBook = function (book) {
  if (this.isCompleted(book)) {
    return true;
  }
  if (typeof book.progressPercent === "number" && book.progressPercent >= 99.9) {
    return true;
  }
  if (this.selectionBlacklistContains(book)) {
    return true;
  }
  if (this.currentBook && this.sameBook(this.currentBook, book)) {
    return true;
  }
  return false;
};

HaoceReader.prototype.findNextCollectionBook = function () {
  var seenSignatures = {};
  for (var attempt = 0; attempt <= 12; attempt += 1) {
    var books = this.listCollectionBooks();
    var signatureParts = [];
    for (var i = 0; i < books.length; i += 1) {
      signatureParts.push(books[i].key || (normalizeTitle(books[i].title) || "untitled"));
    }
    var signature = signatureParts.join("|");
    if (seenSignatures[signature]) {
      break;
    }
    seenSignatures[signature] = true;

    var candidates = [];
    for (var j = 0; j < books.length; j += 1) {
      if (!this.shouldSkipCollectionBook(books[j])) {
        candidates.push(books[j]);
      }
    }

    if (candidates.length) {
      var chosen = candidates[randomInt(0, candidates.length - 1)];
      log("randomly selected one visible collection book from " + candidates.length + " candidate(s): " + this.describeBook(chosen));
      return chosen;
    }

    if (attempt === 12) {
      break;
    }
    log("no selectable visible collection book yet, moving to another collection screen");
    this.scrollCollectionPage();
  }
  return null;
};

HaoceReader.prototype.tapContinueIfPresent = function () {
  var node = textContains(TEXT_CONTINUE).findOne(600);
  if (!node) {
    return false;
  }
  var bounds = this.safeBounds(node);
  if (!bounds) {
    return false;
  }
  if (!this.currentBook) {
    this.currentBook = this.resolveOpenedBook({
      title: null,
      key: null,
      progressText: null,
      progressPercent: null,
      bounds: bounds
    });
  }
  var point = rectCenter(bounds);
  log("found '" + TEXT_CONTINUE + "', tapping " + point[0] + "," + point[1]);
  singleTap(point[0], point[1]);
  sleepMs(this.config.navigation.prepareWaitMs);
  return true;
};

HaoceReader.prototype.tapDetailUpdateIfPresent = function () {
  for (var attempt = 0; attempt < 4; attempt += 1) {
    var exactCandidates = [];
    var rowFallback = null;
    var nodes = this.allNodes();
    for (var i = 0; i < nodes.length; i += 1) {
      var textValue = this.safeText(nodes[i]);
      var bounds = this.safeBounds(nodes[i]);
      if (!textValue || !bounds || rectArea(bounds) <= 0) {
        continue;
      }
      if (textValue === TEXT_UPDATE) {
        exactCandidates.push(bounds);
        continue;
      }
      if (textValue.indexOf(TEXT_UPDATE) >= 0 && bounds.top >= 760 && bounds.top <= 1100) {
        rowFallback = bounds;
      }
    }

    if (exactCandidates.length) {
      exactCandidates.sort(function (a, b) {
        var areaDiff = rectArea(a) - rectArea(b);
        if (areaDiff !== 0) {
          return areaDiff;
        }
        return b.right - a.right;
      });
      var exactPoint = rectCenter(exactCandidates[0]);
      log("found exact '" + TEXT_UPDATE + "', tapping " + exactPoint[0] + "," + exactPoint[1]);
      singleTap(exactPoint[0], exactPoint[1]);
      sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1200));
      return true;
    }

    if (rowFallback) {
      var fallbackX = Math.max(rowFallback.left, rowFallback.right - Math.max(72, Math.floor(rectWidth(rowFallback) * 0.12)));
      var fallbackY = Math.floor((rowFallback.top + rowFallback.bottom) / 2);
      log("found update row fallback, tapping " + fallbackX + "," + fallbackY);
      singleTap(fallbackX, fallbackY);
      sleepMs(Math.max(this.config.navigation.prepareWaitMs, 1200));
      return true;
    }

    sleepMs(350);
  }
  return false;
};

HaoceReader.prototype.tapDetailUpdateRepeatedly = function (rounds, contextLabel) {
  var totalRounds = Math.max(0, rounds || 0);
  for (var roundIndex = 0; roundIndex < totalRounds; roundIndex += 1) {
    log(
      contextLabel + ": checking '" + TEXT_UPDATE + "' " +
      (roundIndex + 1) + "/" + totalRounds
    );
    if (!this.tapDetailUpdateIfPresent()) {
      break;
    }
  }
};

HaoceReader.prototype.tapStartIfPresent = function () {
  var node = textContains(TEXT_START).findOne(600);
  if (!node) {
    return false;
  }
  var bounds = this.safeBounds(node);
  if (!bounds) {
    return false;
  }
  if (!this.currentBook) {
    this.currentBook = this.resolveOpenedBook({
      title: null,
      key: null,
      progressText: null,
      progressPercent: null,
      bounds: bounds
    });
  }
  var point = rectCenter(bounds);
  log("found '" + TEXT_START + "', tapping " + point[0] + "," + point[1]);
  singleTap(point[0], point[1]);
  sleepMs(this.config.navigation.prepareWaitMs);
  return true;
};

HaoceReader.prototype.openRecentBook = function (book) {
  var point = rectCenter(book.bounds);
  log("opening recent book: " + this.describeBook(book) + " at " + point[0] + "," + point[1]);
  singleTap(point[0], point[1]);
  sleepMs(this.config.navigation.prepareWaitMs);
  this.tapDetailUpdateRepeatedly(HOME_ENTRY_UPDATE_ROUNDS, "home recent entry sync");
  this.currentBook = this.resolveOpenedBook(book);
  if (this.tapContinueIfPresent()) {
    return "open_recent_then_continue";
  }
  if (this.tapStartIfPresent()) {
    return "open_recent_then_start";
  }
  return "open_recent";
};

HaoceReader.prototype.refreshRecentHome = function () {
  log("refreshing home page to sync reading progress");
  var start = this.ratioToAbs([0.5, 0.34]);
  var end = this.ratioToAbs([0.5, 0.78]);
  swipe(start[0], start[1], end[0], end[1], 650);
  sleepMs(Math.max(this.config.navigation.prepareWaitMs, 2500));
};

HaoceReader.prototype.refreshCurrentBookPage = function () {
  log("refreshing current page to sync reading progress");
  var start = this.ratioToAbs([0.5, 0.34]);
  var end = this.ratioToAbs([0.5, 0.78]);
  swipe(start[0], start[1], end[0], end[1], 650);
  sleepMs(Math.max(this.config.navigation.prepareWaitMs, 2500));
};

HaoceReader.prototype.looksLikeReturnedBookEntryPage = function () {
  var pageName = this.pageName();
  if (pageName === "home" || pageName === "report") {
    return false;
  }
  if (!text(TEXT_START).exists() && !textContains(TEXT_START).exists()) {
    return false;
  }

  var hintCount = 0;
  for (var i = 0; i < DETAIL_PAGE_HINT_TEXTS.length; i += 1) {
    if (text(DETAIL_PAGE_HINT_TEXTS[i]).exists()) {
      hintCount += 1;
      if (hintCount >= 2) {
        return true;
      }
    }
  }

  return this.detailTitle() !== null || this.detailProgress() !== null;
};

HaoceReader.prototype.syncPageAfterBackOnce = function () {
  if (this.looksLikeReturnedBookEntryPage()) {
    log(
      "returned to the collection detail page after reading, refreshing it " +
      RETURNED_DETAIL_SYNC_ROUNDS + " time(s) before leaving"
    );
    for (var roundIndex = 0; roundIndex < RETURNED_DETAIL_SYNC_ROUNDS; roundIndex += 1) {
      log(
        "collection detail refresh " +
        (roundIndex + 1) + "/" + RETURNED_DETAIL_SYNC_ROUNDS
      );
      this.refreshCurrentBookPage();
    }
    return true;
  }

  var didSync = false;
  if (this.tapDetailUpdateIfPresent()) {
    didSync = true;
  }
  return didSync;
};

HaoceReader.prototype.openCollectionBook = function (book) {
  var point = rectCenter(book.bounds);
  log("opening collection book: " + this.describeBook(book) + " at " + point[0] + "," + point[1]);
  singleTap(point[0], point[1]);
  sleepMs(this.config.navigation.prepareWaitMs);

  if (this.pageName() === "collection") {
    var stillCollectionList = !this.looksLikeReturnedBookEntryPage() && !this.findClickableTextNode(TEXT_CONTINUE);
    if (stillCollectionList) {
      log("collection card tap did not leave the collection page");
      return "open_collection_miss";
    }
  }

  this.tapDetailUpdateIfPresent();
  var selectedBook = this.resolveOpenedBook(book);
  if (this.selectionBlacklistContains(selectedBook)) {
    this.rememberSelectedForCollection(selectedBook);
    log("selected collection book is already in selection blacklist, going back");
    back();
    sleepMs(this.config.navigation.prepareWaitMs);
    return "open_collection_blacklisted";
  }

  this.currentBook = selectedBook;
  this.rememberSelectedForCollection(selectedBook);
  if (this.tapContinueIfPresent()) {
    return "open_collection_then_continue";
  }
  if (this.tapStartIfPresent()) {
    return "open_collection_then_start";
  }
  return "open_collection";
};

HaoceReader.prototype.collectionSlotPoints = function () {
  var points = [];
  for (var i = 0; i < this.config.collection.slotPoints.length; i += 1) {
    points.push(this.ratioToAbs(this.config.collection.slotPoints[i]));
  }
  return points;
};

HaoceReader.prototype.openNextCollectionBookBySlots = function () {
  var triedSlots = {};

  for (var pageIndex = 0; pageIndex < this.config.collection.slotScanPages; pageIndex += 1) {
    var slotCandidates = [];
    var points = this.collectionSlotPoints();
    for (var i = 0; i < points.length; i += 1) {
      slotCandidates.push({
        index: i + 1,
        point: points[i]
      });
    }
    shuffleArray(slotCandidates);

    for (var j = 0; j < slotCandidates.length; j += 1) {
      var slot = slotCandidates[j];
      var slotKey = pageIndex + ":" + slot.point[0] + ":" + slot.point[1];
      if (triedSlots[slotKey]) {
        continue;
      }
      triedSlots[slotKey] = true;

      log("trying collection slot page=" + (pageIndex + 1) + " slot=" + slot.index + " at " + slot.point[0] + "," + slot.point[1]);
      singleTap(slot.point[0], slot.point[1]);
      sleepMs(this.config.navigation.prepareWaitMs + 1000);

      var pageName = this.pageName();
      var reportProgress = this.reportProgress();
      var detailProgress = this.detailProgress();
      var continueNode = this.findClickableTextNode(TEXT_CONTINUE);
      var startNode = this.findClickableTextNode(TEXT_START);
      var openedBook = pageName === "report" || pageName === "detail" || !!continueNode || !!startNode || reportProgress !== null || detailProgress !== null;
      if (!openedBook) {
        continue;
      }

      this.tapDetailUpdateIfPresent();
      pageName = this.pageName();
      reportProgress = this.reportProgress();
      detailProgress = this.detailProgress();
      continueNode = this.findClickableTextNode(TEXT_CONTINUE);
      startNode = this.findClickableTextNode(TEXT_START);

      var title = this.reportTitle() || this.detailTitle() || ("collection-slot-" + (pageIndex + 1) + "-" + slot.index);
      var progress = reportProgress !== null ? reportProgress : detailProgress;
      var selectedBook = {
        title: title,
        key: null,
        progressText: progressTextOf(progress),
        progressPercent: progress,
        bounds: {
          left: slot.point[0] - 1,
          top: slot.point[1] - 1,
          right: slot.point[0] + 1,
          bottom: slot.point[1] + 1
        }
      };
      log("collection candidate opened: " + title + ", progress=" + selectedBook.progressText);

      if (this.currentBook && this.sameBook(this.currentBook, selectedBook)) {
        log("candidate book matches the current book, going back to try another one");
        back();
        sleepMs(this.config.navigation.prepareWaitMs);
        continue;
      }
      if (this.selectionBlacklistContains(selectedBook)) {
        this.rememberSelectedForCollection(selectedBook);
        log("candidate book is already in selection blacklist, going back");
        back();
        sleepMs(this.config.navigation.prepareWaitMs);
        continue;
      }
      if (progress !== null && progress >= 99.9) {
        log("candidate book is already complete, going back to collection page");
        back();
        sleepMs(this.config.navigation.prepareWaitMs);
        continue;
      }

      this.currentBook = selectedBook;
      this.rememberSelectedForCollection(selectedBook);
      if (this.tapContinueIfPresent()) {
        return "open_collection_then_continue";
      }
      if (this.tapStartIfPresent()) {
        return "open_collection_then_start";
      }
      return "open_collection";
    }

    if (pageIndex === this.config.collection.slotScanPages - 1) {
      break;
    }
    this.scrollCollectionPage();
  }

  return "all_done";
};

HaoceReader.prototype.pickNextBookFromCollectionRoot = function () {
  this.chooseRandomCollectionCategory();
  this.randomizeCollectionStart();

  for (var i = 0; i < 4; i += 1) {
    var nextBook = this.findNextCollectionBook();
    if (!nextBook) {
      break;
    }

    var action = this.openCollectionBook(nextBook);
    if (action === "open_collection_blacklisted") {
      continue;
    }
    if (action === "open_collection_miss") {
      log("parsed collection card did not open, falling back to visible slot scanning");
      break;
    }

    log("switched to next book: " + this.describeBook(nextBook) + ", action=" + action);
    return "opened_next";
  }

  log("collection page UI did not expose book cards, falling back to visible slot scanning");
  var fallbackAction = this.openNextCollectionBookBySlots();
  if (fallbackAction === "open_collection" || fallbackAction === "open_collection_then_continue" || fallbackAction === "open_collection_then_start") {
    log("switched to next book by slot fallback, action=" + fallbackAction);
    return "opened_next";
  }

  this.currentBook = null;
  log("no unfinished book found in the collection page, stopping");
  return "all_done";
};

HaoceReader.prototype.openNextBookFromCollection = function () {
  if (this.pageName() !== "home") {
    if (!this.returnToRecentHome()) {
      log("failed to return to recent reading page before opening the collection");
      return "stop";
    }
  }
  if (!this.openHomeCollectionPage()) {
    log("home collection entry was not found, cannot choose the next book");
    return "stop";
  }
  return this.pickNextBookFromCollectionRoot();
};

HaoceReader.prototype.prepareReadingPage = function () {
  var pageName = this.pageName();

  if (pageName === "collection") {
    log("already on collection page during prepare, choosing a book from current collection");
    return this.pickNextBookFromCollectionRoot();
  }

  if (pageName === "report" || textContains(TEXT_CONTINUE).exists()) {
    this.tapDetailUpdateRepeatedly(HOME_ENTRY_UPDATE_ROUNDS, "home entry sync");
    pageName = this.pageName();
  } else {
    this.tapDetailUpdateIfPresent();
    pageName = this.pageName();
  }
  if (pageName === "report" || pageName === "detail") {
    this.currentBook = this.resolveOpenedBook(this.currentBook || {
      title: null,
      key: null,
      progressText: null,
      progressPercent: null,
      bounds: null
    });
  }

  if (this.tapContinueIfPresent()) {
    return "continue";
  }
  if (this.tapStartIfPresent()) {
    return "start";
  }

  var items = this.listRecentBooks();
  if (items.length) {
    var firstRecent = items[0];
    if ((typeof firstRecent.progressPercent === "number" && firstRecent.progressPercent >= 99.9) || this.isCompleted(firstRecent)) {
      this.markCompleted(firstRecent);
      if (typeof firstRecent.progressPercent === "number" && firstRecent.progressPercent >= 99.9) {
        log("first recent book is already complete, opening collection page to choose a new book");
      } else {
        log("first recent book has already been verified as done for this run, opening collection page to choose a new book");
      }
      var result = this.openNextBookFromCollection();
      if (result === "opened_next") {
        return "first_recent_complete_then_opened_next";
      }
      return result;
    }
  }

  if (this.config.navigation.openRecentIndex > 0 && items.length >= this.config.navigation.openRecentIndex) {
    return this.openRecentBook(items[this.config.navigation.openRecentIndex - 1]);
  }
  return "noop";
};

HaoceReader.prototype.returnToRecentHome = function () {
  var backSteps = 0;
  var syncedSinceLastBack = false;

  while (backSteps <= this.config.navigation.maxBackStepsHome) {
    if (this.pageName() === "home") {
      var books = this.listRecentBooks();
      if (books.length) {
        log("recent reading page ready with " + books.length + " visible books");
        return true;
      }
    }

    if (!syncedSinceLastBack && this.syncPageAfterBackOnce()) {
      syncedSinceLastBack = true;
      if (this.pageName() === "home") {
        var syncedBooks = this.listRecentBooks();
        if (syncedBooks.length) {
          log("recent reading page ready with " + syncedBooks.length + " visible books");
          return true;
        }
      }
      continue;
    }

    if (backSteps === this.config.navigation.maxBackStepsHome) {
      break;
    }
    log("recent reading not visible yet, pressing back");
    back();
    sleepMs(this.config.navigation.prepareWaitMs);
    backSteps += 1;
    syncedSinceLastBack = false;
  }
  return false;
};

HaoceReader.prototype.findCurrentBookOnHome = function () {
  if (!this.currentBook) {
    return null;
  }
  if (this.currentBook.key) {
    var found = this.findRecentBookByKey(this.currentBook.key);
    if (found) {
      return found;
    }
  }
  var books = this.listRecentBooks();
  if (!books.length) {
    return null;
  }
  return books[0];
};

HaoceReader.prototype.waitForHomeProgressRefresh = function () {
  if (!this.returnToRecentHome()) {
    return null;
  }

  this.refreshRecentHome();
  var current = this.findCurrentBookOnHome();
  for (var attempt = 0; attempt < 5; attempt += 1) {
    if (current && typeof current.progressPercent === "number" && current.progressPercent >= 99.9) {
      return current;
    }
    if (attempt === 4) {
      break;
    }
    log("current book is not shown as completed yet, waiting for home progress refresh");
    sleepMs(Math.max(this.config.navigation.prepareWaitMs, 2500));
    this.refreshRecentHome();
    current = this.findCurrentBookOnHome();
  }
  return current;
};

HaoceReader.prototype.handleIncompleteCompletionVerification = function (currentOnHome) {
  var verifyKey = this.completionVerificationKey(currentOnHome);
  if (!verifyKey) {
    log("current book progress is still " + currentOnHome.progressText + ", but no stable verification key was found");
    return "stop";
  }

  var verificationCount = (this.incompleteCompletionVerifications[verifyKey] || 0) + 1;
  this.incompleteCompletionVerifications[verifyKey] = verificationCount;
  var maxAttempts = Math.max(1, this.config.runtime.completionVerifyAttempts);

  if (verificationCount < maxAttempts) {
    log("suspected end of book reached, but current book progress is still " + currentOnHome.progressText + "; verification " + verificationCount + "/" + maxAttempts + ", reopening the same book to confirm before skipping");
    var reopenAction = this.openRecentBook(currentOnHome);
    log("reopened current book after incomplete completion verification, action=" + reopenAction);
    return "reopen_current";
  }

  log("current book still has progress " + currentOnHome.progressText + " after " + verificationCount + "/" + maxAttempts + " end-of-book verifications; marking it as done for this run and moving on");
  this.markCompleted(currentOnHome);
  return this.openNextBookFromCollection();
};

HaoceReader.prototype.switchToNextBook = function () {
  if (!this.currentBook) {
    log("current book is unknown, cannot safely switch to the next book");
    return "stop";
  }

  var currentOnHome = this.waitForHomeProgressRefresh();
  if (!currentOnHome) {
    log("failed to return to recent reading page");
    return "stop";
  }
  if (!(typeof currentOnHome.progressPercent === "number" && currentOnHome.progressPercent >= 99.9)) {
    return this.handleIncompleteCompletionVerification(currentOnHome);
  }

  this.markCompleted(currentOnHome);
  log("book completed: " + this.describeBook(currentOnHome));
  return this.openNextBookFromCollection();
};

HaoceReader.prototype.prepare = function (skipPrepare) {
  var result = "noop";
  if (this.config.navigation.launchApp) {
    this.launchApp();
  }
  if (!skipPrepare) {
    result = this.prepareReadingPage();
    log("prepare result: " + result);
  }
  return result;
};

HaoceReader.prototype.run = function (skipPrepare, maxPageTurnsOverride) {
  var prepareResult = this.prepare(!!skipPrepare);
  if (prepareResult === "all_done") {
    log("no unread book found during prepare, stopping");
    return 0;
  }
  if (prepareResult === "stop") {
    log("prepare step did not reach a safe reading page, stopping");
    return 2;
  }

  var maxPageTurns = maxPageTurnsOverride !== undefined && maxPageTurnsOverride !== null ?
    maxPageTurnsOverride : this.config.runtime.maxPageTurns;
  var startTime = new Date().getTime();
  var pageTurns = 0;
  var stuckCount = 0;
  var iteration = 0;

  log("reader loop started");
  while (true) {
    iteration += 1;
    var pauseAfterPageTurn = false;
    var pauseAfterBookSwitch = false;
    var before = this.capture();
    this.performScroll();
    sleepMs(this.config.scroll.settleMs);
    var after = this.capture();

    var metrics = this.diffImages(before, after);
    this.recycleImage(before);
    this.recycleImage(after);

    log("scroll #" + iteration + ": mean_diff=" + metrics.meanDiff.toFixed(3) + ", changed_ratio=" + metrics.changedRatio.toFixed(4));

    if (this.looksStuck(metrics)) {
      stuckCount += 1;
      log("bottom-like state " + stuckCount + "/" + this.config.analysis.bottomConfirmations);
      if (stuckCount < this.config.analysis.bottomConfirmations) {
        sleepMs(this.config.runtime.loopSleepMs);
        continue;
      }

      var beforeTurn = this.capture();
      this.performPageTurn();
      sleepMs(this.config.pageTurn.settleMs);
      var afterTurn = this.capture();
      var turnMetrics = this.diffImages(beforeTurn, afterTurn);
      this.recycleImage(beforeTurn);
      this.recycleImage(afterTurn);

      log("page-turn check: mean_diff=" + turnMetrics.meanDiff.toFixed(3) + ", changed_ratio=" + turnMetrics.changedRatio.toFixed(4));
      if (this.pageTurnConfirmed(turnMetrics)) {
        pageTurns += 1;
        stuckCount = 0;
        pauseAfterPageTurn = true;
        log("moved to next section, total page turns: " + pageTurns);
      } else {
        var switchResult = this.switchToNextBook();
        if (switchResult === "opened_next" || switchResult === "reopen_current") {
          stuckCount = 0;
          pauseAfterBookSwitch = true;
        } else if (switchResult === "all_done") {
          return 0;
        } else {
          log("page turn not confirmed, stopping to avoid misfire");
          return 2;
        }
      }
    } else {
      stuckCount = 0;
      this.sleepScrollPause("scroll pause");
    }

    if (maxPageTurns > 0 && pageTurns >= maxPageTurns) {
      log("reached max_page_turns=" + maxPageTurns + ", stopping");
      return 0;
    }

    if (this.config.runtime.maxMinutes > 0) {
      var elapsedMinutes = (new Date().getTime() - startTime) / 60000;
      if (elapsedMinutes >= this.config.runtime.maxMinutes) {
        log("reached max_minutes=" + this.config.runtime.maxMinutes + ", stopping");
        return 0;
      }
    }

    if (pauseAfterPageTurn) {
      this.sleepScrollPause("page-turn pause");
    }
    if (pauseAfterBookSwitch) {
      this.sleepScrollPause("book-switch pause");
    }

    sleepMs(this.config.runtime.loopSleepMs);
  }
};

function main() {
  auto.waitFor();
  if (!requestScreenCapture()) {
    throw new Error("requestScreenCapture failed");
  }

  if (!files.exists(DEFAULT_CONFIG_PATH)) {
    log("config.json not found, using built-in defaults");
  }
  var rawConfig = readJson(DEFAULT_CONFIG_PATH, {});
  var config = buildConfig(rawConfig);
  var reader = new HaoceReader(config);
  var exitCode = reader.run(false, null);
  log("[DONE] JS script finished with code " + exitCode + ".");
}

try {
  main();
} catch (error) {
  log("[ERROR] " + error);
  throw error;
}
