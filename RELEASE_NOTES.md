# Win11-like Snipping Tool for Linux 1.0.1

Bug-fix release.

## Fixed

- **Hand cursor**: in Settings the pointer turned into a hand over the whole page. It now changes only while the pointer is over a link (the "Change" link and the links in About) and returns to normal as soon as it leaves, or when you leave the page.
- **App name**: the application is now called **Snipping Tool** by default (menu entry, window title, notifications and keyboard shortcut names). The name follows the language selected in Settings and changes immediately: Ferramenta de Captura (Português), Herramienta de recorte, Outil Capture d’écran, Strumento di cattura, 截图工具, Snipping Tool (English, 日本語). Notification titles and the shortcut names created by the app use the same name.

## Verification

- New tests move the real pointer (XTEST) over and away from every link and check the cursor, and check the title bar, header, notifications and desktop entry in all seven languages. The cursor test fails on 1.0.0 and passes on 1.0.1.

## Install

```bash
sudo apt install ./captura_1.0.1_all.deb
```

Verify the download with `sha256sum -c captura_1.0.1_all.deb.sha256`.

This project is not affiliated with or endorsed by Microsoft. See `THIRD_PARTY_NOTICES.md` for the bundled Fluent UI System Icons (MIT) and Selawik font (SIL OFL 1.1). Translations were produced with the help of a language model and have not had human review.
