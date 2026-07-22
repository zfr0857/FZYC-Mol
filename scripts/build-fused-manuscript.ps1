param(
    [Parameter(Mandatory = $true)][string]$StructureJson,
    [Parameter(Mandatory = $true)][string]$FigureDir,
    [Parameter(Mandatory = $true)][string]$OutputDocx,
    [string]$OutputPdf = ''
)

$ErrorActionPreference = 'Stop'
$src = [IO.File]::ReadAllText($StructureJson, [Text.Encoding]::UTF8) | ConvertFrom-Json
$byIndex = @{}
foreach ($p in $src.paragraphs) { $byIndex[[int]$p.index] = $p }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.ScreenUpdating = $false
$doc = $word.Documents.Add()
$sel = $word.Selection

function Set-Font([double]$size, [bool]$bold = $false, [bool]$italic = $false, [string]$eastAsia = '宋体') {
    $script:sel.Font.Name = 'Times New Roman'
    try { $script:sel.Font.NameFarEast = $eastAsia } catch {}
    $script:sel.Font.Size = $size
    $script:sel.Font.Bold = if ($bold) { -1 } else { 0 }
    $script:sel.Font.Italic = if ($italic) { -1 } else { 0 }
}

function Reset-Paragraph {
    $script:sel.ParagraphFormat.Alignment = 3
    $script:sel.ParagraphFormat.LeftIndent = 0
    $script:sel.ParagraphFormat.RightIndent = 0
    $script:sel.ParagraphFormat.FirstLineIndent = 21
    $script:sel.ParagraphFormat.SpaceBefore = 0
    $script:sel.ParagraphFormat.SpaceAfter = 5
    $script:sel.ParagraphFormat.LineSpacingRule = 0
    $script:sel.ParagraphFormat.KeepWithNext = 0
    $script:sel.ParagraphFormat.KeepTogether = 0
    $script:sel.ParagraphFormat.PageBreakBefore = 0
    try { $script:sel.ParagraphFormat.OutlineLevel = 10 } catch {}
}

function Add-Para([string]$text, [string]$kind = 'Body') {
    if ([string]::IsNullOrWhiteSpace($text)) { return }
    $script:sel.EndKey(6) | Out-Null
    Reset-Paragraph
    Set-Font 10.5 $false $false '宋体'
    switch ($kind) {
        'Title' {
            Set-Font 16 $true $false '黑体'
            $script:sel.ParagraphFormat.Alignment = 1
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceAfter = 10
            try { $script:sel.ParagraphFormat.OutlineLevel = 1 } catch {}
        }
        'Subtitle' {
            Set-Font 10.5 $false $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 1
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceAfter = 8
        }
        'H1' {
            Set-Font 14 $true $false '黑体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceBefore = 12
            $script:sel.ParagraphFormat.SpaceAfter = 6
            $script:sel.ParagraphFormat.KeepWithNext = -1
            try { $script:sel.ParagraphFormat.OutlineLevel = 1 } catch {}
        }
        'H2' {
            Set-Font 12 $true $false '黑体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceBefore = 10
            $script:sel.ParagraphFormat.SpaceAfter = 4
            $script:sel.ParagraphFormat.KeepWithNext = -1
            try { $script:sel.ParagraphFormat.OutlineLevel = 2 } catch {}
        }
        'H3' {
            Set-Font 10.5 $true $false '黑体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceBefore = 7
            $script:sel.ParagraphFormat.SpaceAfter = 3
            $script:sel.ParagraphFormat.KeepWithNext = -1
            try { $script:sel.ParagraphFormat.OutlineLevel = 3 } catch {}
        }
        'Caption' {
            Set-Font 8.5 $false $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 3
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceBefore = 2
            $script:sel.ParagraphFormat.SpaceAfter = 7
            $script:sel.ParagraphFormat.KeepTogether = -1
        }
        'TableCaption' {
            Set-Font 8.5 $true $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceBefore = 7
            $script:sel.ParagraphFormat.SpaceAfter = 3
            $script:sel.ParagraphFormat.KeepWithNext = -1
        }
        'Note' {
            Set-Font 8 $false $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 3
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceAfter = 5
        }
        'Keywords' {
            Set-Font 10 $false $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.FirstLineIndent = 0
            $script:sel.ParagraphFormat.SpaceAfter = 8
        }
        'Reference' {
            Set-Font 9 $false $false '宋体'
            $script:sel.ParagraphFormat.Alignment = 0
            $script:sel.ParagraphFormat.LeftIndent = 18
            $script:sel.ParagraphFormat.FirstLineIndent = -18
            $script:sel.ParagraphFormat.SpaceAfter = 2
        }
    }
    $script:sel.TypeText($text)
    $script:sel.TypeParagraph()
}

