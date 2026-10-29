# OCR performance and recognition compatibility

## Scope

The requirement is faster recognition **without reducing recognition quality**.
The final implementation retains the published image preparation, installed
language models, PSM 4 / PSM 11 passes, reading order and table-selection rule.
No model is downloaded or replaced. Recognition remains local and CPU-only.

An initial experiment changed scale, page segmentation and split pages into
masked blocks. It was faster, but output depended on worker count and some words
disappeared. Those changes were rejected, not shipped as equivalent.

## Accepted optimizations

- Load libtesseract once per worker, retaining the model between captures.
- Set `OMP_THREAD_LIMIT=1` and `OMP_NUM_THREADS=1` before loading native libraries.
  Previously two multithreaded CLI processes ran simultaneously. Tesseract's FAQ
  warns that extra threads can slow machines with few cores (reference below).
- Use at most two workers, one per original independent full-page pass. With one
  logical CPU the passes run sequentially in one worker. No crops, masks, new
  segmentation mode or adaptive rescaling change recognition input.
- Transfer opaque pixels through pipes, without temporary PNG files. For images
  with alpha, use PNG **in memory** and Leptonica's normal PNG path; raw RGBA lost
  text in a regression test because its alpha treatment differs.
- Cache the four most recent image/language results. Benchmarks disable caching.
- Warm up workers when opening the overlay text tool; release idle workers after
  90 seconds without interrupting a busy worker.
- Lower worker priority (`nice 4`, configurable with `CAPTURA_OCR_NICE`). Cancel
  signals workers without waiting in GTK; pipe reads and writes have timeouts.
- Cache the installed-language list instead of spawning `--list-langs` for every
  capture. QR colour conversion moves from Python pixel loops into libzbar.

Recognition settings remain PSM 11 on the original and PSM 4 with 2x bilinear
scaling only when the longest side is below 1200 pixels. The sparse result wins
only when the unchanged table detector confirms a table. Existing recognition
errors are not silently traded for different errors in a performance change.
The auxiliary plain-text command retains its separate published PSM 6 CLI route
and exact line-break formatting; it benefits from the same thread limit and
language-list cache, but does not use the persistent word-box pipeline.

## Measurements, October 29, 2026

Machine: Intel Core i5-11400, Tesseract 5.3.4, Leptonica 1.82.0, `por+eng`, Linux.
Affinity limits were applied to logical CPUs 6 and 7. **This is not a real old-PC
benchmark**: it limits scheduling capacity, not clock speed, instruction set,
memory bandwidth or GPU generation. The GPU was not used. The desktop remained
running, so these are comparative observations, not hardware guarantees.

Two reads per image, cache disabled. Values are medians of those two reads. Model
warm-up was measured separately (0.43 s with one CPU; 0.59 s with two), not hidden
in recognition timings. The reference starts fresh CLI processes with its original
unrestricted OpenMP settings. Neither baseline run timed out.

| Image | Before, 1 CPU | After, 1 CPU | Before, 2 CPUs | After, 2 CPUs |
|---|---:|---:|---:|---:|
| Small selection (`sel300`) | 1.416 s | 0.149 s | 0.641 s | 0.088 s |
| Contact text (`ocr-input`) | 2.656 s | 0.397 s | 1.196 s | 0.224 s |
| Selection (`sel600`) | 6.802 s | 1.047 s | 3.288 s | 0.612 s |
| Document (`doc900`) | 27.631 s | 4.476 s | 13.341 s | 2.324 s |
| Dense 1080p page (`web1080`) | 48.673 s | 9.043 s | 24.613 s | 4.720 s |
| **Sum of medians** | **87.178 s** | **15.112 s** | **43.080 s** | **7.968 s** |

Aggregate gain: **5.77x with one logical CPU; 5.41x with two**, on these five
cases. Individual cases range from 5.21x to 9.49x. Timed outputs were also checked
against the reference for ordered words, boxes, line IDs, copied text and table
cells. Repeat reads were identical. Raw measurements:

- [One-CPU speed comparison](ocr-speed-1cpu.json)
- [Two-CPU speed comparison](ocr-speed-2cpu.json)
- [61-image compatibility comparison](ocr-quality-results.json)
- [Golden comparison against the actual published code](ocr-head-golden-results.json)

The latter report runs the archived `textlayer.py` and `services.py` from commit
`959b64a`, with their source bytes checked against `git show`, rather than only
using the benchmark's reimplementation. It checks input PNG SHA-256 hashes and
compares the final pipeline with the archived ordered words, boxes, lines,
clipboard text and table cells: **61 images, zero mismatches**. Signature/source
hashes are stored without publishing the screenshots' recognized text.

