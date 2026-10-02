"""Render the site owner's proofread edition (out/<ep>.auth.json) into dist/.

`out/<ep>.auth.json` is the authoritative text layer: the webmaster's own line-by-line
edition, mapped back onto the raw OCR indices so every line keeps its provenance (`ocr`).
Wording, English, and sectioning all come from the human edition — nothing in `dist/` is
hand-edited, this module regenerates it.

Layout reproduces the uploaded files line-for-line. Two headers are *derived*, not copied:
the 目錄 per-section counts and the 高頻術語 term list are recomputed from the body,
because the copies shipped in the uploads were inherited from the pre-merge build and no
longer matched their own text (they summed to 566/574 while the edition body has 557/533).

Usage:  python3 pipeline/render_auth.py out/shang.auth.json <stem> <meta> <title> [上|下]
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
paths.syspath()
import build_doc as B
import deliver as D
from opencc import OpenCC

T2S = OpenCC('t2s')

# The Markdown keeps the edition's own heading; the HTML page carries the course name
# so a browser tab reads as the school unit rather than just the film title.
HTML_PREFIX = '高二上選修生物一 · '


def fmt(sec):
    return f'{int(sec // 60):02d}:{int(sec % 60):02d}'


def load_auth(p):
    d = json.load(open(p, encoding='utf-8'))
    lines = d['lines']
    head = {'title': d.get('title', ''), 'meta': d.get('meta', '')}
    secs = {s['n']: s for s in d['sections']}
    groups = []
    for ln in lines:
        if not groups or groups[-1][0] != ln['sec']:
            groups.append((ln['sec'], []))
        groups[-1][1].append(ln)
    # section ranges come from the edition itself; fall back to line times
    out = []
    for n, g in groups:
        s = secs.get(n, {})
        start = s.get('s', g[0]['s'])
        end = s.get('e', g[-1]['e'])
        title = s.get('title', f'第{n}段')
        out.append((n, title, start, end, g))
    return out, lines, head


def render_md(groups, lines, path, title, meta, sub):
    """Emit the edition. Layout matches src/<ep>.md line-for-line; the two derived headers
    (目錄 counts and 高頻術語) are recomputed from the body, because the copies in the
    uploads were inherited from the pre-merge build and no longer matched their own text."""
    L = [f'# {title}', '']
    L += [f'**原片**：{meta}',
          '**校訂狀態**：全量專業校訂。已修復 OCR 殘句、畫面雜訊與錯譯；'
          '補全並修正原標記為 `≈` 的推定翻譯；優化中英文對齊與專有名詞。',
          '**產出方式**：中文取自影片燒錄字幕，經 PP-OCRv5 辨識並人工精校；'
          '英文為原聲逐字稿，由 Whisper 辨識並修復亂碼；兩者按時間軸對齊，依場景斷點分段。', '']
    L += ['## 目錄']
    for n, name, st, en_, g in groups:
        L.append(f'- {name} `{fmt(st)}–{fmt(en_)}`（{len(g)} 句）')
    g = B.glossary([{'t': ln['zh']} for ln in lines])
    if g:
        L += ['', '## 高頻術語', '', ' · '.join(f'{k}（{v}）' for k, v in g)]
    L += ['']
    for n, name, st, en_, blk in groups:
        L += ['---', '', f'### {n}. {name}', f'`{fmt(st)}–{fmt(en_)}`', '']
        for ln in blk:
            L.append(f'**{fmt(ln["s"])}**')
            L.append(f'中：{ln["zh"]}')
            if ln['en']:
                L.append(f'EN: {ln["en"]}')
            L.append('')
    txt = '\n'.join(L).rstrip('\n') + '\n'
    open(path, 'w', encoding='utf-8').write(txt)
    print(f'{path}: lines={len(lines)} sections={len(groups)} toc-sum={sum(len(b) for *_, b in groups)}')


def srt_ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'.replace('.', ',')


def write_zh_srt(lines, path):
    with open(path, 'w', encoding='utf-8') as f:
        for i, ln in enumerate(lines, 1):
            f.write(f'{i}\n{srt_ts(ln["s"])} --> {srt_ts(ln["e"])}\n{ln["zh"]}\n\n')


def write_en_srt(lines, path):
    with open(path, 'w', encoding='utf-8') as f:
        n = 0
        for ln in lines:
            if not ln['en']:
                continue
            n += 1
            f.write(f'{n}\n{srt_ts(ln["s"])} --> {srt_ts(ln["e"])}\n{ln["en"]}\n\n')
    return n


def write_html(groups, lines, path, title, meta, stats, sub=''):
    esc = __import__('html').escape
    parts = ['<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{esc(title)}</title><style>{D.CSS}</style></head><body><div class="wrap">',
             f'<h1>{esc(title)}{"（"+esc(sub)+"）" if sub else ""}</h1>'
             f'<div class="meta">{esc(meta)}</div>',
             '<div class="note"><b>校訂狀態</b>：全量專業校訂，中文、英文與分段皆以站長'
             '親自校訂的版本為準（`out/*.auth.json`）。已修復 OCR 殘句、畫面雜訊與錯譯，'
             '並修正專有名詞。<div class="pills">'
             + ''.join(f'<span class="pill">{esc(k)} {esc(str(v))}</span>' for k, v in stats.items())
             + '</div></div>',
             '<input id="q" placeholder="搜尋字幕…" style="width:100%;padding:11px 14px;'
             'border:1px solid var(--line);border-radius:10px;font-size:15px;'
             'background:var(--card);margin:4px 0 0">',
             '<div class="meta" style="margin:8px 0 0">顯示 <span id="cnt">全部</span> · '
             '<button id="tg" style="border:1px solid var(--line);background:var(--card);'
             'border-radius:8px;padding:3px 10px;font-size:13px;cursor:pointer">轉簡體</button></div>',
             '<div class="toc"><b style="font-size:14px">目錄</b>']
    for n, name, st, en_, g in groups:
        parts.append(f'<a href="#s{n}">{n}. {esc(name)} '
                     f'<span class="t">{fmt(st)}–{fmt(en_)} · {len(g)} 句</span></a>')
    parts.append('</div>')
    gloss = B.glossary([{'t': l['zh']} for l in lines])
    if gloss:
        parts.append('<h2 id="glos">高頻術語</h2><div class="glos">')
        parts += [f'<span>{esc(k)} <b>{v}</b></span>' for k, v in gloss]
        parts.append('</div>')
    for n, name, st, en_, blk in groups:
        parts.append(f'<h2 id="s{n}">{n}. {esc(name)}</h2>')
        parts.append(f'<div class="meta">{fmt(st)}–{fmt(en_)}</div>')
        for ln in blk:
            parts.append('<div class="sub">')
            parts.append(f'<div class="ts">{fmt(ln["s"])}–{fmt(ln["e"])}</div>')
            parts.append(f'<div class="z"><span class="tr">{esc(ln["zh"])}</span>'
                         f'<span class="sp" hidden>{esc(T2S.convert(ln["zh"]))}</span></div>')
            if ln['en']:
                parts.append(f'<div class="e">{esc(ln["en"])}</div>')
            parts.append('</div>')
    parts.append(f'</div><script>{D.JS}</script></body></html>')
    open(path, 'w', encoding='utf-8').write('\n'.join(parts))
    print(f'{path}: html written')


def main(auth_p, stem, meta=None, title=None, sub=''):
    groups, lines, head = load_auth(auth_p)
    meta = meta or head['meta']
    title = title or head['title']
    html_title = f'{HTML_PREFIX}{title}'
    stats = {'中文字幕': f'{len(lines)} 行',
             '中文字數': sum(len(l['zh']) for l in lines),
             '英文行': f'{sum(1 for l in lines if l["en"])} 行',
             '英文詞數': len(re.findall(r"[A-Za-z][A-Za-z0-9'\-]*",
                                       ' '.join(l['en'] for l in lines))),
             '段落': len(groups)}
    write_zh_srt(lines, f'{stem}.zh.srt')
    write_en_srt(lines, f'{stem}.en.srt')
    render_md(groups, lines, f'{stem}.md', title, meta, sub)
    write_html(groups, lines, f'{stem}.html', html_title, meta, stats, sub)
    print(f'{stem}: {stats}')


if __name__ == '__main__':
    main(*sys.argv[1:6])
