#!/bin/bash
# Full pipeline: OCR the burned-in Chinese subtitles, transcribe the English audio,
# clean + cross-correct, then emit dist/*.
#
#   bash scripts/run_all.sh
#
# Runs the two heavy stages sequentially on purpose. The sandbox this was built in has
# 7.6 GB RAM and no GPU; overlapping ASR with the server-model OCR re-read hit the OOM
# killer three times. Expect ~1.5 h for both episodes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
P="$ROOT/pipeline"
mkdir -p out logs
D() { echo "[$(date +%H:%M:%S)]"; }

# Pass 1 reads every sampled frame with the mobile model and dumps weak lines as crops;
# pass 2 re-reads them with the server model in its own process, resumable via the cache.
for ep in xia shang; do
  D "pass1 $ep"
  python3 -c "
import sys; sys.path.insert(0,'$P')
from subs import extract
extract('$ROOT/media/$ep.mp4', '$ROOT/out/$ep.zh.json',
        threads=4, esc_conf=0.86, crop_dir='$ROOT/crops_$ep')
" 2>&1 | tee -a logs/ocr_$ep.log

  D "pass2 $ep"
  python3 "$P/esc_pass2.py" "$ROOT/out/$ep.zh.json" "$ROOT/out/$ep.cache.json" \
          "$ROOT/out/$ep.zh.json" 2>&1 | tee -a logs/ocr_$ep.log

  D "postprocess $ep"
  python3 "$P/postprocess_subs.py" "$ROOT/out/$ep.zh.json" "$ROOT/out/$ep.zh.clean.json"
  python3 "$P/clean_zh.py" "$ROOT/out/$ep.zh.clean.json" "$ROOT/out/$ep.zh.x.json"
done

# 下 is the clean reference (avg OCR confidence 0.96, subtitles fully inside the frame),
# so only 上 is corrected against it. Title cards are skipped by crossfix, keeping the
# two "(上)" / "(下)" readings distinct.
D "crossfix"
mv out/xia.zh.x.json out/xia.zh.final.json
python3 "$P/crossfix.py" out/shang.zh.x.json out/xia.zh.final.json out/shang.zh.final.json
rm -f out/*.zh.x.json

# The line-by-line proofreading table is keyed to the caption text and start time of
# each line, so it has to be (re)generated against the final OCR output. If the OCR
# merged or split captions, apply_fixes aborts rather than rewriting the wrong line.
D "fix tables"
python3 "$P/make_fix_tables.py"

D "asr"
python3 "$P/asr.py" 2>&1 | tee -a logs/asr.log

# The authoritative text layer is the webmaster's own edition in src/<ep>.md. It is
# mapped back onto the raw OCR indices (recovering sub-minute and end times, and
# recording provenance), and everything in dist/ is rendered from that. Changing the
# wording means editing src/, not dist/.
D "authoritative edition"
python3 "$P/make_auth_tables.py"

for ep in xia shang; do
  cn=$([ $ep = xia ] && echo 下 || echo 上)
  D "deliver $ep"
  python3 "$P/render_auth.py" "out/$ep.auth.json" "dist/奇妙的人體機器_$cn"
done
D "done: dist/"
