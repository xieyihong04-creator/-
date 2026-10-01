#!/bin/bash
# Download the OCR + ASR models used by the pipeline (about 1.6 GB total).
#
#   bash scripts/setup_models.sh
#
# URLs and byte-for-byte equivalence were verified on 2026-10-01: the mobile ONNX here
# returns the same readings as the copy the transcripts were produced with, and
# ppocrv5_dict.txt is identical (18383 lines).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OCR="$ROOT/models/ocr"
ASR="$ROOT/models/distil-v3"
mkdir -p "$OCR" "$ASR"

B=https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master
get() { # get <url> <dest> <min-bytes>
  local url=$1 dest=$2 min=$3
  if [ -s "$dest" ] && [ "$(stat -c%s "$dest")" -ge "$min" ]; then
    echo "have $(basename "$dest")"; return
  fi
  echo "fetch $(basename "$dest") <- $url"
  curl -sL --fail --max-time 900 -o "$dest.part" "$url"
  test "$(stat -c%s "$dest.part")" -ge "$min"
  mv "$dest.part" "$dest"
}

get "$B/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx" "$OCR/rec_mobile.onnx" 16000000
get "$B/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_server.onnx" "$OCR/rec.onnx"        84000000
get "$B/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_server/ppocrv5_dict.txt" "$OCR/dict.txt" 70000

# Whisper (CTranslate2 format) — distil-large-v3: CPU-viable, RTF ~1.0
python3 - "$ASR" <<'PY'
import os, sys
from huggingface_hub import snapshot_download
dst = sys.argv[1]
if os.path.exists(os.path.join(dst, 'model.bin')):
    print('have distil-v3'); raise SystemExit
snapshot_download('Systran/faster-distil-whisper-large-v3', local_dir=dst,
                  allow_patterns=['*.json', '*.model', '*.bin', 'tokenizer*', 'vocabulary*'])
print('distil-v3 ready')
PY
echo "models ready"
