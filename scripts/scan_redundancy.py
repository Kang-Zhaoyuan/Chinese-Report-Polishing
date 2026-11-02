#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序二专职扫描器：信息冗余扫描 (scan_redundancy.py)
配合角色：【信息冗余审核者】（负责第 4、5、6、8、9 类错误，专职“做减法”）

输出线索：
1. 第 4 类：防御性局限声明；
2. 第 5 类：无信息增益的自我证实表述；
3. 第 6 类：面向专业阅读者的基础常识解释；
4. 第 8 类：正文密集复述图表具体数值嫌疑；
5. 第 9 类：冗余的图表引导与自评。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

REDUNDANCY_PATTERNS = [
    ('第 4 类：防御性局限声明', r'(现有|本次|当前)(测试|实验|数据|日志|记录).*?(没有|未|无法|难以).*?(记录|测量|确定|拆分|区分|得知)'),
    ('第 4 类：防御性局限声明', r'(具体|内部).*?(分块|策略|贡献|实现)无法从.*?(程序|日志|测试|结果).*?确定'),
    ('第 4 类：防御性局限声明', r'效果需要结合具体(规模|场景|情况)判断'),
    ('第 5 类：无信息增益的自我证实表述', r'实际测试|根据实验\s*\d+\s*的实现要求|数据分别来自两次测试|生成文本保持一致|结果由输入矩阵的乘积确定'),
    ('第 6 类：面向专业阅读者的基础常识解释', r'由行号乘以.*?再加列号|编号均从\s*0\s*开始|含义和单位与表.*?相同'),
    ('第 8 类：维度说明可移入表头嫌疑', r'其中\s*[A-Za-z]\s*和\s*[A-Za-z]\s*分别表示'),
    ('第 9 类：冗余的图表引导与自评', r'为了直观(比较|展示)|根据表\s*[\d\-]+\s*的数据展示|从表\s*[\d\-]+\s*和图\s*[\d\-]+\s*可以看出|如(?:图|表)\s*[\d\-]+\s*所示'),
]


def scan_redundancy(items):
    pattern_hits = []
    numeric_recap_suspects = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind) or kind == 'tbl':
            continue

        for cat_name, pat in REDUNDANCY_PATTERNS:
            m = re.search(pat, text)
            if m:
                pattern_hits.append((loc_id, cat_name, m.group(0), text))

        # 检测正文中单句列举 >= 3 个带小数点的具体测量数值（提示审核者核对是否与表格重复）
        floats = re.findall(r'\b\d+\.\d+\b', text)
        if len(floats) >= 3:
            numeric_recap_suspects.append((loc_id, floats, text))

    return {
        'pattern_hits': pattern_hits,
        'numeric_recap_suspects': numeric_recap_suspects,
    }


def print_redundancy_report(res, src_name):
    print(f"=== [工序二：信息冗余审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【信息冗余审核者】参考，聚焦第 4、5、6、8、9 类冗余删减问题。\n")

    print(f"[1. 防御性声明、自我证实、常识解释与图表引导冗余] ({len(res['pattern_hits'])} 处)")
    for loc_id, cat_name, hit, text in res['pattern_hits']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} [{cat_name}] 命中: “{hit}”\n    上下文: {preview}")
    if not res['pattern_hits']:
        print("  - 无")

    print(f"\n[2. 第 8 类线索：正文密集列举浮点测量值（请核对是否与图表重复）] ({len(res['numeric_recap_suspects'])} 处)")
    for loc_id, floats, text in res['numeric_recap_suspects']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} (含 {len(floats)} 个浮点数 {floats[:5]}):\n    上下文: {preview}")
    if not res['numeric_recap_suspects']:
        print("  - 无")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python scan_redundancy.py <文稿路径>")
        sys.exit(1)
    items = load_document_items(sys.argv[1])
    print_redundancy_report(scan_redundancy(items), os.path.basename(sys.argv[1]))
