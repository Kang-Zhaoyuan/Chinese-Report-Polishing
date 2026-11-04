# 中文实验报告语言错误分类总谱 (Master Taxonomy Index)

本文档是实验报告审改体系中 **15 类错误** 的全量总目录索引。

为了防止审核分身在大篇幅规范中发生“注意力稀释（Attention Dilution）”及不必要的上下文 Token 浪费，各工序采用**专属手册物理隔离**机制。审核分身在执行任务时，仅加载并阅读对应工序的微型子手册。

> 常驻撰改者（Writer-Refiner）撰写初稿与改稿时无需通读本总谱，直接遵循 [references/writer_guide.md](writer_guide.md) 中的 4 项核心写作约束。

---

## 工序与专属规范索引

| 工序编号 | 负责角色 | 覆盖错误类别 | 专属子手册链接 |
| :--- | :--- | :--- | :--- |
| **工序一** | 宏观结构审核者 | **第 1 ～ 3 类** | [references/taxonomy_stage1_structure.md](taxonomy_stage1_structure.md) |
| **工序二** | 信息冗余审核者 | **第 4 ～ 8 类** | [references/taxonomy_stage2_redundancy.md](taxonomy_stage2_redundancy.md) |
| **工序三** | 段落逻辑审核者 | **第 9 ～ 10 类** | [references/taxonomy_stage3_logic.md](taxonomy_stage3_logic.md) |
| **工序四** | 句法词法审核者 | **第 11 ～ 15 类** | [references/taxonomy_stage4_syntax.md](taxonomy_stage4_syntax.md) |

---

## 15 类错误速查清单

### 第一阶段：宏观结构审定（工序一）
- [1. 冗余的非核心过程描述](taxonomy_stage1_structure.md#1-冗余的非核心过程描述)：剔除未作要求的硬件环境、编译器版本、采样参数或常规校验
- [2. 脱离代码修改行为的原理概述](taxonomy_stage1_structure.md#2-脱离代码修改行为的原理概述)：严禁脱离代码泛泛讲算法，必须落脚在具体行号、函数与补丁动作
- [3. 双中心并列标题](taxonomy_stage1_structure.md#3-双中心并列标题)：各级标题禁止用“与/及/和”并列两个事项，聚焦单一核心事项

### 第二阶段：信息冗余做减法（工序二）
- [4. 防御性局限声明](taxonomy_stage2_redundancy.md#4-防御性局限声明)：清除“现有测试……无法确定”、“水平有限”等免责声明
- [5. 无信息增益的自我证实表述](taxonomy_stage2_redundancy.md#5-无信息增益的自我证实表述)：删除“实际测试日志”、“根据要求”、段末同义反复确认
- [6. 面向专业阅读者的基础常识解释](taxonomy_stage2_redundancy.md#6-面向专业阅读者的基础常识解释)：删除行优先公式、下标从0开始、跨表重复交代测量方法等先修常识
- [7. 重复图表已有信息](taxonomy_stage2_redundancy.md#7-重复图表已有信息)：正文避免密集抄写表格数值，改为定性归纳；参数符号移入表头括号
- [8. 冗余的图表引导与主观自评](taxonomy_stage2_redundancy.md#8-冗余的图表引导)：精简“如下图所示”等流水账引导，删除主观自我表扬

### 第三阶段：段落逻辑与因果推演（工序三）
- [9. 空洞归因与黑盒动词](taxonomy_stage3_logic.md#9-空洞归因)：清除贴标签式归因（如“从而提升了鲁棒性/灵活性”），必须指出具体机制
- [10. 句间逻辑断层与缺少连接词](taxonomy_stage3_logic.md#10-句间逻辑断层)：多句自然段必须具备时序或因果承接词，消除断崖式并列

### 第四阶段：句法词法与篇章颗粒度（工序四）
- [11. 人工智能过拟合词汇](taxonomy_stage4_syntax.md#11-人工智能过拟合词汇)：清除“基线/闭环/赋能/抓手/深远影响/不难发现”等高危套话
- [12. 主语使用异常与伪拟人](taxonomy_stage4_syntax.md#12-主语使用异常)：区分人类改代码动作与机器运行动作，禁止第一人称“我/笔者”，补足客观主语
- [13. 超长单句](taxonomy_stage4_syntax.md#13-超长单句)：标点间超过 20 字符无停顿的长句，通过加逗号、拆分或改公式切分
- [14. 自然语言算术](taxonomy_stage4_syntax.md#14-自然语言算术)：禁止用中文写“1000除以32余8”或重复汉字参数，统一采用专业数学公式
- [15. 复合分支未拆分](taxonomy_stage4_syntax.md#15-复合分支未拆分collapsed-enumeration-paragraph)：折行 >= 6 行且内含多项自闭合复杂逻辑分支的长段落，在总述后拆解为独立自然段形成视觉阶梯
