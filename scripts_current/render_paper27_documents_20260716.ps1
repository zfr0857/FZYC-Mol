$ErrorActionPreference = "Stop"

$base = "D:\fzyc\output\paper27_equal_size_registry_composition_revision_20260716"
$rendered = Join-Path $base "rendered"
New-Item -ItemType Directory -Force -Path $rendered | Out-Null

$english = Join-Path $base "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx"
$tracked = Join-Path $base "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript_tracked_changes.docx"
$chinese = Get-ChildItem -LiteralPath $base -Filter "*.docx" | Where-Object {
    $_.Name -ne [System.IO.Path]::GetFileName($english) -and
    $_.Name -notmatch "tracked|Reviewer"
} | Select-Object -First 1 -ExpandProperty FullName
$supplement = Join-Path $base "supplementary\Additional_file_1_Supplementary_Methods_and_Results.docx"

$jobs = @(
    @($english, (Join-Path $rendered "English_clean.pdf"), $false),
    @($chinese, (Join-Path $rendered "Chinese_clean.pdf"), $false),
    @($supplement, (Join-Path $rendered "Supplementary_methods.pdf"), $false),
    @($tracked, (Join-Path $rendered "English_tracked_final_view.pdf"), $true)
)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($job in $jobs) {
        $source = $job[0]
        $target = $job[1]
        $isTracked = [bool]$job[2]
        if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
        $doc = $word.Documents.Open($source, $false, $true)
        try {
            if ($isTracked) {
                $doc.ShowRevisions = $false
                $doc.PrintRevisions = $false
            }
            $doc.ExportAsFixedFormat($target, 17)
        }
        finally {
            $doc.Close(0)
        }
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

Get-ChildItem -LiteralPath $rendered -Filter "*.pdf" | Select-Object Name, Length
