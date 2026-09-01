$keep = @(
    "run_pipeline.py",
    "run_pipeline_email_source.py",
    "normalize_bank_statements.py",
    ".env",
    "requirements.txt"
)

New-Item -ItemType Directory -Path "archive" -Force | Out-Null

$allFiles = Get-ChildItem -Path . -File
$toMove = $allFiles | Where-Object { $keep -notcontains $_.Name }

Write-Host "Total files at root: $($allFiles.Count)"
Write-Host "Keeping: $($keep.Count)"
Write-Host "Archiving: $($toMove.Count)"
Write-Host ""

foreach ($file in $toMove) {
    Move-Item -Path $file.FullName -Destination "archive\$($file.Name)"
}

Write-Host "Done."
Write-Host ""
Write-Host "Remaining at root:"
Get-ChildItem -Path . -File | Select-Object Name
