from __future__ import annotations


ABSTRACT_SECTIONS = {
    "Background:": (
        "Background: Molecular property-prediction studies increasingly compare large and correlated "
        "registries of representations, learning algorithms and tuning variants. Such expansion may "
        "introduce useful chemical information, but it also increases the opportunity to repeatedly rank "
        "noisy candidate estimates using finite validation data."
    ),
    "Methods:": (
        "Methods: We conducted a retrospective nested audit across nine public molecular-property endpoints "
        "using repeated seeded scaffold partitions. Progressively expanded candidate registries were evaluated "
        "through matrix-dependent diversity estimators, chance-adjusted ranking measures, permutation and graded "
        "signal-recovery controls, leave-one-seed-out cross-fitted references and matched-size multiview comparisons. Reliability was further examined "
        "across chemical-similarity and scaffold-support boundaries."
    ),
    "Results:": (
        "Results: Estimated candidate diversity changed markedly after common audit-unit difficulty and "
        "utility-level shifts were removed, showing that no single effective-rank value adequately "
        "characterized the registry. Chance-adjusted validation-ranking fidelity weakened as the candidate "
        "pool expanded. Observed adjusted ranking exceeded the permutation envelope at every K, while injected "
        "validation–audit signal monotonically restored recovery and reduced selection loss. Cross-fitted selection gaps increased in six of nine endpoints but decreased in three, "
        "demonstrating substantial endpoint heterogeneity rather than a universal expansion penalty. "
        "Matched-size multiview comparisons produced positive median gains in most endpoints, although the "
        "effects depended on representation composition and learner family. Prediction reliability deteriorated "
        "for molecules with limited chemical support, novel scaffolds and rare toxicity labels."
    ),
    "Conclusions:": (
        "Conclusions: Nominal candidate count alone did not describe the effective structure or risk of "
        "molecular model selection. Candidate expansion created both representational opportunity and "
        "additional selection pressure, while finite audit maxima remained optimistic reference estimates "
        "rather than true generalization bounds. Molecular benchmarks should jointly report candidate "
        "eligibility, matrix-dependent diversity, chance-adjusted ranking, cross-fitted gaps, computational "
        "exposure and chemical-support boundaries."
    ),
    "Scientific Contribution:": (
        "Scientific Contribution: This study separates nominal candidate-pool size from matrix-dependent "
        "utility-pattern diversity and chance-adjusted ranking degradation, calibrated by negative and positive controls. It combines cross-fitted "
        "selection-gap analysis with exhaustive matched-size representation comparisons and chemical-support "
        "auditing. The contribution is an analysis of molecular model-selection practice rather than a new "
        "predictor, universal selector or external validation study."
    ),
}


def render_abstract(endpoint_count: int, positive_count: int, negative_count: int) -> dict[str, str]:
    words = {3: "three", 6: "six", 9: "nine"}
    endpoint_word = words.get(endpoint_count, str(endpoint_count))
    positive_word = words.get(positive_count, str(positive_count))
    negative_word = words.get(negative_count, str(negative_count))
    rendered = dict(ABSTRACT_SECTIONS)
    rendered["Methods:"] = rendered["Methods:"].replace("nine public", f"{endpoint_word} public")
    rendered["Results:"] = rendered["Results:"].replace(
        "six of nine endpoints", f"{positive_word} of {endpoint_word} endpoints"
    ).replace("decreased in three", f"decreased in {negative_word}")
    return rendered


