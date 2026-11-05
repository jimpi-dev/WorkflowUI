#!/usr/bin/env bash
# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: ./install.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/dev-common.sh
. "$ROOT_DIR/scripts/dev-common.sh"
cd "$ROOT_DIR"

echo "WorkflowUI: installing dependencies..."
echo ""

pkg_install() {
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      brew install "$@"
      return 0
    fi
    echo "  Install Homebrew (https://brew.sh), then: brew install $*"
    return 1
  fi
  if [ "$OS" != "Linux" ] || [ ! -f /etc/os-release ]; then
    echo "  Unsupported OS. Install packages manually: $*"
    return 1
  fi
  # shellcheck source=/dev/null
  . /etc/os-release
  case "${ID:-}" in
    debian|ubuntu|linuxmint|pop|zorin|kali)
      sudo apt-get update -qq && sudo apt-get install -y "$@"
      ;;
    fedora)
      sudo dnf install -y "$@"
      ;;
    rhel|centos|rocky|almalinux)
      sudo dnf install -y "$@" 2>/dev/null || sudo yum install -y "$@"
      ;;
    opensuse*|suse)
      sudo zypper install -y "$@"
      ;;
    alpine)
      sudo apk add --no-cache "$@"
      ;;
    *)
      if workflowui_is_arch_like; then
        sudo pacman -S --needed --noconfirm "$@"
      else
        echo "  Unknown distro (${ID:-}). Install with your package manager: $*"
        return 1
      fi
      ;;
  esac
}

ensure_python() {
  PYTHON="$(workflowui_find_python || true)"
  if [ -z "$PYTHON" ]; then
    echo "Python 3 is required but was not found."
    if workflowui_is_arch_like; then
      echo "  Trying: sudo pacman -S --needed --noconfirm python python-pip"
      pkg_install python python-pip
      PYTHON="$(workflowui_find_python || true)"
    elif [ -f /etc/os-release ]; then
      # shellcheck source=/dev/null
      . /etc/os-release
      case "${ID:-}" in
        debian|ubuntu|linuxmint|pop|zorin|kali)
          pkg_install python3 python3-venv python3-pip
          PYTHON="$(workflowui_find_python || true)"
          ;;
      esac
    fi
  fi
  if [ -z "$PYTHON" ]; then
    echo "Could not find a usable Python 3 with the venv module."
    echo "On CachyOS/Arch: sudo pacman -S --needed python python-pip"
    echo "On Debian/Ubuntu: sudo apt-get install python3 python3-venv python3-pip"
    exit 1
  fi
  if ! "$PYTHON" -c "import ensurepip" >/dev/null 2>&1; then
    echo "Python ensurepip is missing (needed to create .venv)."
    if workflowui_is_arch_like; then
      pkg_install python-pip || true
    elif [ -f /etc/os-release ]; then
      # shellcheck source=/dev/null
      . /etc/os-release
      case "${ID:-}" in
        debian|ubuntu|linuxmint|pop|zorin|kali)
          pkg_install python3-venv python3-pip || true
          ;;
      esac
    fi
  fi
  echo "  Python: $PYTHON ($("$PYTHON" -c 'import sys; print(sys.version.split()[0])'))"
}

install_node_userlocal() {
  local dest="${NODE_USER_DIR}"
  if [ -x "$dest/bin/node" ] && [ -x "$dest/bin/npm" ]; then
    export PATH="$dest/bin:$PATH"
    return 0
  fi
  local arch=""
  case "$(uname -m)" in
    x86_64) arch=x64 ;;
    aarch64|arm64) arch=arm64 ;;
    *)
      echo "  Unsupported CPU for bundled Node.js ($(uname -m))."
      return 1
      ;;
  esac
  local ver="v24.20.0"
  local name="node-${ver}-linux-${arch}"
  local url="https://nodejs.org/dist/${ver}/${name}.tar.xz"
  local tmp
  tmp="$(mktemp -d)"
  echo "  Downloading Node.js ${ver} (no sudo) to ${dest} ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp/node.tar.xz"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$tmp/node.tar.xz" "$url"
  else
    echo "  curl or wget is required to download Node.js."
    rm -rf "$tmp"
    return 1
  fi
  tar -xJf "$tmp/node.tar.xz" -C "$tmp"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mv "$tmp/${name}" "$dest"
  rm -rf "$tmp"
  export PATH="$dest/bin:$PATH"
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1
}

