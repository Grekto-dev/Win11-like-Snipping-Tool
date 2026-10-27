# Win11-like Snipping Tool for Linux 1.0.0

First stable release of an independent re-creation of the Windows 11 Snipping Tool for Linux (X11, tested on Linux Mint Cinnamon).

## Highlights

- **Capture**: rectangle, window, full-screen and freeform snips, with a 3/5/10 s delay; Print Screen integration.
- **Editor**: pen, highlighter, eraser, shapes, crop, ruler, emoji, undo/redo, zoom, light and dark themes.
- **Text actions (OCR)**: word/line selection, copy all, copy as table, redact email addresses and phone numbers, QR code reading. The text extractor also works inside the capture overlay.
- **Screen recording** with FFmpeg: region recording, pause/resume, microphone and system audio.
- **After capture** (Settings): show a notification and copy to the clipboard (default), show a notification only, only copy to the clipboard, or open the editor.
- **Languages**: English (default), Portuguese (Brazil), Chinese, Japanese, Spanish, French and Italian; switching applies immediately.
- Command-line modes: `--snip`, `--capture`, `--ocr`, `--color`, `--record`, `--settings`, `--fullscreen`, `--background`, `--version`.

## Install

```bash
sudo apt install ./captura_1.0.0_all.deb
```

Optional features: `tesseract-ocr` (+ language packs) for text extraction, `ffmpeg` for recording, `libzbar0` for QR codes (all installed as recommended packages).

Verify the download with `sha256sum -c captura_1.0.0_all.deb.sha256`.

## Notes

This project is not affiliated with or endorsed by Microsoft. See `THIRD_PARTY_NOTICES.md` for the bundled Fluent UI System Icons (MIT) and Selawik font (SIL OFL 1.1). Translations were produced with the help of a language model and have not had human review.
