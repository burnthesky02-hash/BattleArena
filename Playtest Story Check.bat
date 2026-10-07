@echo off
rem Battle Arena - offline whole-story playtest (DEBUG ONLY). Replays every scene of the story from a new game in a few seconds, no browser needed,
rem and writes saves\playtest_story_report.md (unreachable content, flag typos, broken warps, the order of every fight).
cd /d "%~dp0"
where python >/dev/null 2>/dev/null || (echo Python was not found. Install Python 3 from python.org and tick "Add to PATH". & pause & exit /b 1)
python -m game.playtest_walker --debug %*
echo.
echo Report saved to saves\playtest_story_report.md
pause
