param([string]$RepositoryRoot = (Resolve-Path "$PSScriptRoot/../..").Path)
$ErrorActionPreference = 'Stop'
$inputDeck = Join-Path $RepositoryRoot 'KubeSentinel-AI-Presentation.pptx'
$pdfOutput = Join-Path $RepositoryRoot 'docs/presentations/KubeSentinel-AI-Presentation.pdf'
$previewOutput = Join-Path $RepositoryRoot '.cache/portfolio/slides'
New-Item -ItemType Directory -Force -Path (Split-Path $pdfOutput), $previewOutput | Out-Null
$powerpoint = New-Object -ComObject PowerPoint.Application
try {
    $deck = $powerpoint.Presentations.Open($inputDeck, $true, $false, $false)
    try {
        $deck.SaveAs($pdfOutput, 32)
        $deck.Export($previewOutput, 'PNG', 1280, 720)
    } finally { $deck.Close() }
} finally {
    $powerpoint.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerpoint)
}
Copy-Item (Join-Path $previewOutput 'Slide1.PNG') (Join-Path $RepositoryRoot 'docs/presentations/preview.png') -Force
Write-Output "Exported 25-slide PDF and review PNGs using installed PowerPoint."
