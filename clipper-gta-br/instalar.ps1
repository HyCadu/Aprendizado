# Instala a skill ai-stream-clipper em %USERPROFILE%\.claude\skills e aplica o patch de português (pt-BR).
# Uso (Windows PowerShell):  powershell -ExecutionPolicy Bypass -File clipper-gta-br\instalar.ps1
# "Continue": no Windows PowerShell 5.1, mensagens do git no canal de erro abortariam o script com "Stop".
# Os erros de verdade são checados pelo $LASTEXITCODE.
$ErrorActionPreference = "Continue"

$Repo   = "https://github.com/arcticloud/ai-stream-clipper"
$Commit = "b3546b7e1ce3347dd253a627ccb9e25e5ae32f7a"   # versão em que o patch foi testado
$Dest   = Join-Path $env:USERPROFILE ".claude\skills\ai-stream-clipper"
$PatchOrig = Join-Path $PSScriptRoot "ai-stream-clipper-pt-br.patch"
# O Git for Windows pode ter convertido o .patch para CRLF, e aí ele não aplica: usa uma cópia só com LF.
$Patch = Join-Path $env:TEMP "ai-stream-clipper-pt-br.patch"
[IO.File]::WriteAllText($Patch, ([IO.File]::ReadAllText($PatchOrig) -replace "`r`n", "`n"))

if (-not (Test-Path (Join-Path $Dest ".git"))) {
    Write-Host "Clonando $Repo em $Dest ..."
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    git -c core.autocrlf=false clone $Repo $Dest
    if ($LASTEXITCODE -ne 0) { Write-Host "ERRO: não consegui baixar a skill. Confira a internet e se o Git está instalado."; exit 1 }
}

Push-Location $Dest
try {
    git apply --reverse --check $Patch 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Patch pt-BR já estava aplicado."
    } else {
        git checkout -q $Commit
        if ($LASTEXITCODE -ne 0) { Write-Host "ERRO: não achei a versão testada da skill."; exit 1 }
        git apply --whitespace=nowarn $Patch
        if ($LASTEXITCODE -ne 0) { Write-Host "ERRO: falha ao aplicar o patch pt-BR."; exit 1 }
        Write-Host "Patch pt-BR aplicado."
    }
} finally { Pop-Location }

Write-Host ""
Write-Host "Pronto. Agora abra o Claude Code e digite:  configura o clipper"
