# Win11-like Snipping Tool for Linux 1.1.1

Clipboard fix for captures pasted into other apps.

## Fixed

- **Captures paste into PhotoCraft (X11).** PhotoCraft reads the clipboard as a file list first. On X11 the captured image was not readable that way and paste failed with *incorrect type received from clipboard*. Captures are now offered as PNG together with an empty `text/uri-list`, and both formats are handed to the clipboard manager when the capture is copied, so they stay available after the app closes.

## Verified

- Tested with PhotoCraft 0.20.2 (Flatpak) on X11: the captured image pastes into the canvas.
- Clipboard round-trip tests for the image and the empty file list; full isolated suite run.

Not tested: other applications beyond PhotoCraft. Earlier 1.1.0 changes are unchanged.

## Install or update

```bash
sudo apt install ./captura_1.1.1_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.1.1_all.deb.sha256
```
