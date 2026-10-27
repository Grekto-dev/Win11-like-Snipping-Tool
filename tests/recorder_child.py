"""Processo filho de teste: inicia uma gravação e espera; é morto à força pelo teste (simula o app caindo)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from captura import services  # noqa: E402


def main(argv):
    x, y, w, h, out = int(argv[1]), int(argv[2]), int(argv[3]), int(argv[4]), argv[5]
    r = services.Recorder((x, y, w, h), False, False, out)
    r.start()
    print("started", flush=True)
    time.sleep(60)


if __name__ == "__main__":
    main(sys.argv)
