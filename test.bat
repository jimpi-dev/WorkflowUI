@echo off
REM WorkflowUI — Run frontend tests
REM Usage: test.bat [run|coverage]
REM   no args = watch mode; run = single run; coverage = single run with coverage
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\test.ps1" %*
