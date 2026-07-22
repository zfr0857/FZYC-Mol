param([Parameter(Mandatory = $true)][string]$Root)

$ErrorActionPreference = 'Stop'
Get-ChildItem -LiteralPath $Root -Directory | ForEach-Object {
    $jsonPath = Join-Path $_.FullName 'structure.json'
    if (-not (Test-Path -LiteralPath $jsonPath)) { return }
    $doc = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    $items = New-Object System.Collections.ArrayList

    foreach ($p in $doc.paragraphs) {
        if (-not $p.inTable -and -not [string]::IsNullOrWhiteSpace($p.text)) {
            [void]$items.Add([pscustomobject]@{ start=[int]$p.start; order=2; kind='p'; value=$p })
        }
    }
    foreach ($t in $doc.tables) {
        [void]$items.Add([pscustomobject]@{ start=[int]$t.start; order=1; kind='table'; value=$t })
    }
    foreach ($s in $doc.inlineShapes) {
        [void]$items.Add([pscustomobject]@{ start=[int]$s.start; order=0; kind='image'; value=$s })
    }

    $sb = New-Object Text.StringBuilder
    [void]$sb.AppendLine("# $($doc.meta.name)")
    [void]$sb.AppendLine()
    foreach ($item in ($items | Sort-Object start,order)) {
        if ($item.kind -eq 'p') {
            $p = $item.value
            $style = [string]$p.style
            if ($style -match '^(标题|Heading|Title|Subtitle)') {
                $level = 2
                if ($style -match '([1-6])') { $level = [Math]::Min(6, [int]$matches[1] + 1) }
                [void]$sb.AppendLine((('#' * $level) + ' ' + $p.text))
            } else {
                [void]$sb.AppendLine($p.text)
            }
            [void]$sb.AppendLine()
        } elseif ($item.kind -eq 'table') {
            $t = $item.value
            [void]$sb.AppendLine("[TABLE $($t.index); $($t.rows)x$($t.columns)]")
            foreach ($row in $t.data) {
                $cells = @($row) | ForEach-Object { ([string]$_ -replace '\|','\\|' -replace '[\r\n]+',' ') }
                [void]$sb.AppendLine('| ' + ($cells -join ' | ') + ' |')
            }
            [void]$sb.AppendLine("[/TABLE $($t.index)]")
            [void]$sb.AppendLine()
        } else {
            $s = $item.value
            [void]$sb.AppendLine("[IMAGE $($s.index); $($s.width)x$($s.height) pt; anchor=$($s.start)]")
            [void]$sb.AppendLine()
        }
    }
    [IO.File]::WriteAllText((Join-Path $_.FullName 'fulltext.md'), $sb.ToString(), (New-Object Text.UTF8Encoding($false)))
}
