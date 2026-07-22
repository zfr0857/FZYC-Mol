$ErrorActionPreference = "Stop"

$root = "D:\fzyc\output\paper32_equation_table_format_20260718"
$svg = Join-Path $root "main_figures\Figure7_large_text.svg"
$documents = @(
    (Join-Path $root "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx"),
    (Join-Path $root "Chinese_manuscript_final_unified_format.docx")
)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$rows = @()
try {
    foreach ($path in $documents) {
        $doc = $word.Documents.Open($path, $false, $false, $false)
        if ($doc.InlineShapes.Count -lt 1) { throw "No inline figures found: $path" }
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
            figure7_svg = $svg
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
    figure7_insertion = "native SVG"
    manuscripts = $rows
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root "Unified_format_and_Figure7_insertion_audit.json") -Encoding utf8
