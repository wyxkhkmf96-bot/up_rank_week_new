@echo off
REM Launcher for the unattended weekly charging-UP leaderboard update.
REM Called by the Windows scheduled task "ChargingUP-WeeklyRank".
REM Keep this file ASCII-only: cmd.exe decodes it with the OEM codepage (GBK here),
REM which mangles UTF-8 text and can break lines apart.

setlocal
set BASE=C:\Users\dengyuting02\WorkBuddy\20260514140206
set PY=C:\Users\dengyuting02\AppData\Local\Programs\Python\Python312\python.exe
set PYTHONIOENCODING=utf-8
set TASKLOG=%BASE%\log\auto_weekly_task.log

cd /d "%BASE%"
if not exist "%BASE%\log" mkdir "%BASE%\log"

echo ============================================ >> "%TASKLOG%"
echo [%DATE% %TIME%] task started >> "%TASKLOG%"

REM Python writes its own detailed log to log\auto_weekly_YYYYmmdd_HHMMSS.log
"%PY%" "%BASE%\auto_weekly_update.py" %* >> "%TASKLOG%" 2>&1
set RC=%ERRORLEVEL%

echo [%DATE% %TIME%] finished, exit code=%RC% >> "%TASKLOG%"
exit /b %RC%
