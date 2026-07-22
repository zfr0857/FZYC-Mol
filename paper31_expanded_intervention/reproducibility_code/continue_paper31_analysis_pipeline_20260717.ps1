$ErrorActionPreference = "Stop"
$python = "D:\python\python.exe"
$logs = "D:\fzyc\output\paper31_expanded_intervention_20260717\logs"
$coreNew = "D:\fzyc\results\paper31_expanded_intervention_20260717\new_candidates\run_manifest.json"
$coreOuter = "D:\fzyc\results\paper31_expanded_intervention_20260717\chemprop\chemprop_outer_audit.json"
$simNew = "D:\fzyc\results\paper31_expanded_intervention_20260717\similarity_composition\new_candidates\run_manifest.json"
$simOuter = "D:\fzyc\results\paper31_expanded_intervention_20260717\similarity_composition\chemprop\chemprop_outer_audit.json"

while (-not ((Test-Path -LiteralPath $coreNew) -and (Test-Path -LiteralPath $coreOuter))) {
    Start-Sleep -Seconds 15
}
& $python "D:\fzyc\scripts\analyze_paper31_expanded_intervention_20260717.py" 1> (Join-Path $logs "core_analysis.out.log") 2> (Join-Path $logs "core_analysis.err.log")
if ($LASTEXITCODE -ne 0) { throw "Paper31 core analysis failed." }

while (-not ((Test-Path -LiteralPath $simNew) -and (Test-Path -LiteralPath $simOuter))) {
    Start-Sleep -Seconds 15
}
& $python "D:\fzyc\scripts\analyze_paper31_composition_split_loop_20260717.py" 1> (Join-Path $logs "split_analysis.out.log") 2> (Join-Path $logs "split_analysis.err.log")
if ($LASTEXITCODE -ne 0) { throw "Paper31 split-loop analysis failed." }

[pscustomobject]@{
    status = "complete"
    core_analysis = $true
    split_analysis = $true
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs "analysis_pipeline_complete.json") -Encoding utf8
