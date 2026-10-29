#!/usr/bin/python3
"""Reproducible OCR benchmark and strict compatibility check.

--compare measures the published two-CLI pipeline against persistent workers.
--reference-single-thread bounds OpenMP for a quality-only baseline comparison.
--cores limits logical CPUs by affinity; it does NOT emulate an older processor.
Cache is disabled. Failures/timeouts never count as successful speed-ups.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cairo
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
from captura import ocr_engine as E, services, textlayer


def page(name, width, height, size, cols=1, dark=False):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*((.12, .12, .14) if dark else (1, 1, 1)))
    cr.paint()
    cr.set_source_rgb(*((.86, .86, .9) if dark else (0, 0, 0)))
    cr.select_font_face("DejaVu Sans")
    cr.set_font_size(size)
    prose = ("Permission is hereby granted without restriction to copy and modify this software. "
             "Reconhecimento de texto: ação, coração, informações e documentação. "
             "The quick brown fox jumps over the lazy dog. Contact: jane.doe@example.com.").split()
    colwidth = (width - 60 - (cols - 1) * 40) // cols
    index, truth = 0, []
    for col in range(cols):
        y = 30 + size
        while y < height - size:
            line = []
            while cr.text_extents(" ".join(line + [prose[index % len(prose)]])).x_advance < colwidth:
                line.append(prose[index % len(prose)])
                index += 1
            if not line:
                raise ValueError("column-too-narrow")
            cr.move_to(30 + col * (colwidth + 40), y)
            cr.show_text(" ".join(line))
            truth.extend(line)
            y += int(size * 1.6)
    return name, surface, truth


def corpus():
    return [page("1col-11px", 900, 500, 11), page("1col-14px", 900, 500, 14),
            page("1col-18px", 900, 500, 18), page("1col-30px", 900, 500, 30),
            page("2col-13px", 1400, 800, 13, 2), page("3col-14px-1080p", 1920, 1080, 14, 3),
            page("dark-2col-15px", 1500, 900, 15, 2, True), page("1col-16px-dark", 1200, 700, 16, dark=True)]


def legacy_ocr(surface, single_thread=False):
    """Published PSM4 + PSM11, scale and table selection; two fresh CLI processes."""
    pb = services.surface_to_pixbuf(surface)
    langs = services.ocr_language_spec()
    width, height = pb.get_width(), pb.get_height()
    env = {key: value for key, value in os.environ.items() if key not in ("OMP_THREAD_LIMIT", "OMP_NUM_THREADS")}
    if single_thread:
        env.update(OMP_THREAD_LIMIT="1", OMP_NUM_THREADS="1")
    def tess(path, mode):
        return subprocess.run(["tesseract", path, "stdout", "--psm", str(mode), "-l", langs, "tsv"],
                              capture_output=True, text=True, timeout=60, check=True, env=env).stdout
    with tempfile.TemporaryDirectory() as directory:
        orig = str(Path(directory) / "orig.png")
        pb.savev(orig, "png", [], [])
        scale, src = 1, orig
        if max(width, height) < 1200:
            scale, src = 2, str(Path(directory) / "x2.png")
            pb.scale_simple(width * 2, height * 2, GdkPixbuf.InterpType.BILINEAR).savev(src, "png", [], [])
        with ThreadPoolExecutor(2) as executor:
            sparse_future = executor.submit(tess, orig, 11)
            plain_future = executor.submit(tess, src, 4)
            sparse = textlayer.parse_tsv(sparse_future.result())
            plain = textlayer.parse_tsv(plain_future.result(), scale)
    return sparse if sparse and textlayer.detect_table(sparse) is not None else plain


def signature(words):
    return [(word.text, word.box, word.line) for word in words]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cores", type=int)
    ap.add_argument("--legacy", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--reference-single-thread", action="store_true")
    ap.add_argument("--images", type=Path)
    ap.add_argument("--names", help="comma-separated names, without .png")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.repeat < 1 or (args.cores is not None and args.cores < 1):
        ap.error("--repeat and --cores must be positive")
    if args.cores:
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:args.cores])
    if not services.ocr_available():
        sys.exit("tesseract is not installed")
    E.CACHE_SIZE = 0
    if args.images:
        paths = [args.images / (name + ".png") for name in args.names.split(",")] if args.names else sorted(args.images.glob("*.png"))
        pages = [(path.stem, cairo.ImageSurface.create_from_png(str(path)), None) for path in paths]
    else:
        pages = corpus()
        if args.names:
            wanted = set(args.names.split(","))
            pages = [item for item in pages if item[0] in wanted]
    if not pages:
        ap.error("empty corpus")
    report = {"affinity": sorted(os.sched_getaffinity(0)), "languages": services.ocr_language_spec(),
              "reference_single_thread": args.reference_single_thread, "repeat": args.repeat, "cache": False,
              "tesseract": subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
              "cases": []}
    start = time.perf_counter()
    if not args.legacy or args.compare:
        textlayer.ocr_surface(page("warmup", 400, 150, 18)[1])
    report["warmup_seconds"] = time.perf_counter() - start
    print("affinity=%s languages=%s cache=disabled warmup=%.3fs" % (report["affinity"], report["languages"], report["warmup_seconds"]), flush=True)
    failed = False
    for name, surface, _truth in pages:
        entry, outputs = {"name": name}, {}
        functions = []
        if args.legacy or args.compare:
            functions.append(("legacy", lambda surf: legacy_ocr(surf, args.reference_single_thread)))
        if not args.legacy or args.compare:
            functions.append(("current", textlayer.ocr_surface))
        for label, function in functions:
            elapsed = []
            try:
                previous, stable = None, True
                for _ in range(args.repeat):
                    start = time.perf_counter()
                    words = function(surface)
                    elapsed.append(time.perf_counter() - start)
                    sig = signature(words)
                    stable = stable and (previous is None or previous == sig)
                    previous = sig
                outputs[label] = words
                entry[label] = {"seconds": elapsed, "median_seconds": statistics.median(elapsed),
                                "words": len(words), "repeat_identical": stable}
                failed = failed or not stable
            except Exception as exc:
                entry[label] = {"error": type(exc).__name__ + ": " + str(exc)}
                failed = True
        if args.compare and len(outputs) == 2:
            old, new = outputs["legacy"], outputs["current"]
            entry["equal"] = {"word_order_boxes_lines": signature(old) == signature(new),
                              "clipboard_text": textlayer.words_text(old) == textlayer.words_text(new),
                              "table_cells": textlayer.detect_table(old) == textlayer.detect_table(new)}
            failed = failed or not all(entry["equal"].values())
        report["cases"].append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    E.POOL.shutdown()
    print("cases=%d failures_or_mismatches=%s" % (len(report["cases"]), failed), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
