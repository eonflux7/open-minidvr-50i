#!/bin/sh
# Mini DVR converter for macOS and Linux.
#   macOS: double-click convert.command (next to this file) and choose the recordings.
#   Terminal: sh convert.sh PICT0001.AVI [PICT0002.AVI ...]   (no files: a file dialog opens)
# Makes NAME_576i.mp4 (interlaced) and NAME_576p50.mp4 (smooth 50p) next to each recording, or NAME_480i.mp4 and
# NAME_480p60.mp4 for NTSC recordings (experimental).
# Needs Python 3, numpy and ffmpeg, and offers to install whatever is missing: with Homebrew on macOS, with the
# system's package manager (apt, dnf, pacman or zypper) on Linux.
here=$(cd "$(dirname "$0")" && pwd)

ask() { printf '%s [y/N] ' "$1"; read -r reply; case $reply in [Yy]*) return 0 ;; esac; return 1; }

find_brew() {
  for b in brew /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if command -v "$b" >/dev/null 2>&1; then BREW=$("$b" --prefix); PATH="$BREW/bin:$PATH"; return 0; fi
  done
  return 1
}

ready() {                       # sets PY; on macOS only Homebrew's Python (Apple's /usr/bin/python3 can't get numpy)
  PY=
  if [ "$(uname)" = Darwin ]; then
    [ -n "$BREW" ] && [ -x "$BREW/bin/python3" ] && PY="$BREW/bin/python3"
  else
    PY=$(command -v python3 || command -v python)
  fi
  [ -n "$PY" ] && "$PY" -c 'import numpy' 2>/dev/null && command -v ffmpeg >/dev/null 2>&1
}

[ "$(uname)" = Darwin ] && find_brew
if ! ready; then
  echo "The converter needs Python 3, numpy and ffmpeg, and some of them are missing."
  if [ "$(uname)" = Darwin ]; then
    if [ -z "$BREW" ]; then
      echo "They're installed with Homebrew (https://brew.sh), which isn't on this Mac yet."
      ask "Install Homebrew now? (it asks for your Mac password)" || exit 1
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || exit 1
      find_brew || { echo "Homebrew didn't install. See https://brew.sh"; exit 1; }
    fi
    ask "Install python, numpy and ffmpeg with Homebrew now?" && brew install python numpy ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then
    ask "Install them now? (sudo apt-get install python3 python3-numpy ffmpeg)" &&
      sudo apt-get install -y python3 python3-numpy ffmpeg
  elif command -v dnf >/dev/null 2>&1; then
    echo "(Fedora's own ffmpeg has no H.264 encoder; the one from RPM Fusion, https://rpmfusion.org, does.)"
    ask "Install them now? (sudo dnf install python3 python3-numpy ffmpeg)" &&
      sudo dnf install -y python3 python3-numpy ffmpeg
  elif command -v pacman >/dev/null 2>&1; then
    ask "Install them now? (sudo pacman -S python python-numpy ffmpeg)" &&
      sudo pacman -S --needed --noconfirm python python-numpy ffmpeg
  elif command -v zypper >/dev/null 2>&1; then
    echo "(openSUSE's own ffmpeg has no H.264 encoder; the one from Packman does.)"
    ask "Install them now? (sudo zypper install python3-numpy ffmpeg)" &&
      sudo zypper install -y python3-numpy ffmpeg
  else
    echo "Install python3, numpy and ffmpeg with your system's package manager, then run this again."
  fi
  ready || { echo "Still missing something; nothing was converted."; exit 1; }
fi
exec "$PY" "$here/weave.py" --both "$@"
