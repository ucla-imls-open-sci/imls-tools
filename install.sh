#!/bin/sh
# Install wbcheck (carpentries-workbench-checker) so it runs from anywhere.
#
#   curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | sh
#
# What it does:
#   1. installs pixi (https://pixi.sh) if it isn't already on PATH
#   2. clones the checker into $WBCHECK_HOME (default ~/.local/share/wbcheck),
#      or updates an existing clone there
#   3. builds its pixi environment from the lockfile
#   4. writes a `wbcheck` launcher into $WBCHECK_BIN_DIR (default ~/.pixi/bin,
#      which pixi's installer already puts on your PATH)
#
# Re-running it updates; so does `wbcheck update`. To uninstall, delete
# $WBCHECK_HOME and $WBCHECK_BIN_DIR/wbcheck.
#
# Overrides: WBCHECK_REPO (git URL or local path), WBCHECK_REF (branch, tag,
# or commit; default main), WBCHECK_HOME, WBCHECK_BIN_DIR.

set -eu

REPO="${WBCHECK_REPO:-https://github.com/ucla-imls-open-sci/carpentries-workbench-checker.git}"
REF="${WBCHECK_REF:-main}"
WBCHECK_HOME="${WBCHECK_HOME:-$HOME/.local/share/wbcheck}"
BIN_DIR="${WBCHECK_BIN_DIR:-$HOME/.pixi/bin}"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required (macOS: xcode-select --install)"

if ! command -v pixi >/dev/null 2>&1; then
  if [ -x "$HOME/.pixi/bin/pixi" ]; then
    PATH="$HOME/.pixi/bin:$PATH"
  else
    say "Installing pixi"
    command -v curl >/dev/null 2>&1 || die "curl is required to install pixi"
    curl -fsSL https://pixi.sh/install.sh | sh
    PATH="$HOME/.pixi/bin:$PATH"
  fi
fi
export PATH
command -v pixi >/dev/null 2>&1 || die "pixi install failed; see https://pixi.sh"

if [ -d "$WBCHECK_HOME/.git" ]; then
  say "Updating $WBCHECK_HOME"
  if [ -n "$(git -C "$WBCHECK_HOME" status --porcelain --untracked-files=no)" ]; then
    die "$WBCHECK_HOME has local changes; commit or discard them first"
  fi
  git -C "$WBCHECK_HOME" fetch --quiet origin
  git -C "$WBCHECK_HOME" checkout --quiet "$REF"
  # a branch fast-forwards to its remote; a tag or commit is already exact
  if git -C "$WBCHECK_HOME" symbolic-ref -q HEAD >/dev/null; then
    git -C "$WBCHECK_HOME" pull --quiet --ff-only
  fi
else
  say "Cloning $REPO into $WBCHECK_HOME"
  mkdir -p "$(dirname "$WBCHECK_HOME")"
  git clone --quiet "$REPO" "$WBCHECK_HOME"
  git -C "$WBCHECK_HOME" checkout --quiet "$REF"
fi

say "Building the pixi environment (first run downloads Python and dependencies)"
pixi install --quiet --manifest-path "$WBCHECK_HOME/pixi.toml"

TARGET="$WBCHECK_HOME/.pixi/envs/default/bin/wbcheck"
[ -x "$TARGET" ] || die "expected $TARGET after pixi install"

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/wbcheck" <<EOF
#!/bin/sh
# wbcheck launcher written by install.sh; see $WBCHECK_HOME
exec "$TARGET" "\$@"
EOF
chmod +x "$BIN_DIR/wbcheck"

say "Installed: $("$BIN_DIR/wbcheck" --version)"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf '\nAdd %s to your PATH (e.g. in ~/.zshrc):\n  export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac

cat <<'EOF'

Next:
  wbcheck doctor                 see which optional pieces (gh, quarto, ollama, API key) are ready
  wbcheck --install-completion   tab completion for your shell
  wbcheck check path/to/lesson   run the checks
EOF
