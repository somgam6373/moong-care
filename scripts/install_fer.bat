@echo off
REM ------------------------------------------------------------
REM  MoongCare - FER dependency installer (thin wrapper)
REM
REM  This file is intentionally ASCII-only.
REM  cmd.exe parses .bat files using the system codepage, so any
REM  UTF-8 Korean text here would corrupt command parsing.
REM  All logic and Korean messages live in scripts/install_fer.py
REM
REM  Usage (PowerShell, from project root):
REM      .\scripts\install_fer.bat
REM ------------------------------------------------------------

chcp 65001 > nul
cd /d "%~dp0.."
python "%~dp0install_fer.py"
set EXITCODE=%ERRORLEVEL%
echo.
pause
exit /b %EXITCODE%
