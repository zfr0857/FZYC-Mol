param(
    [Parameter(Mandatory = $true)][string]$MediaDir,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$map = @{
    1 = 16
    2 = 18
    6 = 20
    7 = 21
    9 = 24
}

foreach ($k in $map.Keys) {
    Copy-Item -LiteralPath (Join-Path $MediaDir ("image{0}.png" -f $map[$k])) -Destination (Join-Path $OutputDir ("Figure{0}.png" -f $k)) -Force
}

function New-Canvas([int]$w, [int]$h) {
    $bmp = New-Object Drawing.Bitmap($w, $h)
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.Clear([Drawing.Color]::White)
    $g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    return @($bmp, $g)
}

function Draw-Panel($g, $img, [Drawing.Rectangle]$src, [Drawing.Rectangle]$dst) {
    $g.DrawImage($img, $dst, $src, [Drawing.GraphicsUnit]::Pixel)
}

$src19 = [Drawing.Image]::FromFile((Join-Path $MediaDir 'image19.png'))
try {
    $half = [int][Math]::Floor($src19.Height / 2)
    $cg = New-Canvas $src19.Width $half
    $bmp3, $g3 = $cg
    try {
        Draw-Panel $g3 $src19 (New-Object Drawing.Rectangle(0,0,$src19.Width,$half)) (New-Object Drawing.Rectangle(0,0,$src19.Width,$half))
        $bmp3.Save((Join-Path $OutputDir 'Figure3.png'), [Drawing.Imaging.ImageFormat]::Png)
    } finally { $g3.Dispose(); $bmp3.Dispose() }
} finally { $src19.Dispose() }

$src26 = [Drawing.Image]::FromFile((Join-Path $MediaDir 'image26.png'))
try {
    $cw = [int][Math]::Floor($src26.Width / 3)
    $rh = [int][Math]::Floor($src26.Height / 2)
    $pw = 1200
    $ph = 1440

    $cg = New-Canvas ($pw * 2) ($ph * 2)
    $bmp4, $g4 = $cg
    try {
        $panels4 = @(
            @{ c=0; r=0; x=0; y=0 },
            @{ c=1; r=0; x=$pw; y=0 },
            @{ c=2; r=0; x=0; y=$ph },
            @{ c=0; r=1; x=$pw; y=$ph }
        )
        foreach ($p in $panels4) {
            $sx = $p.c * $cw
            $sy = $p.r * $rh
            $sw = if ($p.c -eq 2) { $src26.Width - $sx } else { $cw }
            $sh = if ($p.r -eq 1) { $src26.Height - $sy } else { $rh }
            Draw-Panel $g4 $src26 (New-Object Drawing.Rectangle($sx,$sy,$sw,$sh)) (New-Object Drawing.Rectangle($p.x,$p.y,$pw,$ph))
        }
        $bmp4.Save((Join-Path $OutputDir 'Figure4.png'), [Drawing.Imaging.ImageFormat]::Png)
    } finally { $g4.Dispose(); $bmp4.Dispose() }

    $cg = New-Canvas ($src26.Width - $cw) ($src26.Height - $rh)
    $bmp5, $g5 = $cg
    try {
        Draw-Panel $g5 $src26 (New-Object Drawing.Rectangle($cw,$rh,($src26.Width-$cw),($src26.Height-$rh))) (New-Object Drawing.Rectangle(0,0,($src26.Width-$cw),($src26.Height-$rh)))
        $bmp5.Save((Join-Path $OutputDir 'Figure5.png'), [Drawing.Imaging.ImageFormat]::Png)
    } finally { $g5.Dispose(); $bmp5.Dispose() }
} finally { $src26.Dispose() }

$src22 = [Drawing.Image]::FromFile((Join-Path $MediaDir 'image22.png'))
$src23 = [Drawing.Image]::FromFile((Join-Path $MediaDir 'image23.png'))
try {
    $w = [Math]::Max($src22.Width, $src23.Width)
    $h = $src22.Height + $src23.Height
    $cg = New-Canvas $w $h
    $bmp8, $g8 = $cg
    try {
        $g8.DrawImage($src22, 0, 0, $src22.Width, $src22.Height)
        $g8.DrawImage($src23, 0, $src22.Height, $src23.Width, $src23.Height)
        $bmp8.Save((Join-Path $OutputDir 'Figure8.png'), [Drawing.Imaging.ImageFormat]::Png)
    } finally { $g8.Dispose(); $bmp8.Dispose() }
} finally { $src22.Dispose(); $src23.Dispose() }
