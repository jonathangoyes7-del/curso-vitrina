# Instalación de Vitrina (Windows 11, PowerShell). Todo con uv.
# Se puede ejecutar cuantas veces haga falta: no borra el entorno (.venv) ni node_modules si ya existen.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Existe($nombre) { [bool](Get-Command $nombre -ErrorAction SilentlyContinue) }

# --- Programas que tienen que estar ya instalados ---
Write-Host "Comprobando los programas necesarios..."
$faltan = @()
if (-not (Existe uv))     { $faltan += "uv (https://docs.astral.sh/uv/)" }
if (-not (Existe node))   { $faltan += "Node.js (https://nodejs.org/)" }
if (-not (Existe npm))    { $faltan += "npm (viene con Node.js)" }
if (-not (Existe ffmpeg)) { $faltan += "ffmpeg (winget install Gyan.FFmpeg)" }
if (-not (Existe git))    { $faltan += "git (https://git-scm.com/)" }
if (-not (Existe ollama)) { $faltan += "Ollama (https://ollama.com/download)" }
if ($faltan.Count -gt 0) {
    throw "Faltan estos programas; instálalos y vuelve a ejecutar:`n - " + ($faltan -join "`n - ")
}
Write-Host "Programas listos: uv, Node, ffmpeg, git y Ollama."

# --- Entorno ---
Write-Host "Creando el entorno con Python 3.11 y PyTorch cu128..."
uv python install 3.11
if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar Python 3.11 con uv." }
# uv sync instala torch/torchvision desde https://download.pytorch.org/whl/cu128 (ver pyproject.toml)
uv sync
if ($LASTEXITCODE -ne 0) { throw "Falló uv sync." }
$version = uv run python --version
if ($version -notmatch "3\.11\.") { throw "Se esperaba Python 3.11 y hay: $version" }
Write-Host "Entorno listo ($version)."

# --- Idol ---
# idol-sdk va fijado al commit probado en el pico (docs/pico-idol.md); uv lo instala con uv sync.
# El paquete de Python se llama "idol". triton-windows (en pyproject.toml) permite el modo rápido de Idol.
# Idol descarga DINOv3 desde Hugging Face: hay que aceptar sus términos con la cuenta y tener la sesión abierta.
uv run hf auth whoami *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "No hay sesión de Hugging Face. Antes, acepta los términos de" -ForegroundColor Yellow
    Write-Host "https://huggingface.co/facebook/dinov3-vith16plus-pretrain-lvd1689m con tu cuenta; después pega aquí tu token." -ForegroundColor Yellow
    uv run hf auth login
    if ($LASTEXITCODE -ne 0) { throw "No se abrió la sesión de Hugging Face." }
}
Write-Host "Sesión de Hugging Face lista."

# --- SPZ ---
# No hay nada que instalar: los bindings `spz` de Niantic no tienen binarios para Windows y compilarlos exige
# Visual Studio, así que panel/splat.py escribe el formato SPZ (v3) en Python puro con numpy.

# --- Visor (Three.js + Spark) ---
# `npm ci` borra node_modules antes de instalar: solo se ejecuta si el visor aún no está instalado.
if (Test-Path "node_modules\three") {
    Write-Host "Visor ya instalado (node_modules existe); no se reinstala."
} else {
    if (Test-Path package-lock.json) { npm ci } else { npm install }
    if ($LASTEXITCODE -ne 0) { throw "Falló npm." }
}
Write-Host "Visor listo."

# --- Navegador para los tests del visor y el Reel (Playwright Chromium) ---
uv run python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de Chromium para Playwright." }
Write-Host "Chromium listo."

# --- Ollama: el modelo de las fichas ---
$modelo = "gemma4:12b"
$descargados = ollama list 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ollama está instalado pero apagado: ábrelo y comprueba después con: ollama list" -ForegroundColor Yellow
} elseif (-not ($descargados | Select-String -SimpleMatch $modelo)) {
    Write-Host "Falta el modelo de las fichas. Descárgalo con: ollama pull $modelo" -ForegroundColor Yellow
} else {
    Write-Host "Modelo $modelo listo."
}

# --- Comprobación final: PyTorch ve la tarjeta gráfica ---
Write-Host "Comprobando la tarjeta gráfica..."
$gpu = uv run python scripts/comprobar_gpu.py
if ($LASTEXITCODE -ne 0) { throw "Falló la comprobación de la GPU." }
$gpu
# El script sale con código 0 aunque no haya GPU: se mira lo que dice.
if ($gpu -match "no disponible") { throw "PyTorch no ve la tarjeta gráfica. Revisa los controladores de NVIDIA." }
Write-Host "`nListo. Para abrir el panel, haz doble clic en iniciar.bat."
