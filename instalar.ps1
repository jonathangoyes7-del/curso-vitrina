# Instalación de Vitrina (Windows 11, PowerShell). Todo con uv.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- Entorno ---
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "No se encontró uv. Instálalo desde https://docs.astral.sh/uv/ y vuelve a ejecutar."
}
Write-Host "Creando el entorno con Python 3.11 y PyTorch cu128..."
uv python install 3.11
if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar Python 3.11 con uv." }
# uv sync instala torch/torchvision desde https://download.pytorch.org/whl/cu128 (ver pyproject.toml)
uv sync
if ($LASTEXITCODE -ne 0) { throw "Falló uv sync." }
Write-Host "Entorno listo."
