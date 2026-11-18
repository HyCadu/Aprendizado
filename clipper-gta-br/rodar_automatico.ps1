# Roda o fluxo de cortes sem interação (para agendar no Agendador de Tarefas do Windows).
# Agendar todo dia às 4h17 (rode uma vez no PowerShell, ajuste o caminho):
#   schtasks /Create /SC DAILY /ST 04:17 /TN "Cortes GTA" /TR "powershell -ExecutionPolicy Bypass -File C:\caminho\Aprendizado\clipper-gta-br\rodar_automatico.ps1"
$ErrorActionPreference = "Stop"
$Repo   = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $env:USERPROFILE "StreamClipper\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
Set-Location $Repo
# Libera só o necessário: python (scripts da skill), leitura/escrita de arquivos. Nada de publicar.
claude -p "/clipar-gta-br" `
  --allowedTools "Bash(python:*)" "PowerShell(python:*)" "Read" "Write" "Glob" `
  --add-dir (Join-Path $env:USERPROFILE "StreamClipper") `
  --add-dir (Join-Path $env:USERPROFILE ".claude\skills\ai-stream-clipper") `
  *> (Join-Path $LogDir ((Get-Date -Format "yyyy-MM-dd_HHmm") + ".log"))
