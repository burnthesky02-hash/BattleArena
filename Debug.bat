@echo off
rem Battle Arena with debug tools (Battle Debug menu, damage graphs, calc log). Keeps a console open.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python was not found. Install Python 3 from python.org and tick "Add to PATH". & pause & exit /b 1)
python -c "import websockets" 2>nul || python -m pip install websockets
python launcher.py --debug %*
pause
