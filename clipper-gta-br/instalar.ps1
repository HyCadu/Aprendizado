# Instala a skill ai-stream-clipper em %USERPROFILE%\.claude\skills e aplica o patch de português (pt-BR).
# Uso (Windows PowerShell):  powershell -ExecutionPolicy Bypass -File clipper-gta-br\instalar.ps1
$ErrorActionPreference = "Stop"

$Repo   = "https://github.com/arcticloud/ai-stream-clipper"
$Commit = "b3546b7e1ce3347dd253a627ccb9e25e5ae32f7a"   # versão em que o patch foi testado
$Dest   = Join-Path $env:USERPROFILE ".claude\skills\ai-stream-clipper"
$Patch  = Join-Path $PSScriptRoot "ai-stream-clipper-pt-br.patch"

if (-not (Test-Path (Join-Path $Dest ".git"))) {
    Write-Host "Clonando $Repo em $Dest ..."
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    git clone $Repo $Dest
}

Push-Location $Dest
try {
    git apply --reverse --check $Patch 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Patch pt-BR já estava aplicado."
    } else {
        git checkout -q $Commit
        git apply --whitespace=nowarn $Patch
        if ($LASTEXITCODE -ne 0) { throw "Falha ao aplicar o patch" }
        Write-Host "Patch pt-BR aplicado."
    }
} finally { Pop-Location }

Write-Host ""
Write-Host "Pronto. Agora abra o Claude Code e digite:  configura o clipper"
