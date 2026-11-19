# Phase 1 — Local chart-region capture

This module adds a local, read-only preview. It does not modify the FastAPI app, market-data providers, Render settings, browser extension, or trading logic.

## Windows setup

From the repository root:

```cmd
.venv\Scripts\activate
python -m pip install -r visual_requirements.txt
python -m visual_engine.screen_capture --select
```

Open Quotex Demo in maximized Chrome before starting. On the monitor screenshot, drag a rectangle around only the candle chart and press Enter. The preview then displays only that rectangle.

Keys: **Q/Esc** stop, **R** reselect and save, **P** pause/resume. The selected rectangle is stored locally in `visual_engine/region_config.json`; it is ignored by Git. Default preview rate is 5 FPS and can be changed up to 15 FPS.

To reuse the saved region:

```cmd
python -m visual_engine.screen_capture
```

To force reselection later:

```cmd
python -m visual_engine.screen_capture --select
```

## Safety and limitations

- Run this capture tool on the Windows computer displaying Quotex. Render cannot capture a user's local Chrome screen.
- Use the Demo account for development. The tool captures pixels only; it does not read cookies, browser profiles, passwords, SSIDs, WebSocket frames, or account data.
- It does not click controls, place trades, or produce signals.
- The chart rectangle should exclude the Buy/Sell panel and browser chrome.
- This phase proves only that a stable chart image can be captured. It does not yet reconstruct OHLC prices or validate a strategy.
- If Windows display scaling or browser zoom changes, reselect the region.

## Tests

```cmd
python -m pytest tests\test_visual_config.py -q
```
