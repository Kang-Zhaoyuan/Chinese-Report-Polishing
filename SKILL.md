---
name: chinese-report-polishing
description: 中文理工科实验报告的语言审查技能。由顶层调度者统筹，通过常驻撰改线程配合五类专职审核线程及对应的专项扫描模块，经工作区文件交换，消除人工智能写作痕迹、防御性论述、无意义冗余及句间逻辑断层。
---

# 中文实验报告语言审改规范

本  Skill 专注于中文理工科实验报告的语言表述与逻辑审改，默认不处理排版格式。全文遵循严谨、冷静、客观的原则，不使用任何 emoji 、文学用典或口语化修辞。

Word 排版作为独立可选插件存在，默认不启用。

---

## 零、 必须遵守的硬性约束

1. **在任何情况下，都应当使用多 SubAgent 的架构方式** ：不论用户是否明确要求，顶层调度者必须始终启动多线程运行。(撰)改者禁止单线程直接修改文稿。

2. **应当显式询问是否需要排版** ：若用户未明确指定排版要求，顶层调度者应暂时停止工作，显式用自然语言询问用户是否需要启用 Word 排版模块；若用户未明确确认，**则默认不启用** 排版线程，仅专注于文稿语言审查。

## 一、 执行顶层调度

当前主线程作为 **顶层调度者 (Orchestrator)** 运行，不直接读取实验指导书、不查阅实验代码、不改写报告正文。架构设计细节见 [references/architecture.md](references/architecture.md)。

> **询问排版需求（可选插件）** ：启动本技能时，若用户未明确指定排版要求，顶层调度者应显式用自然语言询问用户是否需要启用 Word 排版模块；若用户未明确确认，**默认不启用** 排版，仅专注于文稿语言质量审查。排版为全流程收尾工序，具体准则见 [references/rules_word_typesetting.md](references/rules_word_typesetting.md)，自指基准示范见 [references/typesetting_self_referential_case.md](references/typesetting_self_referential_case.md)。

1. **检查前置材料充分性** ：
   在启动撰写或审核子线程前，顶层调度者必须首先核验是否掌握了足够的实验材料：
   - **实验要求 / 指导书**：是否能定位到实验指导书文件（如已存在 `task_spec.md` 或用户在对话中给出了明确实验步骤与评分要求）；
   - **实验代码与数据**：是否能定位到本次实验的源码目录、修改补丁（`git diff` / `patch`）或实测运行日志。
   > **补齐缺失材料** ：若上述两项关键材料缺失任意一项，**顶层调度者必须立即暂停后续所有流程，直接在对话框中向用户明确询问并索取缺失的文件或代码路径**，严禁凭空推测或脑补代码实现细节。

2. **初始化工作区** ：
   确认材料齐全后，创建 `.polish_workspace/` 目录，准备 `task_spec.md`（任务要求）与待审报告文稿（支持 `.docx` 或 `.md`，可由常驻撰改者生成初稿，或直接载入已有初稿），并保存常驻撰改者的会话标识（`conversationId`）。

3. **按序推进五道专职审核工序**：每道工序同一轮启动一个审核线程，撰改者会话始终复用。

   | 工序 | 审核角色 | 类别 | 扫描参数 | 通过标记 |
   | --- | --- | --- | --- | --- |
   | 1 | 宏观结构 | 1～3 | `structure` | `STAGE_1_PASSED` |
   | 2 | 信息冗余 | 4～6 | `redundancy` | `STAGE_2A_PASSED` |
   | 3 | 段落逻辑 | 9～10 | `logic` | `STAGE_2B_PASSED` |
   | 4 | 句法词法 | 11～15 | `syntax` | `STAGE_2C_PASSED` |
   | 5 | 图文重复 | 7～8 | `visuals` | `STAGE_5_PASSED` 或 `STAGE_5_SKIPPED` |

   每轮先运行 `python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage <扫描参数> > .polish_workspace/prose_scan.txt`，再按 [派发模板](references/reviewer_prompt.md) 启动审核者，传入文稿、专属手册和冻结清单。docx 默认从第二页扫描；检查全文时加 `--include-cover`。

   工序1：传入指导书原始文件，要求审核者直接读取。

   工序2：按“段落目的 → 各句贡献 → 最后一句”审核整段，重点检查段末防御性措辞。

   工序3：核对段内因果和时序。

   工序4：将超过15阅读单位的分句交撰改者修改，用 `--check --compare-to <改写前副本>` 复检。确实无法压缩时，在 `dispute_log.md` 记录尝试和理由，交审核者确认 `LENGTH_EXCEPTION`，再按确认的分句复检。

   工序5：待图表完成后，用 `--visual-assets .polish_workspace/visual_assets` 导出图片，连同最新文稿交审核者。收到退出码3（`MATERIALS_PENDING`）时补齐材料并重跑。没有图表及占位符时跳过。修改正文后，复查受影响的冗余、逻辑和句长；修改图表后，再核对图文。

   审核未通过时，复用撰改者逐条修改并维护 `dispute_log.md`，再新建该工序审核者复审。同一位置两次争议升级为 `HOLD_FOR_HUMAN`，加入冻结清单供后续审核跳过。全部五道工序完成后，汇总冻结项提请用户裁决。专项扫描结果须逐项处理；脚本运行成功不替代模型审核。

