#!/usr/bin/python3
"""Compare real prior/current Captura pipelines, interleaved, with result caches disabled.

Example: taskset -c 6 /usr/bin/python3 scripts/ocr_compare_revision.py \
    --previous 215d514 --images ~/ocr-bench/img --repeat 3 --json result.json
CPU affinity limits scheduling capacity; it does not emulate an old processor.
"""
import argparse
import importlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cairo
from captura import textlayer, ocr_engine


def signature(words):
    return [(word.text, word.box, word.line) for word in words]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--names', default='sel300,ocr-input,sel600,doc900,web1080')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', '--verify', args.previous + '^{commit}'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='ocr-reference-') as directory:
        archive = Path(directory) / 'source.tar'
        with archive.open('wb') as stream:
            subprocess.run(['git', '-C', str(ROOT), 'archive', revision], stdout=stream, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(directory, filter='data')
        package = Path(directory) / 'captura'
        spec = importlib.util.spec_from_file_location('captura_perf_reference', package / '__init__.py', submodule_search_locations=[str(package)])
        if spec is None or spec.loader is None:
            raise RuntimeError('reference-package-unavailable')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        reference = importlib.import_module('captura_perf_reference.textlayer')
        ref_engine = importlib.import_module('captura_perf_reference.ocr_engine')
        ref_engine.CACHE_SIZE = ocr_engine.CACHE_SIZE = 0
        pipelines = {'previous': reference, 'current': textlayer}
        report = {'previous_commit': revision, 'affinity': sorted(os.sched_getaffinity(0)),
                  'repeat': args.repeat, 'cache': False, 'warmup_seconds': {}, 'cases': []}
        def save():
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2) + '\n')
        try:
            warm = cairo.ImageSurface.create_from_png(str(args.images / (args.names.split(',')[0] + '.png')))
            for label, pipeline in pipelines.items():
                start = time.perf_counter()
                pipeline.ocr_surface(warm)
                report['warmup_seconds'][label] = time.perf_counter() - start
            report['worker_affinities'] = {
                label: [sorted(os.sched_getaffinity(proc.p.pid)) for proc in engine.POOL.procs]
                for label, engine in [('previous', ref_engine), ('current', ocr_engine)]}
            for affinities in report['worker_affinities'].values():
                assert affinities and all(set(cpus) <= set(report['affinity']) for cpus in affinities)
            failed = False
            for name in args.names.split(','):
                surface = cairo.ImageSurface.create_from_png(str(args.images / (name + '.png')))
                samples = {'previous': [], 'current': []}
                previous_signatures = {}
                stable = True
                equal = True
                for repeat in range(args.repeat):
                    outputs = {}
                    for label in (('previous', 'current') if repeat % 2 == 0 else ('current', 'previous')):
                        start = time.perf_counter()
                        words = pipelines[label].ocr_surface(surface)
                        samples[label].append(time.perf_counter() - start)
                        sig = signature(words)
                        stable = stable and (label not in previous_signatures or previous_signatures[label] == sig)
                        previous_signatures[label] = sig
                        outputs[label] = (sig, pipelines[label].words_text(words), pipelines[label].detect_table(words))
                    equal = equal and outputs['previous'] == outputs['current']
                entry = {'name': name, 'input_sha256': hashlib.sha256((args.images / (name + '.png')).read_bytes()).hexdigest(),
                         'samples_seconds': samples,
                         'median_seconds': {label: statistics.median(values) for label, values in samples.items()},
                         'ordered_words_boxes_lines_text_table_equal': equal, 'repeats_identical': stable}
                report['cases'].append(entry)
                failed = failed or not equal or not stable
                save()
                print(json.dumps(entry), flush=True)
            report['sum_of_medians'] = {label: sum(case['median_seconds'][label] for case in report['cases']) for label in pipelines}
            save()
            print('total', report['sum_of_medians'], 'mismatches', failed, flush=True)
            return 1 if failed else 0
        finally:
            ref_engine.POOL.shutdown()
            ocr_engine.POOL.shutdown()


if __name__ == '__main__':
    sys.exit(main())
