#!/bin/sh
# xingchi-codex installer for macOS and Linux.
# Points the Codex CLI at the Xingchi upstream (OpenAI Responses API).
# Sol is required; Astra is optional and selected explicitly with --astra.
set -eu

REPO=${XINGCHI_REPO:-kikiprojecto/xingchi-codex}
BRANCH=${XINGCHI_BRANCH:-main}
XDIR=${XINGCHI_HOME:-$HOME/.xingchi}
BIN=${XINGCHI_BIN:-$HOME/.local/bin}
UPSTREAM=${XINGCHI_UPSTREAM:-https://api.xingchiapi.com/v1}
MODEL=gpt-6.1-sol
CODEX_DIR=${CODEX_HOME:-$HOME/.codex}
SHARED_SKILLS=$HOME/.agents/skills

die() { echo "error: $*" >&2; exit 1; }

usage() {
  cat <<EOF
usage: install.sh [--yes]

Configures Codex for Xingchi (default: $MODEL).
The required GPT公益/Sol key is stored in $XDIR/upstream.key (mode 600).
The optional Astra-专属余额 key is stored in $XDIR/astra.key (mode 600).
Each key is queried independently and gets its own catalog under
CODEX_HOME (default ~/.codex): xingchi-models.json and
xingchi-models-astra.json.
  Connects directly to $UPSTREAM. The default launcher uses GPT公益/Sol;
  xingchi-codex --astra selects Astra for that whole session.

  --yes     never prompt; requires XINGCHI_API_KEY; Astra is optional

Environment variables:
  XINGCHI_API_KEY          required GPT公益/Sol key (interactive prompt is safer)
  XINGCHI_ASTRA_API_KEY    optional Astra-专属余额 key
  XINGCHI_SKIP_INTEGRATIONS=1
                            leave unified skills and MCP settings untouched

After installation:
  xingchi-codex                 GPT公益/Sol (default)
  xingchi-codex --astra         Astra-专属余额
  xingchi-codex -m gpt-6.1-sol  choose a specific model
  xingchi-codex --astra -m gpt-6-astra
  xingchi-codex /inherit     choose saved history and continue in a fresh chat
  xingchi-codex --continue     fork the latest saved conversation
  /model                       choose model and reasoning effort in Codex
  /inherit                     open the saved-session picker inside the chat
Type / to select /inherit from the command list.
Continue saved work with /inherit (recommended for session limits):
  1. Launch xingchi-codex in the same project directory.
  2. Type /inherit and press Enter to open the session list.
  3. Use Up/Down or Page Up/Down; type a title or ID to filter. Esc cancels.
  4. Press Enter on a session; a fresh chat automatically reads saved history and continues the work.
/inherit automatically uses Full access and approval policy never (no command approval prompts).
Inherited commands run without sandboxing. Other chats keep their existing permissions.
Runtime files are also refreshed in $XDIR/bin.
Why /inherit over --continue: a fresh conversation reads saved history on demand.
--continue forks the saved conversation; copied history can still hit a turn limit.
If the old chat is closed: xingchi-codex /inherit (Astra: xingchi-codex --astra /inherit).
After updating, exit any running Codex and relaunch xingchi-codex to load the update.
At the optional Astra prompt, press Enter to configure GPT公益/Sol only.
An existing $XDIR/astra.key is reused; remove that file to stop storing the Astra key.
EOF
}

ASSUME_YES=0
while [ $# -gt 0 ]; do
  case $1 in
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

SRC=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
if [ -z "$SRC" ] || [ ! -f "$SRC/lib/config.py" ] || [ ! -f "$SRC/lib/models.json" ]; then
  command -v curl >/dev/null 2>&1 || die "curl is required to download the installer"
  command -v tar >/dev/null 2>&1 || die "tar is required to unpack the installer"
  bootstrap=$(mktemp -d)
  echo "downloading $REPO ($BRANCH)..."
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" \
    | tar -xz -C "$bootstrap" || die "download failed"
  exec sh "$bootstrap/xingchi-codex-$BRANCH/install.sh" "$@"
fi

# Pre-flight: Python 3.11+ for native TOML validation.
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 missing, attempting automatic installation..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y python3
  elif command -v apk >/dev/null 2>&1; then
    sudo apk add python3
  elif command -v brew >/dev/null 2>&1; then
    brew install python
  fi
  command -v python3 >/dev/null 2>&1 || die "install python3, then re-run installer"
fi
python3 -c 'import tomllib' 2>/dev/null || die "install Python 3.11 or newer, then re-run installer"

umask 077
mkdir -p "$XDIR" "$BIN"
chmod 700 "$XDIR"

# -----------------------------------------------------------------------------
# STEP 1: Xingchi API key
# -----------------------------------------------------------------------------
echo
echo "============================================================"
echo " [1/3] GPT公益/Sol API key + optional Astra-专属余额 API key"
echo "============================================================"
upstream=${XINGCHI_API_KEY:-}
if [ -n "$upstream" ]; then
  echo "  using key from XINGCHI_API_KEY"
elif [ -s "$XDIR/upstream.key" ]; then
  upstream=$(cat "$XDIR/upstream.key")
  echo "  using key from $XDIR/upstream.key"
fi

if [ -z "$upstream" ]; then
  # A readable /dev/tty can still fail to open (CI, no controlling terminal).
  if [ "$ASSUME_YES" = 1 ] || ! (exec </dev/tty) 2>/dev/null; then
    die "set XINGCHI_API_KEY (your xingchiapi key) or run interactively"
  fi
  printf 'Your GPT公益/Sol Xingchi API key spends account credits.\n' >/dev/tty
  printf 'It is stored only in %s/upstream.key (mode 600).\n' "$XDIR" >/dev/tty
  printf 'Create one at https://xingchiapi.com/keys, then paste it here\n' >/dev/tty
  printf '(input is hidden, press Enter): ' >/dev/tty
  stty -echo </dev/tty 2>/dev/null || true
  # Ctrl-C at the hidden prompt must not leave the terminal without echo.
  trap 'stty echo </dev/tty 2>/dev/null || true; exit 130' INT TERM HUP
  IFS= read -r upstream </dev/tty || upstream=""
  stty echo </dev/tty 2>/dev/null || true
  trap - INT TERM HUP
  printf '\n' >/dev/tty
  [ -n "$upstream" ] || die "no key read"
fi
# Pasting from a browser can carry spaces or CR; trim or the key fails with 401.
upstream=$(printf '%s' "$upstream" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
[ -n "$upstream" ] || die "empty API key"
printf '%s\n' "$upstream" > "$XDIR/upstream.key"
chmod 600 "$XDIR/upstream.key"

astra=${XINGCHI_ASTRA_API_KEY:-}
if [ -z "$astra" ] && [ -s "$XDIR/astra.key" ]; then
  astra=$(cat "$XDIR/astra.key")
  echo "  reusing optional Astra key from $XDIR/astra.key"
fi
if [ -z "$astra" ] && [ "$ASSUME_YES" != 1 ] && (exec </dev/tty) 2>/dev/null; then
  printf '\nOptional Astra key (press Enter to use Sol only).\n' >/dev/tty
  printf 'Paste your Astra key (input is hidden): ' >/dev/tty
  stty -echo </dev/tty 2>/dev/null || true
  trap 'stty echo </dev/tty 2>/dev/null || true; exit 130' INT TERM HUP
  IFS= read -r astra </dev/tty || astra=""
  stty echo </dev/tty 2>/dev/null || true
  trap - INT TERM HUP
  printf '\n' >/dev/tty
fi
astra=$(printf '%s' "$astra" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
if [ -n "$astra" ]; then
  printf '%s\n' "$astra" > "$XDIR/astra.key"
  chmod 600 "$XDIR/astra.key"
  echo "  optional Astra key configured"
else
  echo "  optional Astra key not configured (xingchi-codex --astra unavailable)"
fi

# -----------------------------------------------------------------------------
# STEP 2: Codex CLI
# -----------------------------------------------------------------------------
echo
echo "============================================================"
echo " [2/3] Codex CLI"
echo "============================================================"
cli_version=""
if command -v codex >/dev/null 2>&1; then
  cli_version=$(codex --version 2>/dev/null || true)
fi
if python3 "$SRC/lib/config.py" check-cli "$cli_version" >/dev/null 2>&1; then
  echo "  codex already installed: $cli_version"
else
  echo "  installing/updating @openai/codex (0.170.0 or newer required)..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g @openai/codex || die "npm install -g @openai/codex failed"
  else
    die "npm is missing. Install Node.js, then: npm install -g @openai/codex"
  fi
  command -v codex >/dev/null 2>&1 || \
    die "codex is not on PATH; add npm's global bin directory, then rerun the installer"
  cli_version=$(codex --version 2>/dev/null || true)
  python3 "$SRC/lib/config.py" check-cli "$cli_version" || \
    die "Codex update did not install a compatible CLI"
fi

# -----------------------------------------------------------------------------
# STEP 3: Write Codex config and launchers
# -----------------------------------------------------------------------------
echo
echo "============================================================"
echo " [3/3] Installing Codex configuration, model catalog and launchers"
echo "============================================================"
XINGCHI_API_KEY=$upstream XINGCHI_ASTRA_API_KEY=$astra XINGCHI_UPSTREAM=$UPSTREAM XINGCHI_HOME=$XDIR \
  python3 "$SRC/lib/config.py" codex || die "config for codex failed"

# Install the launchers before the optional integration step. The config now
# names XINGCHI_API_KEY as the provider env key, so an old launcher left in
# place after a later integration error makes Codex start with
# "Missing environment variable: XINGCHI_API_KEY".
cp "$SRC/bin/xingchi-codex" "$BIN/xingchi-codex"
cp "$SRC/bin/xingchi" "$BIN/xingchi"
cp "$SRC/bin/xingchi-codex-runner.py" "$BIN/xingchi-codex-runner.py"
cp "$SRC/bin/xingchi_history.py" "$BIN/xingchi_history.py"
cp "$SRC/bin/xingchi_tui.py" "$BIN/xingchi_tui.py"
cp "$SRC/bin/xingchi_conpty.py" "$BIN/xingchi_conpty.py"
chmod 755 "$BIN/xingchi-codex" "$BIN/xingchi" "$BIN/xingchi-codex-runner.py"
echo "  installed $BIN/xingchi-codex"

# Keep a usable runtime copy with the Xingchi installation as well as on PATH.
# Copy the complete helper set together so /inherit never uses stale modules.
mkdir -p "$XDIR/bin"
if [ "$(CDPATH= cd -- "$XDIR/bin" && pwd -P)" != "$(CDPATH= cd -- "$BIN" && pwd -P)" ]; then
  for runtime in xingchi-codex xingchi xingchi-codex-runner.py xingchi_history.py xingchi_tui.py xingchi_conpty.py; do
    cp "$BIN/$runtime" "$XDIR/bin/$runtime"
  done
fi
chmod 755 "$XDIR/bin/xingchi-codex" "$XDIR/bin/xingchi" "$XDIR/bin/xingchi-codex-runner.py"
echo "  runtime copy: $XDIR/bin"

if [ "${XINGCHI_SKIP_INTEGRATIONS:-}" != 1 ]; then
  XINGCHI_HOME=$XDIR python3 "$SRC/lib/integrations.py" || die "skill and MCP configuration failed"
  echo "  unified skills: $SHARED_SKILLS"
  echo "  MCP definitions: merged into $CODEX_DIR/config.toml (credentialed servers stay inactive until configured)"
else
  echo "  integrations skipped: existing skills and MCP settings were left untouched"
fi

# Ensure PATH in shell rc
case ":$PATH:" in
  *":$BIN:"*) : ;;
  *)
    case "${SHELL:-}" in
      */fish)
        rc="$HOME/.config/fish/config.fish"
        mkdir -p "$(dirname "$rc")"
        if ! grep -qs "xingchi-codex PATH" "$rc"; then
          printf '\n# xingchi-codex PATH\nfish_add_path "%s"\n' "$BIN" >> "$rc"
        fi
        ;;
      *)
        rc="$HOME/.profile"
        case "${SHELL:-}" in
          */zsh) rc="$HOME/.zshrc" ;;
          */bash) rc="$HOME/.bashrc" ;;
        esac
        if ! grep -qs "xingchi-codex PATH" "$rc"; then
          printf '\n# xingchi-codex PATH\nexport PATH="%s:$PATH"\n' "$BIN" >> "$rc"
        fi
        ;;
    esac
    echo "  PATH added to $rc (open a new terminal if commands are not found)"
    ;;
