#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序三专职扫描器：段落逻辑与归因扫描 (scan_logic.py)
配合角色：【段落逻辑审核者】（负责第 10、12 类错误，专职“理逻辑、补机理”）

输出线索：
1. 第 10 类：空洞归因句式嫌疑（仅指出某因素是可能原因或改变了某方式，未展开机理）；
2. 第 12 类：多句自然段缺乏显式逻辑连接词或时序状语嫌疑（辅助定位句间逻辑断层）。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

HOLLOW_ATTRIBUTION_PATTERNS = [
    ('第 10 类：空洞归因嫌疑', r'是影响(运行时间|计算性能|推理速度)的可能因素'),
    ('第 10 类：空洞归因嫌疑', r'改变了线程组织和数据访问方式'),
    ('第 10 类：段末笼统归因提示', r'这些(因素|处理)可能影响结果'),
]

# 显式逻辑连接词与时序过渡词表
TRANSITION_MARKERS = [
    '因此', '因而', '从而', '进而', '这表明', '说明', '表明',
    '这一提升与', '这一差异可能与', '可能的因素是', '原因在于', '究其原因',
    '具体而言', '例如', '由于', '因为', '相比之下', '然而', '同时', '此外',
    '随后', '此时', '在此基础上', '结束后', '完成后', '调用后', '在每轮', '在当前轮'
]


def scan_logic(items):
    hollow_hits = []
    disconnected_paras = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind) or kind == 'tbl':
            continue

        for cat_name, pat in HOLLOW_ATTRIBUTION_PATTERNS:
            m = re.search(pat, text)
            if m:
                hollow_hits.append((loc_id, cat_name, m.group(0), text))

        # 切分自然段内的句子（按中文句号或非序号英文句点切分）
        sentences = [s.strip() for s in re.split(r'(?:。|(?<!\d)\.(?!\d|[A-Za-z]))+', text) if s.strip()]
        if len(sentences) >= 3 and len(text) >= 55:
            has_transition = any(marker in text for marker in TRANSITION_MARKERS)
            if not has_transition:
                disconnected_paras.append((loc_id, len(sentences), text))

    return {
        'hollow_hits': hollow_hits,
        'disconnected_paras': disconnected_paras,
    }


def print_logic_report(res, src_name):
    print(f"=== [工序三：段落逻辑审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【段落逻辑审核者】参考，聚焦第 10 类（空洞归因）与第 12 类（句间逻辑断层）。\n")

    print(f"[1. 第 10 类：空洞归因句式嫌疑] ({len(res['hollow_hits'])} 处)")
    for loc_id, cat_name, hit, text in res['hollow_hits']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} [{cat_name}] 命中: “{hit}”\n    上下文: {preview}")
    if not res['hollow_hits']:
        print("  - 无")

    print(f"\n[2. 第 12 类线索：含 3 句以上但缺少显式过渡词的自然段] ({len(res['disconnected_paras'])} 处)")
    for loc_id, s_cnt, text in res['disconnected_paras']:
        preview = text if len(text) <= 85 else text[:82] + '...'
        print(f"  - 位置 {loc_id} (共 {s_cnt} 句，未检出显式因果/对比/时序连接词):\n    上下文: {preview}")
    if not res['disconnected_paras']:
        print("  - 无")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python scan_logic.py <文稿路径>")
        sys.exit(1)
    items = load_document_items(sys.argv[1])
    print_logic_report(scan_logic(items), os.path.basename(sys.argv[1]))
