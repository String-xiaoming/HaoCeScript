# Haoce Auto Reader

这是一个基于 ADB 的好策自动阅读脚本。

它会做这些事：

- 启动 `app.haoce.com`
- 可选点开“最近阅读”的某一本
- 如果落在“继续阅读”页，会自动点“继续阅读”
- 在正文里自动上滑
- 用截图差分判断是否已经滑到底
- 到底后自动左右翻页进入下一节

## 先看这里：最常改的地方

项目里最重要的配置文件是 [config.json](/E:/haoce/config.json)。

### 1. 15 秒停留在哪改

看这个字段：

```json
"scroll": {
  "pause_ms": 15000
}
```

位置：`config.json -> scroll -> pause_ms`

说明：

- `15000` 表示 `15` 秒
- 单位是毫秒
- 这个停留会发生在：
  - 正常阅读时，每次上滑之后
  - 翻页成功后，开始新一节之前
- 这个停留不会发生在：
  - 已经判断到底，准备翻页时

常用改法：

- 改成 `10000` = 停 `10` 秒
- 改成 `20000` = 停 `20` 秒

### 2. 为什么跑到 30 次就停了

看这个字段：

```json
"runtime": {
  "max_page_turns": 30
}
```

位置：`config.json -> runtime -> max_page_turns`

说明：

- `30` 表示最多翻 `30` 次页后自动结束
- `0` 表示不限次数，一直运行

如果你想一直读下去，改成：

```json
"runtime": {
  "max_page_turns": 0
}
```

### 3. 上下滑太快 / 太慢在哪改

看这几个字段：

```json
"scroll": {
  "duration_ms": 520,
  "duration_jitter_ms": 180,
  "settle_ms": 1200
}
```

说明：

- `duration_ms`
  - 一次上滑本身持续多久
- `duration_jitter_ms`
  - 在基础时长上增加一点随机值，避免每次都完全一样
- `settle_ms`
  - 滑完后，先等页面稳定再截图判断的时间

如果你觉得滑动还是偏快，可以优先：

- 增大 `duration_ms`
- 保留 `pause_ms = 15000`

## 当前脚本的阅读节奏

现在默认逻辑是：

1. 上滑一次
2. 等页面稳定
3. 截图判断是不是到底
4. 如果还没到底，停 `15` 秒，再继续上滑
5. 如果已经到底，直接翻页
6. 翻页成功后，停 `15` 秒，再开始新一节的第一次上滑

## 文件说明

- [haoce_reader.py](/E:/haoce/haoce_reader.py)
  - 主程序，负责 ADB 操作、截图判断、到底检测、自动翻页
- [config.json](/E:/haoce/config.json)
  - 配置文件，几乎所有行为都在这里调
- [start.bat](/E:/haoce/start.bat)
  - 双击即可运行的启动脚本
- [requirements.txt](/E:/haoce/requirements.txt)
  - Python 依赖
- [使用.md](/E:/haoce/使用.md)
  - 额外中文说明

## 环境要求

- Windows
- 已安装 Python
- 已安装 ADB，并且 `adb` 已加入 `PATH`
- 手机已开启 USB 调试
- 电脑已经授权这台手机的 ADB 调试
- 手机里已安装好策，包名为 `app.haoce.com`

安装依赖：

```powershell
pip install -r requirements.txt
```

## 最简单的启动方式

直接双击：

- [start.bat](/E:/haoce/start.bat)

它会自动：

- 检查 `python` 是否可用
- 检查 `adb` 是否可用
- 安装依赖
- 检查设备连接状态
- 启动脚本

## 命令行用法

### 检查设备和页面状态

```powershell
python haoce_reader.py --config config.json doctor
```

### 保存当前截图

```powershell
python haoce_reader.py --config config.json capture current.png
```

### 导出当前页面 UI 结构

```powershell
python haoce_reader.py --config config.json dump-ui current.xml
```

### 正常启动自动阅读

```powershell
python haoce_reader.py --config config.json run
```

### 如果你已经手动进入正文页

```powershell
python haoce_reader.py --config config.json run --skip-prepare
```

### 无限翻页，不受 30 次上限限制

```powershell
python haoce_reader.py --config config.json run --max-page-turns 0
```

## 关键配置说明

### navigation

控制启动后要不要自动进入书籍页面。

常用字段：

- `launch_app`
  - 是否自动启动好策
- `open_recent_index`
  - 自动点开“最近阅读”的第几本
  - `1` 表示第一本
  - `2` 表示第二本
  - `0` 或 `null` 表示不自动点
- `auto_continue_from_report`
  - 如果当前在“继续阅读”页，是否自动点进去

### scroll

控制正文里的上滑动作。

常用字段：

- `start` / `end`
  - 上滑起点和终点，使用相对坐标
- `start_jitter` / `end_jitter`
  - 给起点和终点增加少量随机偏移
- `duration_ms`
  - 上滑持续时间
- `duration_jitter_ms`
  - 上滑持续时间的随机波动
- `settle_ms`
  - 上滑后等待页面稳定的时间
- `pause_ms`
  - 正常阅读停留时间，也是翻页成功后的停留时间

### page_turn

控制到底之后如何进入下一节。

常用字段：

- `action`
  - `"swipe"` 表示左右划
  - `"tap"` 表示点击翻页
- `start` / `end`
  - 左右划的起点和终点
- `start_jitter` / `end_jitter`
  - 左右划轨迹随机偏移
- `duration_ms`
  - 左右划持续时间
- `duration_jitter_ms`
  - 左右划持续时间随机波动
- `settle_ms`
  - 左右划后等待页面稳定

### analysis

控制“是否到底”和“翻页是否成功”的识别灵敏度。

一般先不用动，除非你发现：

- 明明没到底，却误判到底
- 已经到底了，却一直不翻页
- 翻页明明成功了，却没识别出来

### runtime

控制运行时限制。

常用字段：

- `max_page_turns`
  - 最大翻页次数
  - `0` 表示无限制
- `max_minutes`
  - 最长运行分钟数
  - `0` 表示无限制
- `debug_dir`
  - 翻页异常时保存截图的目录

## 常见问题

### 1. 我只想改 15 秒停留

直接改 [config.json](/E:/haoce/config.json) 里的：

```json
"pause_ms": 15000
```

### 2. 我不想 30 次就结束

直接改：

```json
"max_page_turns": 0
```

### 3. 脚本正常结束是什么意思

如果日志里出现：

```text
reached max_page_turns=30, stopping
```

说明：

- 不是报错
- 是因为达到你配置里的翻页上限，所以正常退出

如果 `start.bat` 里显示：

```text
[DONE] Script finished normally.
```

说明脚本退出码是 `0`，属于正常结束。

### 4. 如果翻页失败会怎样

如果脚本怀疑翻页没成功，会停止运行，避免误操作。

这时会把调试截图保存到：

- [debug](/E:/haoce/debug)

你可以把截图发出来继续调。

## 推荐的默认改法

如果你现在只是想稳定挂机，通常建议这样改：

```json
"scroll": {
  "pause_ms": 15000
},
"runtime": {
  "max_page_turns": 0
}
```

这样效果就是：

- 正常阅读时每次上滑后停 15 秒
- 到底直接翻页
- 翻页后再停 15 秒
- 不会因为翻了 30 次就自动停掉
