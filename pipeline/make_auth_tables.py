"""Rebuild the authoritative edition layer out/<ep>.auth.json from the webmaster's own
proofread Markdown (src/<ep>.md) plus the pipeline's OCR output.

`src/<ep>.md` is the human edition: wording, English, and sectioning are all authoritative.
This script does not change a single character of it. It recovers the two things the
edition's `**HH:MM**` labels cannot carry — sub-minute start times and line end times —
by mapping each edition line back onto the raw OCR lines it came from, and records that
provenance in the `ocr` field of every line.

Why map instead of just parsing the timestamps: the edition's labels are minute-floored,
so two captions in the same minute share a label. The map is a sequence alignment between
the edition's Chinese lines and `out/<ep>.zh.final.json` after the first-layer proofreading
table (`out/<ep>.zh.fix.json`) has been applied. Where the edition merged several captions
into one sentence, the covered lines' time span is folded into that one row; `ocr` then
lists every raw index behind it, which is what makes the result auditable.

Everything derived downstream (`dist/*.md|html|srt`) is rendered from this file by
`pipeline/render_auth.py`, so `dist/` is still machine-built and never hand-edited.

Usage:  python3 pipeline/make_auth_tables.py [shang] [xia]
"""
import difflib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
paths.syspath()
import build_doc as B

SRC = os.path.join(paths.ROOT, 'src')
CN = {'shang': '上', 'xia': '下'}


def mmss_to_sec(s):
    m, sec = s.split(':')
    return int(m) * 60 + int(sec)


def parse_edition(p):
    """-> (title, meta, sections, lines). A line is {t, sec, zh, en}; labels are floored
    to the minute by the edition itself, which is why the times are recovered below."""
    raw = open(p, encoding='utf-8').read()
    m = re.search(r'^# (.+)$', raw, re.M)
    title = m.group(1).strip() if m else os.path.basename(p)
    m2 = re.search(r'^\*\*原片\*\*：(.+)$', raw, re.M)
    meta = m2.group(1).strip() if m2 else ''
    txt = raw.splitlines()
    secs = []
    lines = []
    cur = None
    i = 0
    while i < len(txt):
        s = txt[i].strip()
        m = re.match(r'^### (\d+)\. (.+)$', s)
        if m:
            rng = None
            if i + 1 < len(txt):
                r2 = re.match(r'^`(\d+:\d+)–(\d+:\d+)`$', txt[i + 1].strip())
                if r2:
                    rng = (mmss_to_sec(r2.group(1)), mmss_to_sec(r2.group(2)))
                    i += 1
            cur = {'n': int(m.group(1)), 'title': m.group(2).strip(),
                   's': rng[0] if rng else None, 'e': rng[1] if rng else None}
            secs.append(cur)
            i += 1
            continue
        m = re.match(r'^\*\*(\d+:\d+)\*\*$', s)
        if m:
            zh = ''
            en = ''
            j = i + 1
            while j < len(txt):
                s2 = txt[j].strip()
                if (re.match(r'^\*\*\d+:\d+\*\*$', s2) or re.match(r'^### ', s2)
                        or s2 == '---'):
                    break
                m2 = re.match(r'^中[：:]\s?(.*)$', s2)
                if m2:
                    zh = m2.group(1).strip()
                m3 = re.match(r'^EN[：:]\s?(.*)$', s2)
                if m3:
                    en = (en + ' ' + m3.group(1)).strip()
                j += 1
            lines.append({'t': mmss_to_sec(m.group(1)), 'sec': cur['n'] if cur else None,
                          'zh': zh, 'en': en})
            i = j
            continue
        i += 1
    return secs, lines, title, meta


def norm(s):
    return re.sub(r'\s+', '', (s or '').replace('≈', '').strip())


def build(ep):
    subs_p = os.path.join(paths.OUT, f'{ep}.zh.final.json')
    fix_p = B.fix_table_for(subs_p)
    raw = B.zh_lines(B.load(subs_p))                    # index space == raw OCR index
    drop = {e['i'] for e in json.load(open(fix_p, encoding='utf-8')) if e.get('drop')}
    kept = [i for i in range(len(raw)) if i not in drop]
    lines = B.zh_lines(B.load(subs_p), fix_p)           # first-layer proofread edition
    assert len(kept) == len(lines), f'{ep}: {len(kept)} vs {len(lines)}'

    secs, ul, title, meta = parse_edition(os.path.join(SRC, f'{ep}.md'))
    ops = difflib.SequenceMatcher(None, [norm(x['t']) for x in lines],
                                  [norm(x['zh']) for x in ul],
                                  autojunk=False).get_opcodes()
    out = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            out += [([p], j1 + (p - i1)) for p in range(i1, i2)]
        elif tag == 'replace':
            n = min(i2 - i1, j2 - j1)
            out += [([i1 + d], j1 + d) for d in range(n)]
            for d in range(n, i2 - i1):                 # caption the edition folded away
                if out:
                    out[-1][0].append(i1 + d)
            out += [([], j1 + d) for d in range(n, j2 - j1)]
        elif tag == 'delete':
            for p in range(i1, i2):
                if out:
                    out[-1][0].append(p)
        else:
            out += [([], p) for p in range(j1, j2)]

    rows = []
    for srcs, uj in out:
        u = ul[uj]
        label = u['t']
        if srcs:
            o_start = lines[min(srcs)]['s']
            # keep the OCR's sub-second start only when it agrees with the edition's label
            start = o_start if B.fmt_ts(o_start) == f'{label // 60:02d}:{label % 60:02d}' else float(label)
            near = [lines[i] for i in srcs if abs(lines[i]['s'] - start) <= 120]
            end = max((c['e'] for c in near), default=start + 2)
            ocr = sorted(kept[i] for i in srcs)
        else:
            start = float(label)
            end = start + 2
            ocr = []
        if end <= start:
            end = start + 2
        rows.append({'s': round(float(start), 2), 'e': round(float(end), 2),
                     'sec': u['sec'], 'zh': u['zh'], 'en': u['en'], 'ocr': ocr})

    covered = sum(len(r['ocr']) for r in rows)
    assert covered == len(kept), f'{ep}: {covered} of {len(kept)} OCR lines unaccounted'
    assert all(r['e'] > r['s'] for r in rows), f'{ep}: non-monotonic time span'
    assert [r['s'] for r in rows] == sorted(r['s'] for r in rows), f'{ep}: times out of order'
    assert [r['zh'] for r in rows] == [x['zh'] for x in ul], f'{ep}: text altered by mapping'
    assert [r['en'] for r in rows] == [x['en'] for x in ul], f'{ep}: english altered'

    out_p = os.path.join(paths.OUT, f'{ep}.auth.json')
    json.dump({'_source': f'src/{ep}.md — 站長謝宜宏親自校訂版',
               '_note': 'dist/ 的唯一文字來源。zh/en/sec 逐字取自 src/，'
                        's/e 由 OCR 行還原，ocr 記錄每行背後的原始 OCR 序號。',
               'title': title, 'meta': meta, 'sections': secs, 'lines': rows},
              open(out_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{ep}.auth.json: lines={len(rows)} sections={len(secs)} '
          f'ocr-covered={covered}/{len(kept)} (raw {len(raw)}) '
          f'en-rows={sum(1 for r in rows if r["en"])}')


if __name__ == '__main__':
    for ep in sys.argv[1:] or ['shang', 'xia']:
        build(ep)
