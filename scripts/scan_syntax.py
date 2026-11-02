#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序四专职扫描器：句法词法扫描 (scan_syntax.py)
配合角色：【句法词法审核者】（负责第 7、11、13、14 类错误，专职“抠字句”）

输出线索：
1. 第 7 类：人工智能过拟合词汇与欧化翻译腔（覆盖正文及数据表格单元格）；
2. 第 11 类：主语使用异常（伪拟人主语、第一人称泄露、同段 >= 3 次高频重复词）；
3. 第 13 类：标点间超过 20 个阅读单位的超长单句；
4. 第 14 类：自然语言算术与中文数字参数。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

AI_OVERFIT_WORDS = [
    # 软件工程与智能体行话迁移词
    '唯一基线', '基线', '探针', '快照', '证据链', '证据', '门禁', '夹具',
    '校验哈希值', '哈希', '冒烟', '烟测', '可追溯备份', '可追溯', '最小改动',
    '全量', 'dry-run', '实测', '验收矩阵', '兜底', '收口', '口径', '透传', '落盘',
    # 绝对化与情绪化修饰词
    '极限', '显著提升', '至关重要', '深远影响', '极其复杂', '不容忽视', '前所未有',
    # 商业与公文空洞动词/名词
    '赋能', '助力', '打造', '闭环', '抓手', '沉淀', '协同', '重塑', '解构', '升华',
    # 机械过渡与顺从套话
    '你说得对', '诚然', '综上所述', '总而言之', '由此可见', '值得注意的是',
    '不可否认的是', '显而易见', '不难发现',
]

SYNTAX_PATTERNS = [
    (
        '第 7 类：欧化翻译腔与公文套话句式',
        r'不仅.*?而且|一方面.*?另一方面|基于.*?而言|在.*?的背景下|'
        r'从.*?的(?:角度|维度|层面)来看|扮演着.*?的角色|发挥着.*?的作用|'
        r'提供了.*?的(?:支撑|保障)|实现了.*?的(?:跨越|突破|闭环)'
    ),
    (
        '第 11 类：伪拟人主语嫌疑（无生命名词充当人类决策主语，应删去主语）',
        r'(?:^|[，。；：]\s*)(?:本|该|此次)?(?:实验|报告|本文|本节|本研究|本小节|方案)'
        r'(?:进一步|首先|随后|最终|因此|遂)?'
        r'(?:选择|选用|选取|决定|考虑|认为|意识到|注意到|推断|猜测|倾向于|试图|尝试|打算)'
    ),
    (
        '第 11 类：第一人称主语泄露（严禁出现第一人称）',
        r'我们|笔者|本人|(?<![A-Za-z])我(?:在|通过|使用|选择|发现|将|对|认为|编写|实现|测试)'
    ),
    (
        '第 14 类：自然语言算术或中文数字参数（应改写为数学公式或阿拉伯数字）',
        r'\d+\s*除以\s*\d+(?:\s*余\s*\d+)?|'
        r'由[^，。；]{1,15}(?:速度|时间|耗时|大小|边长|长度|维度|结果|电压|电流|功率|幅值|频率|带宽|增益|均值|方差|时延|点数|品质因数)(?:除以|乘以|加上|减去)[^，。；]{1,15}|'
        r'乘以\s*[A-Za-z0-9_]+\s*再加|'
        r'(?:20|10)\s*乘以[^，。；]{0,12}对数|'
        r'1\s*除以\s*2\s*[πpi]*\s*[RCLf√]+|'
        r'两个序列长度之和减(?:一|1)|'
        r'最大包络(?:电压|幅值)(?:减去|与)最小包络(?:电压|幅值)|'
        r'(?:本振频率|载波频率)(?:减去|加上|与)(?:信号频率|本振频率)(?:之差|之和)|'
        r'(?:将|把)(?:零|一|二|三|四|五|六|七|八|九|十)(?:填入|写入|赋给|设为)'
    ),
]

# 跨学科通用高频监控词表（覆盖计算机系统、计算机网络、通信电子电路、数字信号处理、随机信号）
TRACKED_REPEAT_WORDS = [
    # 通用与计算机体系结构
    '程序', '实验', '代码', '函数', '系统', '模块', '过程', '结果', '数据', '测试',
    '线程', '进程', '矩阵', '模型', '内存', '缓存', '指令', '平均', '时间', '性能',
    # 计算机网络
    '报文', '数据包', '分组', '节点', '路由', '协议', '连接', '端口', '链路', '信道', '时延', '丢包',
    # 通信电子电路（高频电子线路）
    '电路', '电压', '电流', '电阻', '电容', '电感', '频率', '幅值', '相位', '波形',
    '增益', '放大器', '振荡器', '谐振', '回路', '选频', '通频带', '品质因数', '静态工作点',
    '载波', '本振', '中频', '包络', '调制', '解调', '调幅', '调频', '检波', '混频', '鉴频', '锁相环', '失真',
    # 数字信号处理（DSP）与随机信号分析
    '信号', '序列', '离散', '采样', '抽样', '卷积', '变换', '频域', '时域', '频谱',
    '滤波器', '通带', '阻带', '过渡带', '阶数', '窗函数', '主瓣', '旁瓣', '量化',
    '噪声', '均值', '方差', '自相关', '功率谱', '谱密度', '分布', '信噪比', '误码率',
    # 高频介词与功能动词
    '在', '通过', '使用', '采用', '进行', '实现', '计算', '完成', '测量', '观察'
]

