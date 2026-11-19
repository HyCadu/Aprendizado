# Roda o fluxo de cortes de lives sem interação (Windows).
#   Automático (streamers de streamers.json):  .\clipper-gta-br\rodar_automatico.ps1
#   Live(s) específica(s):                     .\clipper-gta-br\rodar_automatico.ps1 -Link URL [-Link URL2] [-Top 2]
# Agendar todo dia às 4h17 (ajuste o caminho):
#   schtasks /Create /SC DAILY /ST 04:17 /TN "Cortes GTA" /TR "powershell -ExecutionPolicy Bypass -File C:\caminho\Aprendizado\clipper-gta-br\rodar_automatico.ps1"
param(
    [string[]]$Link = @(),
    [ValidateRange(1, 10)][int]$Top = 0
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

$Prompt = "/clipar-gta-br"
if ($Link.Count -gt 0) { $Prompt += " " + ($Link -join " ") }
if ($Top -gt 0) { $Prompt += " (só $Top cortes por live)" }

$LogDir = Join-Path $env:USERPROFILE "StreamClipper\logs"
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
  --add-dir (Join-Path $env:USERPROFILE "StreamClipper") `
  --add-dir (Join-Path $env:USERPROFILE ".claude\skills\ai-stream-clipper") `
  *> $Log
