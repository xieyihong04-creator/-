# 高二上選修生物一「奇妙的人體機器」影片學習

National Geographic《The Human Machine》兩集影片的**中英對照、分段整理文字稿**，
以及把它做出來的完整管線。

| 集數 | 片長 | 中文字幕 | 英文 | 段落 |
|---|---|---|---|---|
| 上 | 47 分鐘 | 557 行 | 382 行／4,856 詞 | 23 段 |
| 下 | 46 分鐘 | 533 行 | 488 行／5,388 詞 | 20 段 |

- **文字來源**：`dist/` 的中文、英文與分段一律以**站長本人逐行校訂過的版本**（`src/shang.md`、
  `src/xia.md`）為準；管線不產出文字內容，只負責把它還原成 HTML / Markdown / SRT
- **中文**：影片燒錄字幕經 PP-OCRv5 辨識（mobile 初讀 + server 逐行校訂），再經兩道人工校訂
- **英文**：原聲旁白逐字稿（Whisper distil-large-v3），經人工修正專有名詞與亂碼，
  並移除非旁白的現場對白，因此不再宣稱「ASR 詞數全數收錄」
- **對齊與分段**：段落標題與範圍沿用校訂稿自己的切分；時間軸由原始 OCR 行還原（含次分鐘精度）

## 直接閱讀（不需安裝）

| 檔案 | 用途 |
|---|---|
| [上 · HTML](dist/奇妙的人體機器_上.html)｜[下 · HTML](dist/奇妙的人體機器_下.html) | 單檔頁面：全文搜尋、目錄跳轉、一鍵繁簡切換。下載後用瀏覽器開啟即可 |
| [上 · Markdown](dist/奇妙的人體機器_上.md)｜[下 · Markdown](dist/奇妙的人體機器_下.md) | 可貼進 Notion / Obsidian 等筆記軟體 |
| `dist/*.zh.srt`｜`dist/*.en.srt` | 標準字幕檔，可匯入播放器或剪輯軟體 |
| `out/*.json` | 帶時間戳與辨識信心的結構化資料，方便自行再處理 |
| [學習單（空白）](src/衛道高中學習單.pdf)｜[考點思維導圖](src/學習單考點思維導圖.md)｜[完整解答](src/學習單完整解答.md) | 自學與課堂用，非管線產物，由站長提供 |

每段結構為「主題 · 第N段」→ 逐行「時間 / 中文 / 對應英文」。英文只在校訂稿該行有英文時才出現。
Markdown 與 HTML 開頭的「高頻術語」為便於複習所自動統計，非校訂稿內容。

## 校訂層

辨識出來的中文不一定對，因此文字經過**兩道**校訂，兩道都以可稽核的記錄保存，不直接改產物：

**第一道 — 機器產出的逐行校訂**（`out/*.zh.fix.json`）

| 檔案 | 內容 |
|---|---|
| `out/shang.zh.fix.json` | 上集 327 筆：改寫 248 行、剔除 77 行 OCR 殘句與畫面雜訊，另有 2 筆只作定位錨點（原始 643 → 566 行） |
| `out/xia.zh.fix.json` | 下集 74 筆：改寫 30 行、剔除 7 行，另有 37 筆只作定位錨點（原始 581 → 574 行） |
| `pipeline/make_fix_tables.py` | 上述兩檔的來源（FIX／QUERY 對照表）與生成器，重跑可逐位元重建 |

每筆以**雙錨點**定位：`expect`（該行校訂前的文字）與 `at`（該行起點的整數秒）。`build_doc.apply_fixes`
兩項都要核對通過才套用，所以重跑 OCR 造成字幕合併、拆分或索引位移時，建置會直接報錯中止，
而不是把訂正無聲地蓋到錯誤的行上。

**第二道 — 站長親自校訂版**（`src/shang.md`、`src/xia.md`，為最終權威）

