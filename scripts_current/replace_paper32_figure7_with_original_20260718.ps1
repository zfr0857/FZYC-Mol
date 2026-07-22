$ErrorActionPreference = "Stop"

$root = "D:\fzyc\output\paper32_equation_table_format_20260718"
$sourceSvg = "D:\fzyc\output\paper30_submission_package_20260717\main_figures\Figure7.svg"
$packagedSvg = Join-Path $root "main_figures\Figure7_original.svg"
Copy-Item -LiteralPath $sourceSvg -Destination $packagedSvg -Force

$documents = @(
    (Join-Path $root "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx"),
    (Join-Path $root "Chinese_manuscript_final_unified_format.docx")
)

$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceSvg).Hash
$packagedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagedSvg).Hash
if ($sourceHash -ne $packagedHash) {
    throw "Packaged Figure 7 does not match the original SVG."
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$rows = @()
try {
    foreach ($path in $documents) {
        $doc = $word.Documents.Open($path, $false, $false, $false)
        if ($doc.InlineShapes.Count -ne 7) {
            throw "Expected seven inline figures before replacement: $path"
        }

        $target = $doc.InlineShapes.Item(7)
        $insert = $doc.Range($target.Range.Start, $target.Range.Start)
        $target.Delete()
        $shape = $doc.InlineShapes.AddPicture($packagedSvg, $false, $true, $insert)
        $shape.LockAspectRatio = -1
        $usableWidth = $doc.PageSetup.PageWidth - $doc.PageSetup.LeftMargin - $doc.PageSetup.RightMargin
        $shape.Width = $usableWidth
        $shape.Range.ParagraphFormat.Alignment = 1
        $shape.Range.ParagraphFormat.SpaceBefore = 3
        $shape.Range.ParagraphFormat.SpaceAfter = 3
        $shape.Range.ParagraphFormat.KeepWithNext = $true

        $doc.Save()
        $pdf = [IO.Path]::ChangeExtension($path, ".pdf")
        $doc.SaveAs2($pdf, 17)
        $rows += [pscustomobject]@{
            manuscript = $path
            pdf = $pdf
            figure7_svg = $packagedSvg
            original_svg = $sourceSvg
            original_sha256 = $sourceHash
            figure7_page = [int]$shape.Range.Information(3)
            width_points = [double]$shape.Width
            height_points = [double]$shape.Height
            inline_shape_type = [int]$shape.Type
        }
        $doc.Close($false)
    }
}
finally {
    $word.Quit()
}

[pscustomobject]@{
    status = "complete"
    body_format = "unified"
    figure7_insertion = "original native SVG"
    source_and_packaged_hash_match = ($sourceHash -eq $packagedHash)
    manuscripts = $rows
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root "Original_Figure7_insertion_audit.json") -Encoding utf8
