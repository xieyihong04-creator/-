"""Emit deliverables from aligned subtitle data: Markdown, SRT, and a single-file HTML."""
import json, os, re, sys, html
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_doc as B
from opencc import OpenCC

T2S = OpenCC('t2s')


def srt_ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'.replace('.', ',')


def write_srt(zh, path):
    with open(path, 'w', encoding='utf-8') as f:
        for i, z in enumerate(zh, 1):
            f.write(f'{i}\n{srt_ts(z["s"])} --> {srt_ts(z["e"])}\n{z["t"]}\n\n')


def write_en_srt(en, path):
    with open(path, 'w', encoding='utf-8') as f:
        for i, e in enumerate(en, 1):
            f.write(f'{i}\n{srt_ts(e["s"])} --> {srt_ts(e["e"])}\n{e["t"].strip()}\n\n')


CSS = """
:root{--bg:#f7f6f3;--fg:#1c1b1a;--mut:#6b6862;--line:#e0ddd6;--acc:#8a5a2b;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang TC","PingFang SC",
 "Microsoft JhengHei","Noto Sans CJK TC",sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:28px 20px 90px}
h1{font-size:27px;line-height:1.4;margin:0 0 6px}
h2{font-size:21px;margin:38px 0 4px;padding-top:14px;border-top:1px solid var(--line)}
.meta{color:var(--mut);font-size:14px;margin-bottom:16px}
.note{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:13px 16px;font-size:14px;color:var(--mut);margin:16px 0}
.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:16px 20px;margin:18px 0}
.toc a{display:block;padding:5px 0;color:var(--fg);text-decoration:none;font-size:15px;
 border-bottom:1px dashed var(--line)}
.toc a:last-child{border-bottom:0}
.toc .t{color:var(--mut);font-variant-numeric:tabular-nums;font-size:13px}
.glos{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0 22px}
.glos span{background:var(--card);border:1px solid var(--line);border-radius:14px;
 padding:3px 11px;font-size:13.5px}
.glos b{color:var(--acc);font-weight:600}
.sub{padding:11px 0;border-bottom:1px solid var(--line)}
.sub:last-child{border-bottom:0}
.ts{color:var(--acc);font:12.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
 letter-spacing:.02em}
.z{font-size:17px;margin:3px 0}
.e{font-size:14.5px;color:var(--mut);margin:2px 0 0}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 0}
.pill{background:var(--card);border:1px solid var(--line);border-radius:16px;
 padding:4px 12px;font-size:13px;color:var(--mut)}
@media(max-width:600px){body{font-size:15.5px}.z{font-size:16.5px}h1{font-size:23px}}
"""

JS = """
const q=document.getElementById('q'),rows=[...document.querySelectorAll('.sub')],
hs=[...document.querySelectorAll('h2[id]')];
q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();let n=0;
 rows.forEach(r=>{const ok=!v||r.textContent.toLowerCase().includes(v);
 r.style.display=ok?'':'none';if(ok)n++;});
 document.getElementById('cnt').textContent=v?n+' 句':'全部';
 hs.forEach(h=>{let s=0,el=h.nextElementSibling;
  while(el&&el.tagName!=='H2'){if(el.classList.contains('sub')&&el.style.display!=='none')s++;
   el=el.nextElementSibling;}
  h.style.display=(v&&s===0)?'none':'';});});
let simp=false;const tg=document.getElementById('tg');
tg&&tg.addEventListener('click',()=>{simp=!simp;
 document.querySelectorAll('.tr').forEach(e=>e.hidden=simp);
 document.querySelectorAll('.sp').forEach(e=>e.hidden=!simp);
 tg.textContent=simp?'轉繁體':'轉簡體';
 try{localStorage.setItem('sub-simp',simp?'1':'0');}catch(e){}});
try{if(localStorage.getItem('sub-simp')==='1')tg.click();}catch(e){}
"""


