param([int]$CoreInnerPid = 132636)

$ErrorActionPreference = "Stop"
$python = "D:\python\python.exe"
$core = "D:\fzyc\scripts\run_paper31_expansion_training_20260717.py"
$similarity = "D:\fzyc\scripts\run_paper31_similarity_composition_20260717.py"
$logs = "D:\fzyc\output\paper31_expanded_intervention_20260717\logs"
$coreOuterAudit = "D:\fzyc\results\paper31_expanded_intervention_20260717\chemprop\chemprop_outer_audit.json"
$simOuterAudit = "D:\fzyc\results\paper31_expanded_intervention_20260717\similarity_composition\chemprop\chemprop_outer_audit.json"

function Start-AffinityLane {
    param(
        [string]$Name,
        [string]$Body,
        [int64]$Affinity
    )
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Body))
    $proc = Start-Process powershell.exe -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded
    ) -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 250
    try { $proc.ProcessorAffinity = [IntPtr]$Affinity } catch { }
    return $proc
}

$laneA = @"
`$ErrorActionPreference = 'Stop'
try { [Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity = [IntPtr]0x03F } catch { }
while (Get-Process -Id $CoreInnerPid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 10 }
& '$python' '$core' chemprop-outer 1> '$logs\chemprop_outer.out.log' 2> '$logs\chemprop_outer.err.log'
if (`$LASTEXITCODE -ne 0) { throw 'Core Chemprop outer stage failed.' }
"@

$laneB = @"
`$ErrorActionPreference = 'Stop'
try { [Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity = [IntPtr]0xFC0 } catch { }
& '$python' '$similarity' chemprop-inner 1> '$logs\similarity_chemprop_inner.out.log' 2> '$logs\similarity_chemprop_inner.err.log'
if (`$LASTEXITCODE -ne 0) { throw 'Similarity Chemprop inner stage failed.' }
& '$python' '$similarity' chemprop-outer 1> '$logs\similarity_chemprop_outer.out.log' 2> '$logs\similarity_chemprop_outer.err.log'
if (`$LASTEXITCODE -ne 0) { throw 'Similarity Chemprop outer stage failed.' }
"@

$a = Start-AffinityLane -Name "paper31-core" -Body $laneA -Affinity 0x03F
$b = Start-AffinityLane -Name "paper31-similarity" -Body $laneB -Affinity 0xFC0

Wait-Process -Id $a.Id
Wait-Process -Id $b.Id
if (-not (Test-Path -LiteralPath $coreOuterAudit)) { throw "Missing core outer audit." }
if (-not (Test-Path -LiteralPath $simOuterAudit)) { throw "Missing similarity outer audit." }

[pscustomobject]@{
    status = "complete"
    mode = "two affinity-isolated CPU lanes"
    core_outer = $true
    similarity_inner = $true
    similarity_outer = $true
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs "chemprop_pipeline_complete.json") -Encoding utf8