| 檔案 | 內容 |
|---|---|
| `src/shang.md`、`src/xia.md` | 站長本人對兩集的全量逐行校訂，含二次改寫、英文專有名詞修正與自行切分 |
| `out/shang.auth.json`、`out/xia.auth.json` | 由 `src/` 生成的權威文字層：逐字保留校訂稿的中英文與分段，並把時間還原為秒級（起點取原始 OCR 的次分鐘精度、終點取該行字幕結束時間），每行以 `ocr` 欄記錄它對應的原始 OCR 序號 |
| `pipeline/make_auth_tables.py` | 生成上述權威層。以序列對齊把校訂稿對映回原始序號，內含斷言：中文與英文必須逐行等於 `src/`、時間單調遞增、566 / 574 個未剔除的 OCR 行全數有追溯，任一不符即中止 |
| `pipeline/render_auth.py` | 由權威層產出 `dist/*`。版面與 `src/` 逐行相同，僅「目錄句數」與「高頻術語」依內文重算（上傳稿的這兩處沿用合併前的舊數字，與其自身內文不符） |

`pipeline/deliver.py` 保留為第一道校訂的產出路徑，必要時可比對兩版差異，但已不是 `dist/` 的來源。

## 已知限制

**上集的字幕下緣被原片裁掉**（480p 來源，字幕位在 y≈459–480）。缺了下緣筆畫後，「展」看似「屏」、「萬」看似「革」，即使換用更大的辨識模型也會錯。因此另做兩層補救：

1. `crossfix.py` 以「下」集的高信心結果修正兩集重播的同一段開頭字幕。
2. `build_doc.py` 依英文旁白與上下文修正系統性錯讀（`10革次` → `10萬次`、`雨萬次` → `兩萬次`、`什麻` → `什麼`），並把辨識結果中混入的簡體字形統一回復為繁體。

第一道校訂結束後，仍帶有 `≈`（信心偏低、需人工比對）標記的行是上集 13 行、下集 1 行。
第二道校訂逐行改定後，`dist/` 的內文已沒有任何 `≈` 行標記，只剩開頭校訂狀態文字裡對該標記的說明；
來源畫質造成的不確定已由人工判定取代，不再需要對照影片複查可疑行。若重跑 OCR 後建置因錨點報錯，
請更新訂正表（`pipeline/make_fix_tables.py`）並重新生成權威層（`pipeline/make_auth_tables.py`），
而不是放寬檢查。

## 管線

```
media/*.mp4 ─[1] OCR 燒錄字幕─> out/*.zh.json ─[2] server 重讀弱行─┐
        │                                                         ├─[3] 清整併 ─[4] 交叉校正
        └──────[5] ASR 英文原聲──────> out/*.en.json ─────────────┘        │
                                                                          [6] 對齊+分段 ──> 第一道草稿
                                                                                    │ 站長逐行修訂
src/{shang,xia}.md（最終權威） ─[7] make_auth_tables─> out/*.auth.json ─[8] render_auth─> dist/*
```

[6]（`build_doc.py`／`deliver.py`）產出的是供站長修訂的第一道草稿，`scripts/run_all.sh` 已不執行這一步，
需要比對兩版差異時才手動跑；`dist/` 一律由 [8] 從權威層重建。改文字請改 `src/`，不要改 `dist/`。

