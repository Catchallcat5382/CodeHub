@echo off
title CodeHub Bootstrap Loader
color 0A
mode con: cols=110 lines=32
cd /d "%~dp0"
py "%~dp0.codehub_tools\codehub_launcher.py"
exit
