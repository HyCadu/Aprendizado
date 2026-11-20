# Cria um atalho "GTA Clipper Studio V2" na Área de Trabalho.
# Usa o executável (GTA Clipper Studio.exe) se ele existir; senão, o .bat.
# Uso: powershell -ExecutionPolicy Bypass -File gta-clipper-studio-v2\criar_atalho.ps1
$Exe = Join-Path $PSScriptRoot "GTA Clipper Studio.exe"
$Bat = Join-Path $PSScriptRoot "Abrir GTA Clipper Studio.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Lnk = Join-Path $Desktop "GTA Clipper Studio V2.lnk"
$Shell = New-Object -ComObject WScript.Shell
$S = $Shell.CreateShortcut($Lnk)
if (Test-Path $Exe) {
    $S.TargetPath = $Exe
    $S.IconLocation = "$Exe,0"
} else {
    $S.TargetPath = $Bat
    $S.WindowStyle = 7   # minimizado: o .bat só abre o app e fecha
}
$S.WorkingDirectory = $PSScriptRoot
$S.Description = "GTA CLIPPER STUDIO V2"
$S.Save()
Write-Host "Atalho criado: $Lnk"
