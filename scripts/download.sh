#!/bin/bash
# Fetch the two episode videos from this repo's GitHub Releases into media/.
#
#   GH_TOKEN=ghp_xxx bash scripts/download.sh
#
# The token is only read from the environment and never written to a file.
set -euo pipefail
: "${GH_TOKEN:?set GH_TOKEN to a GitHub token with repo scope}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${REPO:-xieyihong04-creator/-}"
OUT="$ROOT/media"
mkdir -p "$OUT"

# release asset ids, listed by: GET /repos/<REPO>/releases
for pair in "603228566:shang" "603233491:xia"; do
  id=${pair%%:*}; name=${pair##*:}
  if [ -s "$OUT/$name.mp4" ]; then
    echo "$name.mp4 already present, skipping"
    continue
  fi
  curl -sL --fail \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/octet-stream" \
    -o "$OUT/$name.mp4.part" \
    -w "$name  http=%{http_code}  size=%{size_download}  avg=%{speed_download}B/s\n" \
    "https://api.github.com/repos/$REPO/releases/assets/$id"
  mv "$OUT/$name.mp4.part" "$OUT/$name.mp4"
done
echo "videos in $OUT"
