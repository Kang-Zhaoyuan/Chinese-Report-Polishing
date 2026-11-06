#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序二专职扫描器：信息冗余扫描 (scan_redundancy.py)
配合角色：【信息冗余审核者】（负责第4～6类错误，专职“做减法”）
第7～8类模式保留供 scan_visuals.py 调用。

输出线索：
1. 第 4 类：防御性局限声明（未测数据免责、内部机制未知免责、条件受限免责、泛泛优化空间免责、消极推脱/弱化结论/过度防卫词）；
2. 第 5 类：无信息增益的自我证实表述（空洞真实性修饰、重复任务要求前提、段末同义反复确认）；
3. 第 6 类：面向专业阅读者的基础常识解释（基础语法/下标/单位换算常识、跨表重复说明）；
4. 第 7 类：重复图表已呈现的数据或符号说明（正文密集复述图表具体数值嫌疑、可移入表头的符号说明）；
5. 第 8 类：冗余图表引导与主观自评。
"""

import re
import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item
from prose_metrics import split_sentences

# 第 4 类扩展：防御性推脱、弱化结论与过度防卫词库（按长度降序排布以便优先匹配最长词条）
DEFENSIVE_HEDGING_KEYWORDS = [
    # 5 字
    '更准确地说', '不足以证明', '不足以说明',
    # 4 字
    '不意味着', '不等同于', '不能仅凭', '不能仅看', '不能仅靠', '不能只凭', '不能只看',
    '不能当作', '不能承诺', '不能据此', '不能推出', '不能断定', '不能断言', '不能确定',
    '不能确认', '不能简单', '不能视为', '不能认定', '不能证明', '不能说明', '只能证明',
    '只能说明', '无法证明', '无法说明',
    # 3 字
    '不一定', '不代表', '不保证', '不完全', '不必然', '不是说', '不构成', '不等于',
    '不能做', '不能把', '不证明', '尚不能', '并不是', '并不能',
    # 2 字高危推脱词
    '并非', '而非',
    # 例后限定、额外插入的纠正或适用范围说明。
    '仅用于说明', '不作为', '需要澄清的是', '严格来说',
]

REDUNDANCY_PATTERNS = [
    # 第 4 类：防御性局限声明（通用句式）
    (
        '第 4 类：防御性局限声明（未采集数据/无法拆分贡献）',
        r'(?:现有|本次|当前|本|上述)(?:测试|实验|评测|数据|日志|记录|分析).*?'
        r'(?:没有|未|尚未|并未|未能|无法|难以).*?'
        r'(?:记录|测量|采集|包含|覆盖|确定|拆分|区分|得知|量化|排除)'
    ),
    (
        '第 4 类：防御性局限声明（底层/内部策略未知）',
        r'(?:具体|内部|底层|实际).*?(?:分块|策略|调度|实现|贡献|原因|机制|细节|开销)'
        r'(?:无法|难以|不能|尚无法)从.*?(?:程序|日志|测试|结果|数据|实验).*?(?:确定|得知|获知|观察|看出)'
    ),
    (
        '第 4 类：防御性局限声明（模糊条件受限、寄生/噪声/量化误差免责或待进一步验证）',
        r'(?:效果|性能|结论|收益|表现|优劣|特性|滤波效果|选频特性)(?:需要|有待|仍需|还需)(?:结合|根据|在).*?'
        r'(?:具体|实际|更多|更大|不同).*?(?:规模|场景|情况|负载|数据集|硬件|频段|信噪比|信道|阶数|窗函数|进一步实验).*?(?:判断|验证|确定|评估|分析)|'
        r'由于(?:时间|条件|篇幅|硬件|环境|仪器精度|采样点数|FFT\s*点数|测试范围)(?:有限|限制|所限)|'
        r'(?:寄生电容|寄生电感|寄生参数|分布电容|分布参数|引线电感|接触电阻|导线损耗|仪器内阻|元件公差|'
        r'晶体管结电容|谐振回路损耗|本振泄露|组合频率干扰|温度漂移|'
        r'有限字长效应|量化误差|截断误差|舍入误差|频谱泄露|栅栏效应|吉布斯现象|环境噪声|背景流量)'
        r'[^，。；]{0,18}(?:无法|难以|未|未能)(?:单独测量|精确量化|完全消除|具体拆分|从实验中确定)|'
        r'(?:受限于|鉴于).*?(?:未能|未对|暂未).*?(?:展开|进行|做进一步)(?:测试|分析|探讨|验证|测量)|'
        r'(?:仍存在|还有)(?:进一步|一定的)?(?:优化|改进|提升)(?:空间|余地)'
    ),
    (
        '第 4 类：防御性局限声明（消极推脱/弱化结论/过度防卫词）',
        r'(?:' + '|'.join(re.escape(w) for w in sorted(DEFENSIVE_HEDGING_KEYWORDS, key=lambda x: -len(x))) + r')|'
        r'(?:不是|并不是|并非|并未|没有)[^。；]{1,25}(?:[，,]\s*)?而是|'
        r'并不(?:等同于|保证|证明|必然|是|代表|能|意味着|一定|等于|构成|完全|充分)|'
        r'不能(?:据此|由此|完全|直接|轻易|断然|简单)?(?:成立|证明|说明|确定|确认|断言|断定|认定|推出|保证|承诺|视为|当作|代表|反映|涵盖|体现|排除|兼顾|解释|得出|认为|做|把|看|凭|靠)'
    ),
    # 第 5 类：无信息增益的自我证实表述（通用句式）
    (
        '第 5 类：无信息增益的自我证实表述（空洞真实性修饰）',
        r'(?:实际|真实|正式)(?:测试|运行|实验|测量)(?:日志|数据|结果|记录|输出)'
    ),
    (
        '第 5 类：无信息增益的自我证实表述（重复指导书/实验要求前提）',
        r'(?:根据|按照|遵循|依据|为了满足)(?:本)?(?:实验|指导书|题目|任务|步骤)\s*[0-9一二三四五六七八九十]*\s*的?'
        r'(?:实现|实验|具体|相关|任务|设计)?(?:要求|规定|目标)'
    ),
    (
        '第 5 类：无信息增益的自我证实表述（显然的数据来源或段末自我表扬）',
        r'数据(?:分别|均)?来自(?:于)?(?:不同|两次|多次|独立|各自)的?(?:测试|实验|运行|记录)|'
        r'验证了(?:本|上述|该|优化)(?:方法|方案|实现|算法|代码|策略)的(?:有效性|正确性|可行性|优越性)|'
        r'各轮(?:优化版|优化后)?(?:速度|性能|耗时|结果)均(?:高于|快于|优于|低于)(?:对应)?(?:原版|原始|优化前|未优化|基线)'
    ),
    # 第 6 类：面向专业阅读者的基础常识解释（仅匹配跨表重复交代、基础量纲/下标约定及教科书定义式句型；
    # 具体领域概念是否属于“无需解释的专业常识”，由审核者模型结合课程背景与上下文语义判定）
    (
        '第 6 类：跨表重复说明或基础下标/量纲常识',
        r'由行号乘以.*?再加列号|'
        r'(?:下标|索引|编号|行号|列号|序号)(?:均|都)?从\s*0\s*开始|'
        r'(?:含义|意义|单位|计时方法|测试方法|测量方法)(?:和|与|及)?(?:单位|含义)?(?:均)?与(?:表|图|实验)\s*[\d\-一二三四五六七八九十]+\s*(?:保持)?(?:相同|一致)|'
        r'\b1\s*(?:s|秒|ms|毫秒|Byte|字节|kB|MB|GB|kHz|MHz|GHz)\s*(?:等于|为|折合)\s*\d+'
    ),
    (
        '第 6 类线索：教科书定义式句型（请结合课程专业背景语义判断是否为无需解释的基础常识）',
        r'所谓[^，。；]{1,15}[，,]?\s*(?:是指|即指|就是)|'
        r'[^，。；]{2,15}(?:定理|定律|定义)(?:指出|表明|认为|是指)'
    ),
    # 第 7 类：可移入表头的符号定义说明
    (
        '第 7 类：符号定义或表名重复嫌疑（可移入表头括号或删去）',
        r'其中\s*[，,]?\s*[A-Za-z0-9_]+\s*(?:和|与|、)\s*[A-Za-z0-9_]+\s*分别(?:表示|代表|为)|'
        r'(?:表|图)\s*[\d\-]+\s*(?:列出了|给出了|展示了|显示了|汇总了)[^，。；]{2,20}对应的(?:尺寸|数据|结果|耗时|性能|速度)'
    ),
    # 第 8 类：冗余的图表引导与自评
    (
        '第 8 类：冗余的图表引导与主观自评',
        r'为了(?:更|更加)?(?:直观|清晰|清楚|一目了然|形象|便于)地?(?:比较|展示|呈现|观察|看出|体现|反映|对比)|'
        r'图\s*[\d\-]+\s*(?:根据|依据|基于|由)\s*表\s*[\d\-]+\s*的?(?:数据|结果)?(?:绘制|展示|给出|呈现)|'
        r'(?:从|由|观察|对比|结合)\s*(?:表\s*[\d\-]+|图\s*[\d\-]+)(?:和|与|及)?(?:表\s*[\d\-]+|图\s*[\d\-]+)?\s*(?:中|的数据|的结果)?(?:可以|能够|不难)?(?:看出|看到|发现|得知|观察到)|'
        r'如(?:图|表)\s*[\d\-]+\s*所示'
    ),
]


def scan_redundancy(items, include_visuals=False):
    pattern_hits = []
    numeric_recap_suspects = []
    paragraph_tails = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind) or kind == 'tbl':
            continue

        for cat_name, pat in REDUNDANCY_PATTERNS:
            if not include_visuals and cat_name.startswith(('第 7 类', '第 8 类')):
                continue
            for m in re.finditer(pat, text):
                pattern_hits.append((loc_id, cat_name, m.group(0), text))

        sentences = split_sentences(text)
        if sentences:
            tail = sentences[-1]
            defensive = list(dict.fromkeys(
                m.group() for cat, pat in REDUNDANCY_PATTERNS
                if cat.startswith('第 4 类') for m in re.finditer(pat, tail)))
            paragraph_tails.append((loc_id, tail, defensive, text))

        # 检测正文中单段列举 >= 3 个带小数点的具体测量数值（提示审核者核对是否与表格重复）
        floats = re.findall(r'\b\d+\.\d+\b', text)
        if include_visuals and len(floats) >= 3:
            numeric_recap_suspects.append((loc_id, floats, text))

    return {
        'pattern_hits': pattern_hits,
        'numeric_recap_suspects': numeric_recap_suspects,
        'paragraph_tails': paragraph_tails,
    }


def print_redundancy_report(res, src_name):
    print(f"=== [工序二：信息冗余审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【信息冗余审核者】参考，聚焦第4～6类；第7～8类交由图文专职审核者处理。\n")

    print(f"[1. 防御性声明、自我证实、常识解释与图表引导冗余] ({len(res['pattern_hits'])} 处)")
    for loc_id, cat_name, hit, text in res['pattern_hits']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} [{cat_name}] 命中: “{hit}”\n    上下文: {preview}")
    if not res['pattern_hits']:
        print("  - 无")

    print('\n[2. 逐段审核：段落目的 → 各句贡献 → 最后一句]')
    print('每句均须服务本段。重点检查段末的重复总结、防御性限定和额外反驳；同时处理段内命中。')
    for loc, tail, defensive, context in res['paragraph_tails']:
        print(f'  - {loc} 最后一句: {tail}')
        if defensive:
            print(f'    段末防御性措辞: {defensive}')
        print(f'    整段: {context}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python scan_redundancy.py <文稿路径>")
        sys.exit(1)
    items = load_document_items(sys.argv[1], skip_first_page=True)
    print_redundancy_report(scan_redundancy(items), os.path.basename(sys.argv[1]))
