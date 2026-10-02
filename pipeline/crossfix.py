"""Fix 上's OCR errors using 下 as reference.

The two episodes repeat the same intro montage, and 下's burned-in subtitles sit fully
inside the frame while 上's bottom line is clipped by the video edge — so the identical
sentence is read at ~0.99 confidence in 下 and mangled in 上 ("一固尋堂又特殊的日子" vs
"一個尋常又特殊的日子"). Any 上 line that closely matches a confident 下 line is replaced
by it; the length guard plus 0.80 similarity means only genuinely the same subtitle hits.
"""
import json, os, sys, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_doc import trad, fixconf

MIN_LEN = 5      # short lines ("引擎", "哈囉") are too ambiguous to trust a match for


def norm(t):
    return fixconf(trad(t)).replace(' ', '')


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def main(target_p, ref_p, out_p, ref_conf=0.90, thr=0.80):
    target = json.load(open(target_p, encoding='utf-8'))
    refs = []
    for s in json.load(open(ref_p, encoding='utf-8')):
        # index both the whole subtitle and each of its lines: 上 is read line by line,
        # so a 2-line reference must still correct a single wrong line.
        cand = [' '.join(l['text'] for l in s['lines'])] + [l['text'] for l in s['lines']]
        conf = [max(l['conf'] for l in s['lines'])] * len(s['lines']) + \
               [l['conf'] for l in s['lines']]
        for t, c in zip(cand, conf):
            t = norm(t)
            if len(t) >= MIN_LEN and c >= ref_conf:
                refs.append(t)
    refs = sorted(set(refs), key=len, reverse=True)
    fixed = 0
    for s in target:
        for l in s['lines']:
            t = norm(l['text'])
            # Title cards and credits genuinely differ between the two episodes
            # ("…機器(上)" vs "…機器(下)"), so they must never be cross-corrected.
            if any(ch in l['text'] for ch in '()（）“”"'):
                continue
            if len(t) < MIN_LEN or l['conf'] >= 0.93:
                continue
            best, br = None, 0.0
            for r in refs:
                if not (0.75 * len(t) <= len(r) <= 1.35 * len(t)):
                    continue
                v = ratio(t, r)
                if v > br:
                    best, br = r, v
            if best and br >= thr:
                if best != l['text']:
                    l['text'] = best
                    l['conf'] = round(min(0.99, br), 3)
                    fixed += 1
    json.dump(target, open(out_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{target_p}: {len(target)} subs, {fixed} lines corrected from {ref_p}')
    return target


if __name__ == '__main__':
    main(*sys.argv[1:4])
