---
name: chinese-report-polishing
description: 中文理工科实验报告的语言审查技能。由顶层调度者统筹，通过常驻撰改线程配合四类专职审核线程及对应的专项扫描模块，经工作区文件交换，消除人工智能写作痕迹、防御性论述、无意义冗余及句间逻辑断层。
---

# 中文实验报告语言审改规范

本技能专注于中文理工科实验报告的语言表述与逻辑审改，默认不处理排版格式。全文遵循严谨、冷静、客观的原则，不使用任何表情符号、文学用典或口语化修辞。Word 排版作为独立可选插件存在，默认不启用。

---

## 一、 顶层调度执行流程

当前主线程作为 **顶层调度者 (Orchestrator)** 运行，不直接读取实验指导书、不查阅实验代码、不改写报告正文。架构设计细节见 [references/architecture.md](references/architecture.md)。

> **排版询问机制（可选插件）** ：启动本技能时，若用户未明确指定排版要求，顶层调度者应显式用自然语言询问用户是否需要启用 Word 排版模块；若用户未明确确认，**默认不启用** 排版，仅专注于文稿语言质量审查。排版具体准则见 [references/rules_word_typesetting.md](references/rules_word_typesetting.md)，基准案例见 [references/typesetting_case_os_lab4.md](references/typesetting_case_os_lab4.md) 与 [references/typesetting_case_csapp_lab4_5.md](references/typesetting_case_csapp_lab4_5.md)。

1. **前置材料充分性检查** ：
   在启动撰写或审核子线程前，顶层调度者必须首先核验是否掌握了足够的实验材料：
   - **实验要求 / 指导书**：是否能定位到实验指导书文件（如已存在 `task_spec.md` 或用户在对话中给出了明确实验步骤与评分要求）；
   - **实验代码与数据**：是否能定位到本次实验的源码目录、修改补丁（`git diff` / `patch`）或实测运行日志。
   > **缺失处理约束** ：若上述两项关键材料缺失任意一项，**顶层调度者必须立即暂停后续所有流程，直接在对话框中向用户明确询问并索取缺失的文件或代码路径**，严禁凭空推测或脑补代码实现细节。

2. **初始化工作区** ：
   确认材料齐全后，创建 `.polish_workspace/` 目录，准备 `task_spec.md`（任务要求）与待审报告文稿（支持 `.docx` 或 `.md`，可由常驻撰改者生成初稿，或直接载入已有初稿），并保存常驻撰改者的会话标识（`conversationId`）。

3. **按序推进四道专职审核工序** ：
   每道工序绑定独立的扫描模块（模板见 [references/reviewer_prompt.md](references/reviewer_prompt.md)）。顶层调度者统一维护一份【已冻结的人工裁决位置清单】（初始为空）。每轮启动审核分身前，顶层调度者负责调用对应 `--stage` 参数，导出纯文本镜像 `draft_view.md` 并生成专属的 `prose_scan.txt`。派发指令时，顶层调度者显式传入原文稿路径及当前冻结清单：
   - **工序一：宏观结构审核者（第 1～3 类）**
     - 必须显式传入实验指导书原始裸文件（`{spec_path}`），要求审核者直接阅读裸文件，严防中间转述过滤掉必选图表或任务细节；
     - 调度生成扫描报告：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage structure > .polish_workspace/prose_scan.txt`（底层调用 [scan_structure.py](scripts/scan_structure.py)）
     - 专属子手册：[references/taxonomy_stage1_structure.md](references/taxonomy_stage1_structure.md)
     - 循环新建宏观结构审核分身（自动跳过已冻结位置），直至未冻结文本全部达标输出 `STAGE_1_PASSED`。
   - **工序二：信息冗余审核者（第 4～8 类）**
     - 调度生成扫描报告：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage redundancy > .polish_workspace/prose_scan.txt`（底层调用 [scan_redundancy.py](scripts/scan_redundancy.py)）
     - 专属子手册：[references/taxonomy_stage2_redundancy.md](references/taxonomy_stage2_redundancy.md)
     - 循环新建信息冗余审核分身（自动跳过已冻结位置），直至未冻结文本全部达标输出 `STAGE_2A_PASSED`。
   - **工序三：段落逻辑审核者（第 9～10 类）**
     - 调度生成扫描报告：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage logic > .polish_workspace/prose_scan.txt`（底层调用 [scan_logic.py](scripts/scan_logic.py)）
     - 专属子手册：[references/taxonomy_stage3_logic.md](references/taxonomy_stage3_logic.md)
     - 循环新建段落逻辑审核分身（自动跳过已冻结位置），直至未冻结文本全部达标输出 `STAGE_2B_PASSED`。
   - **工序四：句法词法审核者（第 11～15 类）**
     - 调度生成扫描报告：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage syntax > .polish_workspace/prose_scan.txt`（底层调用 [scan_syntax.py](scripts/scan_syntax.py)）
     - 专属子手册：[references/taxonomy_stage4_syntax.md](references/taxonomy_stage4_syntax.md)
     - 循环新建句法词法审核分身（自动跳过已冻结位置），直至未冻结文本全部达标输出 `STAGE_2C_PASSED`。
   任一轮若未输出通过标记，顶层调度者即按模板五唤醒常驻撰改者修改文稿并更新 `dispute_log.md`。若产生新增的 `HOLD_FOR_HUMAN` 争议，常驻撰改者向顶层调度者汇报对应位置编号，顶层调度者将其加入冻结清单。后续审核轮次自动跳过已冻结位置，直至未冻结文本全部达标通过。四道工序全部完成后，若存在冻结位置，顶层调度者汇总清单并在对话中提请用户最终人工裁决。

