@echo off
title JARVIS AI Assistant
cd /d "%~dp0"
echo Starting JARVIS...
".venv\Scripts\python.exe" main.py %*
pause
