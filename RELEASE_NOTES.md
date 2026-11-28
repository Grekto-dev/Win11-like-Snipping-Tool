# Win11-like Snipping Tool for Linux 1.2.1

## Fixed: rectangular captures at screen edges

Rectangular selections can now start or end at a screen edge or corner. On X11, a desktop edge window could cause mouse events to be delivered to the capture overlay itself rather than its drawing area. The overlay now handles those events without intercepting its own toolbar controls.

## Install or update

```bash
sudo apt install ./captura_1.2.1_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.2.1_all.deb.sha256
```
