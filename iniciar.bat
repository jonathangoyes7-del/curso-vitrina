@echo off
rem Doble clic para abrir Vitrina. Un .ps1 no se ejecuta con doble clic (se abre en el Bloc de notas),
rem por eso existe este lanzador: llama a iniciar.ps1 sin pedir permisos ni escribir nada.
title Vitrina
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar.ps1"
if errorlevel 1 (
    echo.
    echo Vitrina no pudo abrirse. Lee el mensaje de arriba.
    pause
)
