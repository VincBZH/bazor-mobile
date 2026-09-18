@echo off
title BAZOR GITHUB WATCHER
cd /d "%~dp0"
echo ============================================================
echo   BAZOR GITHUB WATCHER - GitHub ^> Core ^> Ollama ^> GitHub
echo ============================================================
where gh >nul 2>nul || (echo [BLOQUE] GitHub CLI gh introuvable.& pause& exit /b 1)
gh auth status || (echo [BLOQUE] GitHub CLI non connecte.& pause& exit /b 1)
python bazor_github_watcher.py
echo.
echo [BLOQUE] Le watcher s'est arrete. Voir le diagnostic ci-dessus.
pause
