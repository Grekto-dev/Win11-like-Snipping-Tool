# Win11-like Snipping Tool for Linux 1.1.3

The text extractor no longer depends on the saved capture mode.

## Changed

- **The text extractor always selects a rectangle.** Before, its button used whatever capture mode was saved (window, full screen, free-form), so a click could select a whole window or screen instead of the region you dragged. Now it always uses the rectangle, and it never reads or changes the saved mode.
- **The two are independent.** After using the text extractor and going back with the arrow, the capture bar still shows your saved mode, and picking a mode in the bar saves it as before. The same holds for the extractor opened from the capture bar button, the start-screen button and `captura --ocr`. It also ignores the photo/video choice without changing it.

## Verified

- Unit tests for every saved mode, real mouse drags and clicks (XTEST) through the bar button and back with the settings file re-read, and the real launcher (`captura --ocr`) in an isolated X11 session with the saved mode set to window, full screen and free-form.
- Full isolated suite: 327 tests passed on the final run. In two earlier runs a few real-click tests (and an intermittent recording test) failed once and passed when rerun alone.

Not changed: the color picker still follows the saved capture mode.

## Install or update

```bash
sudo apt install ./captura_1.1.3_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.1.3_all.deb.sha256
```
