New-Item -ItemType Directory -Path "archive\src_legacy_architecture" -Force | Out-Null

Move-Item -Path "src\core" -Destination "archive\src_legacy_architecture\core"
Move-Item -Path "src\services" -Destination "archive\src_legacy_architecture\services"
Move-Item -Path "src\utils" -Destination "archive\src_legacy_architecture\utils"

Write-Host "Moved core/services/utils to archive."
Write-Host ""
Write-Host "Current src/ tree:"
Get-ChildItem -Path "src" -Recurse | Select-Object FullName
