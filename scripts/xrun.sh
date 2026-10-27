#!/bin/bash
# Executa um comando dentro de um Xephyr isolado (:9, 1440x900). uso: scripts/xrun.sh comando args...
pkill -x Xephyr 2>/dev/null; sleep .6
Xephyr :9 -screen 1440x900 -nolisten tcp >/dev/null 2>&1 &
XP=$!
for i in $(seq 1 30); do DISPLAY=:9 xdpyinfo >/dev/null 2>&1 && break; sleep .2; done
DISPLAY=:9 "$@" 2>&1 | grep -v "dbind-WARNING"
rc=${PIPESTATUS[0]}
kill $XP 2>/dev/null; wait $XP 2>/dev/null
exit $rc
