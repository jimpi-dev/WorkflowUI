@echo off
REM WorkflowUI — (Re)start backend and frontend (launches start.ps1)
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\start.ps1"
