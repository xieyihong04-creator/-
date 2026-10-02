"""Burned-in subtitle extractor.

Strategy: the fast PP-OCRv5 *mobile* recognizer runs on every sampled frame that
contains subtitle text, and duplicates are removed by comparing recognised TEXT
(not pixels). This avoids the classic failure of pixel-signature dedup, where a
two-line subtitle is OCR'd after only its first line has appeared and the second
line is lost. Low-confidence lines are re-read by the heavier *server* model.
"""
import av, json, sys, time, os, difflib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OCR_MOBILE, OCR_SERVER
from ocrsub import Rec, find_rows

BAND = (300, 478, 20, 620)


def yplane(fr):
    p = fr.planes[0]
    return np.frombuffer(p, dtype=np.uint8).reshape(fr.height, p.line_size)[:, :fr.width]


def _junk(t):
    core = [ch for ch in t if ch.isalnum()]
    if not core:
        return True
    if len(core) < 2 and not any('\u4e00' <= c <= '\u9fff' for c in core):
        return True
    return False


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def scan_lines(y):
    """Return list of (row_band, x0, x1) subtitle line crops for one frame."""
    out = []
    for ra, rb in find_rows(y):
        seg = y[ra:rb, BAND[2]:BAND[3]]
        cols = np.where((seg > 170).any(axis=0))[0]
        if len(cols) < 8:
            continue
        x0 = max(0, BAND[2] + cols[0] - 3)
        x1 = min(y.shape[1], BAND[2] + cols[-1] + 4)
        if (x1 - x0) < 16:
            continue
        out.append((ra, rb, x0, x1))
    return out


