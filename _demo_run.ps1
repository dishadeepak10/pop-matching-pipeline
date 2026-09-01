$targets = @(
    "data\input\Disha_Learning\Disha_Learning\00084772_POP_Document.jpeg",
    "data\input\Disha_Learning\Disha_Learning\00084851_POP_Document.jpeg"
)

foreach ($t in $targets) {
    Write-Host ""
    Write-Host "========== Processing: $t ==========" -ForegroundColor Cyan
    python run.py $t
}
