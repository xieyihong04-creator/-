"""Post-process extracted subtitles: absorb flicker fragments and merge splits.

A two-line subtitle can flicker between frames that show both lines and frames
that show only the second, which splits one subtitle into several groups. Merge
any group whose text is contained in (or nearly equal to) a neighbour.
"""
import json, sys, difflib


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def text_of(s):
    return ' '.join(l['text'] for l in s['lines'])


def clean(subs, gap=1.6):
    subs = [dict(s) for s in subs]
    changed = True
    while changed:
        changed = False
        out = []
        i = 0
        while i < len(subs):
            cur = subs[i]
            t = text_of(cur)
            if out:
                prev = out[-1]
                pt = text_of(prev)
                near = cur['start'] - prev['end'] <= gap
                if near and (t == pt or ratio(t, pt) >= 0.93):
                    prev['end'] = max(prev['end'], cur['end'])
                    prev['nframes'] = prev.get('nframes', 1) + cur.get('nframes', 1)
                    if len(t) > len(pt):
                        prev['lines'] = cur['lines']
                    changed = True
                    i += 1
                    continue
                # fragment: cur's text is a piece of prev's (flicker of 2nd line)
                if near and len(t) < len(pt) and (t in pt or all(
                        l['text'] in pt for l in cur['lines'])):
                    prev['end'] = max(prev['end'], cur['end'])
                    prev['nframes'] = prev.get('nframes', 1) + cur.get('nframes', 1)
                    changed = True
                    i += 1
                    continue
                # prev was the fragment and cur is the full subtitle
                if near and len(pt) < len(t) and (pt in t or all(
                        l['text'] in t for l in prev['lines'])):
                    out[-1] = cur
                    out[-1]['start'] = min(prev['start'], cur['start'])
                    out[-1]['end'] = max(prev['end'], cur['end'])
                    changed = True
                    i += 1
                    continue
            out.append(cur)
            i += 1
        subs = out
    # final: drop single-frame groups with very little text
    subs = [s for s in subs
            if not (s.get('nframes', 1) <= 1 and len(text_of(s)) <= 3)]
    return subs


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding='utf-8') as f:
        d = json.load(f)
    c = clean(d)
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    print(f'{src}: {len(d)} -> {len(c)} subs')