ensure_node() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "  Node: $(command -v node) ($(node --version))"
    echo "  npm:  $(command -v npm) ($(npm --version))"
    return 0
  fi
  echo "  Node.js/npm not found; attempting install..."
  set +e
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    pkg_install node
  elif workflowui_is_arch_like; then
    pkg_install nodejs npm
  elif [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}" in
      debian|ubuntu|linuxmint|pop|zorin|kali|fedora)
        pkg_install nodejs npm
        ;;
    esac
  fi
  set -e
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "  Node: $(command -v node) ($(node --version))"
    echo "  npm:  $(command -v npm) ($(npm --version))"
    return 0
  fi
  install_node_userlocal || {
    echo "Could not install Node.js automatically."
    echo "On CachyOS/Arch: sudo pacman -S --needed nodejs npm"
    echo "Then re-run ./install.sh"
    exit 1
  }
  echo "  Node: $(command -v node) ($(node --version))"
  echo "  npm:  $(command -v npm) ($(npm --version))"
}

echo "Backend (Python): virtualenv + pip install -r backend/requirements.txt"
ensure_python
if ! workflowui_venv_python >/dev/null 2>&1; then
  if workflowui_can_symlink "$ROOT_DIR"; then
    VENV_DIR="$PROJECT_VENV_DIR"
  else
    VENV_DIR="$HOME_VENV_DIR"
    echo "  Project filesystem does not support symlinks (e.g. exFAT)."
    echo "  Creating virtualenv at ${VENV_DIR} instead of .venv in the repo."
  fi
  echo "  Creating virtual environment at ${VENV_DIR} ..."
  if [ -d "$PROJECT_VENV_DIR" ] && [ ! -x "${PROJECT_VENV_DIR}/bin/python" ] && [ ! -x "${PROJECT_VENV_DIR}/Scripts/python.exe" ]; then
    rm -rf "$PROJECT_VENV_DIR"
  fi
  workflowui_run "$PYTHON" "$ROOT_DIR/scripts/create_venv.py" "$VENV_DIR"
  printf '%s\n' "$VENV_DIR" > "$ROOT_DIR/.venv-path"
fi
VENV_PY="$(workflowui_venv_python)" || {
  echo "Failed to create virtualenv."
  exit 1
}
workflowui_run "$VENV_PY" -m pip install --upgrade pip
workflowui_run "$VENV_PY" -m pip install -r backend/requirements.txt

echo ""
echo "Frontend (Node): npm install in frontend/"
ensure_node
OS="$(uname -s)"
if [ "$OS" = "Linux" ] && [ -d frontend/node_modules/@esbuild/win32-x64 ]; then
  if [ ! -d frontend/node_modules/@esbuild/linux-x64 ] && [ ! -d frontend/node_modules/@esbuild/linux-x64-gnu ]; then
    echo "  Removing Windows-native frontend modules so npm can install Linux binaries..."
    rm -rf frontend/node_modules
  fi
fi
if [ "$OS" = "Darwin" ] && [ -d frontend/node_modules/@esbuild/win32-x64 ]; then
  if [ ! -d frontend/node_modules/@esbuild/darwin-x64 ] && [ ! -d frontend/node_modules/@esbuild/darwin-arm64 ]; then
    echo "  Removing Windows-native frontend modules so npm can install macOS binaries..."
    rm -rf frontend/node_modules
  fi
fi
if workflowui_can_symlink "$ROOT_DIR/frontend"; then
  (cd frontend && npm install)
else
  echo "  Filesystem does not support symlinks; using npm --no-bin-links."
  (cd frontend && npm install --no-bin-links)
fi
if [ -f frontend/node_modules/@sveltejs/kit/svelte-kit.js ]; then
  echo "  Running svelte-kit sync..."
  (cd frontend && node node_modules/@sveltejs/kit/svelte-kit.js sync) || true
fi

echo ""
echo "ffmpeg (video thumbnails + GenVault HEVC compress — optional but recommended)..."
has_hevc_encoder() {
  command -v ffmpeg >/dev/null 2>&1 || return 1
  ffmpeg -hide_banner -encoders 2>&1 | grep -q libx265
}
ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "  Already installed: $(command -v ffmpeg)"
    return 0
  fi
  echo "  Not found; attempting install for this OS..."
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    pkg_install ffmpeg
  elif [ "$OS" = "Linux" ]; then
    pkg_install ffmpeg
  else
    echo "  Unsupported OS for auto-install. Install ffmpeg manually: https://ffmpeg.org/download.html"
    return 1
  fi
}
set +e
ensure_ffmpeg
FFMPEG_RC=$?
set -e
if [ "$FFMPEG_RC" -ne 0 ] || ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  Note: Without ffmpeg, video thumbnails may fail unless ComfyUI serves previews."
  echo "  GenVault video compression (HEVC) also requires ffmpeg with libx265."
else
  echo "  ffmpeg is available."
  if has_hevc_encoder; then
    echo "  libx265 (HEVC): available — GenVault video compression enabled."
  else
    echo "  libx265 (HEVC): not found in this build. GenVault video compress disabled."
    echo "  Install a full distro ffmpeg package (most include libx265)."
  fi
fi

echo ""
echo "Done. Local development: ./start-dev.sh"
echo "Production-like start:  ./start.sh"
echo "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
