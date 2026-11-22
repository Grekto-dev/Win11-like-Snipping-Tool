# Win11-like Snipping Tool for Linux 1.2.0

## New: choose one monitor or all screens

- **Full screen** highlights the monitor under the pointer. Click to capture just that monitor, including its taskbar. On a single-monitor setup it still captures the entire screen.
- **All screens**, immediately after **Full screen** in the capture menu, keeps the previous whole-desktop behavior: one image containing every monitor in its desktop layout.
- The same choices set the region for screen recording. The text extractor still uses a rectangle independently of the saved capture mode.

## Install or update

```bash
sudo apt install ./captura_1.2.0_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.2.0_all.deb.sha256
```