---

## 二、 文件索引

- [references/architecture.md](references/architecture.md)：三层线程职责、四道专职工序及工作区文件通信协议。
- [references/writer_guide.md](references/writer_guide.md)：常驻撰改者核心规范（4 项硬性技术写作约束）。
- [references/error_taxonomy.md](references/error_taxonomy.md)：15 类语言错误总谱导航索引与分工映射。
  - [references/taxonomy_stage1_structure.md](references/taxonomy_stage1_structure.md)：工序一专属（第 1～3 类：非核心过程、脱离代码原理、双中心标题）。
  - [references/taxonomy_stage2_redundancy.md](references/taxonomy_stage2_redundancy.md)：工序二专属（第 4～8 类：防御性局限、自我证实、专业常识、重复图表、冗余图表引导）。
  - [references/taxonomy_stage3_logic.md](references/taxonomy_stage3_logic.md)：工序三专属（第 9～10 类：空洞归因、句间逻辑断层）。
  - [references/taxonomy_stage4_syntax.md](references/taxonomy_stage4_syntax.md)：工序四专属（第 11～15 类：AI 过拟合词、主语异常、超长单句、自然语言算术、复合分支长段未拆分）。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个经典自然段拆解案例库。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：撰改者开局指令与四类专职审核分身的派发指令模板。
- [references/rules_word_typesetting.md](references/rules_word_typesetting.md)：【可选插件】Word 实验报告紧凑排版工程规范（8523 dxa 居中基准、大章节强制分页、68 字符单行容量限制、VS Code Beautifier 风格行尾注释第 44 列垂直对齐、空行三态、跨页流式代码框、双轨字体与 OMML 原生公式）。
- [references/typesetting_case_os_lab4.md](references/typesetting_case_os_lab4.md)：排版基准案例一（操作系统 Lab 4 关键版面解析：表格收窄居中、大章节另起新页、单行代码完整保留与行尾注释垂直列对齐）。
- [references/typesetting_case_csapp_lab4_5.md](references/typesetting_case_csapp_lab4_5.md)：排版基准案例二（CSAPP Lab 4-5 关键版面解析：长代码跨页流式断开无留白、多列数据表空行与原生 OMML 矢量公式）。
- `scripts/`（包含语言扫描模块与排版工程套件）：
  - [scripts/word_layout_engine.py](scripts/word_layout_engine.py)：Word 紧凑排版工程引擎（支持 8523 dxa 收窄、Beautifier 注释对齐、跨页流式代码框与 Word COM 无损导出）。
  - [scripts/check_layout.py](scripts/check_layout.py)：Word 报告机械静态排版合规检查器。
  - [scripts/check_prose.py](scripts/check_prose.py)：命令行总控调度入口。
  - [scripts/doc_parser.py](scripts/doc_parser.py)：`.docx` 表格递归解析、`.md` 跨行自然段合并及纯文本镜像导出模块。
  - [scripts/scan_structure.py](scripts/scan_structure.py)：工序一宏观结构扫描器。
  - [scripts/scan_redundancy.py](scripts/scan_redundancy.py)：工序二信息冗余扫描器。
  - [scripts/scan_logic.py](scripts/scan_logic.py)：工序三段落逻辑扫描器。
  - [scripts/scan_syntax.py](scripts/scan_syntax.py)：工序四句法词法扫描器。
