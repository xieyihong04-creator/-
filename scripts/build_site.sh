#!/usr/bin/env bash
# Assemble the GitHub Pages site and prove dist/ is still a pure rebuild.
#
#   bash scripts/build_site.sh            # writes _site/, verifies dist/ is reproducible
#   SKIP_DIST_CHECK=1 bash scripts/build_site.sh   # CI opt-out (there is none today)
#
# Two jobs, one script, because the site must never become a second copy of the text:
#   1. dist/ is rebuilt from out/*.auth.json + src/*.md and compared against the
#      committed bytes. A mismatch means someone hand-edited dist/ (or src/ changed
#      without re-rendering) — the site deploy stops there.
#   2. _site/ is assembled as a strict subset of the repo (index.html + dist/ + src/
#      + out/ + LICENSE), so every link on the landing page resolves to a real file.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
P="$ROOT/pipeline"
SITE="$ROOT/_site"

python3 -c "import opencc" 2>/dev/null || {
  echo "missing dependency: opencc  →  pip install opencc-python-reimplemented==0.1.7" >&2
  exit 1; }

# --- 1. dist/ must be exactly what the authoritative layer renders -------------------
if [ "${SKIP_DIST_CHECK:-0}" != 1 ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  for ep in shang xia; do
    cn=$([ "$ep" = xia ] && echo 下 || echo 上)
    python3 "$P/render_auth.py" "out/$ep.auth.json" "$TMP/奇妙的人體機器_$cn" >/dev/null
  done
  for f in "$TMP"/*; do
    base="$(basename "$f")"
    if ! cmp -s "$f" "dist/$base"; then
      echo "dist/$base differs from a fresh render of out/ + src/." >&2
      echo "dist/ is machine-built — edit src/*.md (or out/*.zh.fix.json) and re-run" >&2
      echo "scripts/run_all.sh, or:  bash scripts/build_site.sh after restoring dist/." >&2
      diff -u "dist/$base" "$f" | head -20 >&2 || true
      exit 1
    fi
  done
  echo "[build_site] dist/ verified: byte-identical to a fresh render"
fi

# --- 2. assemble _site/ --------------------------------------------------------------
# Where the source lives, for the nav links that must leave the static site.
REPO_URL="${REPO_URL:-https://github.com/xieyihong04-creator/the-human-machine-transcripts}"

rm -rf "$SITE"
mkdir -p "$SITE"
cp -R dist src out LICENSE "$SITE/"
python3 "$P/make_index.py" "$SITE" "$REPO_URL"
: > "$SITE/.nojekyll"          # we ship plain files; skip Jekyll's ignore rules

# --- 3. every local href on the landing page has to exist ----------------------------
python3 - "$SITE" <<'PY'
import os, re, sys, urllib.parse
site = sys.argv[1]
html = open(os.path.join(site, 'index.html'), encoding='utf-8').read()
bad = []
for href in re.findall(r'href="([^"]+)"', html):
    if href.startswith(('#', 'mailto:')):
        continue
    if re.match(r'^https?://', href):
        if not href.startswith('https://github.com/'):
            bad.append(('external', href))
        continue
    p = os.path.join(site, urllib.parse.unquote(href.split('#')[0]))
    if not os.path.exists(p):
        bad.append(('missing', href))
if bad:
    for kind, h in bad:
        print(f'[{kind}] {h}', file=sys.stderr)
    sys.exit(f'index.html has {len(bad)} broken link(s)')
n = len([h for h in re.findall(r'href="([^"]+)"', html) if not h.startswith('#')])
print(f'[build_site] index.html: {n} links, all resolve')
PY

echo "[build_site] $(du -sh "$SITE" | cut -f1) in $SITE"
