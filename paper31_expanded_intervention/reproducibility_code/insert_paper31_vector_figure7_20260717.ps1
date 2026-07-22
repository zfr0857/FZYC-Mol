param(
    [Parameter(Mandatory = $true)][string]$EnglishPath,
    [Parameter(Mandatory = $true)][string]$ChinesePath,
    [string]$FigureSvg = "D:\fzyc\output\paper31_expanded_intervention_20260717\figures\Figure_7_expanded_equal_size_intervention.svg",
    [string]$AuditPath = "D:\fzyc\output\paper31_expanded_intervention_20260717\figures\Paper31_Figure7_Word_insertion_audit.json"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $FigureSvg)) {
    throw "Missing Figure 7 SVG: $FigureSvg"
}
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$rows = @()
try {
    foreach ($path in @($EnglishPath, $ChinesePath)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing manuscript: $path" }
        $doc = $word.Documents.Open($path, $false, $false)
        $search = $doc.Content.Duplicate
        $find = $search.Find
        $find.Text = "[[FIGURE_7_VECTOR]]"
        $find.Wrap = 0
        if (-not $find.Execute()) {
            $doc.Close($false)
            throw "Figure 7 placeholder not found in $path"
        }
        $paragraph = $search.Paragraphs.Item(1)
        $paragraph.Range.Text = "`r"
        $insert = $paragraph.Range.Duplicate
        $insert.End = $insert.Start
        $shape = $doc.InlineShapes.AddPicture($FigureSvg, $false, $true, $insert)
        $shape.LockAspectRatio = $true
        $usableWidth = $doc.PageSetup.PageWidth - $doc.PageSetup.LeftMargin - $doc.PageSetup.RightMargin
        if ($shape.Width -gt $usableWidth) { $shape.Width = $usableWidth }
        $shape.Range.ParagraphFormat.Alignment = 1
        $shape.Range.ParagraphFormat.SpaceBefore = 3
        $shape.Range.ParagraphFormat.SpaceAfter = 3
        $shape.Range.ParagraphFormat.KeepWithNext = $true
        $nextStart = $shape.Range.Paragraphs.Item(1).Range.End
        $nextParagraph = $doc.Range($nextStart, $nextStart + 1).Paragraphs.Item(1)
        $nextParagraph.Format.KeepTogether = $true
        $doc.Save()
        $rows += [pscustomobject]@{
            manuscript = $path
            source_svg = $FigureSvg
            inline_shape_type = [int]$shape.Type
            width_points = [double]$shape.Width
            height_points = [double]$shape.Height
            placeholder_remaining = $false
        }
        $doc.Close()
    }
}
finally {
    $word.Quit()
}
$audit = [pscustomobject]@{
    status = "complete"
    insertion_mode = "Microsoft Word native SVG inline shape"
    rasterized_before_insertion = $false
    manuscripts = $rows
}
$audit | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $AuditPath -Encoding utf8
Write-Output ($audit | ConvertTo-Json -Depth 5)
