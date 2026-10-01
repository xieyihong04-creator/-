"""Merge zh subtitles (OCR) + en transcript (ASR) into a segmented bilingual study doc."""
import json, re, sys, bisect
from collections import Counter

# --- topic vocabulary, tuned to this documentary's actual subtitle wording ------
TOPICS = [
    ('視覺與眼睛',   ['眼睛', '視覺', '眼球', '視網膜', '角膜', '瞳孔', '眨眼', '看', '影像', '視野']),
    ('聽覺與耳朵',   ['耳朵', '聽', '聲音', '耳蝸', '鼓膜', '聽力', '音波', '噪音']),
    ('味覺與嗅覺',   ['味覺', '舌頭', '味道', '嗅', '氣味', '鼻子', ' taste']),
    ('皮膚與觸覺',   ['皮膚', '觸覺', '摸', '指尖', '汗', '毛髮', '指甲', '癢']),
    ('疼痛與大腦',   ['疼痛', '痛苦', '痛', '腦部', '大腦', '腦', '思考', '記憶', '夢', '睡眠']),
    ('神經與傳導',   ['神經', '電纜', '脊髓', '軸突', '訊號', '传导', '移植', '接合']),
    ('骨骼與關節',   ['骨骼', '骨頭', '關節', '骨髓', '鈣', '骨折', '韌帶', '膝', '脊椎']),
    ('肌肉與運動',   ['肌肉', '收縮', '肌腱', '運動', '抽筋', '力量', '蛋白質', '二頭肌']),
    ('循環與血液',   ['心臟', '血流', '血管', '血液', '心跳', '動脈', '靜脈', '血壓', '氧氣', '血红']),
    ('消化與代謝',   ['消化', '胃', '腸', '肝', '膽', '營養', '唾液', '酶', '食物', '代謝', '熱量']),
    ('呼吸與睡眠',   ['呼吸', '肺', '氣管', '打鼾', '吸氣', '吐氣', '睡眠']),
    ('免疫與修護',   ['免疫', '病毒', '細菌', '白血球', '傷口', '癒合', '抗體', '發炎', '修復']),
    ('生殖與基因',   ['生殖', '精子', '卵子', '基因', '染色體', '懷孕', '胚胎', '嬰兒', '受精', 'DNA', '繁殖']),
    ('人體概論',     ['人體', '機器', '細胞', '器官', '物種', '演化', '奇蹟']),
]


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


# Source subtitles are Traditional Chinese, but the recognizer sometimes returns the
# Simplified shape of a glyph. Fixing the unambiguous ones (体→體, 时→時 …) removes
# hundreds of such slips. Two classes are deliberately left alone: characters that are
# also valid Traditional forms (台 唇 床 群 松 乾 里 干 征 须 托 咸 咨 兹 佣 迹 乾 …), and
# targets that several simplified glyphs share (發/髮, 後/厚 …) — rewriting those would
# introduce errors rather than remove them, and would half-convert words such as 頭髮.
_S2T_BLOCK = set('台唇床群托咸咨兹佣征遥须里干松面斗适迹置画异於畝週'
                 '后游于丑藉覆複作分注佐劫兆更膏脂拖矜甦願搭拚分')
_S2T_MAP = {}
try:
    from opencc import OpenCC as _OpenCC
    _s2t, _t2s = _OpenCC('s2t'), _OpenCC('t2s')
    _all = ''.join(chr(c) for c in range(0x4E00, 0x9FFF + 1))
    _cand = {ch: t for ch, t in zip(_all, _s2t.convert(_all)) if t != ch}
    _rev = {}
    for ch, t in _cand.items():
        _rev.setdefault(t, []).append(ch)
    for ch, t in _cand.items():
        # skip ambiguous sources, many-to-one targets, and anything already Traditional
        if ch in _S2T_BLOCK or len(_rev[t]) > 1 or _t2s.convert(ch) != ch:
            continue
        _S2T_MAP[ch] = t
    _S2T_MAP['为'] = '為'          # OpenCC prefers the 爲 variant; 為 is the standard form
    _S2T_TABLE = str.maketrans(_S2T_MAP)
except Exception:                  # opencc missing → leave text untouched
    _S2T_TABLE = {}


def trad(t):
    return t.translate(_S2T_TABLE) if _S2T_TABLE else t


# Systematic glyph confusions that survive re-reading, because the clipped 480p subtitle
# really does look like the wrong character. Each pair is only ever a misread in these
# contexts: a numeral followed by 革/麻 must be 萬 ("10革次的心跳"), 麻 after 什/怎 must be
# 麼 ("做此什麻"), and 雨 before a numeral must be 兩 ("雨萬次的呼吸"). 麻 that is part of
# 麻醉/麻薩諸塞 never matches, so those stay untouched.
_FIXES = [
    (re.compile(r'([零一二三四五六七八九十百\d０-９])([革麻])(?=[次道倍多裏厘单約的跟向對先數])'), r'\1萬'),
    (re.compile(r'([什怎])麻'), r'\1麼'),
    (re.compile(r'雨(?=[零一二三四五六七八九十百\d萬百千杯片條顆個種處道])'), '兩'),
]


