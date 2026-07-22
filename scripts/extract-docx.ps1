param(
    [Parameter(Mandatory = $true)][string[]]$Paths,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.ScreenUpdating = $false

try {
    foreach ($path in $Paths) {
        $stem = [IO.Path]::GetFileNameWithoutExtension($path)
        $safe = ($stem -replace '[\\/:*?"<>|]', '_')
        $dir = Join-Path $OutputDir $safe
        New-Item -ItemType Directory -Path $dir -Force | Out-Null

        $doc = $word.Documents.Open($path, $false, $true)
        try {
            $paragraphs = New-Object System.Collections.ArrayList
            for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
                $p = $doc.Paragraphs.Item($i)
                $text = $p.Range.Text -replace '[\r\a]+$', ''
                $style = ''
                try { $style = [string]$p.Range.Style.NameLocal } catch { try { $style = [string]$p.Range.Style } catch {} }
                [void]$paragraphs.Add([pscustomobject]@{
                    index = $i
                    start = $p.Range.Start
                    end = $p.Range.End
                    style = $style
                    outlineLevel = [int]$p.OutlineLevel
                    inTable = [bool]$p.Range.Information(12)
                    text = $text
                })
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($p)
            }

            $tables = New-Object System.Collections.ArrayList
            for ($i = 1; $i -le $doc.Tables.Count; $i++) {
                $t = $doc.Tables.Item($i)
                $rows = New-Object System.Collections.ArrayList
                for ($r = 1; $r -le $t.Rows.Count; $r++) {
                    $cells = New-Object System.Collections.Generic.List[string]
                    for ($c = 1; $c -le $t.Columns.Count; $c++) {
                        try {
                            $cellText = $t.Cell($r, $c).Range.Text -replace '[\r\a]+$', ''
                            $cells.Add($cellText)
                        } catch { $cells.Add('') }
                    }
                    [void]$rows.Add([object]$cells.ToArray())
                }
                [void]$tables.Add([pscustomobject]@{
                    index = $i
                    start = $t.Range.Start
                    end = $t.Range.End
                    rows = $t.Rows.Count
                    columns = $t.Columns.Count
                    data = @($rows)
                })
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($t)
            }

            $inline = New-Object System.Collections.ArrayList
            for ($i = 1; $i -le $doc.InlineShapes.Count; $i++) {
                $s = $doc.InlineShapes.Item($i)
                [void]$inline.Add([pscustomobject]@{
                    index = $i
                    start = $s.Range.Start
                    end = $s.Range.End
                    type = [int]$s.Type
                    title = [string]$s.Title
                    altText = [string]$s.AlternativeText
                    width = [math]::Round([double]$s.Width, 2)
                    height = [math]::Round([double]$s.Height, 2)
                })
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($s)
            }

            $floating = New-Object System.Collections.ArrayList
            for ($i = 1; $i -le $doc.Shapes.Count; $i++) {
                $s = $doc.Shapes.Item($i)
                [void]$floating.Add([pscustomobject]@{
                    index = $i
                    anchorStart = $s.Anchor.Start
                    type = [int]$s.Type
                    title = [string]$s.Title
                    altText = [string]$s.AlternativeText
                    width = [math]::Round([double]$s.Width, 2)
                    height = [math]::Round([double]$s.Height, 2)
                })
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($s)
            }

            $sections = New-Object System.Collections.ArrayList
            for ($i = 1; $i -le $doc.Sections.Count; $i++) {
                $sec = $doc.Sections.Item($i)
                [void]$sections.Add([pscustomobject]@{
                    index = $i
                    start = $sec.Range.Start
                    end = $sec.Range.End
                    orientation = [int]$sec.PageSetup.Orientation
                    pageWidth = [math]::Round([double]$sec.PageSetup.PageWidth, 2)
                    pageHeight = [math]::Round([double]$sec.PageSetup.PageHeight, 2)
                    marginLeft = [math]::Round([double]$sec.PageSetup.LeftMargin, 2)
                    marginRight = [math]::Round([double]$sec.PageSetup.RightMargin, 2)
                })
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($sec)
            }

            $meta = [pscustomobject]@{
                path = $path
                name = $doc.Name
                paragraphs = $doc.Paragraphs.Count
                tables = $doc.Tables.Count
                inlineShapes = $doc.InlineShapes.Count
                floatingShapes = $doc.Shapes.Count
                revisions = $doc.Revisions.Count
                comments = $doc.Comments.Count
                pages = $doc.ComputeStatistics(2)
                words = $doc.ComputeStatistics(0)
                characters = $doc.ComputeStatistics(3)
                sections = @($sections)
            }

            [pscustomobject]@{
                meta = $meta
                paragraphs = @($paragraphs)
                tables = @($tables)
                inlineShapes = @($inline)
                floatingShapes = @($floating)
            } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $dir 'structure.json') -Encoding UTF8

        } finally {
            $doc.Close(0)
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
        }

        $packageDir = Join-Path $dir 'package'
        if (Test-Path -LiteralPath $packageDir) { Remove-Item -LiteralPath $packageDir -Recurse -Force }
        [IO.Compression.ZipFile]::ExtractToDirectory($path, $packageDir)
    }
} catch {
    Write-Error ("Extraction failed at line {0}: {1}`n{2}" -f $_.InvocationInfo.ScriptLineNumber, $_.Exception.Message, $_.ScriptStackTrace)
    throw
} finally {
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
