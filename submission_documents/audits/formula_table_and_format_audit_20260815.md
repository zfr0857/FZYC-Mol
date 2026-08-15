# Formula, table and format audit

Audit date: 2026-08-15

Result: 66 PASS, 0 FAIL.

The nine main-text displays and Supplementary Equations (1)–(22b) are native editable OMML. Table 3 deliberately remains formatted text rather than OMML so its symbol column survives WPS and LibreOffice conversion.

WPS and LibreOffice visual renders contain all equations and all Table 3 symbols. WPS exports equation glyphs through a non-semantic math-font map, so copied equation text from the WPS PDF is not reliable; the DOCX and LibreOffice PDF remain editable/searchable sources. This is a renderer limitation, not missing content.

## Checks

- **PASS — Main formulas — Nine Methods 2.5 displays are editable OMML**: count=9
- **PASS — Main formulas — Display equations centred**: all nine checked
- **PASS — Main formulas — Required token: arg max**: present
- **PASS — Main formulas — Required token: ∈**: present
- **PASS — Main formulas — Required token: Ginv**: present
- **PASS — Main formulas — Required token: Gdep**: present
- **PASS — Main formulas — Required token: Gavail**: present
- **PASS — Main formulas — Required token: Δq**: present
- **PASS — Main formulas — Required token: 32**: present
- **PASS — Main formulas — Required token: 4**: present
- **PASS — Main formulas — Exact decomposition identity displayed**: G_inv = G_avail + G_dep
- **PASS — Main formulas — Structured minus/fraction/summation operators**: minus is Unicode; summations stored as OMML n-ary objects
- **PASS — Main formulas — No malformed or replacement glyphs in DOCX math XML**: malformed=False
- **PASS — Main formulas — Outer-fold mean uses the defined fixed fold count F**: Gq,e,s(K) = f=1FGq((s,f),K)F,   q ∈ {inv, avail, dep}
- **PASS — Main formulas — Endpoint contrast uses the defined primary split-seed count S_main**: Δq(e) = s=1SmainGq,e,s(32) − Gq,e,s(4)Smain
- **PASS — Main formulas — Seed-level mean carries an explicit overbar**: Equation 8
- **PASS — Main formulas — Operators and descriptive subscripts upright; index q italic**: upright tokens=['arg max', 'avail', 'dep', 'inv', 'main', 'ref']
- **PASS — Main formulas — All display-math runs use explicit Cambria Math 11 pt**: runs=120; fonts=True; sizes=True
- **PASS — Chinese formulas — Nine displays are symbol-for-symbol synchronized with the English main text**: count=9
- **PASS — Supplement formulas — Equation inventory is exactly (1)–(22b)**: labels=['1', '2', '3', '4', '5a', '5b', '6', '7', '8', '9', '10a', '10b', '11', '12a', '12b', '13', '14', '15', '16', '17a', '17b', '18a', '18b', '19a', '19b', '20a', '20b', '21', '22a', '22b']
- **PASS — Supplement formulas — Equation (1) contains set-membership operator**: j ∈ C_K
- **PASS — Supplement formulas — No malformed formula glyphs in DOCX math XML**: checked all numbered displays
- **PASS — Supplement formulas — Equations (13) and (14) use the same overbar notation as the main text**: overbars=1 and 2
- **PASS — Supplement formulas — All numbered display-math runs use explicit Cambria Math 11 pt**: runs=433; fonts=True; sizes=True
- **PASS — Supplement formulas — Equation bodies are centred and numbers right-aligned without text boxes**: tabbed=30/30
- **PASS — Supplement formulas — Mixed descriptive and index subscripts follow mathematical typography**: best upright; u italic in Equation (2); same constructor used for X/G/L definitions
- **PASS — Formula-to-data — Delta_inv = Delta_avail + Delta_dep holds for every split-seed row**: rows=90; max absolute error=1.041e-16
- **PASS — Formula-to-code — Every displayed equation is mapped to an implementation or archived definition**: mapping rows=32; non-PASS=[]
- **PASS — Main tables — Exactly four editable Word tables**: count=4
- **PASS — Table 1 — Row inventory**: rows=10; expected=10
- **PASS — Table 1 — Rows cannot split across pages**: cantSplit=10/10
- **PASS — Table 1 — No vertical borders**: vertical-border elements=0
- **PASS — Table 1 — No colour or shading**: non-white fills=[]
- **PASS — Table 1 — Header rule is 0.75 pt**: cells=4/4
- **PASS — Table 1 — Fixed editable table grid**: twips=[1757, 1134, 4252, 2098]
- **PASS — Table 2 — Row inventory**: rows=6; expected=6
- **PASS — Table 2 — Rows cannot split across pages**: cantSplit=6/6
- **PASS — Table 2 — No vertical borders**: vertical-border elements=0
- **PASS — Table 2 — No colour or shading**: non-white fills=[]
- **PASS — Table 2 — Header rule is 0.75 pt**: cells=4/4
- **PASS — Table 2 — Fixed editable table grid**: twips=[1757, 1757, 3402, 2324]
- **PASS — Table 3 — Row inventory**: rows=12; expected=12
- **PASS — Table 3 — Rows cannot split across pages**: cantSplit=12/12
- **PASS — Table 3 — No vertical borders**: vertical-border elements=0
- **PASS — Table 3 — No colour or shading**: non-white fills=[]
- **PASS — Table 3 — Header rule is 0.75 pt**: cells=2/2
- **PASS — Table 3 — Fixed editable table grid**: twips=[2268, 6973]
- **PASS — Table 3 — Eleven core symbols retained**: u = (s, f); CK; V(u, j); A(u, j); ĵu(K); jrefinv(−s); jrefdep(−s, K); Ginv(u, K); Gdep(u, K); Gavail(u, K); Δinv(e)
- **PASS — Table 3 — Symbol column uses text runs rather than formula boxes**: OMML objects=0
- **PASS — Table 4 — Row inventory**: rows=10; expected=10
- **PASS — Table 4 — Rows cannot split across pages**: cantSplit=10/10
- **PASS — Table 4 — No vertical borders**: vertical-border elements=0
- **PASS — Table 4 — No colour or shading**: non-white fills=[]
- **PASS — Table 4 — Header rule is 0.75 pt**: cells=5/5
- **PASS — Table 4 — Fixed editable table grid**: twips=[1304, 2835, 1361, 1361, 2381]
- **PASS — Table 4 — Fixed requested column widths**: actual=[1304, 2835, 1361, 1361, 2381]; target=[1304, 2835, 1361, 1361, 2381]
- **PASS — Table 4 — All endpoint rows retained**: BACE; BBBP; ClinTox; HIA; P-gp; ESOL; FreeSolv; Lipophilicity; Caco2
- **PASS — Main formatting — No manual page breaks**: document.xml
- **PASS — Main formatting — Continuous line numbering configured**: section properties
- **PASS — Main formatting — Clean file has no active track revisions**: settings.xml
- **PASS — Supplementary workbook — Worksheet inventory**: sheets=64
- **PASS — Supplementary workbook — No formula error tokens**: formulas=337; errors=[]
- **PASS — Additional file 4 — Outer SHA-256 matches**: 10B4385D65337D0919AA5B11344519441CF77DC1C9BB4F56051DADF826501A71
- **PASS — Additional file 4 — ZIP CRC and internal SHA-256 manifest**: version=paper-release-2026-08-r12.9; verified=884/884; bad=None
- **PASS — Cross-software — WPS formula/table rendering**: pages=33; Methods 2.5 page=9; Table 3 page=10; symbols copyable=True
- **PASS — Cross-software — LibreOffice formula/table rendering**: pages=34; Methods 2.5 page=9; Table 3 page=10; symbols copyable=True
