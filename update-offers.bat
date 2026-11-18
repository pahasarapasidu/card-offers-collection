@echo off
rem Refreshes all bank offers. Double-click to run, or schedule it daily.
cd /d "%~dp0"
python scraper\scrape.py
if errorlevel 1 pause
rem Keep the mobile app's bundled copy in sync
copy /y data\offers.json mobile\assets\offers.json >nul
