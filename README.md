# Haoce Auto Reader

This project drives `app.haoce.com` through ADB and uses screenshot-difference
detection to decide whether the current chapter has reached the bottom.

## What it does

- Launches Haoce through ADB.
- Optionally opens the first item in `最近阅读`.
- If it lands on the stats/report page, it automatically taps `继续阅读`.
- Scrolls vertically inside the current chapter.
- Detects "cannot scroll further" from screenshot differences.
- When bottom is confirmed, swipes left to enter the next section/chapter.

The default config was tuned on a `1080x2400` device and validated against the
real behavior of `专利笔记`: vertical reading page, bottom reached when upward
swipes stop moving, then a left swipe enters the next section.

## Install

```powershell
pip install -r requirements.txt
```

ADB must already be available in `PATH`.

## Commands

Check connection, package, screen size, and whether the current UI contains
`继续阅读` or `最近阅读`:

```powershell
python haoce_reader.py --config config.json doctor
```

Save current screenshot:

```powershell
python haoce_reader.py --config config.json capture current.png
```

Save current UI XML:

```powershell
python haoce_reader.py --config config.json dump-ui current.xml
```

Run the reader loop:

```powershell
python haoce_reader.py --config config.json run
```

Run from the current page without trying to open `最近阅读` or tapping
`继续阅读`:

```powershell
python haoce_reader.py --config config.json run --skip-prepare
```

Limit the number of chapter/page turns:

```powershell
python haoce_reader.py --config config.json run --max-page-turns 20
```

## Config Notes

`config.json` contains the important knobs:

- `navigation.open_recent_index`
  - `1` means open the first item under `最近阅读`.
  - `null` or `0` means do not auto-open a recent book.
- `scroll`
  - Controls the vertical swipe used inside one chapter.
  - `pause_ms` is the dwell time after each normal upward swipe. Set to
    `15000` to stay 15 seconds before the next reading scroll.
  - When the bottom is being confirmed or a page turn is about to happen, the
    script does not wait for `pause_ms`.
  - After a page turn is confirmed, the script waits for `pause_ms` before the
    first upward swipe in the new section.
  - `start_jitter` / `end_jitter` and `duration_jitter_ms` add small random
    offsets so each swipe path is a bit different.
- `page_turn`
  - Default action is a left swipe for the next section.
  - `start_jitter` / `end_jitter` and `duration_jitter_ms` can randomize the
    horizontal page-turn swipe as well.
  - If a different book needs tapping instead of swiping, set
    `"action": "tap"` and fill `tap`.
- `analysis`
  - `stuck_*` thresholds decide whether the screen is effectively not moving.
  - `page_turn_*` thresholds decide whether the next section really loaded.
- `runtime.max_page_turns`
  - `0` means unlimited.

## If A Book Behaves Differently

Some Haoce books can use different reading layouts. When that happens:

1. Open the target book manually.
2. Use `capture` and `dump-ui` to inspect the page.
3. Adjust `scroll` and `page_turn` coordinates in `config.json`.
4. If the bottom detection is too sensitive or too loose, tune the values in
   `analysis`.

If a page turn cannot be confirmed, the script stops and saves screenshots into
`debug/` so you can inspect what happened.
