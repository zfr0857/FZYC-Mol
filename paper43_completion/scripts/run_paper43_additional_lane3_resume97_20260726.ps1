param([int]$WaitPid)

$ErrorActionPreference = 'Stop'
$repo = 'D:\fzyc'
$runner = Join-Path $repo 'scripts\run_expanded_nested_candidate_pool_20260621.py'
$logDir = Join-Path $repo 'output\paper43_jcheminform_completion_20260726\logs'
$tasks = @('bbbp', 'bace', 'clintox', 'esol', 'freesolv', 'lipo', 'tdc_caco2_wang', 'tdc_hia_hou', 'tdc_pgp_broccatelli')

"$(Get-Date -Format o) lane3 waiting to resume seed=97 after pid=$WaitPid" | Tee-Object -FilePath (Join-Path $logDir 'additional_parallel_orchestrator.log') -Append
Wait-Process -Id $WaitPid -ErrorAction SilentlyContinue
$seed = 97
$env:FZYC_NESTED_OUT = Join-Path $repo "results\paper43_additional_seeds\seed_$seed"
"$(Get-Date -Format o) START lane3 resume additional full nested seed=$seed" | Tee-Object -FilePath (Join-Path $logDir 'additional_parallel_orchestrator.log') -Append
& py $runner --tasks $tasks --max-candidates 32 --seed $seed `
    1>> (Join-Path $logDir "additional_seed_${seed}.out.log") `
    2>> (Join-Path $logDir "additional_seed_${seed}.err.log")
if ($LASTEXITCODE -ne 0) { throw "Additional nested resume failed for seed $seed" }
"$(Get-Date -Format o) COMPLETE lane3 seed=97" | Tee-Object -FilePath (Join-Path $logDir 'additional_parallel_orchestrator.log') -Append
