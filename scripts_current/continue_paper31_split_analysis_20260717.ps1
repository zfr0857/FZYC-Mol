$ErrorActionPreference = "Stop"
$python = "D:\python\python.exe"
$script = "D:\fzyc\scripts\analyze_paper31_composition_split_loop_20260717.py"
$logs = "D:\fzyc\output\paper31_expanded_intervention_20260717\logs"
$simNew = "D:\fzyc\results\paper31_expanded_intervention_20260717\similarity_composition\new_candidates\run_manifest.json"
$simOuter = "D:\fzyc\results\paper31_expanded_intervention_20260717\similarity_composition\chemprop\chemprop_outer_audit.json"

while (-not ((Test-Path -LiteralPath $simNew) -and (Test-Path -LiteralPath $simOuter))) {
    Start-Sleep -Seconds 15
}

$proc = Start-Process -FilePath $python -ArgumentList @($script) -Wait -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\split_analysis.out.log" `
    -RedirectStandardError "$logs\split_analysis.err.log"
if ($proc.ExitCode -ne 0) { throw "Paper31 split-loop analysis failed with exit code $($proc.ExitCode)." }

[pscustomobject]@{
    status = "complete"
    core_analysis = $true
    split_analysis = $true
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath "$logs\analysis_pipeline_complete.json" -Encoding utf8