INTRODUCTION_PARAGRAPHS = [
    (
        "Modern molecular property prediction operates over a candidate space that extends far beyond a few "
        "fixed fingerprints and regressors. Contemporary studies may compare circular and substructure "
        "fingerprints, physicochemical descriptor panels, graph models, directed message-passing models, "
        "chemical-language models, pretrained representations, automated machine-learning systems, ensembles "
        "and post-hoc calibration strategies within the same benchmark [1,2,5–10,16–24,34,35]. Each component "
        "can encode a different inductive bias: fingerprints emphasize local motifs, descriptors summarize "
        "global molecular properties, graph networks learn neighbourhood interactions, and language models "
        "transfer regularities from large molecular corpora. The final reported performance therefore depends "
        "not only on the predictive capacity of individual candidates but also on which candidates entered the "
        "search, how extensively they were tuned, how their utilities were compared and how a winner was chosen. "
        "These choices can materially change the apparent benchmark conclusion. "
        "As registries grow, model search becomes part of the estimand rather than a neutral preliminary step, "
        "yet benchmark reports often describe the selected predictor more completely than the selection process "
        "that produced it."
    ),
    (
        "Candidate expansion has two distinct effects: genuine representational opportunity arises when an "
        "additional representation or learner captures chemical information that the existing registry cannot "
        "express; repeated validation-selection opportunity arises because every eligible candidate contributes "
        "another noisy utility estimate that can be ranked using the same finite validation information. The first "
        "mechanism can improve generalization through complementary chemical signal; the second can favour a "
        "candidate whose apparent advantage is specific to the available validation scaffolds. Correlation among "
        "candidates moderates but does not remove this tension, because near-duplicate pipelines may share most "
        "errors while still exchange ranks under finite sampling. Direct test leakage is not required: repeated "
        "comparisons among representations, learners, tuning variants, calibration rules and ensemble choices can "
        "consume validation information even when the final audit fold remains hidden during fitting [3,4]. A "
        "larger registry may therefore create useful opportunity and additional selection pressure at the same time."
    ),
    (
        "Nested cross-validation is the principal design for separating these stages. Inner folds support "
        "candidate ranking, hyperparameter selection and any fitted preprocessing, whereas an outer fold evaluates "
        "the frozen decision produced by that inner procedure. This separation prevents the tuning score itself "
        "from being reported as final predictive performance and permits alternative selectors to be compared on "
        "shared outer folds. Repeated seeded scaffold partitions further expose sensitivity to chemically coherent "
        "test groups and allow paired candidate comparisons under identical audit conditions. For molecular data, "
        "where random splits can place closely related compounds on both sides of the evaluation boundary, nested "
        "scaffold designs offer an important safeguard. They preserve a clear distinction between inner selection "
        "and outer evaluation and provide an auditable record of how a registered selector behaves across repeated "
        "chemical partitions."
    ),
    (
        "Nested evaluation nevertheless leaves several properties of the search unresolved. It does not quantify "
        "candidate dependence or establish that nominal candidate count equals effective diversity. It does not "
        "equalize compute exposure when larger registries require more fits, nor does it automatically account for "
        "unavailable or failed candidates. An outer score is valid for evaluating a frozen selector, but the maximum "
        "taken across many outer candidate scores can still exhibit outer-maximum optimism when examined after the "
        "fact. Effective-rank estimates also depend on matrix construction: raw utilities retain common audit-unit "
        "difficulty, row-centred utilities remove level shifts, fixed-reference contrasts depend on the chosen "
        "reference, and rank matrices discard utility spacing. These distinctions become acute when the number of "
        "candidates exceeds the number of audit units and an empirical candidate-correlation matrix is rank deficient. "
        "Finally, reuse of public outer folds for retrospective decomposition remains different from evaluation on "
        "an independent external cohort, even when inner fitting is leakage free."
    ),
    (
        "Model-selection behaviour must also be interpreted at chemical-support boundaries. Molecular similarity "
        "and scaffold novelty alter prediction difficulty, while activity cliffs show that close structural "
        "neighbours can have sharply different properties [9–14,29,30,33]. Rare positive classes create a separate "
        "risk: ROC-AUC can appear favourable even when precision, minority recall or false-negative behaviour is "
        "unsuitable for screening. Applicability-domain diagnostics, support-stratified performance, error overlap, "
        "uncertainty and conditional coverage therefore delimit what a selected model result means. Such analyses "
        "do not form an independent confirmation of the candidate-expansion finding, and they should not be averaged "
        "into a single performance score. They provide boundary evidence showing where apparently strong aggregate "
        "selection results may weaken for dissimilar molecules, novel scaffolds, activity-cliff pairs or scarce "
        "toxicity labels."
    ),
    (
        "Under a retrospectively locked repeated nested scaffold evaluation, how did candidate-pool expansion relate "
        "to matrix-dependent utility-pattern diversity, chance-adjusted ranking fidelity, cross-fitted selection gaps "
        "and representation-composition effects? We address this limited question through three contributions. First, "
        "we separate nominal K from diversity estimated under explicitly defined utility matrices. Second, we calibrate "
        "chance-adjusted validation ranking against permutation and graded signal-recovery controls and jointly audit leave-one-seed-out cross-fitted gaps, retaining classification "
        "and regression as task-stratified evidence rather than pooling incompatible units. Third, we combine "
        "matched-size representation comparisons with chemical-support and reliability analyses that bound the "
        "interpretation. Candidate eligibility, failed fits, split identities, source hashes and computational exposure "
        "remain part of the audit trail. The study evaluates model-selection behaviour and does not propose a new "
        "molecular predictor or an independent external validation."
    ),
]