esac

echo
echo "============================================================"
echo " Installation complete"
echo "============================================================"
echo "  api:   $UPSTREAM"
echo "  Sol key:   $XDIR/upstream.key (GPT公益; default)"
if [ -s "$XDIR/astra.key" ]; then
  echo "  Astra key: $XDIR/astra.key (Astra-专属余额; --astra)"
else
  echo "  Astra key: not configured (optional; add XINGCHI_ASTRA_API_KEY or rerun interactively)"
fi
echo "  catalogs:  $CODEX_DIR/xingchi-models.json"
echo "             $CODEX_DIR/xingchi-models-astra.json"
if [ "${XINGCHI_SKIP_INTEGRATIONS:-}" = 1 ]; then
  echo "  skills/MCP: skipped (XINGCHI_SKIP_INTEGRATIONS=1)"
else
  echo "  skills:    $SHARED_SKILLS (shared with local Codex/Claude installs)"
  echo "  conflicts: $XDIR/skill-conflicts.json"
fi
echo
echo "Start Codex with:"
if command -v xingchi-codex >/dev/null 2>&1; then
  echo "  xingchi-codex"
else
  echo "  $BIN/xingchi-codex      (PATH updates in a new terminal)"
fi
echo "  xingchi-codex --astra      (Astra-专属余额, if astra.key is configured)"
echo "  xingchi-codex -m gpt-6.1-sol"
echo "  xingchi-codex --astra -m gpt-6-astra"
echo 'Choose your model and reasoning level with /model in Codex.'
echo 'Type / to select /inherit, then Enter to choose a saved session and continue in a fresh chat.'
echo 'Continue saved work with /inherit (recommended for session limits):'
echo '  1. Launch xingchi-codex in the same project directory.'
echo '  2. Type /inherit and press Enter to open the session list.'
echo '  3. Use Up/Down or Page Up/Down; type a title or ID to filter. Esc cancels.'
echo '  4. Press Enter on a session; a fresh chat automatically reads saved history and continues the work.'
echo '/inherit automatically uses Full access and approval policy never (no command approval prompts).'
echo 'Inherited commands run without sandboxing. Other chats keep their existing permissions.'
echo 'Why /inherit over --continue: a fresh conversation reads saved history on demand.'
echo '--continue forks the saved conversation; copied history can still hit a turn limit.'
echo 'If the old chat is closed: xingchi-codex /inherit (Astra: xingchi-codex --astra /inherit).'
echo 'After updating, exit any running Codex and relaunch xingchi-codex to load the update.'
echo 'The key group is selected at launch; /model never switches API keys.'
echo 'After session_request_limit_exceeded or session_turn_limit_exceeded: use /inherit.'
echo "Check the setup with:"
if command -v xingchi >/dev/null 2>&1; then
  echo "  xingchi"
else
  echo "  $BIN/xingchi"
fi
