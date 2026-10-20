@echo off
rem Drag a DVR .AVI onto this file: makes NAME_576i.mp4 (interlaced) and NAME_576p50.mp4 (smooth 50p) next to it,
rem or NAME_480i.mp4 and NAME_480p60.mp4 for NTSC recordings (experimental).
rem Needs Python 3, numpy (pip install numpy) and ffmpeg on the PATH.
if "%~1"=="" (echo Drag an .AVI file onto convert.bat & pause & exit /b 1)
for %%F in (%*) do (
  python "%~dp0weave.py" "%%~F" "%%~dpnF_{fmt}.mp4"
  python "%~dp0weave.py" "%%~F" "%%~dpnF_{fmt}.mp4" --bob
)
pause
