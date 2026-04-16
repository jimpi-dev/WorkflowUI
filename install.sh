#!/usr/bin/env bash
# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: ./install.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$ROOT_DIR"

echo "WorkflowUI: installing dependencies..."
echo ""

echo "Backend (Python): pip install -r backend/requirements.txt"
(cd backend && pip install -r requirements.txt)

echo ""
echo "Frontend (Node): npm install in frontend/"
(cd frontend && npm install)

echo ""
echo "ffmpeg (video output thumbnails — optional but recommended)..."
ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "  Already installed: $(command -v ffmpeg)"
    return 0
  fi
  echo "  Not found; attempting install for this OS..."
  OS="$(uname -s)"
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      brew install ffmpeg
    else
      echo "  Install Homebrew (https://brew.sh), then run: brew install ffmpeg"
      return 1
    fi
  elif [ "$OS" = "Linux" ] && [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}" in
      debian|ubuntu|linuxmint|pop|zorin|kali)
        sudo apt-get update -qq && sudo apt-get install -y ffmpeg
        ;;
      fedora)
        sudo dnf install -y ffmpeg
        ;;
      rhel|centos|rocky|almalinux)
        sudo dnf install -y ffmpeg 2>/dev/null || sudo yum install -y ffmpeg
        ;;
      opensuse*|suse)
        sudo zypper install -y ffmpeg
        ;;
      arch|manjaro|endeavouros)
        sudo pacman -S --needed --noconfirm ffmpeg
        ;;
      alpine)
        sudo apk add --no-cache ffmpeg
        ;;
      *)
        echo "  Unknown distro ($ID). Install ffmpeg with your package manager, or see https://ffmpeg.org/download.html"
        return 1
        ;;
    esac
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
  echo "  Note: Without ffmpeg, video WebP thumbnails may fail unless ComfyUI serves previews."
else
  echo "  ffmpeg is available."
fi

echo ""
echo "Done. Start the app with: ./start.sh"
echo "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
