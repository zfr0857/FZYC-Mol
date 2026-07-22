$ErrorActionPreference = "Stop"
$python = "D:\python\python.exe"
$root = "D:\fzyc"
$out = "$root\output\paper31_expanded_intervention_20260717"
$logs = "$out\logs"
$package = "$root\output\paper31_submission_package_20260717"
$analysisMarker = "$logs\analysis_pipeline_complete.json"
$english = "$package\Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(7).docx"
$chinese = "$package\候选池扩张与模型选择损失_中文完整论文(7).docx"

function Invoke-Python {
    param([string]$Script, [string]$Name)
    & $python $Script 1> "$logs\$Name.out.log" 2> "$logs\$Name.err.log"
    if ($LASTEXITCODE -ne 0) { throw "$Name failed." }
}

while (-not (Test-Path -LiteralPath $analysisMarker)) {
    Start-Sleep -Seconds 15
}

Invoke-Python "$root\scripts\build_paper31_figures_20260717.py" "final_figures"
Invoke-Python "$root\scripts\build_paper31_supplementary_tables_20260717.py" "final_tables"
Invoke-Python "$root\scripts\build_paper31_equation_assets_20260717.py" "final_equations"
Invoke-Python "$root\scripts\build_paper31_manuscripts_20260717.py" "final_manuscripts"

& "$root\scripts\insert_paper31_native_equations_20260717.ps1" -EnglishPath $english -ChinesePath $chinese 1> "$logs\insert_equations.out.log" 2> "$logs\insert_equations.err.log"
if ($LASTEXITCODE -ne 0) { throw "Native equation insertion failed." }
& "$root\scripts\insert_paper31_vector_figure7_20260717.ps1" -EnglishPath $english -ChinesePath $chinese 1> "$logs\insert_figure7.out.log" 2> "$logs\insert_figure7.err.log"
if ($LASTEXITCODE -ne 0) { throw "Vector Figure 7 insertion failed." }
& "$root\scripts\export_paper31_manuscript_pdfs_20260717.ps1" -EnglishPath $english -ChinesePath $chinese 1> "$logs\export_pdfs.out.log" 2> "$logs\export_pdfs.err.log"
if ($LASTEXITCODE -ne 0) { throw "PDF export failed." }

Invoke-Python "$root\scripts\assemble_paper31_submission_package_20260717.py" "assemble_pre_qc"
Invoke-Python "$root\scripts\verify_paper31_submission_package_20260717.py" "final_qc"
Invoke-Python "$root\scripts\assemble_paper31_submission_package_20260717.py" "assemble_post_qc"

[pscustomobject]@{
    status = "complete"
    package = $package
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath "$logs\finalization_pipeline_complete.json" -Encoding utf8
