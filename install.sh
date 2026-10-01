#!/usr/bin/env bash
# Set up a Motiontale workspace: the folder your videos will live in.
#
#   cd ~/videos                      # or any folder you like
#   bash <plugin>/install.sh
#
# Safe to run again: it skips what's already done, and never overwrites your .env or sound library.
set -euo pipefail

PLUGIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(pwd)"
say()  { printf '\n==> %s\n' "$*"; }
fail() { printf '\nSetup stopped: %s\n' "$*" >&2; exit 1; }

say "Setting up a Motiontale workspace in $WS"

# 1. Python 3.11 or later, and ffmpeg
PY3=""
for c in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY3="$c"; break
  fi
done
[ -n "$PY3" ] || fail "Python 3.11 or later is needed.
  macOS:          brew install python
  Debian/Ubuntu:  sudo apt install python3 python3-venv"
command -v ffmpeg >/dev/null 2>&1 || fail "ffmpeg is needed.
  macOS:          brew install ffmpeg
  Debian/Ubuntu:  sudo apt install ffmpeg"
say "Found $("$PY3" --version) and $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

# 2. A Python environment for the engine, inside the workspace
if [ -x .venv/bin/python ]; then
  say "Python environment .venv already here"
else
  say "Creating the Python environment .venv"
  "$PY3" -m venv .venv
fi
say "Installing the engine's Python packages (pinned versions)"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r "$PLUGIN/engine/requirements.txt"

# 3. The browser the renderer draws frames with
say "Installing the Chromium the renderer uses (about 150 MB, once per machine)"
if [ "$(uname -s)" = "Linux" ]; then
  .venv/bin/python -m playwright install --with-deps chromium || .venv/bin/python -m playwright install chromium
else
  .venv/bin/python -m playwright install chromium
fi

# 4. The sound library
if [ -f kit/AUDIO.md ]; then
  say "Sound library already in kit/"
else
  say "Downloading and measuring the sound library into kit/"
  .venv/bin/python "$PLUGIN/engine/kit.py"
fi

# 5. Settings: .env from .env.example, readable only by you
if [ -f .env ]; then
  say ".env already here: left as it is"
else
  cp "$PLUGIN/.env.example" .env
  chmod 600 .env
  say "Created .env from .env.example. Add keys only if you want an AI voice (see the README's Settings and keys)"
fi

# 6. Check everything
say "Checking the setup"
.venv/bin/python "$PLUGIN/engine/film.py" doctor

cat <<EOF

Ready. Open Claude Code or Codex in:
  $WS
and ask for a video, for example:
  "Make a 45-second launch video for <your product>, editorial style."
EOF