DISCUSSION_SECTIONS = [
    (
        "4.1 Nominal K did not define candidate diversity",
        [
            "Candidate count, family count, representation count, compute exposure and effective diversity describe different aspects of a model search. Nominal K records how many candidates were eligible, whereas family and representation counts describe registry composition and compute exposure records how much fitting opportunity was consumed. None of these quantities establishes how independently candidates behaved across audit units.",
            "The registered prefixes increased candidate and compute exposure mechanically, but their candidates shared representations and closely related learners. Effective diversity instead summarized variation in observed utility patterns and remained conditional on the evaluated endpoints and splits. Molecular benchmark reports should therefore distinguish search size, registry composition, computational exposure and matrix-dependent effective diversity rather than treating any one quantity as a substitute for the others.",
        ],
    ),
    (
        "4.2 Matrix construction changed effective-rank interpretation",
        [
            "Raw utility, row-centred utility, fixed-reference utility and within-unit rank matrices answer different questions. Raw utilities retain common audit-unit difficulty; row-centred utilities remove common level shifts while imposing a row-sum constraint; fixed-reference contrasts depend on the prespecified reference; and within-unit ranks preserve ordering while discarding utility spacing. Their effective ranks should not be interpreted as competing estimates of one intrinsic candidate count.",
            "At the largest registry each endpoint supplied only 15 outer rows, so the empirical candidate-correlation matrix was rank deficient. Ledoit–Wolf shrinkage stabilized noisy covariance directions but did not create independent audit information. Spectral entropy and participation-ratio rank weight the eigenvalue spectrum differently, and omission and reference-sensitivity analyses changed endpoint magnitudes. Reporting these estimators together makes the matrix dependence visible and prevents selective use of whichever rank best supports a preferred narrative.",
        ],
    ),
    (
        "4.3 Chance-adjusted ranking degradation accompanied selection gaps",
        [
            "Raw winner recovery becomes mechanically harder as K grows, so the interpretation relies on opportunity-adjusted and graded ranking measures. CAHit@3 asks whether the eventual outer best entered a short validation list, normalized MRR credits its position relative to the random-order expectation, NDCG emphasizes the ordered utility profile, and Spearman, Kendall and rank percentile capture broader reordering.",
            "The permutation negative control placed both adjusted metrics around their random-order zero, whereas every observed CAHit@3 endpoint median exceeded its 95% null envelope. In the graded positive control, increasing injected validation–audit signal monotonically increased CAHit@3 and normalized MRR gain and reduced fixed-range selection loss at every K, reaching zero loss at perfect signal. These controls show that the metrics have the intended null and recovery behaviour. The empirical degradation still accompanied heterogeneous endpoint gaps without proving that one ranking statistic caused every loss.",
        ],
    ),
    (
        "4.4 Cross-fitting attenuated same-unit maxima",
        [
            "A same-unit maximum reuses the evaluated outer scores to define the reference and can therefore overstate the opportunity available to the selector. The leave-one-seed-out cross-fitted reference separated reference selection from held-out-seed evaluation and attenuated same-unit effects in most endpoints while retaining positive and negative cases.",
            "Cross-fitting did not remove finite-maximum optimism, model-registry conditioning or public endpoint reuse. The known-truth simulation illustrated finite-maximum optimism when noisy candidate estimates were maximized, but it was not used as a bias correction. Because the cross-fitted reference still uses the same public endpoint population and split generator, it is sensitivity evidence rather than external validation. Same-unit and cross-fitted estimates should be shown together so that dependence on the evaluated-unit maximum remains visible.",
        ],
    ),
    (
        "4.5 Matched-size analyses refined the multiview interpretation",
        [
            "Exhaustive enumeration of 220 overlapping matched-size subsets held candidate count fixed while changing representation and learner composition. These subsets map sensitivity within one registry and are not independent experiments. Mutually exclusive composition classes prevent balance, concatenation, representation and learner labels from being interpreted as independent factors.",
            "Endpoint-specific distributions retained heterogeneous and negative results, including the BACE negative median, while avoiding a pooled scale for ROC-AUC gains and RMSE reductions. Learner interaction and representation breadth remained intertwined in the larger K ladder, and matched size did not equalize every tuning or training budget. The analysis therefore supports endpoint-dependent composition effects rather than a general claim that multiview expansion is beneficial.",
        ],
    ),
    (
        "4.6 Reliability remained conditional on chemical support",
        [
            "Tanimoto support and novel-scaffold analyses showed that selection results remained conditional on chemical neighbourhood. Evidence from activity cliffs further demonstrates that close structural similarity does not guarantee similar properties, so applicability cannot be summarized by one average scaffold score. Error overlap, disagreement and support-stratified performance provide complementary boundary evidence.",
            "ClinTox illustrates why discrimination, conformal coverage and screening safety must remain separate. ROC-AUC can coexist with weak rare-class behaviour, and nominal coverage does not guarantee acceptable minority recall or false-negative risk. Conditional methods may improve coverage by enlarging prediction sets, but they do not establish deployment readiness. These reliability analyses delimit the model-selection audit rather than independently confirm it.",
        ],
    ),
    (
        "4.7 Limitations",
        [
            "The primary registry was intentionally near-duplicate, only nine endpoints entered the main audit, and effective diversity at the largest registry was estimated from 15 outer rows. Shrinkage and hierarchical resampling expose sensitivity but cannot replace additional independent audit units. The study was retrospective and not prospectively preregistered, and public outer folds were not an independent lockbox.",
            "The multiview and four-model panels reused public endpoints and did not equalize tuning budgets, so they cannot rank fully optimized modern architectures. Normalized utilities depend on finite pool scales, matched subsets overlap, and prediction-level exports were incomplete across the full registry. Post-hoc classification exports showed small stochastic refit drift, so locked primary metrics remained the source of record. Conformal, activity-cliff and chemical-support analyses are boundary evidence rather than prospective deployment studies.",
        ],
    ),
]


