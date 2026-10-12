@echo off
rem Builds the standalone, protected demo into dist_demo\SkyborneSagaDemo (and a zip). Run on Windows; first run takes a while.
rem Needs Python 3.9-3.13 on PATH (and an internet connection the first time, to fetch Nuitka and its C compiler).
rem Node.js (nodejs.org) is optional but recommended: it is used to obfuscate the JavaScript.
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python was not found on PATH. & pause & exit /b 1)
if not exist build_demo mkdir build_demo
if not exist build_demo\venv (python -m venv build_demo\venv || (echo venv failed & pause & exit /b 1))
call build_demo\venv\Scripts\activate.bat
python -m pip install --upgrade pip nuitka ordered-set zstandard websockets || (echo pip failed & pause & exit /b 1)
where node >nul 2>&1 || echo NOTE: Node.js not found - JavaScript will not be obfuscated.
python tools\build_demo.py %*
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
echo.
echo The demo is in dist_demo\SkyborneSagaDemo  (zip: dist_demo\SkyborneSagaDemo.zip)
pause
