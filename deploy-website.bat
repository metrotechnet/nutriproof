@echo off
cd /d "%~dp0website"
firebase deploy --only hosting
pause