CHINESE_ABSTRACT_SECTIONS = {
    "背景：": "背景：分子性质预测研究越来越多地比较由表征、学习算法和调参变体组成的大型相关候选登记表。候选扩张可能引入有用的化学信息，但也增加了在有限验证数据上反复排序带噪候选估计的机会。",
    "方法：": "方法：本研究使用重复seeded scaffold partitions，对九个公开分子性质终点开展回顾性嵌套审计。递增候选登记表通过矩阵依赖多样性估计、机会校正排序、置换负对照与分级信号恢复正对照、留一seed交叉拟合参照和等规模多视图比较进行评价，并进一步考察化学相似性和骨架支持边界处的可靠性。",
    "结果：": "结果：去除共同审计单元难度和效用水平位移后，候选多样性估计发生明显变化，说明单一有效秩不足以刻画登记表。随着候选池扩大，机会校正验证排序保真度减弱。全部K下的观测校正排序均高于置换包络；注入的验证—审计信号增强时，恢复率单调提高且选择损失降低。交叉拟合选择差距在九个终点中六个增大、三个降低，表现为显著的终点异质性，而非普遍扩张惩罚。等规模多视图比较在多数终点产生正中位收益，但效应依赖表征组成和学习器家族。有限化学支持、新颖骨架和罕见毒性标签下的预测可靠性下降。",
    "结论：": "结论：名义候选数量本身不能描述分子模型选择的有效结构或风险。候选扩张同时带来表征机会和额外选择压力，而有限审计最大值仍是带有乐观性的参照估计，并非真实泛化上界。分子基准应联合报告候选资格、矩阵依赖多样性、机会校正排序、交叉拟合差距、计算暴露和化学支持边界。",
    "科学贡献：": "科学贡献：本研究将名义候选池规模与矩阵依赖效用模式多样性和机会校正排序退化分开，并用负对照与正对照校准排序量。研究联合交叉拟合选择差距、穷举等规模表征比较与化学支持审计。本文贡献是对分子模型选择实践的分析，而非新的预测器、通用选择器或外部验证研究。",
}


