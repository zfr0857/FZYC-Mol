param([int]$CoreInnerPid = 132636)

$ErrorActionPreference = "Stop"
$python = "D:\python\python.exe"
$core = "D:\fzyc\scripts\run_paper31_expansion_training_20260717.py"
$similarity = "D:\fzyc\scripts\run_paper31_similarity_composition_20260717.py"
$logs = "D:\fzyc\output\paper31_expanded_intervention_20260717\logs"

while (Get-Process -Id $CoreInnerPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 10
}

& $python $core chemprop-outer 1> (Join-Path $logs "chemprop_outer.out.log") 2> (Join-Path $logs "chemprop_outer.err.log")
if ($LASTEXITCODE -ne 0) { throw "Core Chemprop outer stage failed." }

& $python $similarity chemprop-inner 1> (Join-Path $logs "similarity_chemprop_inner.out.log") 2> (Join-Path $logs "similarity_chemprop_inner.err.log")
if ($LASTEXITCODE -ne 0) { throw "Similarity Chemprop inner stage failed." }

& $python $similarity chemprop-outer 1> (Join-Path $logs "similarity_chemprop_outer.out.log") 2> (Join-Path $logs "similarity_chemprop_outer.err.log")
if ($LASTEXITCODE -ne 0) { throw "Similarity Chemprop outer stage failed." }

[pscustomobject]@{
    status = "complete"
    core_outer = $true
    similarity_inner = $true
    similarity_outer = $true
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs "chemprop_pipeline_complete.json") -Encoding utf8
