@echo off
echo ========================================
echo   AlgoForge Full Trading Dashboard
echo ========================================
echo.
echo Starting Backend API Server...
echo.

REM Start backend in a new window
start "AlgoForge Backend" cmd /k "python -m algoforge.api.server"

REM Wait a bit for backend to start
timeout /t 3 /nobreak > nul

echo.
echo Backend started on http://127.0.0.1:8000
echo.
echo Starting Frontend Dashboard...
echo.

REM Start frontend in a new window
start "AlgoForge Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo   Dashboard Starting...
echo ========================================
echo.
echo Backend API: http://127.0.0.1:8000
echo Frontend UI: http://localhost:3000
echo.
echo Wait 10 seconds, then open: http://localhost:3000
echo.
echo Press any key to open browser automatically...
pause > nul

REM Wait for frontend to fully start
timeout /t 10 /nobreak > nul

REM Open browser
start http://localhost:3000

echo.
echo Dashboard opened in browser!
echo.
echo To stop: Close both terminal windows
echo.
