param(
    [Parameter(Mandatory = $true)][string]$EnglishPath,
    [Parameter(Mandatory = $true)][string]$ChinesePath,
    [string]$MappingCsv = "D:\fzyc\output\paper31_expanded_intervention_20260717\equation_assets\Paper31_equation_code_mapping.csv",
    [string]$AuditPath = "D:\fzyc\output\paper31_expanded_intervention_20260717\equation_assets\Paper31_Word_equation_audit.json"
)

$ErrorActionPreference = "Stop"
$equations = Import-Csv -LiteralPath $MappingCsv | Sort-Object {[int]$_.equation_number}
if ($equations.Count -ne 27) {
    throw "Expected 27 equation rows; found $($equations.Count)."
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$auditRows = @()

try {
    foreach ($path in @($EnglishPath, $ChinesePath)) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Missing manuscript: $path"
        }
        $doc = $word.Documents.Open($path, $false, $false)
        $before = [int]$doc.OMaths.Count
        foreach ($item in $equations) {
            $number = [int]$item.equation_number
            $placeholder = "[[EQ_$number]]"
            $search = $doc.Content.Duplicate
            $find = $search.Find
            $find.ClearFormatting()
            $find.Text = $placeholder
            $find.Forward = $true
            $find.Wrap = 0
            if (-not $find.Execute()) {
                $doc.Close($false)
                throw "Placeholder $placeholder not found in $path"
            }
            $paragraph = $search.Paragraphs.Item(1)
            $paragraphStart = [int]$paragraph.Range.Start
            $formula = [string]$item.linear_equation
            $punctuation = $(if ($number -in @(8, 11, 19, 25, 27)) { "." } else { "," })
            $fontSize = $(
                if ($number -in @(22, 24)) { 7.5 }
                elseif ($number -in @(10, 19)) { 9.0 }
                else { 10.5 }
            )
            $lowSurrogates = @($formula.ToCharArray() | Where-Object { [char]::IsLowSurrogate($_) }).Count
            $formulaWordLength = $formula.Length - $lowSurrogates
            $usableWidth = $doc.PageSetup.PageWidth - $doc.PageSetup.LeftMargin - $doc.PageSetup.RightMargin

            if ($number -in @(22, 24)) {
                $search.Text = ""
                $insertPoint = $doc.Range($paragraphStart, $paragraphStart)
                $table = $doc.Tables.Add($insertPoint, 1, 2)
                $table.Borders.Enable = 0
                $table.AllowAutoFit = $false
                $table.Columns.Item(1).Width = $usableWidth - 42
                $table.Columns.Item(2).Width = 42
                $table.Rows.Alignment = 1
                $formulaCell = $table.Cell(1, 1)
                $numberCell = $table.Cell(1, 2)
                $formulaCell.VerticalAlignment = 1
                $numberCell.VerticalAlignment = 1
                $formulaCell.Range.Text = "$formula$punctuation"
                $numberCell.Range.Text = "($number)"
                $formulaCell.Range.Font.Name = "Cambria Math"
                $formulaCell.Range.Font.Size = $fontSize
                $numberCell.Range.Font.Name = "Cambria Math"
                $numberCell.Range.Font.Size = 10.5
                $formulaCell.Range.ParagraphFormat.Alignment = 1
                $numberCell.Range.ParagraphFormat.Alignment = 2
                $formulaCell.Range.ParagraphFormat.SpaceBefore = 3
                $formulaCell.Range.ParagraphFormat.SpaceAfter = 3
                $numberCell.Range.ParagraphFormat.SpaceBefore = 3
                $numberCell.Range.ParagraphFormat.SpaceAfter = 3
                $equationRange = $doc.Range($formulaCell.Range.Start, $formulaCell.Range.Start + $formulaWordLength)
                $mathRange = $doc.OMaths.Add($equationRange)
                $mathRange.OMaths.Item(1).BuildUp()
                continue
            }

            $search.Text = "`t$formula$punctuation`t($number)"
            $paragraph = $doc.Range($paragraphStart, $paragraphStart + 1).Paragraphs.Item(1)
            $paragraph.Range.Font.Name = "Cambria Math"
            $paragraph.Range.Font.Size = $fontSize
            $paragraph.Format.SpaceBefore = 3
            $paragraph.Format.SpaceAfter = 3
            $paragraph.Format.KeepTogether = $true
            $paragraph.Format.KeepWithNext = $false
            $paragraph.Format.TabStops.ClearAll()
            [void]$paragraph.Format.TabStops.Add($usableWidth / 2, 1)
            [void]$paragraph.Format.TabStops.Add($usableWidth, 2)
            # Word Range positions count a supplementary-plane math glyph as
            # one character, while .NET String.Length counts its surrogate
            # pair as two.  Use Unicode scalar count so the OMath range never
            # consumes the following punctuation, tab stop, or equation number.
            $equationRange = $doc.Range($paragraphStart + 1, $paragraphStart + 1 + $formulaWordLength)
            $mathRange = $doc.OMaths.Add($equationRange)
            $mathRange.OMaths.Item(1).BuildUp()
        }
        $after = [int]$doc.OMaths.Count
        $remaining = 0
        foreach ($item in $equations) {
            $needle = "[[EQ_$([int]$item.equation_number)]]"
            $check = $doc.Content.Duplicate
            $checkFind = $check.Find
            $checkFind.Text = $needle
            $checkFind.Wrap = 0
            if ($checkFind.Execute()) { $remaining += 1 }
        }
        $doc.Save()
        $doc.Close()
        $auditRows += [pscustomobject]@{
            manuscript = $path
            omath_before = $before
            omath_after = $after
            native_equations_added = $after - $before
            placeholders_remaining = $remaining
            used_bordered_table = $false
            used_borderless_table_for_long_equations = $true
            equation_editor = "Microsoft Word OMath"
        }
    }
}
finally {
    $word.Quit()
}

$passed = ($auditRows | Where-Object { $_.native_equations_added -ne 27 -or $_.placeholders_remaining -ne 0 }).Count -eq 0
$audit = [pscustomobject]@{
    status = $(if ($passed) { "complete" } else { "failed" })
    equation_count_expected = 27
    manuscripts = $auditRows
}
$audit | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $AuditPath -Encoding utf8
if (-not $passed) {
    throw "Native equation audit failed; see $AuditPath"
}
Write-Output ($audit | ConvertTo-Json -Depth 5)