function Add-PageBreak {
    $script:sel.EndKey(6) | Out-Null
    $script:sel.InsertBreak(7)
}

function Get-TableData([int]$index) {
    $t = $src.tables | Where-Object { [int]$_.index -eq $index } | Select-Object -First 1
    $rows = New-Object System.Collections.ArrayList
    foreach ($row in @($t.data)) { [void]$rows.Add([object[]]@($row)) }
    return ,$rows.ToArray()
}

function Add-Table([object[]]$data, [string]$caption, [string]$note = '') {
    Add-Para $caption 'TableCaption'
    $rows = $data.Count
    $cols = @($data[0]).Count
    $script:sel.EndKey(6) | Out-Null
    $tbl = $script:doc.Tables.Add($script:sel.Range, $rows, $cols)
    try {
        for ($r = 1; $r -le $rows; $r++) {
            $row = @($data[$r-1])
            for ($c = 1; $c -le $cols; $c++) {
                $tbl.Cell($r,$c).Range.Text = [string]$row[$c-1]
            }
        }
        $tbl.AllowAutoFit = -1
        $tbl.AutoFitBehavior(2)
        $tbl.Borders.Enable = 1
        $tbl.Rows.Item(1).HeadingFormat = -1
        $tbl.Rows.Item(1).Range.Bold = -1
        $tbl.Rows.Item(1).Range.ParagraphFormat.Alignment = 1
        $tbl.Rows.Item(1).Shading.BackgroundPatternColor = 15132390
        try { $tbl.Rows.AllowBreakAcrossPages = 0 } catch {}
        $tbl.Range.Font.Name = 'Times New Roman'
        try { $tbl.Range.Font.NameFarEast = '宋体' } catch {}
        $tbl.Range.Font.Size = 8
        $tbl.Range.ParagraphFormat.FirstLineIndent = 0
        $tbl.Range.ParagraphFormat.SpaceAfter = 0
        $tbl.TopPadding = 2
        $tbl.BottomPadding = 2
        $tbl.LeftPadding = 3
        $tbl.RightPadding = 3
        $script:sel.SetRange($tbl.Range.End, $tbl.Range.End)
        $script:sel.TypeParagraph()
    } finally {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($tbl)
    }
    if ($note) { Add-Para $note 'Note' }
}

function Add-Figure([int]$number, [string]$caption, [double]$width = 440, [bool]$newPage = $false) {
    if ($newPage) { Add-PageBreak }
    $path = Join-Path $FigureDir ("Figure{0}.png" -f $number)
    $script:sel.EndKey(6) | Out-Null
    Reset-Paragraph
    $script:sel.ParagraphFormat.Alignment = 1
    $script:sel.ParagraphFormat.FirstLineIndent = 0
    $script:sel.ParagraphFormat.SpaceAfter = 2
    $script:sel.ParagraphFormat.KeepWithNext = -1
    $shape = $script:sel.InlineShapes.AddPicture($path, $false, $true, $script:sel.Range)
    try {
        $shape.LockAspectRatio = -1
        $shape.Width = $width
        $script:sel.SetRange($shape.Range.End, $shape.Range.End)
        $script:sel.TypeParagraph()
    } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shape) }
    Add-Para $caption 'Caption'
}

function Apply-Replacements([string]$text, [hashtable]$repl) {
    foreach ($k in $repl.Keys) { $text = $text.Replace([string]$k, [string]$repl[$k]) }
    return $text
}