SPLIT_PUNCT = re.compile(r'(?:[，。；：？！、,;?!（）()|]|\.(?![A-Za-z0-9_]))+')


def measure_clause_length(clause):
    """
    计算分句的阅读长度：
    将连续的英文单词、函数名、带上下标的变量或数字算式计为 1 个阅读单元，中文字符每个计为 1 个单元。
    """
    collapsed = re.sub(r'[A-Za-z0-9_.\-+/*=<>()\[\]\u2070-\u209f\u00b2\u00b3\u00b9×÷±≈≠≤≥]+', 'X', clause)
    collapsed = re.sub(r'\s+', '', collapsed)
    return len(collapsed)


def scan_syntax(items, max_clause_len=20, repeat_threshold=3):
    long_clauses = []
    repeat_issues = []
    word_and_syntax_hits = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind):
            continue

        # 1. 第 13 类：超长单句检查
        clauses = [c.strip() for c in SPLIT_PUNCT.split(text) if c.strip()]
        for c in clauses:
            if len(re.findall(r'[\u4e00-\u9fff]', c)) < 4:
                continue
            c_len = measure_clause_length(c)
            if c_len > max_clause_len:
                long_clauses.append((loc_id, c_len, c))

        # 2. 第 11 类：同段高频重复词检查（长度 >= 30 字的自然段）
        if len(text) >= 30:
            found_repeats = []
            for w in TRACKED_REPEAT_WORDS:
                if w == '在':
                    count = len(re.findall(r'(?:^|[，。；\s])在', text))
                else:
                    count = text.count(w)
                if count >= repeat_threshold:
                    found_repeats.append(f"“{w}”({count}次)")
            if found_repeats:
                repeat_issues.append((loc_id, ', '.join(found_repeats), text))

        # 3. 第 7 类：AI 过拟合词汇检查（含正文与表格单元格）
        hit_words = [w for w in AI_OVERFIT_WORDS if w in text]
        if hit_words:
            word_and_syntax_hits.append((loc_id, '第 7 类：AI 过拟合词汇', f"命中词汇: {hit_words}", text))

        # 4. 第 7、11、14 类正则模式检查
        for cat_name, pat in SYNTAX_PATTERNS:
            m = re.search(pat, text)
            if m:
                word_and_syntax_hits.append((loc_id, cat_name, f"命中片段: “{m.group(0).strip()}”", text))

    return {
        'max_clause_len': max_clause_len,
        'repeat_threshold': repeat_threshold,
        'long_clauses': long_clauses,
        'repeat_issues': repeat_issues,
        'word_and_syntax_hits': word_and_syntax_hits,
    }


def print_syntax_report(res, src_name):
    print(f"=== [工序四：句法词法审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【句法词法审核者】参考，聚焦第 7、11、13、14 类问题。\n")

    print(f"[1. 第 13 类：超过 {res['max_clause_len']} 字符的超长单句] ({len(res['long_clauses'])} 处)")
    for loc_id, c_len, c_text in res['long_clauses']:
        print(f"  - 位置 {loc_id} (长度 {c_len}): 「{c_text}」")
    if not res['long_clauses']:
        print("  - 无")

    print(f"\n[2. 第 11 类：同段高频重复词 (单段 >= {res['repeat_threshold']} 次)] ({len(res['repeat_issues'])} 处)")
    for loc_id, rep_info, p_text in res['repeat_issues']:
        preview = p_text if len(p_text) <= 80 else p_text[:77] + '...'
        print(f"  - 位置 {loc_id} [{rep_info}]: {preview}")
    if not res['repeat_issues']:
        print("  - 无")

    print(f"\n[3. 第 7、11、14 类：高危词汇、伪拟人主语与自然语言算术] ({len(res['word_and_syntax_hits'])} 处)")
    for loc_id, cat, detail, p_text in res['word_and_syntax_hits']:
        preview = p_text if len(p_text) <= 85 else p_text[:82] + '...'
        print(f"  - 位置 {loc_id} [{cat}] {detail}\n    上下文: {preview}")
    if not res['word_and_syntax_hits']:
        print("  - 无")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python scan_syntax.py <文稿路径>")
        sys.exit(1)
    items = load_document_items(sys.argv[1])
    print_syntax_report(scan_syntax(items), os.path.basename(sys.argv[1]))
