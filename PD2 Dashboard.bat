@echo off
title PD2 Sniper Dashboard Server
echo.
echo  ================================
echo   PD2 Market Sniper Dashboard
echo  ================================
echo.
echo  Starting server on http://localhost:8420
echo  Press Ctrl+C to stop
echo.

cd /d "C:\Users\jding\.agents\skills\pd2-market-sniper\scripts"
python sniper.py serve --port 8420

echo.
echo  Server stopped.
pause
