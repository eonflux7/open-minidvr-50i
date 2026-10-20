Mini DVR converter for Windows (open-minidvr-50i)
==================================================

Turns the DVR's raw recordings (made with this project's ADJUST.BIN and UPOKE.BIN) into normal video files.
Nothing to install: Python, numpy and ffmpeg are included.

HOW TO USE
  Drag one or more .AVI recordings onto MiniDVR-Convert.exe.
  Or double-click MiniDVR-Convert.exe and choose the recordings.

  Each recording becomes two files next to it:
    NAME_576i.mp4    720x576 interlaced (25i): TVs, DVD/Blu-ray authoring, video editors
    NAME_576p50.mp4  720x576 at 50p: smooth on computers and phones, and for uploading
  NTSC recordings (experimental) become NAME_480i.mp4 and NAME_480p60.mp4.

  Keep everything in this folder together: the .exe needs the _internal folder and ffmpeg.exe next to it.

"WINDOWS PROTECTED YOUR PC"
  Windows shows this for programs that aren't signed with a paid certificate. Click "More info", then "Run anyway".
  You only have to do this once. The program is built from the public source code by GitHub Actions; see the
  project page below.

MORE
  Project, instructions and source code: https://github.com/eonflux7/open-minidvr-50i
  Command-line options: open a terminal in this folder and run  MiniDVR-Convert.exe --help

LICENCES
  The converter: MIT, see LICENSE.txt.
  ffmpeg.exe: FFmpeg essentials build by Gyan Doshi (https://www.gyan.dev/ffmpeg/builds/), licensed under the
  GPL version 3, see ffmpeg-LICENSE.txt and ffmpeg-README.txt (versions of every library in it). Source code:
  https://ffmpeg.org/download.html and https://github.com/GyanD/codexffmpeg
  Python and numpy (in _internal): their own open-source licences (PSF licence, BSD licence).
