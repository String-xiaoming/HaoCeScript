# 好策自动阅读脚本使用说明

## 文件说明

- [start.bat](/E:/haoce/start.bat)
  - 一键启动脚本，直接双击即可。
- [haoce_reader.py](/E:/haoce/haoce_reader.py)
  - 主程序，负责 ADB 控制、截图识别、到底检测和自动翻页。
- [config.json](/E:/haoce/config.json)
  - 配置文件，改这里可以适配不同书籍或翻页方式。
- [requirements.txt](/E:/haoce/requirements.txt)
  - Python 依赖列表。

## 最简单的用法

1. 手机打开 USB 调试，并确保已经允许这台电脑的 ADB 调试。
2. 用数据线连上手机。
3. 确认手机里已经安装好策，包名是 `app.haoce.com`。
4. 双击 [start.bat](/E:/haoce/start.bat)。

脚本会自动做这几件事：

- 检查 `python` 和 `adb` 是否可用。
- 自动安装依赖。
- 检查手机是否连接成功、好策是否已安装。
- 自动启动好策。
- 如果当前在“阅读报告/章节完结情况”页，会自动点“继续阅读”。
- 进入正文后自动上滑。
- 识别滑到底部后自动左滑到下一节。

## 当前默认逻辑

这套默认配置已经按你当前设备实测通过：

- 设备分辨率：`1080x2400`
- App：`app.haoce.com`
- 正文页：竖向滚动
- 到底判断：连续两次上滑后画面几乎不变化
- 翻页方式：到底后左滑进入下一节

如果别的书也是这个模式，直接用就行。

## 常用命令

如果你想手动从命令行启动，可以在当前目录执行：

```powershell
python haoce_reader.py --config config.json run
```

如果你已经手动进入正文页，不想让脚本自动点“最近阅读”或“继续阅读”，可以执行：

```powershell
python haoce_reader.py --config config.json run --skip-prepare
```

检查设备状态：

```powershell
python haoce_reader.py --config config.json doctor
```

保存当前截图：

```powershell
python haoce_reader.py --config config.json capture current.png
```

导出当前界面结构：

```powershell
python haoce_reader.py --config config.json dump-ui current.xml
```

## 如何停止

- 如果是双击 [start.bat](/E:/haoce/start.bat) 运行的，窗口运行时按 `Ctrl + C`。
- 如果手机已经停在某一页，不会继续自动操作，直接关闭命令窗口也可以。

## 配置怎么改

主要改 [config.json](/E:/haoce/config.json)。

### 1. 切换要打开的最近阅读书籍

`navigation.open_recent_index`

- `1` 表示打开“最近阅读”的第 1 本书
- `2` 表示第 2 本
- `null` 或 `0` 表示不自动点最近阅读

### 2. 调整正文滚动动作

`scroll.start` 和 `scroll.end`

- 这是相对坐标，不是固定像素
- 比如 `[0.5, 0.8]` 表示屏幕中间偏下
- 如果上滑太短，可以把 `start` 调低一点、`end` 调高一点

### 3. 调整翻页动作

`page_turn`

- 现在默认是：
  - 到底后从右往左滑一下
- 如果某本书是点击翻页：
  - 把 `"action"` 改成 `"tap"`
  - 再填写 `tap`

例如：

```json
"page_turn": {
  "action": "tap",
  "start": null,
  "end": null,
  "tap": [0.85, 0.5],
  "duration_ms": 300,
  "settle_ms": 1500
}
```

### 4. 调整到底识别灵敏度

`analysis`

- `stuck_mean_diff_max`
  - 越大越容易判定“到底了”
- `stuck_changed_ratio_max`
  - 越大越容易判定“到底了”
- `bottom_confirmations`
  - 建议保留 `2`
  - 数字越大越稳，但翻页会更慢一点

## 常见问题

### 1. 双击 `start.bat` 没反应

先确认：

- 安装了 Python
- 安装了 ADB
- 两者都已经加入 `PATH`

命令行里能执行这两个命令才行：

```powershell
python --version
adb version
```

### 2. 提示没有设备

先执行：

```powershell
adb devices
```

如果设备显示 `unauthorized`：

- 看手机弹窗
- 点允许 USB 调试

### 3. 能滑动，但翻不到下一节

说明这本书的翻页方式可能不是“左滑下一节”。

这时你可以给我这些信息，我可以继续帮你适配：

- 正文页截图
- 滑到底部后的截图
- 你手动翻到下一节时的动作
  - 是左滑
  - 右滑
  - 点右侧
  - 点按钮
- 如果能提供一份 `dump-ui` 导出的 XML，会更快

### 4. 脚本误判到底，翻页太早

可以把 [config.json](/E:/haoce/config.json) 里这两个值调小一些：

```json
"stuck_mean_diff_max": 1.2,
"stuck_changed_ratio_max": 0.008
```

### 5. 脚本到了底部却一直不翻页

可以把这两个值调大一些：

```json
"stuck_mean_diff_max": 3.0,
"stuck_changed_ratio_max": 0.02
```

## 现在推荐的启动方式

平时直接双击 [start.bat](/E:/haoce/start.bat) 就够了。

如果后面你想继续扩展，我可以再给你补这些功能：

- 多本书不同配置自动切换
- OCR 识别章节标题
- 自动统计阅读时长
- 日志保存到文件
- 失败后自动重试
