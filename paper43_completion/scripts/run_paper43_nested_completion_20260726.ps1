$ErrorActionPreference = 'Stop'

$repo = 'D:\fzyc'
$runner = Join-Path $repo 'scripts\run_expanded_nested_candidate_pool_20260621.py'
$logDir = Join-Path $repo 'output\paper43_jcheminform_completion_20260726\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$classTasks = @('bbbp', 'bace', 'clintox', 'tdc_hia_hou', 'tdc_pgp_broccatelli')
$allTasks = @('bbbp', 'bace', 'clintox', 'esol', 'freesolv', 'lipo', 'tdc_caco2_wang', 'tdc_hia_hou', 'tdc_pgp_broccatelli')
$oldSeeds = @(11, 23, 37, 53, 71)
$newSeeds = @(83, 97, 113, 127, 149)

foreach ($seed in $oldSeeds) {
    $env:FZYC_NESTED_OUT = Join-Path $repo "results\paper43_metric_rerun\seed_$seed"
    $stamp = Get-Date -Format o
    "$stamp START old-seed classification metric rerun seed=$seed" | Tee-Object -FilePath (Join-Path $logDir 'orchestrator.log') -Append
    & py $runner --tasks $classTasks --max-candidates 32 --seed $seed --force `
        1>> (Join-Path $logDir "metric_seed_${seed}.out.log") `
        2>> (Join-Path $logDir "metric_seed_${seed}.err.log")
    if ($LASTEXITCODE -ne 0) { throw "Metric rerun failed for seed $seed" }
}

foreach ($seed in $newSeeds) {
    $env:FZYC_NESTED_OUT = Join-Path $repo "results\paper43_additional_seeds\seed_$seed"
    $stamp = Get-Date -Format o
    "$stamp START additional full nested seed=$seed" | Tee-Object -FilePath (Join-Path $logDir 'orchestrator.log') -Append
    & py $runner --tasks $allTasks --max-candidates 32 --seed $seed --force `
        1>> (Join-Path $logDir "additional_seed_${seed}.out.log") `
        2>> (Join-Path $logDir "additional_seed_${seed}.err.log")
    if ($LASTEXITCODE -ne 0) { throw "Additional nested run failed for seed $seed" }
}

$stamp = Get-Date -Format o
"$stamp COMPLETE all nested completion runs" | Tee-Object -FilePath (Join-Path $logDir 'orchestrator.log') -Append
