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

# --- Idol ---
# idol-sdk fijado al commit probado en el pico (docs/pico-idol.md); uv lo instala desde pyproject.toml con uv sync.
# El paquete de Python se llama "idol". triton-windows (en pyproject.toml) permite el modo rápido de Idol (optimize=True).
Write-Host "Idol: comprueba que aceptaste los términos de facebook/dinov3-vith16plus-pretrain-lvd1689m en Hugging Face y ejecutaste 'uv run hf auth login'."
$env:USERNAME = if ($env:USERNAME) { $env:USERNAME } else { [Environment]::UserName }

# --- Visor (Three.js + Spark) ---
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "No se encontró npm (Node.js). Instálalo y vuelve a ejecutar."
}
if (Test-Path package-lock.json) { npm ci } else { npm install }
if ($LASTEXITCODE -ne 0) { throw "Falló npm." }
Write-Host "Visor listo."
