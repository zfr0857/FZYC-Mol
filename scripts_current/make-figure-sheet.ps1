param(
    [Parameter(Mandatory = $true)][string]$MediaDir,
    [Parameter(Mandatory = $true)][int]$First,
    [Parameter(Mandatory = $true)][int]$Last,
    [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$cellW = 600
$cellH = 450
$cols = 2
$count = $Last - $First + 1
$rows = [int][Math]::Ceiling($count / $cols)
$sheetW = $cellW * $cols
$sheetH = $cellH * $rows
$sheet = New-Object Drawing.Bitmap($sheetW, $sheetH)
$g = [Drawing.Graphics]::FromImage($sheet)
$g.Clear([Drawing.Color]::White)
$g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = New-Object Drawing.Font('Arial', 16, [Drawing.FontStyle]::Bold)
try {
    for ($n = $First; $n -le $Last; $n++) {
        $idx = $n - $First
        $x = ($idx % $cols) * $cellW
        $y = [Math]::Floor($idx / $cols) * $cellH
        $path = Join-Path $MediaDir ("image{0}.png" -f $n)
        $img = [Drawing.Image]::FromFile($path)
        try {
            $maxW = $cellW - 30
            $maxH = $cellH - 55
            $scale = [Math]::Min($maxW / $img.Width, $maxH / $img.Height)
            $w = [int]($img.Width * $scale)
            $h = [int]($img.Height * $scale)
            $dx = $x + [int](($cellW - $w) / 2)
            $dy = $y + 35 + [int](($maxH - $h) / 2)
            $g.DrawString(("Figure {0} / image{1}.png" -f ($idx + 1), $n), $font, [Drawing.Brushes]::Black, $x + 10, $y + 5)
            $g.DrawImage($img, $dx, $dy, $w, $h)
        } finally { $img.Dispose() }
    }
    $sheet.Save($Output, [Drawing.Imaging.ImageFormat]::Png)
} finally {
    $font.Dispose(); $g.Dispose(); $sheet.Dispose()
}