def fixconf(t):
    for pat, rep in _FIXES:
        t = pat.sub(rep, t)
    return t


def zh_lines(subs):
    out = []
    for s in subs:
        t = ' '.join(l['text'] for l in s['lines'])
        t = re.sub(r'\s+', ' ', t).strip()
        t = fixconf(trad(t))
        if len(t) >= 2:
            out.append({'s': s['start'], 'e': s.get('end', s['start'] + 2), 't': t,
                        'c': max(l['conf'] for l in s['lines'])})
    return out


def en_lines(asr):
    out = []
    for s in asr:
        t = re.sub(r'\s+', ' ', s['t']).strip()
        if len(t) > 1 and not re.fullmatch(r'[\W_]*', t):
            out.append({'s': s['s'], 'e': s['e'], 't': t})
    return out


def classify(text):
    """Score each topic by weighted term hits.

    Multi-character terms are reliable and count double; single characters such as
    痛/腦 appear inside unrelated words, so they only contribute a small amount and
    cannot win a section on their own.
    """
    scores = {}
    for name, keys in TOPICS:
        sc = 0.0
        for k in keys:
            n = text.count(k)
            if not n:
                continue
            sc += 2.0 * n if len(k) >= 2 else 0.35 * n
        if sc >= 1.5:
            scores[name] = sc
    if not scores:
        return '人體概論'
    return max(scores.items(), key=lambda kv: kv[1])[0]


def segment(pairs, gap=8.0, max_len=40, min_len=5):
    """Split at scene gaps; then merge blocks that are too short into a neighbour."""
    blocks = []
    cur = []
    for i, (z, e) in enumerate(pairs):
        cur.append((z, e))
        nxt = pairs[i + 1][0]['s'] if i + 1 < len(pairs) else None
        if nxt is None or (nxt - z['e'] > gap) or len(cur) >= max_len:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    # merge tiny blocks forward
    merged = []
    for b in blocks:
        if merged and len(b) < min_len:
            merged[-1] = merged[-1] + b
        elif merged and len(merged[-1]) < min_len:
            merged[-1] = merged[-1] + b
        else:
            merged.append(b)
    # split any over-long merged block back at its largest internal gap
    final = []
    for b in merged:
        while len(b) > 34:
            best, bi = -1, 0
            for k in range(1, len(b) - 10):
                g = b[k][0]['s'] - b[k - 1][0]['e']
                if g > best:
                    best, bi = g, k
            final.append(b[:bi])
            b = b[bi:]
        final.append(b)
    return final


def _sentences(text):
    """Split narration into sentences, keeping the terminator with its sentence."""
    parts = re.findall(r'[^.!?]+[.!?]*\s*', text)
    return [p.strip() for p in parts if p.strip()]


def align(zh, en):
    """Chinese-driven pairing: every Chinese subtitle line stays its own row, and the
    English narration is hung on the lines it belongs to.

    distil-whisper returns coarse English segments (often 15-20s, covering several
    Chinese lines), so a one-to-one match would either fragment the English or lose
    it. Each segment is split into sentences and the sentences are spread across the
    Chinese lines the segment spans, so a line carries the English it actually
    translates. The segment index never moves backwards, keeping the reading order
    monotonic; every English sentence appears exactly once, whole.
    """
    if not en:
        return [(z, '') for z in zh]
    starts = [z['s'] for z in zh]
    ends = [z['e'] for z in zh]
    mids = [(z['s'] + z['e']) / 2 for z in zh]
    buckets = [[] for _ in zh]
    prev = -1
    for e in en:
        i = max(0, bisect.bisect_left(starts, e['s']) - 1)
        cand = None
        while i < len(zh) and starts[i] < e['e']:
            if ends[i] > e['s']:      # real time overlap
                cand = i
                break
            i += 1
        if cand is None:              # gap in the subtitles: nearest line by midpoint
            lo = bisect.bisect_left(mids, (e['s'] + e['e']) / 2)
            cand = min((lo - 1, lo), key=lambda q: 1e9 if q < 0 or q >= len(zh)
                        else abs(mids[q] - (e['s'] + e['e']) / 2))
        last = cand
        k = cand
        while k < len(zh) and starts[k] < e['e']:
            if ends[k] > e['s']:
                last = k
            k += 1
        cand = max(cand, prev)        # keep the reading order monotonic
        last = max(last, cand)
        sents = _sentences(e['t'])
        total = sum(len(s) for s in sents) or 1
        dur = max(0.1, e['e'] - e['s'])
        acc = 0.0
        for si, s in enumerate(sents):
            # a sentence's own time window, proportional to its length in the segment
            t0 = e['s'] + dur * (acc / total)
            t1 = e['s'] + dur * ((acc + len(s)) / total)
            acc += len(s)
            mid = (t0 + t1) / 2
            lo = bisect.bisect_left(mids, mid)
            tgt = min((lo - 1, lo), key=lambda q: 1e9 if q < 0 or q >= len(zh)
                      else abs(mids[q] - mid))
            tgt = min(max(tgt, cand), last)     # stay inside the covered lines
            buckets[tgt].append(s)
        prev = last
    return [(z, ' '.join(b).strip()) for z, b in zip(zh, buckets)]


