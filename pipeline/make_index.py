"""Generate the Pages entry page (index.html) from the authoritative layer.

The episode pages in `dist/` are self-contained single files, so the site needs one
landing page that links them. Everything shown here is read from `out/<ep>.auth.json`
and `src/`, which means the page cannot drift from the content it links to — it is
rebuilt by the same `scripts/build_site.sh` that runs in CI.

Deterministic on purpose: no timestamps, no commit SHAs, so rebuilding the same tree
gives byte-identical output and the Pages deploy can be verified against the repo.
"""
import json, os, re, sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
paths.syspath()

SRC = os.path.join(paths.ROOT, 'src')
DIST = os.path.join(paths.ROOT, 'dist')

# The Pages bundle carries index.html + dist/ + src/ + out/ + LICENSE. Anything else
# (README, scripts/) has to link out to the repo instead of a path that isn't deployed.
DEFAULT_REPO = 'https://github.com/xieyihong04-creator/the-human-machine-transcripts'

# Pages deployment order mirrors the reading order of the transcripts.
EPS = [('shang', '上', '47 分鐘'), ('xia', '下', '46 分鐘')]
SHEETS = [('學習單考點思維導圖.md', '考點思維導圖', '心智圖，複習前掃一遍'),
          ('學習單完整解答.md', '學習單完整解答', '上、下集逐題解答'),
          ('衛道高中學習單.pdf', '空白學習單', '學校發印原件，可列印')]


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def link(p):
    """Percent-encode a repo path for use in an href, keeping the directory part."""
    d, f = os.path.split(p.replace('\\', '/'))
    return (quote(d) + '/' if d else '') + quote(f)


def episode_stats(ep):
    d = json.load(open(os.path.join(paths.OUT, f'{ep}.auth.json'), encoding='utf-8'))
    lines = d['lines']
    en = [l['en'] for l in lines if l.get('en')]
    return {
        'title': d['title'],
        'zh': len(lines),
        'chars': sum(len(l['zh']) for l in lines),
        'en_rows': len(en),
        'en_words': len(re.findall(r"[A-Za-z][A-Za-z0-9'\-]*", ' '.join(en))),
        'sections': len(d['sections']),
        'span': f"{lines[0]['s'] / 60:.0f}–{lines[-1]['e'] / 60:.0f} 分鐘有字幕",
    }


def file_row(label, sub, path, kind):
    return (f'<a class="file" href="{link(path)}">'
            f'<span class="k {kind}">{esc(kind)}</span>'
            f'<span class="fn">{esc(label)}</span>'
            f'<span class="fs">{esc(sub)}</span></a>')


