# Win11-like Snipping Tool for Linux 1.0.2

OCR performance and reliability release. Recognition remains local and CPU-only.

## Changed

- **Persistent Tesseract workers** retain installed language models between captures instead of repeatedly starting the recognizer. At most two workers run, with one native CPU thread per worker.
- **One-CPU shortcut** omits the dense recognition pass only when the unchanged selection rule has already chosen the sparse result. Otherwise, the original dense pass still runs. With two workers, the original independent passes remain concurrent.
- **Lower transport overhead** sends pixels in memory. Images with transparency retain the PNG/Leptonica alpha-handling path; recognition models, languages, segmentation modes and image scaling are not replaced.
- **Responsive lifecycle** warms up models and discovers languages outside the GTK thread, reuses a bounded result cache, and shuts down idle workers without interrupting a busy request.
- **Safer cancellation and cleanup** keep editor and overlay requests independent, discard stale UI results, and carry cancellation through the CLI fallback. Recognition failures are reported as errors rather than silently treated as an image with no text.
- **Native binding hardening** improves OCR/QR buffer validation and process/resource cleanup.

No experimental RapidOCR models or additional runtime dependencies are included.

## Measurements and compatibility

After the initial persistent-worker change, an interleaved follow-up comparison on one logical CPU, with warm models and result caching disabled, reduced the **sum of five image medians from 14.55 s to 9.94 s**. The `web1080` case fell from **8.76 s to 4.23 s**. Each median uses three recognitions.

These are measured cases, not a five-second guarantee: the five-image total is not a single capture, the five-second aggregate target was not reached, and restricting a modern CPU's affinity does not emulate an old computer.

The successful output matched the archived previous pipeline across **61 PNG files (60 distinct images)** for ordered words, bounding boxes, block/paragraph/line identifiers, copied plain text and table cells. This is evidence for the tested corpus, not a universal accuracy guarantee.

See [`docs/OCR_PERFORMANCE.md`](docs/OCR_PERFORMANCE.md) for the initial optimization and [`docs/OCR_SINGLE_CPU_FOLLOWUP.md`](docs/OCR_SINGLE_CPU_FOLLOWUP.md) for paired measurements, raw results, compatibility checks and verification limits.

## Unchanged limitations

X11 is required. Recording timing/first-frame delays, hard-killed MP4 recovery and the recording-editing options remain outside this OCR update; see the README. No recording reliability fix is claimed here.

## Install or update

```bash
sudo apt install ./captura_1.0.2_all.deb
```

Verify the download with:

```bash
sha256sum -c captura_1.0.2_all.deb.sha256
```

This project is not affiliated with or endorsed by Microsoft. See `THIRD_PARTY_NOTICES.md` for the bundled Fluent UI System Icons (MIT) and Selawik font (SIL OFL 1.1). Translations were produced with the help of a language model and have not had human review.