| 腳本 | 做什麼 |
|---|---|
| `pipeline/paths.py` | 路徑解析（可用 `HM_ROOT` 指定模型／影片位置） |
| `pipeline/ocrsub.py` | PP-OCRv5 ONNX 識別器，含 mobile / server 兩款與 CTC 解碼 |
| `pipeline/subs.py` | 逐幀抽字幕：白字列偵測 → mobile 初讀 → 依文字去重分組 → 弱行存成裁圖 |
| `pipeline/esc_pass2.py` | 弱行交 server 模型重讀：獨立程序、可中斷續跑、依像素雜湊去重 |
| `pipeline/postprocess_subs.py`、`clean_zh.py` | 併合淡入碎句與重複列、濾除浮水印與雜訊 |
| `pipeline/crossfix.py` | 以另一集高信心同句修正被裁切造成的錯讀 |
| `pipeline/build_doc.py` | 繁簡正規化、系統性錯字修補、套用逐行校訂表（雙錨點驗證）、英文句子時間對齊、主題分類與分段；`render_auth.py` 亦沿用它的字數統計與時間格式 |
| `pipeline/make_fix_tables.py` | 由 FIX／QUERY 對照表生成 `out/*.zh.fix.json` 訂正表 |
| `pipeline/make_auth_tables.py` | 把 `src/*.md` 對映回原始 OCR 序號，生成權威層 `out/*.auth.json`（含逐行追溯與一致性斷言） |
| `pipeline/render_auth.py` | 由權威層輸出 `dist/*`：HTML / Markdown / 中英 SRT，並重算目錄句數與高頻術語 |
| `pipeline/deliver.py` | （舊路徑）由第一道校訂的 `out/*.zh.final.json` ＋ `out/*.en.json` 輸出草稿，已不是 `dist/` 的來源 |
| `pipeline/asr.py` | faster-whisper 英文逐字稿 |
| `scripts/*.sh` | 下載影片、抓模型、跑完整管線 |

### 實作備註

- 沙箱內無 ffmpeg，改用 PyAV 直接取 Y 平面（`av==14.0.1`，新版與 faster-whisper 的 `metadata_errors` 參數不相容）。
- `large-v3` 在 CPU 上 RTF≈2.1 且會幻覺輸出，改用 `distil-large-v3`（RTF≈1.0）。
- server 模型每張輸入寬度不同，ONNX Runtime 的 memory arena 會持續長大；把重讀拆成獨立程序後穩定維持在 340 MB，否則在 7.6 GB 環境中會被 OOM 終止。

## 重現

```bash
pip install -r requirements.txt
bash scripts/setup_models.sh              # PP-OCRv5 ONNX + distil-large-v3，約 1.6 GB
GH_TOKEN=ghp_xxx bash scripts/download.sh # 從本 Repo 的 Releases 取得影片
bash scripts/run_all.sh                   # OCR → ASR → 校正 → dist/*
```

需 4 核心 CPU、8 GB RAM，兩集全跑約 1.5 小時（無 GPU）。所有腳本皆由環境變數 `GH_TOKEN` 讀取權杖，檔內不含任何金鑰。
`scripts/run_all.sh` 缺少 `opencc` 時會直接中止，不會把簡體錨點寫進訂正表後讓建置報錯。

文字與 `dist/` 的重現不需要重跑 OCR：以 clean clone 依序執行
`pipeline/make_fix_tables.py`（驗證 `git status` 乾淨）→ `pipeline/make_auth_tables.py` → `pipeline/render_auth.py`（上下集各一），
即可由 `out/*.json`、`out/*.zh.fix.json` 與 `src/*.md` 逐位元重建 `dist/*` 全部 8 個檔案，已驗證一致。
重跑 OCR 後若字幕行位移，`apply_fixes` 會因錨點不符而中止，需同步更新訂正表；`make_auth_tables.py`
的斷言（中英文逐行等於 `src/`、時間單調、OCR 行全數有追溯）任一不符同樣會中止。

## 授權

管線程式碼採 MIT（見 [LICENSE](LICENSE)）；兩支影片、燒錄字幕與旁白逐字稿的著作財產權
仍屬 National Geographic，不在 MIT 授權範圍內。詳見 LICENSE 的三類區分。

Repo 公開後，Releases 內的兩支影片即為所有人可下載之狀態。目前兩個 Release 皆維持 **draft**
（僅站長與協作者可見），公開 Repo 不會讓影片被一般訪客下載；後續若需調整請直接改這兩個
Release，不要把它設為 latest。
