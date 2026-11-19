# Roda os cortes do YouTube sem interação (Windows).
#   Automático (canais de canais.json):  .\cortes-youtube\rodar_automatico.ps1
#   Vídeo(s) específico(s):              .\cortes-youtube\rodar_automatico.ps1 -Link URL [-Link URL2] [-Top 3]
#     (vários de uma vez também:          -Link URL1,URL2)
# Agendar todo dia às 5h23:
#   schtasks /Create /SC DAILY /ST 05:23 /TN "Cortes YouTube" /TR "powershell -ExecutionPolicy Bypass -File C:\caminho\Aprendizado\cortes-youtube\rodar_automatico.ps1"
param(
    [string[]]$Link = @(),
    [ValidateRange(1, 5)][int]$Top = 0
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

$Prompt = "/cortes-youtube"
if ($Link.Count -gt 0) { $Prompt += " " + ($Link -join " ") }
if ($Top -gt 0) { $Prompt += " --top $Top" }

$LogDir = Join-Path $env:USERPROFILE "CortesYouTube\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ((Get-Date -Format "yyyy-MM-dd_HHmmss") + ".log")
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
Set-Location $Repo
Write-Host "Rodando: $Prompt  (log em $Log)"
# Avisos do claude no canal de erro não podem derrubar o script (Windows PowerShell 5.1).
$ErrorActionPreference = "Continue"
# Libera só o necessário: python (scripts da skill), leitura/escrita de arquivos. Nada de publicar.
claude -p $Prompt `
  --allowedTools "Bash(python:*)" "PowerShell(python:*)" "Read" "Write" "Glob" `
  --add-dir (Join-Path $env:USERPROFILE "CortesYouTube") `
  *> $Log
