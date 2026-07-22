param(
    [string]$Package = "D:\fzyc\output\paper31_submission_package_20260717",
    [string]$EnglishPath = "",
    [string]$ChinesePath = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($EnglishPath)) {
    $EnglishPath = Join-Path $Package "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(7).docx"
}
if ([string]::IsNullOrWhiteSpace($ChinesePath)) {
    $ChinesePath = Join-Path $Package "候选池扩张与模型选择损失_中文完整论文(7).docx"
}
$documents = @($EnglishPath, $ChinesePath)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$rows = @()
try {
    foreach ($docx in $documents) {
        $pdf = [System.IO.Path]::ChangeExtension($docx, ".pdf")
        if (-not (Test-Path -LiteralPath $docx)) { throw "Missing manuscript: $docx" }
        $doc = $word.Documents.Open($docx, $false, $true)
        $pages = [int]$doc.ComputeStatistics(2)
        $doc.SaveAs2($pdf, 17)
        $doc.Close($false)
        $rows += [pscustomobject]@{ docx = $docx; pdf = $pdf; pages = $pages }
    }
}
finally {
    $word.Quit()
}
$rows | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $Package "Manuscript_PDF_export_audit.json") -Encoding utf8
Write-Output ($rows | ConvertTo-Json -Depth 3)
