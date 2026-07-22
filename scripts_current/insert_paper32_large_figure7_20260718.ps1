$ErrorActionPreference = "Stop"

$root = "D:\fzyc\output\paper32_equation_table_format_20260718"
$svg = Join-Path $root "main_figures\Figure7_large_text.svg"
$pairs = @(
    @(
        (Join-Path $root "Candidate_pool_expansion_Journal_of_Cheminformatics_equations_tables_formatted.docx"),
        (Join-Path $root "Candidate_pool_expansion_Journal_of_Cheminformatics_equations_tables_large_Figure7.docx"),
        "Figure 7"
    ),
    @(
        (Join-Path $root "Chinese_manuscript_equations_tables_formatted.docx"),
        (Join-Path $root "Chinese_manuscript_equations_tables_large_Figure7.docx"),
        "图 7"
    )
)

if (-not (Test-Path -LiteralPath $svg)) { throw "Missing SVG: $svg" }
foreach ($pair in $pairs) { Copy-Item -LiteralPath $pair[0] -Destination $pair[1] -Force }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$rows = @()
try {
    foreach ($pair in $pairs) {
        $path = $pair[1]
        $doc = $word.Documents.Open($path, $false, $false, $false)
        if ($doc.InlineShapes.Count -lt 1) {
            $doc.Close($false)
            throw "No inline figures found: $path"
        }
        # Figure 7 is the final inline figure in both source manuscripts.
        $target = $doc.InlineShapes.Item($doc.InlineShapes.Count)
        $insert = $doc.Range($target.Range.Start, $target.Range.Start)
        $target.Delete()
        $shape = $doc.InlineShapes.AddPicture($svg, $false, $true, $insert)
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
            source_svg = $svg
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

$audit = [pscustomobject]@{
    status = "complete"
    replacement = "Figure 7 enlarged-text native SVG"
    manuscripts = $rows
}
$audit | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root "Figure7_large_text_insertion_audit.json") -Encoding utf8
$audit | ConvertTo-Json -Depth 5
