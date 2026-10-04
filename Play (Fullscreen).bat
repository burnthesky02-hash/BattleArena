@echo off
rem Battle Arena - borderless fullscreen window (no title bar). Alt+F4 closes the game.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python was not found. Install Python 3 from python.org and tick "Add to PATH". & pause & exit /b 1)
python -c "import websockets" 2>nul || python -m pip install websockets
where pythonw >nul 2>nul && (start "" pythonw launcher.py --fullscreen  %*) || (start "" python launcher.py --fullscreen %*)
