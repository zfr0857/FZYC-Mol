$ErrorActionPreference = "Stop"

$source = "C:\Users\Administrator\Desktop\Chinese_manuscript_final_unified_format.docx"
$outDir = "D:\fzyc\output\paper32_font_corrected_20260718"
$output = Join-Path $outDir "Chinese_manuscript_final_unified_format_Times_New_Roman_figures.docx"
$figure7 = "D:\fzyc\output\paper32_equation_table_format_20260718\main_figures\Figure7_final_requested.svg"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $output -Force

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($output, $false, $false, $false)
    if ($doc.InlineShapes.Count -ne 7) {
        throw "Expected seven inline figures, found $($doc.InlineShapes.Count)."
    }
    $target = $doc.InlineShapes.Item(7)
    $insert = $doc.Range($target.Range.Start, $target.Range.Start)
    $target.Delete()
    $shape = $doc.InlineShapes.AddPicture($figure7, $false, $true, $insert)
    $shape.LockAspectRatio = -1
    $usableWidth = $doc.PageSetup.PageWidth - $doc.PageSetup.LeftMargin - $doc.PageSetup.RightMargin
    $shape.Width = $usableWidth
    $shape.Range.ParagraphFormat.Alignment = 1
    $shape.Range.ParagraphFormat.SpaceBefore = 3
    $shape.Range.ParagraphFormat.SpaceAfter = 3
    $shape.Range.ParagraphFormat.KeepWithNext = $true
    $doc.Save()
    $doc.Close($false)
}
finally {
    $word.Quit()
}

Write-Output $output
