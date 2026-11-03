---
name: chinese-report-polishing
description: 中文理工科实验报告的语言审查技能。由顶层调度者统筹，通过常驻撰改线程配合四类专职审核线程及对应的专项扫描模块，经工作区文件交换，消除人工智能写作痕迹、防御性论述、无意义冗余及句间逻辑断层。
---

# 中文实验报告语言审改规范

本技能专注于中文理工科实验报告的语言表述与逻辑审改，默认不处理排版格式。全文遵循严谨、冷静、客观的原则，不使用任何表情符号、文学用典或口语化修辞。Word 排版作为独立可选插件存在，默认不启用。

---

## 一、 顶层调度执行流程

当前主线程作为**顶层调度者（Orchestrator）**运行，不直接读取实验指导书、不查阅实验代码、不改写报告正文。架构设计细节见 [references/architecture.md](references/architecture.md)。

> **排版询问机制（可选插件）**：启动本技能时，若用户未明确指定排版要求，顶层调度者应显式用自然语言询问用户是否需要启用 Word 排版模块；若用户未明确确认，**默认不启用**排版，仅专注于文稿语言质量审查。排版具体准则见 [references/rules_word_typesetting.md](references/rules_word_typesetting.md)。

1. **初始化工作区**：
   创建 `.polish_workspace/` 目录，准备 `task_spec.md`（任务要求）与待审报告文稿（支持 `.docx` 或 `.md`，可由常驻撰改者生成初稿，或直接载入已有初稿），并保存常驻撰改者的会话标识（`conversationId`）。
2. **按序推进四道专职审核工序**：
   每道工序绑定独立的扫描模块（模板见 [references/reviewer_prompt.md](references/reviewer_prompt.md)）。每轮启动审核分身前，顶层调度者先调用对应 `--stage` 参数，导出纯文本镜像 `draft_view.md`，并生成当前分身专属的 `prose_scan.txt`：
   - **工序一：宏观结构审核者（第 1、2、3 类）**
     - 前置扫描：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage structure > .polish_workspace/prose_scan.txt`（底层调用 [scan_structure.py](scripts/scan_structure.py)）
     - 循环新建宏观结构审核分身，直至输出 `STAGE_1_PASSED`。
   - **工序二：信息冗余审核者（第 4、5、6、8、9 类）**
     - 前置扫描：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage redundancy > .polish_workspace/prose_scan.txt`（底层调用 [scan_redundancy.py](scripts/scan_redundancy.py)）
     - 循环新建信息冗余审核分身，直至输出 `STAGE_2A_PASSED`。
   - **工序三：段落逻辑审核者（第 10、12 类）**
     - 前置扫描：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage logic > .polish_workspace/prose_scan.txt`（底层调用 [scan_logic.py](scripts/scan_logic.py)）
     - 循环新建段落逻辑审核分身，直至输出 `STAGE_2B_PASSED`。
   - **工序四：句法词法审核者（第 7、11、13、14 类）**
     - 前置扫描：`python scripts/check_prose.py <文稿> --extract .polish_workspace/draft_view.md --stage syntax > .polish_workspace/prose_scan.txt`（底层调用 [scan_syntax.py](scripts/scan_syntax.py)）
     - 循环新建句法词法审核分身，直至输出 `STAGE_2C_PASSED`。
   任一轮若未输出通过标记，顶层调度者即按模板五唤醒常驻撰改者，修改原文稿并更新 `dispute_ledger.md`，随后重新执行当前工序。

---

## 二、 文件索引

- [references/architecture.md](references/architecture.md)：三层线程职责、四道专职工序及工作区文件通信协议。
- [references/error_taxonomy.md](references/error_taxonomy.md)：14 类语言错误的定义、原因说明、伪正则模式及真实修改典例。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个经典自然段拆解案例库。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：各子线程的派发及唤醒指令模板。
- [references/rules_word_typesetting.md](references/rules_word_typesetting.md)：【可选插件】Word 实验报告紧凑排版工程规范（空行三态、跨页流式代码框、双轨字体与 OMML 原生公式）。
- `scripts/`（模块化扫描器，与四个审核分身一一对应）：
  - [scripts/check_prose.py](scripts/check_prose.py)：命令行总控调度入口。
  - [scripts/doc_parser.py](scripts/doc_parser.py)：`.docx` 表格递归解析、`.md` 跨行自然段合并及纯文本镜像导出模块。
  - [scripts/scan_structure.py](scripts/scan_structure.py)：工序一宏观结构扫描器。
  - [scripts/scan_redundancy.py](scripts/scan_redundancy.py)：工序二信息冗余扫描器。
  - [scripts/scan_logic.py](scripts/scan_logic.py)：工序三段落逻辑扫描器。
  - [scripts/scan_syntax.py](scripts/scan_syntax.py)：工序四句法词法扫描器。
