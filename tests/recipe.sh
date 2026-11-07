#!/usr/bin/env bash
# The three checks to pass before anyone writes "I built this".
#   (a) clean clone, empty outputs, no keys, no outbound network: four MP4s after the sign-offs
#   (b) refuse Short 2: the package waits, the fix replaces that Short only
#   (c) change one script line and approve it again: its voice and captions change, nothing re-renders
# Installed beforehand: Blender 5.2, ffmpeg, docker, the n8n and socat images, the Kokoro model in the
# Hugging Face cache. Python packages are installed into the clone (the only step that uses the network).
set -euo pipefail
REPO="${1:?usage: tests/recipe.sh <git url or path> <empty work dir>}"
WORK="${2:?usage: tests/recipe.sh <git url or path> <empty work dir>}"
git clone --quiet "$REPO" "$WORK/clone"
cd "$WORK/clone"
python3.12 -m venv .venv && .venv/bin/pip install --quiet -r requirements.txt
echo "== (a) clean clone"
test ! -e out && test ! -e cache && echo "no out/, no cache/"
if env | grep -q -i -E "^(openai|elevenlabs|kling|runway|anthropic|gemini)[a-z_]*key="; then echo "a model API key is set"; exit 1; fi
echo "no model API key in the environment"
sandbox-exec -f tests/no-network.sb .venv/bin/python -c "import urllib.request; urllib.request.urlopen('https://huggingface.co', timeout=5)" 2>/dev/null \
  && { echo "sandbox lets traffic out"; exit 1; } || echo "render service sandbox: outbound blocked"

./flow.py up --offline
COMPOSE="docker compose"; $COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"
$COMPOSE exec -T n8n sh -c "wget -qO- -T 5 https://example.com >/dev/null 2>&1" && { echo "n8n reached the internet"; exit 1; } || echo "n8n: no route out"

echo "== (a) + (b): one run, Short 2 refused once"
time ./flow.py run --reject-short 2 --note "The caption covers the lug" --fix caption_pos=lower
.venv/bin/python tests/check_ab.py out/DEMO-001

echo "== (c): one sentence changes"
sed -i.bak 's/^L08: .*/L08: It locks with a single, audible click./' script/DEMO-001_script.md
./flow.py run
.venv/bin/python tests/check_c.py out/DEMO-001 L08
echo "== all three checks passed"
