#!/bin/bash
# Builds dist/captura_<version>_all.deb from the working tree (version read from captura/__init__.py).
# Layout: /usr/lib/captura (code, icons, fonts, translations), /usr/bin/captura (symlink), desktop entry, icon, docs.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(python3 -c 'import re; print(re.search(r"__version__ = \"([^\"]+)\"", open("captura/__init__.py").read()).group(1))')"
PKG="captura"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
DEB="dist/${PKG}_${VERSION}_all.deb"
LIB="$ROOT/usr/lib/$PKG"

install -d "$ROOT/DEBIAN" "$LIB/bin" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
  "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/doc/$PKG"

# application code and bundled data (no caches)
cp -r captura "$LIB/captura"
find "$LIB" -name '__pycache__' -type d -prune -exec rm -rf {} +
rm -f "$LIB/captura/data/i18n/_candidates.json"
install -m 0755 bin/captura "$LIB/bin/captura"
ln -s ../lib/$PKG/bin/captura "$ROOT/usr/bin/captura"
install -m 0644 captura/data/icons/captura.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/captura.svg"
install -m 0644 data/captura.desktop "$ROOT/usr/share/applications/captura.desktop"
install -m 0644 README.md THIRD_PARTY_NOTICES.md "$ROOT/usr/share/doc/$PKG/"
install -d "$ROOT/usr/share/doc/$PKG/third_party"
install -m 0644 third_party/LICENSE-*.txt "$ROOT/usr/share/doc/$PKG/third_party/"

cat > "$ROOT/usr/share/doc/$PKG/copyright" <<'CPR'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Win11-like Snipping Tool for Linux
Source: https://github.com/Grekto-dev/Win11-like-Snipping-Tool

Files: *
Copyright: 2026 Grekto-dev
License: GPL-3+

Files: usr/lib/captura/captura/data/icons/fluent/*
Copyright: 2020 Microsoft Corporation
License: MIT
 Fluent UI System Icons. The full notice is in
 /usr/share/doc/captura/third_party/LICENSE-fluentui-system-icons.txt

Files: usr/lib/captura/captura/data/fonts/*
Copyright: Microsoft Corporation
License: OFL-1.1
 Selawik. The full text is in
 /usr/share/doc/captura/third_party/LICENSE-selawik-OFL.txt

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it under
 the terms of the GNU General Public License as published by the Free Software
 Foundation, either version 3 of the License, or (at your option) any later
 version.
 .
 On Debian systems, the complete text of the GNU General Public License version
 3 can be found in "/usr/share/common-licenses/GPL-3".
CPR

SIZE="$(du -sk "$ROOT/usr" | cut -f1)"
cat > "$ROOT/DEBIAN/control" <<CTL
Package: $PKG
Version: $VERSION
Section: graphics
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0, gir1.2-pango-1.0, gir1.2-wnck-3.0, gir1.2-notify-0.7, librsvg2-common, xdg-utils
Recommends: tesseract-ocr, tesseract-ocr-eng, ffmpeg, libzbar0, pulseaudio-utils, xdg-user-dirs
Suggests: tesseract-ocr-por, tesseract-ocr-spa, tesseract-ocr-fra, tesseract-ocr-ita, tesseract-ocr-chi-sim, tesseract-ocr-jpn
Installed-Size: $SIZE
Maintainer: Grekto-dev <176182924+Grekto-dev@users.noreply.github.com>
Homepage: https://github.com/Grekto-dev/Win11-like-Snipping-Tool
Description: Screenshot, annotation, OCR and screen-recording tool inspired by Windows 11
 An independent re-creation of the Windows 11 Snipping Tool for Linux (X11):
 rectangle, window, full-screen and freeform captures with a delay, an editor
 with pen, highlighter, shapes, crop, rulers and emoji, a text extractor (OCR)
 with copy-as-table and QR code reading, screen recording with FFmpeg, light and
 dark themes. The interface is available in English, Portuguese (Brazil),
 Spanish, French, Italian, Chinese (Simplified) and Japanese.
CTL

cat > "$ROOT/DEBIAN/postinst" <<'PST'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || true
  command -v python3 >/dev/null 2>&1 && python3 -m compileall -q /usr/lib/captura/captura >/dev/null 2>&1 || true
fi
exit 0
PST
cat > "$ROOT/DEBIAN/postrm" <<'PRM'
#!/bin/sh
set -e
case "$1" in
  remove|purge)
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || true
    rm -rf /usr/lib/captura 2>/dev/null || true ;;
esac
exit 0
PRM
chmod 0755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"

find "$ROOT" -type d -exec chmod 0755 {} +
find "$ROOT/usr" -type f ! -perm -u+x -exec chmod 0644 {} +
mkdir -p dist
fakeroot dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$DEB" >/dev/null
sha256sum "$DEB" | sed "s#dist/##" > "$DEB.sha256"
echo "Built $DEB"
dpkg-deb --info "$DEB" | sed -n '1,14p'
