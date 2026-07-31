$ErrorActionPreference = 'Stop'

$repo = 'D:\fzyc'
$runner = Join-Path $repo 'scripts\run_expanded_nested_candidate_pool_20260621.py'
$logDir = Join-Path $repo 'output\paper43_jcheminform_completion_20260726\logs'
$tasks = @('esol', 'freesolv', 'lipo', 'tdc_caco2_wang')
$seeds = @(11, 23, 37, 53, 71)

foreach ($seed in $seeds) {
    $env:FZYC_NESTED_OUT = Join-Path $repo "results\paper43_regression_split_rerun\seed_$seed"
    "$(Get-Date -Format o) START regression split-manifest rerun seed=$seed" | Tee-Object -FilePath (Join-Path $logDir 'regression_split_orchestrator.log') -Append
    & py $runner --tasks $tasks --max-candidates 32 --seed $seed --force `
        1>> (Join-Path $logDir "regression_split_seed_${seed}.out.log") `
        2>> (Join-Path $logDir "regression_split_seed_${seed}.err.log")
    if ($LASTEXITCODE -ne 0) { throw "Regression split rerun failed for seed $seed" }
}
"$(Get-Date -Format o) COMPLETE regression split-manifest reruns" | Tee-Object -FilePath (Join-Path $logDir 'regression_split_orchestrator.log') -Append