def render_chinese_abstract(endpoint_count: int, positive_count: int, negative_count: int) -> dict[str, str]:
    words = {3: "三", 6: "六", 9: "九"}
    endpoint_word = words.get(endpoint_count, str(endpoint_count))
    positive_word = words.get(positive_count, str(positive_count))
    negative_word = words.get(negative_count, str(negative_count))
    rendered = dict(CHINESE_ABSTRACT_SECTIONS)
    rendered["方法："] = rendered["方法："].replace("九个公开", f"{endpoint_word}个公开")
    rendered["结果："] = rendered["结果："].replace(
        "九个终点中六个", f"{endpoint_word}个终点中{positive_word}个"
    ).replace("三个降低", f"{negative_word}个降低")
    return rendered


CHINESE_INTRODUCTION_PARAGRAPHS = [
    "现代分子性质预测的候选空间已远超少量固定指纹和回归器。当前研究可能在同一基准中同时比较环形与子结构指纹、理化描述符、图模型、消息传递模型、化学语言模型、预训练表征、AutoML、集成和校准策略[1,2,5–10,16–24,34,35]。每类候选具有不同归纳偏置，最终报告性能不仅取决于单个预测器，也取决于哪些候选进入搜索、调优暴露、效用比较方式以及获胜者如何确定。因此，模型搜索本身构成研究估计对象的一部分，而不是与结论无关的预处理步骤。",
    "候选扩张具有双重作用。真实表征机会是指新增候选捕获原登记表无法表达的互补化学信息；重复验证选择机会则来自每个候选在同一有限验证信息上贡献一个带噪效用估计。前者可能改善泛化，后者可能使特定验证骨架上偶然占优的候选获得更高排名。候选相关性会削弱但不能消除这种张力，因为高度相似的流程仍可能在有限样本下交换排序。即使外层折不参与拟合，表征、学习器、调参变体、校准规则和集成方案的反复比较仍会消耗验证信息[3,4]。",
    "嵌套交叉验证是分离内层选择和外层评估的主要设计。内层折用于候选排序、超参数选择和所有拟合型预处理，外层折仅评估由内层程序冻结的决策，从而避免把调参分数直接当作最终性能。重复的seeded scaffold partitions还能在化学连贯的测试组上暴露划分敏感性，并支持候选在共享外层折上的配对比较。对可能存在近邻分子跨随机划分的数据而言，这种设计是重要保障。",
    "然而，嵌套评价不会自动解决候选依赖、名义K与有效多样性的区别、计算暴露不等、失败或不可用候选、矩阵构造敏感性以及外层最大值乐观性。外层折可以有效评价冻结选择器，但事后在多个外层候选估计中取最大值仍可能产生有限最大值偏差。当候选数超过审计单元数时，经验候选相关矩阵还会秩亏。原始、逐行中心化、固定参照和秩矩阵回答不同问题。复用公开外层折进行回顾性分解也不同于独立外部验证。",
    "模型选择结果还必须由化学支持边界限定。分子相似性和骨架新颖性会改变预测难度，活性悬崖说明结构接近并不保证性质相近[9–14,29,30,33]。罕见阳性类别还可能使ROC-AUC掩盖精确率、少数类召回和假阴性风险。适用域、支持分层性能、错误重叠、不确定性和条件覆盖应作为边界证据，说明总体选择结果在低相似度分子、新颖骨架、活性悬崖或稀少毒性标签处可能如何减弱，而不是作为独立确认或合并成单一得分。",
    "本研究提出一个限定问题：在回顾性锁定的重复嵌套骨架评价下，候选池扩张如何与矩阵依赖效用模式多样性、机会校正排序保真度、交叉拟合选择差距和表征组成效应相关？贡献限定为三点：区分名义K与明确矩阵下估计的多样性；以置换和分级信号恢复对照校准机会校正排序，并联合审计留一seed交叉拟合差距；结合等规模表征比较和化学支持边界分析。研究保留候选资格、失败拟合、划分身份、source hashes和计算暴露。本文评价模型选择行为，不提出新的分子预测器，也不构成独立外部验证。",
]


