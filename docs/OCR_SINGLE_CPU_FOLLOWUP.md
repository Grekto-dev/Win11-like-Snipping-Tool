# OCR follow-up: one-CPU short-circuit

This follows the persistent-worker optimization in commit `215d514`.
The target is lower latency without changing successful recognized content.
No language, model, scale, segmentation mode or table-selection heuristic changes.
No new runtime dependency is added.

## What changes

On **one logical CPU**, recognize PSM 11 first. If the existing table-selection
rule would choose that result, do not compute the PSM 4 result that would be
thrown away. Otherwise, run PSM 4 with the same original image preparation.
This is the original selector, including any existing false positives, not a new
approximate layout predictor. It does not attempt to fix existing OCR errors.

With two workers, retain the concurrent full passes. Calling the engine's full
pair API without a selector still returns both passes. Partial selected results
have a distinct cache key, including the selector policy, so they cannot replace
a requested full result. Cancellation is checked before any remaining pass.
The auxiliary PSM 6 service and CLI fallback are unchanged.

## Paired measurements, October 29, 2026

Intel Core i5-11400, Tesseract 5.3.4, installed `por+eng` models. Both the parent
and each actual OCR worker were restricted to logical CPU **6**. This limits CPU
capacity; it **does not emulate an old computer** or isolate a physical core from
its SMT sibling. Desktop load can affect absolute wall times.

The real archived `215d514` source and current source were run interleaved,
alternating order, with **result caching disabled** and models already warm.
Each value is the median of three actual recognitions of that image.

| Input | Previous | Current |
|---|---:|---:|
| `sel300` | 0.141 s | 0.135 s |
| `ocr-input` | 0.345 s | 0.340 s |
| `sel600` | 0.962 s | 0.955 s |
| `doc900` | 4.346 s | 4.285 s |
| `web1080` | 8.757 s | **4.231 s** |
| **Sum of the five medians** | **14.551 s** | **9.945 s** |

The five-case sum is **31.7% lower**, not a single capture taking 9.945 seconds.
The substantial improvement is the omitted pass on `web1080`; a separate native
call trace, [`ocr-round2-pass-trace-1cpu.json`](ocr-round2-pass-trace-1cpu.json),
records only PSM 11 for that input and PSM 11 + PSM 4 for the other four. Small
changes on other inputs are measurement variation, not an additional claim.
The initial warm-up call was measured separately: 0.416 s previous, 0.414 s
current. That is an initial recognition call, not a pure model-loading timer.
Raw repetitions, input hashes and actual worker affinities are in
[`ocr-round2-speed-1cpu.json`](ocr-round2-speed-1cpu.json).

All five **current** individual medians are below five seconds on this machine. **The target
of five seconds for the complete five-image set is not reached. Nor is a five-
second limit established for arbitrary captures:** 21 of the 61 expanded quality
cases took more than five seconds in their single current measurement. No
five-second guarantee is made for old hardware.

Reproduce with the same external corpus (not distributed in this repository):

```sh
taskset -c 6 /usr/bin/python3 scripts/ocr_compare_revision.py \
  --previous 215d514 --images /path/to/ocr-bench/img --repeat 3 \
  --json /path/to/results.json
```

## Recognition checks

All **61 PNG files (60 distinct input hashes)** were compared against the actual
archived previous source with one logical CPU and result caching disabled.
`ocr-table` and `tab-orig` contain the same image bytes. No differences were found in:

- Ordered recognized words and bounding boxes.
- Block, paragraph and line identifiers.
- Plain text produced by `words_text`.
- Detected table cells and their ordering.

The five benchmark images were also identical across all three repetitions.
This is evidence for the tested corpus, not a proof for every possible image.
[`ocr-round2-quality-1cpu.json`](ocr-round2-quality-1cpu.json) records all 61 input
hashes and comparison results. The first measurement command hit the tool's
wall-time limit after 30 completed comparisons; its saved results were retained,
and the remaining 31 were completed in a second batch. No unfinished result was
counted as a successful comparison, and that file is not used as a timing sum.

The exact 61 input names are the `cases[].name` entries in the quality JSON.
To reproduce that complete set in one background command, without a tool's
foreground wall-time limit:

```sh
names=$(/usr/bin/python3 -c 'import json; print(",".join(c["name"] for c in json.load(open("docs/ocr-round2-quality-1cpu.json"))["cases"]))')
taskset -c 6 /usr/bin/python3 scripts/ocr_compare_revision.py \
  --previous 215d514 --images /path/to/ocr-bench/img --names "$names" \
  --repeat 1 --json /path/to/quality-results.json
```

For recovery after interruption, the second batch's names were the requested
input-name set minus the completed first batch's `cases[].name` set. Results were
merged by name, rejecting duplicates, checking both batches' revision/affinity,
requiring all comparison flags true, and asserting the final name set equalled
all 61 corpus files. Case records were preserved; no combined timing total was
reported for the recovered quality run.

Regression tests cover the skipped pass, necessary dense pass, unchanged
parallel path, exact selection rule, full/partial cache separation, different
selector policies, and cancellation between passes. Existing lifecycle and
fallback tests remain in use.

## Other investigated paths

Forcing alternative `DOTPRODUCT` settings did not produce a material gain in
the measured probes; none is forced in the application. The default string
`dotproduct=generic` printed by Tesseract is not proof that runtime SIMD dispatch
is disabled. Cropping, adaptive scaling, different PSMs, language removal and
model replacement are not part of this change.

A separate RapidOCR 3.10.0 / ONNX experiment tested PP-OCRv6 tiny multilingual
and PP-OCRv5 Latin mobile. Neither was adopted: some aggregate token scores
improved while previously correct accents or e-mails became wrong. Their
one-shot measurements used another CPU affinity and are not presented as paired
speed-ups over this pipeline. Replacement-engine experiments remain outside the
application and add no package dependency.

## Broader verification and remaining failures

- All OCR tests and the 61-case recognition comparison passed.
- The latest complete isolated-Xephyr run executed **283 tests**, with **two
  recording failures**: multiple-pause duration and quoted/accented-path playback.
  This is **not** reported as a fully green suite.
- A complete run of the real archived `215d514` source executed **277 tests** and
  also failed the multiple-pause duration assertion. The recorder's entire
  `services.py` is byte-identical between that revision and this change.
- The quoted/accented-path case then passed all **three paired rechecks per
  revision**, without code changes. Its transient full-suite failure remains
  recorded; it is not represented as a reproduced baseline failure.
- Recording code and timing assertions were not changed to make this OCR change
  pass. Recording reliability remains a separate unresolved issue.
- The rebuilt `captura_1.0.1_all.deb` was extracted, not installed. Its packaged
  OCR source matched the checkout, recognized a real rendered `Captura OCR 123`
  sample with its native worker restricted to one CPU, and passed checksum
  validation.
