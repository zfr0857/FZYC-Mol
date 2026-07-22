$ErrorActionPreference = "Stop"

$docx = "D:\fzyc\output\paper32_font_corrected_20260718\Chinese_manuscript_final_unified_format_Times_New_Roman_figures_DISPLAY_VERIFIED.docx"
$pdf = [IO.Path]::ChangeExtension($docx, ".pdf")
$temp = Join-Path $env:TEMP "Chinese_manuscript_TNR_figures_render_copy.docx"
Copy-Item -LiteralPath $docx -Destination $temp -Force

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($temp, $false, $true, $false)
    if ($doc.InlineShapes.Count -ne 7) { throw "Expected seven figures." }
    $doc.SaveAs2($pdf, 17)
    $doc.Close($false)
}
finally {
    $word.Quit()
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}

Write-Output $pdf
