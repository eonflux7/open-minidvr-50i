@echo off
rem Mini DVR converter for Windows.
rem   Drag one or more DVR .AVI files onto this file, or double-click it and choose them.
rem   Makes NAME_576i.mp4 (interlaced) and NAME_576p50.mp4 (smooth 50p) next to each recording,
rem   or NAME_480i.mp4 and NAME_480p60.mp4 for NTSC recordings (experimental).
rem   It needs Python 3, numpy and ffmpeg, and offers to install whatever is missing (with winget, built into Windows).
setlocal
title Mini DVR converter
set "TRIED="

:find_python
rem The py launcher first. "python" can be the Microsoft Store placeholder, so run it to be sure it's real.
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (python -c "import sys" >nul 2>nul && set "PY=python")
if defined PY goto have_python
if defined TRIED goto restart
echo Python 3 is not installed. The converter is a Python program, so it needs it.
call :install Python.Python.3.13 "Python 3" "https://www.python.org/downloads/ (tick 'Add python.exe to PATH')" || goto end
set "TRIED=1"
goto find_python

:have_python
%PY% -c "import numpy" >nul 2>nul && goto have_numpy
echo Installing numpy (a Python package the converter uses)...
%PY% -m pip install --user --disable-pip-version-check numpy || (echo numpy could not be installed. & goto end)

:have_numpy
rem winget puts ffmpeg here; a window opened before the install doesn't have it on its PATH yet.
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
where ffmpeg >nul 2>nul && goto have_ffmpeg
echo ffmpeg is not installed. The converter uses it to read and write video.
call :install Gyan.FFmpeg.Essentials "ffmpeg" "https://www.gyan.dev/ffmpeg/builds/ (then add its bin folder to PATH)" || goto end
where ffmpeg >nul 2>nul && goto have_ffmpeg
goto restart

:have_ffmpeg
%PY% "%~dp0weave.py" --both %*
rem With no files, weave.py opens a file dialog and waits for Enter itself.
if "%~1"=="" exit /b
goto end

:restart
echo.
echo Installed. Close this window and start the converter again (Windows only finds new programs in a new window).
goto end

rem :install WINGET_ID "name" "manual download hint"
:install
where winget >nul 2>nul || goto install_manual
choice /c YN /m "Install %~2 now"
if errorlevel 2 goto install_manual
winget install -e --id %1 --accept-source-agreements --accept-package-agreements && exit /b 0
echo The install didn't finish.
:install_manual
echo Download it from %~3, install it, and start the converter again.
exit /b 1

:end
echo.
pause
