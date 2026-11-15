# Abre el panel de Vitrina (127.0.0.1:8765). Normalmente se lanza con iniciar.bat (doble clic).
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "No se encontró uv. Ejecuta primero instalar.ps1." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path .venv)) {
    Write-Host "Falta el entorno. Ejecuta primero instalar.ps1." -ForegroundColor Red
    exit 1
}
uv run python -m panel
exit $LASTEXITCODE
