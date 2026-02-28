@echo off
REM Run backend tests (pytest).
REM From backend folder:  test.bat   (cmd)  or  .\test.bat   (PowerShell)
REM From repo root:       backend\test.bat
cd /d "%~dp0"
python -m pytest tests\ -v --tb=short
exit /b %ERRORLEVEL%
