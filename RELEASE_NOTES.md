# Win11-like Snipping Tool for Linux 1.1.0

"After capture" options and capture-overlay cursor fixes.

## Changed

- **After capture** (Settings) now has four separate options, with short names and a tooltip for each:
  - **Show notification** (new default): copies the capture to the clipboard and shows one system notification naming what was captured (screen, window or region). It no longer opens the editor.
  - **Open editor**: opens only the editor. Previously this was tied to the old notification behaviour.
  - **Copy only**: copies to the clipboard, with no notification.
  - **Save only**: saves to the captures folder, with no notification and no clipboard copy. If the save fails, the editor opens so the capture is not lost.
  Quick markup, when turned on in the capture bar, still opens the editor. An open app window or the *New* button no longer override the chosen option. The old "notify and copy" value migrates to *Show notification*. Recordings follow the same choice: the file is copied (*Show notification*, *Copy only*), opened in the default video player (*Open editor*, since there is no video editor) or left silently saved (*Save only*).
- **Capture overlay cursor**: the toolbars always show the normal arrow. The crosshair appears only outside the toolbars in rectangle and free-form modes (and the text extractor); window and full-screen modes keep the arrow. The cursor is recomputed from the real pointer position after a mode change.

## Fixed

- **Copy as table** never reached the clipboard: the call it used does not exist in this PyGObject version, and only mocked tests hid it. Clipboard writes now use a real selection owner and are covered by round-trip tests.

## Notes

- System notifications are placed by the desktop (Cinnamon shows them at the top right); the app cannot choose their position.
- Limitations in the README remain, including X11 only and the recording options without a video editor.

## Install or update

```bash
sudo apt install ./captura_1.1.0_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.1.0_all.deb.sha256
```