def extract(path, out_json, sample_fps=3.0, threads=4, limit=None, quiet=False,
            fast_model=OCR_MOBILE,
            slow_model=OCR_SERVER,
            esc_conf=0.86, crop_dir=None):
    """Pass 1. With crop_dir set, weak lines are saved as PNGs on disk instead of
    being held in memory, so the heavier server re-read can run as a separate
    resumable process (keeping ~600 crops in this process is what OOM-killed it).
    """
    st = time.time()
    fast = Rec(threads=threads, path=fast_model)
    if crop_dir:
        os.makedirs(crop_dir, exist_ok=True)
    slow = None
    c = av.open(path)
    vs = c.streams.video[0]
    vs.thread_type = 'AUTO'
    fps = float(vs.average_rate)
    step = max(1, int(round(fps / sample_fps)))
    n = 0
    raw = []
    stop = False
    for pkt in c.demux(vs):
        for fr in pkt.decode():
            if fr.pts is None:
                continue
            t = float(fr.pts * vs.time_base)
            if not n % step:
                y = yplane(fr)
                lines = scan_lines(y)
                if lines:
                    crops = [y[ra:rb, x0:x1] for ra, rb, x0, x1 in lines]
                    res = fast.batch(crops)
                    ent = []
                    for (ra, rb, x0, x1), (txt, conf) in zip(lines, res):
                        txt = txt.strip()
                        if _junk(txt):
                            continue
                        e = {'text': txt, 'conf': round(float(conf), 3)}
                        if conf < esc_conf:      # keep the pixels for a later re-read
                            if crop_dir:
                                fn = os.path.join(crop_dir, f'c{n:06d}_{ra}_{x0}.png')
                                if not os.path.exists(fn):
                                    Image.fromarray(y[ra:rb, x0:x1]).save(fn)
                                e['_crop'] = fn
                            else:
                                e['_img'] = np.ascontiguousarray(y[ra:rb, x0:x1]).copy()
                        ent.append(e)
                    if ent:
                        raw.append((round(t, 2), ent))
            n += 1
            if limit and t > limit:
                stop = True
                break
        if stop:
            break
    c.close()
    t_scan = time.time() - st

    # ---- group consecutive frames that carry the same subtitle ---------------
    # Short lines flicker between readings ("引樊"/"引擎"/"引垫"), so we group with a
    # permissive similarity threshold and then pick the best reading per group,
    # instead of treating each differing string as a new subtitle.
    groups = []          # each: {'start','end','best':(text,conf,ent),'n'}
    for t, ent in raw:
        a = ' '.join(e['text'] for e in ent)
        ca = float(np.mean([e['conf'] for e in ent]))
        g = groups[-1] if groups else None
        same = False
        if g is not None:
            b = g['best'][0]
            gap = t - g['end']
            r = _ratio(a, b)
            if gap <= 3.5 and (r >= 0.72 or (a and b and (b.startswith(a) or a.startswith(b)))):
                same = True
        if same:
            g['end'] = t
            prev = g['best']
            # a fuller reading wins if it is not much less confident (2nd line appeared)
            if len(a) > len(prev[0]) and ca >= prev[1] - 0.12:
                g['best'] = (a, ca, ent)
            elif ca > prev[1]:
                g['best'] = (a, ca, ent)
            g['n'] += 1
        else:
            for e in ent:
                if e['conf'] >= esc_conf:
                    e.pop('_img', None)
                    e.pop('_crop', None)
            groups.append({'start': t, 'end': t, 'best': (a, ca, ent), 'n': 1})

    subs = []
    for g in groups:
        lines = [dict(l) for l in g['best'][2]]
        subs.append({'start': g['start'], 'end': g['end'], 'lines': lines,
                     'nframes': g['n']})

    for i, s in enumerate(subs):
        if s['end'] <= s['start']:
            nxt = subs[i + 1]['start'] if i + 1 < len(subs) else s['start'] + 4
            s['end'] = round(min(nxt - 0.1, s['start'] + 8.0), 2)

    # ---- escalate low-confidence lines to the heavier server model -----------
    # In-memory escalation is only safe for a handful of lines. With crop_dir set the
    # weak lines were written to disk above, so this pass stops here and a separate
    # resumable process (esc_pass2.py) re-reads them; that split is what keeps the
    # server model's arena from piling up next to the decoded frames and OOM-killing us.
    weak = [(s, l) for s in subs for l in s['lines']
            if l['conf'] < esc_conf and '_img' in l]
    if crop_dir:
        npop = 0
        for s in subs:
            for l in s['lines']:
                if l['conf'] >= esc_conf:
                    l.pop('_crop', None)
                else:
                    npop += 1
        subs = finalize(subs)
        json.dump(subs, open(out_json, 'w'), ensure_ascii=False, indent=1)
        el = time.time() - st
        if not quiet:
            print(f'{os.path.basename(out_json)}: pass1 {n} frames, {len(raw)} text '
                  f'frames -> {len(subs)} subs, {npop} weak crops -> {crop_dir} '
                  f'| {el:.0f}s', flush=True)
        return subs

    if weak:
        slow = Rec(threads=threads, path=slow_model)
        for _s, l in weak:
            txt, conf = slow(l['_img'], maxw=320)
            txt = txt.strip()
            if len(txt) >= 2 and conf > l['conf']:
                l['text'] = txt
                l['conf'] = round(float(conf), 3)
    for s in subs:
        for l in s['lines']:
            l.pop('_img', None)
    subs = finalize(subs)

    json.dump(subs, open(out_json, 'w'), ensure_ascii=False, indent=1)
    el = time.time() - st
    if not quiet:
        print(f'{os.path.basename(out_json)}: {n} sampled, {len(raw)} text frames -> '
              f'{len(subs)} subs ({len(weak)} escalated) | scan {t_scan:.0f}s total {el:.0f}s',
              flush=True)
    return subs


def finalize(subs):
    """Collapse adjacent groups that read the same line, then drop residual noise."""
    # ---- collapse adjacent groups that ended up reading the same line --------
    flat = []
    for s in subs:
        txt = ' '.join(l['text'] for l in s['lines'])
        if flat:
            ptxt = ' '.join(l['text'] for l in flat[-1]['lines'])
            if s['start'] - flat[-1]['end'] <= 2.0 and _ratio(txt, ptxt) >= 0.90:
                flat[-1]['end'] = s['end']
                flat[-1]['nframes'] += s['nframes']
                continue
        flat.append(s)
    subs = flat

    # ---- drop residual noise (logo fragments, stray single glyphs) -----------
    clean = []
    for s in subs:
        txt = ' '.join(l['text'] for l in s['lines'])
        core = [ch for ch in txt if ch.isalnum()]
        if len(core) <= 1 and s['nframes'] <= 3:
            continue
        if len(core) <= 2 and s['nframes'] <= 1 and (s['end'] - s['start']) < 0.8:
            continue
        clean.append(s)
    return clean


if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2],
            limit=float(sys.argv[3]) if len(sys.argv) > 3 else None)