CHINESE_DISCUSSION_SECTIONS = [
    ("4.1 名义K不能定义候选多样性", ["候选数量、家族数量、表征数量、计算暴露和有效多样性描述模型搜索的不同维度。名义K记录可选择候选数，家族与表征数描述登记组成，计算暴露记录拟合机会；这些量均不能直接证明候选在审计单元上的行为独立性。", "登记前缀随K机械增加候选与计算暴露，但候选共享表征和相近学习器。有效多样性仅概括既定终点与划分中的效用模式，因此报告时应将搜索规模、登记组成、计算暴露和矩阵依赖有效多样性分开。"]),
    ("4.2 矩阵构造改变有效秩解释", ["原始效用、逐行中心化效用、固定参照效用和单元内秩回答不同问题。原始矩阵保留共同审计难度；逐行中心化去除水平位移但引入行和约束；固定参照依赖预设参照；秩矩阵保留顺序却丢失效用间距。", "最大登记表中每个终点只有15个外层行，经验候选相关矩阵因而秩亏。Ledoit–Wolf收缩稳定噪声协方差方向，却不会创造独立信息。谱熵秩与参与率秩对特征谱赋权不同，应与留一和参照敏感性结果共同报告。"]),
    ("4.3 机会校正排序退化伴随选择差距", ["原始获胜者恢复会随K机械变难，因此解释依赖机会校正和分级排序量。CAHit@3评价外层最佳是否进入验证短名单，标准化MRR相对随机期望评价其位置，NDCG、Spearman、Kendall和秩百分位刻画更广泛的重排。", "置换负对照使两个校正指标回到随机排序零点，所有K下的观测CAHit@3终点中位数均高于95%置换包络。分级正对照中，注入验证—审计信号增强时，CAHit@3和标准化MRR单调提高，固定范围选择损失单调降低，并在完全信号时降为零。这证明指标具有预期的零点与信号恢复行为；真实排序退化仍与异质终点差距相伴，但不能证明单一排序量造成每个损失。"]),
    ("4.4 交叉拟合削弱同一单元最大值", ["同一单元最大值使用被评价外层分数定义参照，可能夸大选择器可利用的机会。留一seed交叉拟合将参照选择与留出seed评价分离，在多数终点削弱同一单元效应，同时保留正负结果。", "交叉拟合没有消除有限最大值乐观性、登记条件化或公开终点复用。已知真值模拟只说明最大化带噪候选估计的机械性质，不用于偏差校正。该参照是敏感性证据而非外部验证。"]),
    ("4.5 等规模分析修正多视图解释", ["完整枚举220个重叠等规模子集，在固定候选数下改变表征和学习器组成。这些子集描绘同一登记表中的敏感性，并非独立实验；互斥组成类别避免把平衡、拼接、表征和学习器标签解释为独立因素。", "终点分布保留BACE负中位效应及其他弱效应，且不合并ROC-AUC收益和RMSE降低。更大K阶梯仍交织表征广度、学习器相互作用和额外选择机会，因此只支持依赖终点的组成效应。"]),
    ("4.6 可靠性仍取决于化学支持", ["Tanimoto支持、新颖骨架和活性悬崖表明选择结果依赖化学邻域。错误重叠、分歧与支持分层性能是互补边界证据，不能由单一平均骨架分数替代。", "ClinTox说明判别、保形覆盖和筛选安全性必须分开。ROC-AUC可能与罕见类别召回不足或较高假阴性风险并存；提高条件覆盖通常还会扩大预测集。这些分析限定模型选择审计，不证明部署就绪。"]),
    ("4.7 局限性", ["主要登记表有意包含近重复候选，主审计仅含九个终点，最大登记表的有效多样性由15个外层行估计。收缩和层级重采样不能替代更多独立审计单元；本研究为回顾性分析且未前瞻性预注册，公开外层折也不是独立锁箱。", "多视图和四模型面板复用公开终点且调优预算不等，不能形成现代架构排行榜。标准化效用依赖有限池尺度，等规模子集高度重叠，完整逐候选预测导出仍不齐全。事后分类导出存在小幅随机重拟合漂移，因此锁定主指标继续作为正式结果来源。"]),
]
