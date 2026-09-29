@echo off
rem Puts "Battle Arena" and "Battle Arena (Debug)" shortcuts on your Desktop.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell;" ^
 "foreach($p in @(@('Battle Arena','Play.bat'),@('Battle Arena (Debug)','Debug.bat'))){" ^
 " $s=$w.CreateShortcut((Join-Path $d ($p[0]+'.lnk'))); $s.TargetPath=(Join-Path '%~dp0' $p[1]);" ^
 " $s.WorkingDirectory='%~dp0'; if(Test-Path '%~dp0icon.ico'){$s.IconLocation='%~dp0icon.ico'}; $s.WindowStyle=7; $s.Save() }"
echo Shortcuts created on your Desktop.
pause
