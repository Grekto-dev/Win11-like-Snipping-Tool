#!/bin/bash
# Roda a bateria de desempenho/depuração num Xephyr isolado (:9, 1440x900). uso: scripts/perf.sh [grupo ...]
# Também conta os avisos Gtk/GLib (WARNING/CRITICAL) que o processo escreveu no stderr.
cd "$(dirname "$0")/.."
LOG=${TMPDIR:-/tmp}/perf_battery.log
pkill -x Xephyr 2>/dev/null; sleep .6
Xephyr :9 -screen 1440x900 -nolisten tcp >/dev/null 2>&1 &
XP=$!
for i in $(seq 1 30); do DISPLAY=:9 xdpyinfo >/dev/null 2>&1 && break; sleep .2; done
DISPLAY=:9 /usr/bin/python3 -X faulthandler scripts/perf_battery.py "$@" > "$LOG" 2>&1
rc=$?
kill $XP 2>/dev/null; wait $XP 2>/dev/null
grep -v "dbind-WARNING" "$LOG" | grep -v '^$' | grep -vE "(WARNING|CRITICAL|ERROR) \*\*"
if grep -q "fuzz" "$LOG"; then
  grep -q "already inside a container" "$LOG" && echo "autoteste: o aviso GTK proposital apareceu no stderr (coletor OK)" || { echo "FALHA: o aviso proposital não apareceu; coletor de avisos quebrado"; rc=1; }
fi
real=$(grep -E "(WARNING|CRITICAL|ERROR) \*\*" "$LOG" | grep -v "dbind-WARNING" | grep -v "already inside a container" | sed -E 's/\([^)]*\): //; s/[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+: //' | sort | uniq -c | sort -rn)
n=$(echo -n "$real" | grep -c . )
echo "avisos/críticos Gtk-GLib reais no stderr: $n tipos"
[ "$n" -gt 0 ] && echo "$real" | head -10 && rc=1
exit $rc
