"""Pass 2: re-read the weak subtitle lines flagged by subs.extract(crop_dir=...) with the
heavy PP-OCRv5 *server* recognizer.

Kept as its own process because the server model's ORT arena grows steadily per distinct
input width, and doing this inside the extraction pass is what repeatedly OOM-killed the
sandbox process. Here nothing competes with decoded video frames, results are cached to
JSON after every crop, and a restart resumes where it left off.
"""
import json, os, sys, time, hashlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OCR_SERVER
from ocrsub import Rec
from subs import finalize


def crop_path(line):
    return line.get('_crop')


def digest(fn):
    """Same subtitle text appears in many sampled frames, so identical crops (same
    pixels) are OCR'd once and reused — that alone cuts the server reads by ~3x."""
    try:
        return hashlib.md5(open(fn, 'rb').read()).hexdigest()
    except Exception:
        return None


def main(subs_json, cache_json, threads=4, maxw=320, min_conf=0.86, quiet_every=25):
    subs = json.load(open(subs_json, encoding='utf-8'))
    cache = {}
    if os.path.exists(cache_json):
        cache = json.load(open(cache_json, encoding='utf-8'))
    todo = [l for s in subs for l in s['lines']
            if crop_path(l) and l['conf'] < min_conf and crop_path(l) not in cache]
    print(f'{len(todo)} weak lines to re-read ({len(cache)} cached), server model',
          flush=True)
    if not todo:
        return subs, cache
    slow = Rec(threads=threads, path=OCR_SERVER)
    st = time.time()
    for i, l in enumerate(todo, 1):
        fn = crop_path(l)
        key = '#' + (digest(fn) or fn)
        hit = cache.get(key)
        if hit is None:
            try:
                img = np.asarray(Image.open(fn).convert('L'))
                txt, conf = slow(img, maxw=maxw)
                txt = txt.strip()
            except Exception as ex:                  # missing/unreadable crop
                txt, conf = '', 0.0
                print(f'  skip {fn}: {ex}', flush=True)
            hit = [txt, round(float(conf), 3)]
            cache[key] = hit
        cache[fn] = hit
        if i % quiet_every == 0:
            el = time.time() - st
            reads = sum(1 for k in cache if k.startswith('#'))
            print(f'  {i}/{len(todo)} {el:.0f}s eta {(len(todo)-i)*el/i:.0f}s '
                  f'distinct reads {reads} mem {rss_mb():.0f}MB', flush=True)
            json.dump(cache, open(cache_json, 'w'), ensure_ascii=False)
    json.dump(cache, open(cache_json, 'w'), ensure_ascii=False)
    print(f'pass2 done: {len(todo)} lines in {time.time()-st:.0f}s', flush=True)
    return subs, cache


def rss_mb():
    try:
        with open(f'/proc/{os.getpid()}/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
    except Exception:
        pass
    return 0.0


def apply_cache(subs, cache, min_conf=0.86):
    """Fold the server readings back in; a re-read wins only if it is confident
    enough and not shorter than what the mobile model already read."""
    changed = 0
    for s in subs:
        for l in s['lines']:
            fn = crop_path(l)
            if not fn or l['conf'] >= min_conf:
                continue
            hit = cache.get(fn)
            if not hit:
                continue
            txt, conf = hit
            # A re-read replaces the mobile reading only when it is more confident AND
            # either keeps the length or is itself very confident. Bottom-clipped lines
            # sometimes make the server model drop leading glyphs ("也神就", conf 0.77) —
            # a shorter but barely-more-confident reading is not an upgrade.
            old = l['text'].replace(' ', '')
            keep = len(txt) >= 2 and conf > l['conf'] and (len(txt) >= len(old) or conf >= 0.95)
            if keep:
                if txt != l['text']:
                    changed += 1
                l['text'] = txt
                l['conf'] = conf
            l.pop('_crop', None)
    print(f'server re-reads applied to {changed} lines', flush=True)
    return subs


if __name__ == '__main__':
    subs_json = sys.argv[1]
    cache_json = sys.argv[2]
    out_json = sys.argv[3] if len(sys.argv) > 3 else None
    subs, cache = main(subs_json, cache_json)
    if out_json:
        subs = apply_cache(subs, cache)
        for s in subs:
            for l in s['lines']:
                l.pop('_crop', None)
        json.dump(finalize(subs), open(out_json, 'w'), ensure_ascii=False, indent=1)
        print(f'{out_json}: {len(subs)} subs written', flush=True)
