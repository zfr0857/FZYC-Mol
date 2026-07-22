param(
    [Parameter(Mandatory=$true)][string]$Original,
    [Parameter(Mandatory=$true)][string]$Revised,
    [Parameter(Mandatory=$true)][string]$Output
)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$originalDoc = $null
$revisedDoc = $null
$comparedDoc = $null
try {
    $originalDoc = $word.Documents.Open($Original, $false, $true, $false)
    $revisedDoc = $word.Documents.Open($Revised, $false, $true, $false)
    $comparedDoc = $word.CompareDocuments(
        $originalDoc, $revisedDoc, 2, 1,
        $false, $true, $false, $true, $true, $true, $true, $true, $true, $true,
        "OpenAI Codex", $true
    )
    $comparedDoc.SaveAs2($Output, 16)
}
finally {
    if ($null -ne $comparedDoc) { $comparedDoc.Close($false) }
    if ($null -ne $revisedDoc) { $revisedDoc.Close($false) }
    if ($null -ne $originalDoc) { $originalDoc.Close($false) }
    $word.Quit()
    foreach ($obj in @($comparedDoc, $revisedDoc, $originalDoc, $word)) {
        if ($null -ne $obj) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
