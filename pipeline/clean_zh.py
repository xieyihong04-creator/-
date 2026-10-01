"""Final Chinese cleanup: drop fade-in fragments and unreadable junk, keep real on-screen text.

The 480p source clips its bottom subtitle line, so during a subtitle's fade-in the
recognizer sometimes reads a half-line ("理解能会人" before "理解能力令人詫異"). Those
fragments are short, single-frame, and fuzzily contained in a neighbour, so they are
removed here. Real name credits (conf >= 0.7) stay.
"""
import json, re, sys, difflib


def text_of(s):
    return ' '.join(l['text'] for l in s['lines'])


def conf_of(s):
    return max(l['conf'] for l in s['lines'])


def similar(a, b):
    """Two readings of the same subtitle: fuzzy-equal, or one nearly contains the other.
    Length matters — a short credit line must not be swallowed by an unrelated long one."""
    if a == b:
        return True
    if difflib.SequenceMatcher(None, a, b).ratio() >= 0.80:
        return True
    short, lng = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) < 0.55 * len(lng):
        return False
    sm = difflib.SequenceMatcher(None, short, lng)
    return sum(bl.size for bl in sm.get_matching_blocks()) >= 0.85 * len(short)


def merge_variants(subs, gap=2.5):
    """Collapse adjacent near-duplicates of the same subtitle (fade-in drift produces
    "一固錄堂…" then "一個錄堂…" for one line). Keep the more confident reading."""
    out = []
    for s in subs:
        if out:
            p = out[-1]
            if s['start'] - p['end'] <= gap and similar(text_of(p).replace(' ', ''),
                                                        text_of(s).replace(' ', '')):
                p['end'] = max(p['end'], s['end'])
                p['nframes'] = p.get('nframes', 1) + s.get('nframes', 1)
                if conf_of(s) > conf_of(p):
                    p['lines'] = s['lines']
                continue
        out.append(s)
    return out


def drop_fragments(subs, gap=2.0, thr=0.85):
    """Remove a subtitle that is only a fuzzy piece of an adjacent one."""
    out = []
    for i, s in enumerate(subs):
        t = text_of(s).replace(' ', '')
        weak = s.get('nframes', 1) <= 2 and conf_of(s) < 0.90
        neighbour_ok = False
        for j in (i - 1, i + 1):
            if not (0 <= j < len(subs)):
                continue
            n = subs[j]
            if abs(n['start'] - s['end']) > gap and abs(s['start'] - n['end']) > gap:
                continue
            nt = text_of(n).replace(' ', '')
            if len(nt) <= len(t) and conf_of(n) < conf_of(s):
                continue
            sm = difflib.SequenceMatcher(None, t, nt)
            cover = sum(bl.size for bl in sm.get_matching_blocks()) / max(1, len(t))
            if cover >= thr:
                neighbour_ok = True
                break
        if weak and neighbour_ok:
            continue
        out.append(s)
    return out


def junk(s):
    t = text_of(s).replace(' ', '')
    c = conf_of(s)
    if not t:
        return True
    has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in t)
    if not has_cjk:
        # Latin lines are on-screen credits; keep them only if the read is confident
        # and long enough to be a name/title.
        if c < 0.70:
            return True
        if len(t) <= 4 and not re.search(r'[a-z]', t):
            return True
        if re.fullmatch(r'[\W_]*', t):
            return True
        return False
    if c < 0.55 and s.get('nframes', 1) <= 2:
        return True
    if len(t) <= 3 and s.get('nframes', 1) <= 1 and c < 0.80:
        return True
    return False


def clean(subs):
    subs = [s for s in subs if not junk(s)]
    prev = None
    while prev != len(subs):
        prev = len(subs)
        subs = drop_fragments(subs)
    return merge_variants(subs)


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    d = json.load(open(src, encoding='utf-8'))
    c = clean(d)
    json.dump(c, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{src}: {len(d)} -> {len(c)} subs (final)')
