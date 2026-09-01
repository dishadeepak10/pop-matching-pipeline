$keep = @(
    "main.py",
    "matching.py",
    "pop_row_builder.py",
    "email_log_parser.py",
    "storage.py"
)

New-Item -ItemType Directory -Path "archive\src_diagnostics" -Force | Out-Null

$allFiles = Get-ChildItem -Path "src" -File
$toMove = $allFiles | Where-Object { $keep -notcontains $_.Name }

Write-Host "Total files in src: $($allFiles.Count)"
Write-Host "Keeping: $($keep.Count)"
Write-Host "Archiving: $($toMove.Count)"
Write-Host ""

foreach ($file in $toMove) {
    Move-Item -Path $file.FullName -Destination "archive\src_diagnostics\$($file.Name)"
}

Write-Host "Done."
Write-Host ""
Write-Host "Remaining in src:"
Get-ChildItem -Path "src" -File | Select-Object Name
