$ErrorActionPreference = "Stop"

$root = "D:\fzyc\output\paper32_equation_table_format_20260718"
$documents = @(
    (Join-Path $root "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx"),
    (Join-Path $root "Chinese_manuscript_final_unified_format.docx")
)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($path in $documents) {
        $doc = $word.Documents.Open($path, $false, $true, $false)
        $pdf = [IO.Path]::ChangeExtension($path, ".pdf")
        $doc.SaveAs2($pdf, 17)
        $doc.Close($false)
    }
}
finally {
    $word.Quit()
}
