# Chinese-Report-Polishing

苦AI味写作久矣，遂写一个 Skill，只针对“中国理工科大学生实验报告撰写”这个场景，尝试做一些优化。至于实验怎么完成，建议向神灵祈祷；**实验指导书以及实验报告撰写的要求是本Skill很重要的资源**，如果想图省事，就应该把它们全部都爬下来，打包成Markdown传进项目里。这个Skill不负责排版，只负责写作。

> 你说得对，但我将要开始探针、快照、证据、门禁、夹具，还有哈希、冒烟、基线了。我要先建立唯一基线，再进行可追溯备份，先进行最小改动，我先进行一轮烟测，检查114个门禁是否通过，上线前进行一轮全量dry-run，上线后校验哈希值，最后进行一轮实测的验收矩阵！

我非常希望获得更多真实的修改的例子，以及人类的批注。目前正在做大量数据收集的工作，尝试训练一个会说人话的小模型，返璞归真。期待PR和Issue，任何实例都极其宝贵。

---

## 一、 运行机制

系统采用三层角色隔离架构，通过 `.polish_workspace/` 下的本地文件交换数据，原生支持 `.docx` 文稿的提取与审改：
- **顶层调度者（Orchestrator）**：主线程，仅负责运行静态扫描与文本提取脚本、按序派发子线程及控制工序流转，不在自身上下文中载入指导书或报告正文。
- **常驻撰改者（Writer-Refiner）**：单一持久子线程，全程复用同一会话完成写稿与多轮改稿，掌握实验代码与历轮修改依据，在审核意见违背专业事实时行使反驳权。
- **四类专职审核者（Specialist Reviewers）**：专人干专事，每轮新建独立子线程，按**宏观结构审核（1～3 类）$\rightarrow$ 信息冗余审核（4、5、6、8、9 类）$\rightarrow$ 段落逻辑审核（10、12 类）$\rightarrow$ 句法词法审核（7、11、13、14 类）**四道工序依次审查，单轮结束后即销毁。同一位置往返分歧达 2 次时，标记为 `HOLD_FOR_HUMAN` 交由人工裁决。

---

## 二、 文件导航

- [SKILL.md](SKILL.md)：技能入口与顶层调度执行步骤。
- [references/architecture.md](references/architecture.md)：三层线程职责、四道专职审核工序及文件通信协议。
- [references/error_taxonomy.md](references/error_taxonomy.md)：14 类语言错误的症状定义、说服逻辑、伪正则模式及原版对照典例。
- [references/classic_critiques.md](references/classic_critiques.md)：8 个多轮自然段拆解与演进案例。
- [references/reviewer_prompt.md](references/reviewer_prompt.md)：四类专职审核线程与常驻撰改线程的派发指令模板。
- [scripts/check_prose.py](scripts/check_prose.py)：支持 `.docx` 表格提取、跨行自然段合并及四类语言线索扫描的静态脚本。
