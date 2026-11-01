---
name: chinese-report-polishing
description: 中文理工科实验报告的语言审查技能。由顶层调度者统筹，通过常驻撰改线程配合每轮新建的审核线程，经工作区文件交换，分两阶段消除人工智能写作痕迹、防御性论述、无意义冗余及句间逻辑断层。
---

# 中文实验报告语言审改规范

本技能针对中文理工科实验报告的语言表述，展开多轮审改，不处理排版格式。全文遵循严谨、冷静、客观的原则，不使用任何表情符号、文学用典或口语化修辞。

---

## 一、 顶层调度执行流程

当前主线程作为**顶层调度者（Orchestrator）**运行，不直接读取实验指导书、不查阅实验代码、不改写报告正文。架构设计细节与通信协议见 [references/architecture.md](references/architecture.md)。

1. **初始化工作区**：
   创建 `.polish_workspace/` 目录，准备 `task_spec.md`（任务要求）与 `draft_current.md`（由常驻撰改者子线程生成初稿，或直接载入已有初稿），并保存常驻撰改者子线程的会话标识（`conversationId`）。
2. **第一阶段循环（宏观结构审定）**：
   - 按 [references/reviewer_prompt.md](references/reviewer_prompt.md) 模板一新建审核者子线程，输出 `.polish_workspace/round_{k}_review.md`。
   - 若输出为 `STAGE_1_PASSED`，进入第二阶段；否则按模板三唤醒常驻撰改者子线程更新 `draft_current.md` 与 `dispute_ledger.md`，进入下一轮。
3. **第二阶段循环（微观语言精修）**：
   - 运行静态扫描脚本：
     ```bash
     python scripts/check_prose.py .polish_workspace/draft_current.md > .polish_workspace/prose_scan.txt
     ```
   - 按 [references/reviewer_prompt.md](references/reviewer_prompt.md) 模板二新建审核者子线程，输出 `.polish_workspace/round_{k}_review.md`。
   - 若输出为 `STAGE_2_PASSED`（或仅剩针对 `HOLD_FOR_HUMAN` 冻结文本的异议），终止流程并交付最终文稿；否则按模板三唤醒常驻撰改者子线程处理批注，进入下一轮。

---

## 二、 参考文件索引

- [references/architecture.md](references/architecture.md)：三层线程职责划分、两阶段状态流转及工作区文件通信协议。
- [references/error_taxonomy.md](references/error_taxonomy.md)：14 类语言错误的定义、原因说明、伪正则模式及真实修改典例。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个经典自然段拆解案例库。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：顶层调度者派发或唤醒子线程的指令模板。
- [scripts/check_prose.py](scripts/check_prose.py)：超长单句、同段高频词、并列标题及高危词句的静态扫描脚本。
