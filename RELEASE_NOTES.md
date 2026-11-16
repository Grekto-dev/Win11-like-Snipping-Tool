# Win11-like Snipping Tool for Linux 1.1.2

Clipboard fix: captures paste into browsers and PhotoCraft again.

## Fixed

- **Pasting into websites works again.** Version 1.1.1 added an empty file list to the copied capture to satisfy PhotoCraft. Browsers then gave websites that list as text instead of the image, so ChatGPT, Gemini and Google did not accept the paste. The empty list is gone.
- **PhotoCraft still pastes, when the capture is saved.** PhotoCraft asks for a file list before the image. The copy now offers the image together with the saved capture file (the PNG in the captures folder), so both browsers and PhotoCraft receive a real image file.

## Behaviour to know

- With **automatic saving on** (the default), a copied capture also carries the saved file. A website may show the pasted image with the file name "Captura de tela ....png".
- With **automatic saving off**, or for copies made from the editor, only the image is copied. Websites work; PhotoCraft does not paste it (same as before 1.1.1).
- Flatpak browsers only read files inside folders they can access, such as the Pictures folder, where captures are saved by default. A custom captures folder outside those may not paste into a Flatpak browser.

## Verified

- Chrome (Flatpak), Firefox and PhotoCraft 0.20.2 pasted a 1920x1080 capture after the app had exited, using the Cinnamon clipboard manager in an isolated X11 session.
- Pasting into ChatGPT and Gemini was confirmed by the maintainer on a real desktop.
- Clipboard round-trip tests for the saved-file and image-only cases, and the full isolated suite.

## Install or update

```bash
sudo apt install ./captura_1.1.2_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.1.2_all.deb.sha256
```