CSS = ''':root{--bg:#f7f6f3;--fg:#1c1b1a;--mut:#6b6862;--line:#e0ddd6;--acc:#8a5a2b;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang TC","PingFang SC",
 "Microsoft JhengHei","Noto Sans CJK TC",sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:32px 20px 90px}
h1{font-size:28px;line-height:1.4;margin:0 0 6px}
h2{font-size:20px;margin:36px 0 4px;padding-top:14px;border-top:1px solid var(--line)}
.lede{color:var(--mut);font-size:15px;margin:0 0 8px}
.cards{display:grid;gap:12px;margin:18px 0 4px}
@media(min-width:640px){.cards{grid-template-columns:1fr 1fr}}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;
 padding:16px 18px;text-decoration:none;color:inherit}
.card:hover{border-color:var(--acc)}
.card .t{font-size:19px;font-weight:600}
.card .n{color:var(--mut);font-size:13.5px;margin:2px 0 10px}
.stats{display:flex;flex-wrap:wrap;gap:6px}
.pill{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:2px 10px;
 font-size:12.5px;color:var(--mut);font-variant-numeric:tabular-nums}
.pill b{color:var(--acc);font-weight:600}
.files{display:grid;gap:8px;margin:14px 0 4px}
@media(min-width:640px){.files{grid-template-columns:1fr 1fr}}
.file{display:flex;align-items:baseline;gap:9px;background:var(--card);
 border:1px solid var(--line);border-radius:10px;padding:10px 13px;
 text-decoration:none;color:inherit}
.file:hover{border-color:var(--acc)}
.k{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
 border:1px solid var(--line);border-radius:5px;padding:1px 5px;color:var(--mut)}
.k.html,.k.md{color:var(--acc);border-color:var(--acc)}
.fn{font-size:15px;font-weight:600}
.fs{color:var(--mut);font-size:12.5px;margin-left:auto;text-align:right}
.note{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:14px 17px;font-size:14px;color:var(--mut);margin:26px 0 0}
.note a{color:var(--acc)}
nav.top{display:flex;gap:14px;flex-wrap:wrap;font-size:14px;margin:14px 0 0}
nav.top a{color:var(--acc);text-decoration:none}
nav.top a:hover{text-decoration:underline}'''


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else paths.ROOT
    repo = (sys.argv[2] if len(sys.argv) > 2 else DEFAULT_REPO).rstrip('/')
    os.makedirs(out_dir, exist_ok=True)

    P = []
    P.append('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">')
    P.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    P.append('<title>高二上選修生物一 · 奇妙的人體機器（中英對照逐字稿）</title>')
    P.append('<meta name="description" content="National Geographic《The Human Machine》'
             '兩集中英對照、分段逐字稿與學習單，附完整 OCR／ASR 管線。">')
    P.append(f'<style>{CSS}</style></head><body><div class="wrap">')
    P.append('<h1>奇妙的人體機器 · 影片學習</h1>')
    P.append('<p class="lede">National Geographic《The Human Machine》兩集，'
             '中英對照、主題分段。中文經 PP-OCRv5 辨識與<strong>兩道人工校訂</strong>，'
             '英文為原聲逐字稿經人工修復。每段可全文搜尋，並附一鍵繁簡切換。</p>')
    P.append('<nav class="top">')
    for path, lbl in [(f'{repo}/blob/main/README.md', 'Repo 與管線說明'),
                      (link('LICENSE'), '授權'),
                      (f'{repo}/blob/main/scripts/run_all.sh', '完整重建腳本'),
                      (repo, '原始 Repo')]:
        P.append(f'<a href="{path}">{esc(lbl)}</a>')
    P.append('</nav>')

    P.append('<h2>兩集逐字稿</h2><div class="cards">')
    for ep, cn, dur in EPS:
        s = episode_stats(ep)
        stem = f'dist/奇妙的人體機器_{cn}'
        P.append(f'<a class="card" href="{link(stem + ".html")}">'
                 f'<div class="t">（{cn}）{esc(re.sub("（上）|（下）", "", s["title"]) or "奇妙的人體機器")}</div>'
                 f'<div class="n">{esc(dur)}｜{esc(s["span"])}</div><div class="stats">'
                 f'<span class="pill">中文 <b>{s["zh"]}</b> 行</span>'
                 f'<span class="pill">英文 <b>{s["en_rows"]}</b> 行／<b>{s["en_words"]}</b> 詞</span>'
                 f'<span class="pill"><b>{s["sections"]}</b> 段</span></div></a>')
    P.append('</div>')

    P.append('<h2>單一檔案下載</h2><div class="files">')
    for ep, cn, dur in EPS:
        stem = f'dist/奇妙的人體機器_{cn}'
        P.append(file_row(f'（{cn}）Markdown', '貼進 Notion／Obsidian', stem + '.md', 'md'))
        P.append(file_row(f'（{cn}）HTML', '離線單檔，瀏覽器直接開', stem + '.html', 'html'))
        P.append(file_row(f'（{cn}）中文字幕', '.srt，匯入播放器', stem + '.zh.srt', 'srt'))
        P.append(file_row(f'（{cn}）英文字幕', '.srt，含時間軸', stem + '.en.srt', 'srt'))
    P.append(file_row('結構化資料', 'out/*.json：時間戳、辨識信心、OCR 序號追溯',
                      'out/shang.auth.json', 'json'))
    P.append(file_row('校訂稿原始版本', 'src/shang.md｜src/xia.md（最終權威）',
                      'src/shang.md', 'md'))
    P.append('</div>')

    P.append('<h2>學習單</h2><div class="files">')
    for f, label, sub in SHEETS:
        kind = 'pdf' if f.endswith('.pdf') else 'md'
        P.append(file_row(label, sub, 'src/' + f, kind))
    P.append('</div>')

    P.append('<div class="note">兩支影片、燒錄字幕與旁白的著作財產權仍屬 National Geographic，'
             '本站文字僅供本課程學習用途，完整重製或再散布請改從原影片取得授權（見 '
             f'<a href="{link("LICENSE")}">LICENSE</a>）。影片本身不在此站提供。<br>'
             f'本頁與所有文字產物皆由 <a href="{repo}/blob/main/scripts/build_site.sh">'
             'scripts/build_site.sh</a> 從 <code>src/</code> 與 <code>out/</code> 自動重建，'
             '並在建置時檢查 <code>dist/</code> 是否仍與重新渲染的結果逐位元相同。</div>')
    P.append('</div></body></html>')

    html_s = '\n'.join(P)
    path = os.path.join(out_dir, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_s)
    print(f'{path}: index written ({len(html_s)} bytes)')


if __name__ == '__main__':
    main()
