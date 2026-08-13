@echo off
cd /d "%~dp0"
echo Starting RepoLens...
echo.
start "RepoLens Backend" cmd /k call "%~dp0start-backend.cmd"
start "RepoLens Frontend" cmd /k call "%~dp0start-frontend.cmd"
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Close karna ho to windows band kar do.
