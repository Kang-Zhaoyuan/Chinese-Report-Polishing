#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序四专职扫描器：句法词法扫描 (scan_syntax.py)
配合角色：【句法词法审核者】（负责第 7、11、13、14 类错误，专职“抠字句”）

输出线索：
1. 第 7 类：人工智能过拟合词汇与欧化翻译腔（覆盖正文及数据表格单元格）；
2. 第 11 类：主语使用异常（伪拟人主语“实验选择”、同段 >= 3 次高频重复词）；
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
    ('第 7 类：欧化翻译腔句式', r'不仅.*?而且|一方面.*?另一方面|基于.*?而言|在.*?的背景下'),
    ('第 11 类：伪拟人主语嫌疑', r'实验选择该|本文选择该'),
    ('第 14 类：自然语言算术或中文数字参数', r'\d+\s*除以\s*\d+\s*余\s*\d+|由.*?(平均速度|时间)除以.*?(平均速度|时间)|将零填入'),
]

TRACKED_REPEAT_WORDS = [
    '程序', '实验', '线程', '矩阵', '模型', '平均', '在', '通过', '使用', '计算'
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
                word_and_syntax_hits.append((loc_id, cat_name, f"命中片段: “{m.group(0)}”", text))

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