The expanded compatibility run uses the 61 research PNGs (light/dark text, font
sizes, paragraphs, columns, tables and selections), with OpenMP also limited in
the CLI reference to avoid timeouts. **61/61 match** on ordered words, original
coordinate boxes, line/paragraph IDs, plain clipboard text and table cells.
Confidence rounding is not a comparison criterion; the UI does not use it to
change these outputs. This is corpus-specific evidence, not proof for every
screenshot, model package or Tesseract release. It establishes compatibility
with the baseline, not that the baseline OCR is error-free.

## Reproduce

```sh
# Self-contained synthetic corpus; default uses installed languages.
/usr/bin/python3 scripts/ocr_bench.py --cores 1 --compare --repeat 2 --json result.json

# Research images are not bundled; provide your own PNG directory.
/usr/bin/python3 scripts/ocr_bench.py --images /path/to/pngs --compare \
  --reference-single-thread --json quality.json

# Includes transparent images; compares against real CLI TSV.
/usr/bin/python3 -m unittest discover -s tests -p 'test_ocr*.py' -v
```

The benchmark exits nonzero on errors, timeouts, non-identical repeats or any
structured-output mismatch. A timed-out old run is never presented as a speed-up
or a quality score of zero. JSON files are updated after each image.

## Deliberate operational changes (not recognition equivalence)

The equality claim concerns **successful recognition output**, not reproducing
misleading failure handling. These operational differences are intentional:

- The auxiliary PSM 6 command now checks a nonzero CLI exit code (`check=True`).
  It reports extraction failure instead of presenting an engine crash as "no
  text found". Its timeout is 300 seconds instead of 60, and its OpenMP thread
  limits are explicit.
- The word-box CLI fallback also rejects nonzero exits and missing TSV headers.
  These raise `WorkerError`; they are not valid empty-page recognitions.
- Workers use bounded read/write timeouts (240 seconds per call), and cancellation
  is owner-scoped. A cancelled read is discarded, not published as empty text.
- An actually empty page with a valid recognition result still returns no words.

`test_ocr_service_compat` checks both exact successful PSM 6 formatting and an
intentional nonzero-exit error. `test_ocr_lifecycle` checks CLI failure, malformed
output, cancellation and timeouts. This is an explicit improvement in failure
reporting, not evidence of better OCR accuracy.

Known infrastructure limits: warm-up model initialization itself can take up to
60 seconds per worker; a cancelled queued thread may wait for the pool lease
before unwinding. If one of the two native passes fails while its sibling is
still busy, fallback waits for that sibling's bounded call. These waits do not
run on the GTK thread. Model warm-up can retain workers until the idle timeout;
cancelling a running recognition discards its workers and the next read reloads
them. The first language-list lookup now also runs off the GTK thread.

## Verification

- Full GTK/X11 suite: **277 tests passed**, 260.915 seconds, in an isolated
  Xephyr display (1920x1080), private D-Bus session and settings directory, with
  Portuguese UI. This includes a real XTEST sequence: activate Text actions,
  wait for real recognition, click Copy, read the clipboard. An earlier 275-test
  run also passed on the physical desktop. The later 277-test physical-desktop
  run failed one moving-window video test (identical frames); that exact test and
  then the full suite passed in Xephyr without changing recording code.
- Focused coverage includes owner-scoped cancellation before worker startup,
  cancelled fallback process reaping, pipe-write timeouts, idle shutdown during a
  read, malformed replies, native buffer validation and initialization failure.
- Compilation, translation extraction (240 catalogued / zero new UI strings) and
  `git diff --check` pass. The `.deb` builds; an extracted copy recognizes a real
  sample using its packaged worker, and the package checksum verifies. It has not
  been installed or published as a new release.
- The full suite still prints ResourceWarnings from the existing video-process
  stdout test and the global X11 test connection; an OK result is not a claim
  that the test runner's warning output is clean.

## Alternatives and GPU

The alternate-engine experiments are not an exhaustive comparison of current
engines/models. The initial RapidOCR test used the older `rapidocr_onnxruntime`
package, not every multilingual route in current RapidOCR. Current documentation
describes multiple model families and backends. That test cannot justify claiming
all ONNX or GPU OCR is slower or less accurate.

A replacement needs equivalent word boxes, reading order, paragraphs, Portuguese
accents and table copying, plus validation on the target hardware. No replacement
has passed that compatibility requirement in this work. This change therefore
ships scheduling/lifetime improvements, not a new recognizer.

Tesseract's OpenCL documentation calls that path experimental and does not
recommend enabling it. GPU support is not assumed merely because a PC has an
integrated GPU. **No old integrated GPU has been benchmarked here**; testing on
the user's actual slow machine remains necessary.

## Primary references

- [Tesseract FAQ: thread limits](https://tesseract-ocr.github.io/tessdoc/FAQ)
- [Tesseract OpenCL limitations](https://github.com/tesseract-ocr/tessdoc/blob/main/TesseractOpenCL.md)
- [Current RapidOCR package/backend overview](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)
- [Current RapidOCR model/language routes](https://rapidai.github.io/RapidOCRDocs/main/en/model_list/)