def write_html(pairs, merged, title, meta, path, stats):
    esc = html.escape
    parts = ['<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">',
             f'<h1>{esc(title)}</h1><div class="meta">{esc(meta)}</div>',
             '<div class="note"><b>產出方式</b>：中文取自影片燒錄字幕，由 PP-OCRv5 辨識'
             '（mobile 初讀、server 校訂）並依畫面去重；英文為原聲逐字稿，由 Whisper '
             'distil-large-v3 辨識。兩者按時間軸對齊，再依場景斷點分段。中文行首時間後面的 '
             '「≈」代表该行辨識信心較低（原片字幕下緣被裁切），可能有個別錯字。'
             '<div class="pills">'
             + ''.join(f'<span class="pill">{esc(k)} {esc(str(v))}</span>'
                       for k, v in stats.items())
             + '</div></div>',
             '<input id="q" placeholder="搜尋字幕…" style="width:100%;padding:11px 14px;'
             'border:1px solid var(--line);border-radius:10px;font-size:15px;'
             'background:var(--card);margin:4px 0 0">',
             '<div class="meta" style="margin:8px 0 0">顯示 <span id="cnt">全部</span> · '
             '<button id="tg" style="border:1px solid var(--line);background:var(--card);'
             'border-radius:8px;padding:3px 10px;font-size:13px;cursor:pointer">轉簡體</button></div>',
             '<div class="toc"><b style="font-size:14px">目錄</b>']
    for i, (name, b) in enumerate(merged, 1):
        parts.append(f'<a href="#s{i}">{i}. {esc(name)} '
                     f'<span class="t">{B.fmt_ts(b[0][0]["s"])}–{B.fmt_ts(b[-1][0]["e"])}'
                     f' · {len(b)} 句</span></a>')
    parts.append('</div>')
    g = B.glossary([z for z, _ in pairs])
    if g:
        parts.append('<h2 id="glos">高頻術語</h2><div class="glos">')
        parts += [f'<span>{esc(k)} <b>{v}</b></span>' for k, v in g]
        parts.append('</div>')
    for i, (name, b) in enumerate(merged, 1):
        parts.append(f'<h2 id="s{i}">{i}. {esc(name)}</h2>')
        parts.append(f'<div class="meta">{B.fmt_ts(b[0][0]["s"])}–{B.fmt_ts(b[-1][0]["e"])}</div>')
        for z, e in b:
            simp = T2S.convert(z['t'])
            warn = z.get('c', 1) < 0.80
            parts.append('<div class="sub">')
            parts.append(f'<div class="ts">{B.fmt_ts(z["s"])}–{B.fmt_ts(z["e"])}'
                         + ('　≈' if warn else '') + '</div>')
            parts.append(f'<div class="z"><span class="tr">{esc(z["t"])}</span>'
                         f'<span class="sp" hidden>{esc(simp)}</span></div>')
            if e:
                parts.append(f'<div class="e">{esc(e)}</div>')
            parts.append('</div>')
    parts.append(f'</div><script>{JS}</script></body></html>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    print(f'{path}: html written')


def main(zh_p, en_p, stem, title, meta):
    zh = B.zh_lines(B.load(zh_p))
    en = B.en_lines(B.load(en_p)) if en_p != '-' else []
    pairs, merged = B.sections(zh_p, en_p)

    nchars = sum(len(z['t']) for z in zh)
    write_srt(zh, f'{stem}.zh.srt')
    if en:
        write_en_srt(en, f'{stem}.en.srt')
    B.build(zh_p, en_p, f'{stem}.md', title, meta)
    # English coverage: every ASR word should appear in the doc, in order. Sentence
    # splitting means whole-segment substring checks no longer hold, so count words.
    dw = ' '.join(e for _, e in pairs if e).split()
    aw = ' '.join(x['t'] for x in en).split()
    shown_en = min(len(dw), len(aw))
    both = sum(1 for z, e in pairs if z['t'] and e)
    write_html(pairs, merged, title, meta, f'{stem}.html',
               {'中文字幕': f'{len(zh)} 句', '中文字數': nchars,
                '對照單元': len(pairs),
                '英文句': f'{len(en)}（掛在 {both} 行）' if en else '—',
                '英文收錄': f'{shown_en}/{len(aw)} 詞' if en else '—',
                '段落': len(merged)})
    print(f'{stem}: {len(zh)} zh ({nchars} chars), {len(en)} en ({shown_en}/{len(aw)} words), '
          f'{len(pairs)} units, {both} annotated rows, {len(merged)} sections')


if __name__ == '__main__':
    from collections import Counter
    main(*sys.argv[1:6])
