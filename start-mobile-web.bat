@echo off
rem Starts the Expo dev server (web mode) for the mobile app.
set "PATH=%PATH%;C:\Program Files\nodejs"
cd /d "%~dp0mobile"
call npx expo start --web --port 8081
