---
name: chinese-report-polishing
description: 中文理工科实验报告的语言审查技能。由顶层调度者统筹，通过常驻撰改线程配合四类专职审核线程，经工作区文件交换，消除人工智能写作痕迹、防御性论述、无意义冗余及句间逻辑断层。
---

# 中文实验报告语言审改规范

本技能针对中文理工科实验报告的语言表述，展开多轮审改，不处理排版格式。全文遵循严谨、冷静、客观的原则，不使用任何表情符号、文学用典或口语化修辞。

---

## 一、 顶层调度执行流程

当前主线程作为**顶层调度者（Orchestrator）**运行，不直接读取实验指导书、不查阅实验代码、不改写报告正文。架构设计细节见 [references/architecture.md](references/architecture.md)。

1. **初始化工作区**：
   创建 `.polish_workspace/` 目录，准备 `task_spec.md`（任务要求）与待审报告文稿（支持 `.docx` 或 `.md`，可由常驻撰改者生成初稿，或直接载入已有初稿），并保存常驻撰改者的会话标识（`conversationId`）。
2. **每轮前置提取与扫描**：
   由于最终文稿常为 `.docx` 格式，每次启动专职审核子线程前，顶层调度者先运行 [scripts/check_prose.py](scripts/check_prose.py)，同步生成带定位编号的纯文本视图 `draft_view.md`（含正文段落与数据表格单元格）及静态扫描报告 `prose_scan.txt`：
   ```bash
   python scripts/check_prose.py <当前文稿路径> --extract .polish_workspace/draft_view.md > .polish_workspace/prose_scan.txt
   ```
3. **按序执行四道专职审核工序**：
   按 [references/reviewer_prompt.md](references/reviewer_prompt.md) 中的模板一至模板四，依次推进四道专职审核工序（每轮均新建独立审核子线程，输出至 `.polish_workspace/round_{k}_review.md`）：
   - **工序一：宏观结构审核者（第 1、2、3 类）** $\rightarrow$ 直至输出 `STAGE_1_PASSED`；
   - **工序二：信息冗余审核者（第 4、5、6、8、9 类）** $\rightarrow$ 直至输出 `STAGE_2A_PASSED`；
   - **工序三：段落逻辑审核者（第 10、12 类）** $\rightarrow$ 直至输出 `STAGE_2B_PASSED`；
   - **工序四：句法词法审核者（第 7、11、13、14 类）** $\rightarrow$ 直至输出 `STAGE_2C_PASSED`。
   任一轮若未输出通过标记，顶层调度者即按模板五唤醒常驻撰改者，修改原文稿并更新 `dispute_ledger.md`，随后重新执行当前工序审查。

---

## 二、 参考文件索引

- [references/architecture.md](references/architecture.md)：三层线程职责划分、四道专职审核工序及工作区文件通信协议。
- [references/error_taxonomy.md](references/error_taxonomy.md)：14 类语言错误的定义、原因说明、伪正则模式及真实修改典例。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个经典自然段拆解案例库。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：各子线程的派发及唤醒指令模板。
- [scripts/check_prose.py](scripts/check_prose.py)：支持 `.docx` 表格提取、自然段合并及语言线索扫描的静态脚本。
