#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序一专职扫描器：宏观结构扫描 (scan_structure.py)
配合角色：【宏观结构审核者】（负责第 1、2、3 类错误）

输出线索：
1. 全文章节标题大纲树（供审核者对照任务要求核查章节划分与序号连续性）；
2. 双中心并列标题嫌疑（第 3 类：含“与”、“及”、“和”、“以及”的标题）；
3. 冗余的非核心过程描述嫌疑（第 1 类：含硬件型号、编译器版本、随机种子、采样温度或独立“正确性测试”小节）。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

NON_CORE_PATTERNS = [
    ('硬件环境与编译器参数（若任务未要求应整段删除）', r'Intel\s+Core|NVIDIA\s+GeForce|Compute\s+Capability|CUDA\s+Toolkit|GCC\s+\d'),
    ('脚本控制参数与文本一致性校验（若任务未要求应整段删除）', r'随机种子|温度设为|生成文本保持一致|均显示文本一致'),
    ('独立正确性测试小节嫌疑（建议并入测试结果节）', r'^（[一二三四五六七八九十]+）正确性(测试|检查)$'),
]


def scan_structure(items):
    headings = []
    dual_center_headings = []
    non_core_suspects = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind):
            headings.append((loc_id, text))
            conj_match = re.findall(r'(与|及|和|以及)', text)
            if conj_match:
                dual_center_headings.append((loc_id, text, conj_match))

        for label, pat in NON_CORE_PATTERNS:
            m = re.search(pat, text)
            if m:
                non_core_suspects.append((loc_id, label, m.group(0), text))

    return {
        'headings': headings,
        'dual_center_headings': dual_center_headings,
        'non_core_suspects': non_core_suspects,
    }


def print_structure_report(res, src_name):
    print(f"=== [工序一：宏观结构审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【宏观结构审核者】参考，聚焦第 1、2、3 类问题。\n")

    print(f"[1. 全文章节标题大纲] (共 {len(res['headings'])} 个标题)")
    for loc_id, h_text in res['headings']:
        print(f"  - [{loc_id}] {h_text}")
    if not res['headings']:
        print("  - 未检测到标准章节标题")

    print(f"\n[2. 第 3 类：双中心并列标题嫌疑] ({len(res['dual_center_headings'])} 处)")
    for loc_id, h_text, conjs in res['dual_center_headings']:
        print(f"  - 位置 {loc_id}: 「{h_text}」 (含并列连词: {conjs})")
    if not res['dual_center_headings']:
        print("  - 无")

    print(f"\n[3. 第 1 类：冗余的非核心过程描述嫌疑] ({len(res['non_core_suspects'])} 处)")
    for loc_id, label, hit, text in res['non_core_suspects']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} [{label}] 命中: “{hit}”\n    上下文: {preview}")
    if not res['non_core_suspects']:
        print("  - 无")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python scan_structure.py <文稿路径>")
        sys.exit(1)
    items = load_document_items(sys.argv[1])
    print_structure_report(scan_structure(items), os.path.basename(sys.argv[1]))