---

## 二、 文件索引

- [references/architecture.md](references/architecture.md)：三层线程职责、五道专职工序及工作区文件通信协议。
- [references/writer_guide.md](references/writer_guide.md)：常驻撰改者核心规范（4 项硬性技术写作约束）。
- [references/error_taxonomy.md](references/error_taxonomy.md)：15 类语言错误总谱导航索引与分工映射。
  - [references/taxonomy_stage1_structure.md](references/taxonomy_stage1_structure.md)：工序一专属（第 1～3 类：非核心过程、脱离代码原理、双中心标题）。
  - [references/taxonomy_stage2_redundancy.md](references/taxonomy_stage2_redundancy.md)：工序二专属（第 4～6 类：防御性局限、自我证实、专业常识）。
  - [references/taxonomy_stage3_logic.md](references/taxonomy_stage3_logic.md)：工序三专属（第 9～10 类：空洞归因、句间逻辑断层）。
  - [references/taxonomy_stage4_syntax.md](references/taxonomy_stage4_syntax.md)：工序四专属（第 11～15 类：AI 过拟合词、主语异常、句长、自然语言算术、复合分支长段未拆分）。
  - [references/taxonomy_stage5_visuals.md](references/taxonomy_stage5_visuals.md)：工序五专属（第7～8类图文重复）。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个经典自然段拆解案例库。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：撰改者开局指令与五类专职审核分身的派发指令模板。
- [references/rules_word_typesetting.md](references/rules_word_typesetting.md)：【可选插件】Word 实验报告排版规范总则（8523 dxa 居中基准、参数速查与子手册导航）。
  - [references/typesetting_spacing_geometry.md](references/typesetting_spacing_geometry.md)：子手册一（版面几何与空行规范：左右边距、容器收窄、大章节分页与空行三态）。
  - [references/typesetting_code_blocks.md](references/typesetting_code_blocks.md)：子手册二（代码排版与注释规范：流式跨页、68 字符单行容量、逻辑单行跨行内在缩进、行尾注释垂直列对齐）。
  - [references/typesetting_fonts_math.md](references/typesetting_fonts_math.md)：子手册三（字符字体与公式规范：中西文字体映射、OMML 原生矢量公式）。
  - [references/typesetting_self_referential_case.md](references/typesetting_self_referential_case.md)：经典基准案例（排版参考样例：全要素自指叙述与一页式渲染示范）。
- `scripts/`（包含语言扫描模块与排版工程套件）：
  - [scripts/word_layout_engine.py](scripts/word_layout_engine.py)：Word 紧凑排版工程引擎（支持 8523 dxa 收窄、Beautifier 注释对齐、跨页流式代码框与 Word COM 无损导出）。
  - [scripts/check_layout.py](scripts/check_layout.py)：Word 报告机械静态排版合规检查器。
  - [scripts/check_prose.py](scripts/check_prose.py)：命令行总控调度入口。
  - [scripts/doc_parser.py](scripts/doc_parser.py)：`.docx` 表格递归解析、`.md` 跨行自然段合并及纯文本镜像导出模块。
  - [scripts/scan_structure.py](scripts/scan_structure.py)：工序一宏观结构扫描器。
  - [scripts/scan_redundancy.py](scripts/scan_redundancy.py)：工序二信息冗余扫描器。
  - [scripts/scan_logic.py](scripts/scan_logic.py)：工序三段落逻辑扫描器。
  - [scripts/scan_syntax.py](scripts/scan_syntax.py)：工序四句法词法扫描器。
  - [scripts/scan_visuals.py](scripts/scan_visuals.py)：导出实际图片及相邻图表文字，配对图文审核者。
  - [scripts/prose_metrics.py](scripts/prose_metrics.py)：统一阅读单位、分句切分及仅加逗号的复检。