function Add-SourceRange([int]$start, [int]$end, [hashtable]$repl = @{}) {
    for ($i=$start; $i -le $end; $i++) {
        if (-not $byIndex.ContainsKey($i)) { continue }
        $p = $byIndex[$i]
        if ($p.inTable) { continue }
        $style = [string]$p.style
        if ($style -match 'FigureCaption|TableCaption|TableNote') { continue }
        $text = [string]$p.text
        if ([string]::IsNullOrWhiteSpace($text) -or $text.Trim() -eq '/') { continue }
        $text = Apply-Replacements $text $repl
        $kind = 'Body'
        if ($style -match '^标题 1') { $kind='H1' }
        elseif ($style -match '^标题 2') { $kind='H2' }
        elseif ($style -match '^标题 3') { $kind='H3' }
        Add-Para $text $kind
    }
}

try {
    $doc.PageSetup.PageWidth = 595.3
    $doc.PageSetup.PageHeight = 841.9
    $doc.PageSetup.TopMargin = 56.7
    $doc.PageSetup.BottomMargin = 56.7
    $doc.PageSetup.LeftMargin = 56.7
    $doc.PageSetup.RightMargin = 56.7
    $doc.PageSetup.HeaderDistance = 28.35
    $doc.PageSetup.FooterDistance = 28.35
    try { $doc.BuiltInDocumentProperties.Item('Title').Value = 'FZYC-Mol：候选扩张与多视图异质性下分子性质模型选择的验证治理' } catch {}
    try { $doc.BuiltInDocumentProperties.Item('Subject').Value = '融合修订稿：验证治理、候选池扩张、多视图候选与可靠性边界' } catch {}

    Add-Para 'FZYC-Mol：候选扩张与多视图异质性下分子性质模型选择的验证治理' 'Title'
    Add-Para '研究论文' 'Subtitle'

    Add-Para '摘要' 'H1'
    Add-Para '分子性质预测常需在有限验证信息上，从不断扩张且表征异质的候选中冻结最终策略；候选增加既可能提高可达到上界，也可能放大选择偏差。FZYC-Mol 将候选登记、验证侧选择、外层审计和可靠性证据组织为可追踪的验证治理协议。九个终点的 3 外层×3 内层×5 重复确认性实验中，K=32 相对 K=4 的配对固定分母选择损失（遗憾）增加 0.122（端点聚类 95% CI 0.072–0.175；精确 P=0.0078；九项检验 Holm P=0.039），经候选数机会校正的命中率下降 0.642（0.442–0.780）。随机排序负对照和六级信号恢复正对照验证了指标的零点与单调响应；原等权选择风险未通过层内置换，而严格嵌套的跨端点元风险在完全留出端点上将 MAE 从 0.123 降至 0.112，并使 50% 风险门控遗憾降低 0.034（0.020–0.047）。在相同冻结划分上，12 个多视图候选完成 6,480 次拟合，validation-best 相对 Morgan-only 的配对效用增益为 0.343（0.210–0.483），九个端点方向一致。MoleculeNet、TDC、逐样本风险、标签条件保形、MoleculeACE 和 bRo5 进一步表明，收益与失效均具有终点和化学空间依赖性。结果支持把冻结治理用于暴露并部分管理选择风险，但不支持外推至未同折重训的深度模型、独立时间外 ADMET 盲测或临床部署。' 'Body'

    Add-Para '科学贡献' 'H1'
    Add-Para 'FZYC-Mol 以冻结候选登记、随机化候选池和 3×3×5 重复嵌套审计评价模型选择；端点配对效应量、精确符号翻转和 Holm 校正确认 K=32 相对 K=4 的遗憾增加并非由少数折驱动。' 'Body'
    Add-Para '随机排序负对照给出零信息基线，连续信号注入正对照进一步验证机会校正命中、MRR 和固定分母遗憾能够随可恢复排序信息单调响应。' 'Body'
    Add-Para '风险证据被分为未通过独立验证的等权选择风险和严格嵌套的跨端点元风险；共享划分多视图重训则检验验证治理能否兑现异质候选的可达到上界。' 'Body'
    Add-Para '关键词：分子性质预测；模型选择治理；候选池扩张；多视图候选；嵌套验证；跨端点风险；信号恢复；固定分母遗憾' 'Keywords'

    Add-Para '1 引言' 'H1'
    Add-Para '药物发现早期的溶解度、脂溶性、渗透性、毒性和药代动力学预测不仅影响候选排序，也会改变合成、实验排队和风险复核的优先级。MoleculeNet 与 Therapeutics Data Commons（TDC）提供了可比较的公开任务和评价指标[1-2]。随着 Morgan 指纹、理化描述符、图神经网络、D-MPNN、冻结化学语言模型和预测层融合被纳入同一实验体系，“选择哪个模型”已从附属步骤转变为异质候选池中的独立决策问题。' 'Body'
    Add-SourceRange 12 16 @{ 'DCPM-ADMET、KROVEX 与 MolGramTreeNet'='DCPM-ADMET、多模态图融合与 MolGramTreeNet' }

    Add-Para '2 材料与方法' 'H1'
    for ($i=18; $i -le 226; $i++) {
        if ($i -eq 23) {
            $data1 = New-Object System.Collections.ArrayList
            $sourceTable1 = $src.tables | Where-Object { [int]$_.index -eq 1 } | Select-Object -First 1
            foreach ($row in @($sourceTable1.data)) { [void]$data1.Add([object[]]@($row)) }
            [void]$data1.Add([object[]]@('跨任务清洗审计','14 个主流程终点','标准化与哈希去重','冻结流程','53,878→53,522；15 无效、186 一致重复、155 冲突重复','泄漏与重复审计'))
            Add-Table $data1.ToArray() '表 1 | 数据资源、清洗、划分及其证据用途' '注：TDC 为跨来源公开面板，不等同于前瞻性时间外盲测；MoleculeACE 仅报告经核验且实际完成的 17 个任务。'
            continue
        }
        if ($i -eq 88) {
            Add-Table (Get-TableData 2) '表 2 | 候选选择策略、AutoML 对照及测试标签使用边界' '注：AutoGluon-Tabular 与轻量候选使用相同 Morgan-512 特征和外层划分；测试事后上界只用于评价，不参与晋级。'
            continue
        }
        if ($i -eq 154) {
            Add-Figure 1 '图 1 | FZYC-Mol 总体工作流。任务协议、分子视图、专家池、验证治理和证据输出在最终测试前形成单向冻结流程；虚线边界区分历史探索候选与共享划分确认候选。该图为概念图，不构成性能结果。' 440
            continue
        }
        if ($i -eq 156) { continue }
        if (-not $byIndex.ContainsKey($i)) { continue }
        $p = $byIndex[$i]
        if ($p.inTable) { continue }
        $style = [string]$p.style
        if ($style -match 'FigureCaption|TableCaption|TableNote') { continue }
        $text = [string]$p.text
        if ([string]::IsNullOrWhiteSpace($text) -or $text.Trim() -eq '/') { continue }
        $kind = 'Body'
        if ($style -match '^标题 2') { $kind='H2' }
        elseif ($style -match '^标题 3') { $kind='H3' }
        Add-Para $text $kind
    }

    Add-Para '3 结果' 'H1'

    Add-Para '3.1 随机化候选池控制确认规模效应' 'H2'
    Add-SourceRange 229 238 @{ '图 11b'='图 4b' }
    Add-Figure 2 '图 2 | 随机化候选池与随机排序负对照。a，三种随机化模式的完整 32 池固定分母遗憾。b，真实重复嵌套选择与 1,000 次置换负对照的机会校正 Top-3 命中率。c，三种随机化模式的 MRR。d，真实流程与置换负对照的固定分母遗憾。区间按终点聚类或置换分布给出。' 440

    Add-Para '3.2 重复嵌套验证、统计校准与跨端点风险' 'H2'
    Add-SourceRange 242 249 @{ '图 11d'='图 4d' }
    Add-Table (Get-TableData 3) '表 3 | 轻量候选池 3×3×5 重复嵌套审计' '注：共 9 个终点、5 个重复和 135 个外层测试单元/池规模。遗憾分母固定为同一外层单元完整 32 候选的测试效用范围；区间以终点为主要聚类单位。'
    Add-Figure 3 '图 3 | 3×3×5 重复嵌套扩池效应。a，完整 32 池固定分母遗憾随 K 增加。b，机会校正 Top-3 命中率随 K 增加而下降。稳定性与选择熵见表 3。' 440
    Add-Figure 4 '图 4 | 指标校准与跨端点风险闭环。a，九个终点中 K=32 相对 K=4 的配对固定分母遗憾变化。b，K=32 下六级信号恢复正对照。c，原等权选择风险的四分位趋势；层内置换 P=0.953，故仅作描述性证据。d，严格嵌套留一端点元风险在 50% 保留覆盖下的遗憾变化。' 390

    Add-Para '3.3 共享冻结划分的多视图候选确认' 'H2'
    Add-SourceRange 543 546
    Add-Table (Get-TableData 8) '表 4 | 配对扩池、风险校准与共享划分多视图结果' '注：遗憾与效用增益均以同一外层单元完整候选效用范围归一化。测试事后上界仅定义可达到上界，不参与选择。'
    Add-Figure 5 '图 5 | 共享冻结划分多视图收益（原闭环图 e、f 面板）。e，固定 Morgan RF、one-SE、风险调整和 validation-best 的平均标准化遗憾。f，多视图可达到增益、实际选择增益、拼接视图增益及 validation-best 相对 one-SE 的配对增益；误差条为端点聚类 95% CI。' 440

    Add-Para '3.4 MoleculeNet 冻结性能与 ClinTox 筛选语境' 'H2'
    Add-SourceRange 290 293 @{ '表 4'='表 5'; '图 5'='图 6'; '清楚展示了'='量化了' }
    Add-Table (Get-TableData 4) '表 5 | MoleculeNet 冻结结果与测试事后上界' '注：测试事后上界仅用于计算测试遗憾，不参与晋级；FreeSolv 保留了冻结选择与事后上界之间的差距。'
    Add-Figure 6 '图 6 | MoleculeNet 冻结性能、ClinTox 固定精度召回和排序审计。a,b，分类 ROC-AUC 与回归 RMSE；测试事后上界仅为评价参照。c，ClinTox 在精度不低于 0.80 或 0.90 时的召回率。d，不同候选池的验证-测试排序 Spearman。' 440

    Add-Para '3.5 TDC 门控显示终点异质性' 'H2'
    Add-SourceRange 348 351 @{ '表 5'='表 6'; '17 个保留终点不再被写成“0 个下降”。其中'='17 个保留终点不能被概括为“均无测试伤害”。其中' }
    Add-Table (Get-TableData 5) '表 6 | TDC 冻结策略晋级的五个终点' '注：相对增益均已转换为正向效用；95% 配对置信区间由 3 个随机种子的 Student t 区间计算。其余 17 个终点保留原基线。'
    Add-Figure 7 '图 7 | TDC 门控有效性审计。a，按门控类别汇总晋级与保留终点数。b，22 个终点的方向归一化测试变化及三随机种子区间；宽置信区间单独标记为证据不确定。' 440

    Add-Para '3.6 逐样本风险、标签条件保形与低相似度边界' 'H2'
    Add-SourceRange 399 405
    Add-Figure 8 '图 8 | 逐样本风险与标签条件保形。A 组（上部 a-d），BBBP、ClinTox 和 Caco2 的逐样本风险-覆盖曲线及描述性选择风险曲线；真实误差排序只定义风险下界。B 组（下部 a-d），分类总体和类别条件覆盖、回归覆盖、分类预测集合大小与 pooled fallback，以及回归区间宽度和训练标签 SD 标准化宽度。两类风险的统计单位不同，不作直接数值比较。' 380 $true

    Add-Para '3.7 MoleculeACE 与 bRo5 界定化学边界' 'H2'
    Add-SourceRange 411 414 @{ '表 6'='表 7' }
    Add-Table (Get-TableData 6) '表 7 | MoleculeACE 与 bRo5 化学边界结果' '注：MoleculeACE 汇总基于实际完成的 17 个任务和 3 个随机种子；方向准确率不等同于悬崖幅度预测准确。'
    Add-Figure 9 '图 9 | 化学边界分析。a，17 个 MoleculeACE 任务中预测差异与真实差异的 Spearman。b，差异相关与活性悬崖分子对方向准确率。c，CycPept-PAMPA 四种划分的 RMSE。d，LinPept CellPen 和 NonFouling 在随机、骨架和外缘划分下的 ROC-AUC 与 PR-AUC。' 440

    Add-Para '3.8 治理规则、负结果与失败案例' 'H2'
    Add-Para '治理规则与候选家族消融' 'H3'
    Add-SourceRange 469 474 @{ '普遍降低遗憾的机制'='能够稳定改善遗憾的机制' }
    Add-Para '失败案例与证据完整性' 'H3'
    Add-SourceRange 600 605
    $data8 = New-Object System.Collections.ArrayList
    $sourceTable9 = $src.tables | Where-Object { [int]$_.index -eq 9 } | Select-Object -First 1
    foreach ($row in @($sourceTable9.data)) { [void]$data8.Add([object[]]@($row)) }
    [void]$data8.Add([object[]]@('决策卡输出','跨终点','治理与适用域记录','被选候选、遗憾、AD、风险、保形与最近邻','接受/需人工复核/超出适用域','结构化字段用于审计，不构成临床阈值'))
    Add-Table $data8.ToArray() '表 8 | 代表性失败案例与决策卡字段' '注：案例按预定义的高误差、高风险或低相似度条件选取；案例用于解释边界，不用于估计总体发生率。'

    Add-Para '3.9 Source data 自动重建' 'H2'
    Add-SourceRange 651 651 @{ '图 1–11'='图 1–9' }

    Add-Para '4 讨论' 'H1'
    Add-SourceRange 653 658 @{ '随机化候选池、置换负对照、端点配对精确检验与 3×3×5 重复嵌套验证共同表明，候选池扩张削弱选择可信度'='随机化候选池、置换负对照、端点配对精确检验与 3×3×5 重复嵌套验证共同表明，在本研究覆盖的九个终点和轻量候选中，候选池扩张削弱选择可信度'; '连续信号恢复又证明指标能从正确零点单调响应'='连续信号恢复又验证了指标能够从正确零点单调响应' }
    Add-Para '在实际使用中，FZYC-Mol 更适合输出终点级选择记录与样本级决策卡，而不是只给出一个预测值。决策卡应同时记录被选候选、适用域相似度、逐样本预测风险、校准状态、保形集合或区间、最近邻和复核理由；这些字段提供可审计的降置信依据，但阈值仍应由具体实验场景、误判代价和独立验证共同确定。' 'Body'
    Add-SourceRange 659 661 @{ '不足以证明选择可靠'='不足以建立选择可靠性' }

    Add-Para '5 结论' 'H1'
    Add-SourceRange 701 703 @{ '信号恢复证明指标可校准'='信号恢复验证了指标的校准行为'; '不能保证普遍性能提升'='不意味着跨任务性能均会提升' }

    Add-Para '声明' 'H1'
    Add-SourceRange 705 720

    Add-Para '补充信息' 'H1'
    Add-SourceRange 722 722
    Add-SourceRange 723 723 @{ '图 1–11 均配套 PNG/SVG、source data 和生成脚本。'='图 1–9 的 PNG 预览已嵌入本稿；SVG、source data 与生成脚本应在投稿前按发布清单逐一核对并归档。' }

    Add-PageBreak
    Add-Para '参考文献' 'H1'
    for ($i=725; $i -le $src.paragraphs.Count; $i++) {
        if (-not $byIndex.ContainsKey($i)) { continue }
        $p = $byIndex[$i]
        if ($p.inTable) { continue }
        $text = [string]$p.text
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        if ($text.StartsWith('[11] ')) {
            $text = '[11] Uchibori Y, Kaneko H. Generation of molecules near the applicability domain boundaries of property prediction models. J Chem Inf Model. 2026;66:6866-6879. doi:10.1021/acs.jcim.5c03220.'
        }
        Add-Para $text 'Reference'
    }

    foreach ($sec in $doc.Sections) {
        try {
            $footer = $sec.Footers.Item(1)
            $footer.Range.ParagraphFormat.Alignment = 1
            [void]$footer.PageNumbers.Add()
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($footer)
        } catch {}
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($sec)
    }

    $doc.Repaginate()
    $doc.SaveAs2($OutputDocx, 16)
    if ($OutputPdf) { $doc.ExportAsFixedFormat($OutputPdf, 17) }
} catch {
    Write-Error ("Build failed at line {0}: {1}`n{2}" -f $_.InvocationInfo.ScriptLineNumber, $_.Exception.Message, $_.ScriptStackTrace)
    throw
} finally {
    $doc.Close(0)
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($sel)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