def fmt_ts(s):
    return f'{int(s // 60):02d}:{int(s % 60):02d}'


def glossary(zh):
    """Top recurring domain terms, for a quick review list."""
    words = Counter()
    for _, keys in TOPICS:
        for k in keys:
            if len(k) >= 2 and not k.isascii():
                n = sum(z['t'].count(k) for z in zh)
                if n:
                    words[k] = n
    return words.most_common(28)


def sections(zh_p, en_p):
    """Return (pairs, merged_sections) where merged is [(topic_name, [units])]."""
    zh = zh_lines(load(zh_p))
    en = en_lines(load(en_p)) if en_p and en_p != '-' else []
    pairs = align(zh, en)
    pairs = [(z, e) for z, e in pairs if z['t'] or len(e) > 3]
    blocks = segment(pairs)
    named = [(classify(''.join(z['t'] for z, _ in b)), b) for b in blocks]
    merged = []
    for name, b in named:
        # merge adjacent same-topic blocks, but keep sections to a studyable size
        if merged and merged[-1][0] == name and len(merged[-1][1]) + len(b) <= 45:
            merged[-1] = (name, merged[-1][1] + b)
        else:
            merged.append((name, b))
    # absorb stub sections (<6 lines) into a neighbour, then re-label from full text
    out = []
    for name, b in merged:
        if out and len(b) < 6:
            out[-1] = (out[-1][0], out[-1][1] + b)
        elif out and len(out[-1][1]) < 6:
            out[-1] = (out[-1][0], out[-1][1] + b)
        else:
            out.append((name, list(b)))
    merged = [(classify(''.join(z['t'] for z, _ in b)), b) for _n, b in out]
    # label repeated topics as "主題 · 第N段" so the TOC stays readable
    seen, total = Counter(), Counter(n for n, _ in merged)
    labelled = []
    for name, b in merged:
        if total[name] > 1:
            seen[name] += 1
            labelled.append((f'{name} · 第{seen[name]}段', b))
        else:
            labelled.append((name, b))
    return pairs, labelled


def build(zh_p, en_p, out_p, title, meta):
    pairs, merged = sections(zh_p, en_p)

    L = [f'# {title}', '', f'> {meta}', '']
    L += ['**產出方式**：中文取自影片燒錄字幕，經 PP-OCRv5 辨識（mobile 初讀 + server 校訂）'
          '並依畫面去重；英文為原聲逐字稿，由 Whisper distil-large-v3 辨識；兩者按時間軸對齊，'
          '再依場景斷點分段、依詞頻標主題。', '']
    L += ['## 目錄', '']
    for i, (name, b) in enumerate(merged, 1):
        L.append(f'{i}. **{name}**　`{fmt_ts(b[0][0]["s"])}–{fmt_ts(b[-1][0]["e"])}`'
                 f'（{len(b)} 句）')
    L.append('')
    g = glossary([z for z, _e in pairs if z['t']])
    if g:
        L += ['## 高頻術語', '',
              '　·　'.join(f'{k}（{v}）' for k, v in g), '']
    L += ['---']
    for i, (name, b) in enumerate(merged, 1):
        L += ['', f'## {i}. {name}', '', f'`{fmt_ts(b[0][0]["s"])}–{fmt_ts(b[-1][0]["e"])}`', '']
        for z, e in b:
            L.append(f'**{fmt_ts(z["s"])}**' + ('　≈' if z.get('c', 1) < 0.80 else ''))
            L.append(f'- 中：{z["t"]}')
            if e:
                L.append(f'- EN：{e}')
            L.append('')
    with open(out_p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    matched = sum(1 for z, _e in pairs if z['t'])
    print(f'{out_p}: units={len(pairs)} with_zh={matched} blocks={len(merged)}')
    return merged


if __name__ == '__main__':
    build(*sys.argv[1:6])
