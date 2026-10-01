# 高二上選修生物一「奇妙的人體機器」影片學習

National Geographic《The Human Machine》兩集影片的**中英對照、分段整理文字稿**，
以及把它做出來的完整管線。

| 集數 | 片長 | 中文字幕 | 英文逐字稿 | 段落 |
|---|---|---|---|---|
| 上 | 47 分鐘 | 566 行 | 493 段 | 27 段 |
| 下 | 46 分鐘 | 574 行 | 579 段 | 20 段 |

- **中文**：直接取自影片燒錄字幕，PP-OCRv5 辨識（mobile 初讀 + server 逐行校訂），**再逐行人工校訂**
- **英文**：原聲旁白逐字稿，Whisper distil-large-v3（CPU int8）
- **對齊**：依時間軸掛靠，英文以句子為單位分散到對應中文行；兩集英文各 5145 / 5688 詞全數收錄
- **分段**：依場景斷點切段，再依詞頻自動標主題（視覺／聽覺／神經／骨骼／循環／消化…）

## 直接閱讀（不需安裝）

| 檔案 | 用途 |
|---|---|
| [上 · HTML](dist/奇妙的人體機器_上.html)｜[下 · HTML](dist/奇妙的人體機器_下.html) | 單檔頁面：全文搜尋、目錄跳轉、一鍵繁簡切換。下載後用瀏覽器開啟即可 |
| [上 · Markdown](dist/奇妙的人體機器_上.md)｜[下 · Markdown](dist/奇妙的人體機器_下.md) | 可貼進 Notion / Obsidian 等筆記軟體 |
| `dist/*.zh.srt`｜`dist/*.en.srt` | 標準字幕檔，可匯入播放器或剪輯軟體 |
| `out/*.json` | 帶時間戳與辨識信心的結構化資料，方便自行再處理 |

每段結構為「主題 · 第N段」→ 逐行「時間 / 中文 / 對應英文」。行首時間後的 `≈` 表示該行字幕在原片裡被裁切、只能依英文旁白推定，建議比對影片。

## 校訂層

辨識出來的中文不一定對，因此 `dist/` 的最後一道是**逐行人工校訂**，以訂正表記錄，不直接改產物：

| 檔案 | 內容 |
|---|---|
| `out/shang.zh.fix.json` | 上集 327 筆：改寫 248 行、剔除 77 行 OCR 殘句與畫面雜訊（全文 643 → 566 行） |
| `out/xia.zh.fix.json` | 下集 74 筆：改寫 30 行、剔除 7 行，另有 37 筆只作定位錨點（全文 581 → 574 行） |
| `pipeline/make_fix_tables.py` | 訂正表的來源（FIX／QUERY 對照表）與生成器，重跑可逐位元產生上述兩檔 |

每筆以**雙錨點**定位：`expect`（該行校訂前的文字）與 `at`（該行起點的整數秒）。`build_doc.apply_fixes`
兩項都要核對通過才套用，所以重跑 OCR 造成字幕合併、拆分或索引位移時，建置會直接報錯中止，
而不是把訂正無聲地蓋到錯誤的行上。剔除（`drop`）發生在英文對齊之前，掛在殘句上的英文會重新
接到相鄰行，因此兩集英文詞彙覆蓋仍為 5145 / 5688（全數收錄）。

## 已知限制

**上集的字幕下緣被原片裁掉**（480p 來源，字幕位在 y≈459–480）。缺了下緣筆畫後，「展」看似「屏」、「萬」看似「革」，即使換用更大的辨識模型也會錯。因此另做兩層補救：

1. `crossfix.py` 以「下」集的高信心結果修正兩集重播的同一段開頭字幕。
2. `build_doc.py` 依英文旁白與上下文修正系統性錯讀（`10革次` → `10萬次`、`雨萬次` → `兩萬次`、`什麻` → `什麼`），並把辨識結果中混入的簡體字形統一回復為繁體。

人工校訂把標記 `≈` 的行從原本的 37 行（上集）壓到 13 行，其中 5 行是字幕被裁切、依英文旁白推定的補字，
8 行是信心偏低、但校訂後與英文無衝突而保留的原讀；下集剩 1 行。這部分是來源畫質本身造成的不確定，
非管線可完全消除，建議對照影片。若重跑 OCR 後建置因錨點報錯，請更新訂正表（`pipeline/make_fix_tables.py`）
而不是放寬檢查。

## 管線

```
media/*.mp4 ─[1] OCR 燒錄字幕─> out/*.zh.json ─[2] server 重讀弱行─┐
        │                                                         ├─[3] 清整併 ─[4] 交叉校正
        └──────[5] ASR 英文原聲──────> out/*.en.json ─────────────┘        │
                                                                          [6] 對齊+分段+輸出 ──> dist/*
```

| 腳本 | 做什麼 |
|---|---|
| `pipeline/paths.py` | 路徑解析（可用 `HM_ROOT` 指定模型／影片位置） |
| `pipeline/ocrsub.py` | PP-OCRv5 ONNX 識別器，含 mobile / server 兩款與 CTC 解碼 |
| `pipeline/subs.py` | 逐幀抽字幕：白字列偵測 → mobile 初讀 → 依文字去重分組 → 弱行存成裁圖 |
| `pipeline/esc_pass2.py` | 弱行交 server 模型重讀：獨立程序、可中斷續跑、依像素雜湊去重 |
| `pipeline/postprocess_subs.py`、`clean_zh.py` | 併合淡入碎句與重複列、濾除浮水印與雜訊 |
| `pipeline/crossfix.py` | 以另一集高信心同句修正被裁切造成的錯讀 |
| `pipeline/build_doc.py` | 繁簡正規化、系統性錯字修補、套用逐行校訂表（雙錨點驗證）、英文句子時間對齊、主題分類與分段、Markdown 輸出 |
| `pipeline/make_fix_tables.py` | 由 FIX／QUERY 對照表生成 `out/*.zh.fix.json` 訂正表 |
| `pipeline/deliver.py` | 輸出 HTML / Markdown / SRT |
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
提交內的 `out/*.json` 與 `out/*.zh.fix.json` 即管線的最終產物，`pipeline/deliver.py` 由它們重建 `dist/*` 全部 8 個檔案，已驗證可逐位元重現；
`pipeline/make_fix_tables.py` 亦可由對照表重建兩份訂正表。重跑 OCR 後若字幕行位移，建置會因錨點不符而中止，需同步更新訂正表。

## 授權

管線程式碼採 MIT（見 [LICENSE](LICENSE)）；兩支影片、燒錄字幕與旁白逐字稿的著作財產權
仍屬 National Geographic，不在 MIT 授權範圍內。詳見 LICENSE 的三類區分。

Repo 公開後，Releases 內的兩支影片即為所有人可下載之狀態。若不希望如此，請先將該兩個
Release 設為 draft 或刪除，再公開 Repo。
