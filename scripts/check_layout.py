#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 实验报告排版机械静态检查器 (check_layout.py)
对 .docx 报告进行机械化排版合规检测：
1. 检查 1x1 代码框是否遵循【上不空行、下空一行】
2. 检查 1x1 代码框是否【未设置 cantSplit】（允许自然跨页切分）
3. 检查数据表格与插图是否遵循【上空一行、下空一行】
4. 检查西文字体是否混淆（如将 GPU/CPU 设为 Consolas）
"""

import sys
import os
import re
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn


def is_spacer_paragraph(p):
    """判断段落是否为空行 spacer"""
    return len(p.text.strip()) == 0


def check_word_layout(docx_path: str):
    doc = Document(docx_path)
    body_elements = list(doc._body._body)
    
    print(f"=== [排版检查] 开始扫描: {os.path.basename(docx_path)} ===")
    issues = []
    
    # 建立 xml element 到 index 的映射
    elem_idx = {elem: i for i, elem in enumerate(body_elements)}
    
    table_count = 0
    code_box_count = 0
    data_table_count = 0
    
    for t_idx, table in enumerate(doc.tables):
        table_count += 1
        tbl_el = table._tbl
        idx = elem_idx.get(tbl_el, -1)
        if idx == -1:
            continue
            
        rows_len = len(table.rows)
        cols_len = len(table.columns)
        is_code_box = (rows_len == 1 and cols_len == 1)
        
        # 1. 检查 cantSplit
        tr = tbl_el.find(".//" + qn("w:tr"))
        has_cant_split = False
        if tr is not None:
            trPr = tr.find(qn("w:trPr"))
            if trPr is not None and trPr.find(qn("w:cantSplit")) is not None:
                has_cant_split = True
                
        if is_code_box:
            code_box_count += 1
            if has_cant_split:
                issues.append(f"[Table {t_idx}] 1x1 代码框设置了 cantSplit=True，可能导致长代码框整块推移并造成上一页大面积死白。应允许跨页。")
            
            # 检查前一个元素（上不空行）
            if idx > 0:
                prev_el = body_elements[idx - 1]
                if prev_el.tag.endswith('p'):
                    p_text = ''.join(prev_el.itertext()).strip()
                    if len(p_text) == 0:
                        issues.append(f"[Table {t_idx}] 代码框上方存在空行！按准则应【上不空行】，引导语应紧贴代码框。")
                    else:
                        # 检查前一段是否有 keep_with_next
                        pPr = prev_el.find(qn("w:pPr"))
                        kwn = pPr.find(qn("w:keepNext")) if pPr is not None else None
                        if kwn is None:
                            issues.append(f"[Table {t_idx}] 代码框上方引导语未设置 keep_with_next，可能在页末发生标题与代码框孤悬断裂。")
            
            # 检查后一个元素（下空一行）
            if idx < len(body_elements) - 1:
                next_el = body_elements[idx + 1]
                if next_el.tag.endswith('p'):
                    p_text = ''.join(next_el.itertext()).strip()
                    if len(p_text) > 0:
                        issues.append(f"[Table {t_idx}] 代码框下方未空行！按准则应【下空一行】，需插入 11pt 独立空段落。")
                elif next_el.tag.endswith('tbl'):
                    issues.append(f"[Table {t_idx}] 代码框紧挨着下一个表格，中间缺少空行。")
        else:
            data_table_count += 1
            # 数据表格：上空一行、下空一行
            if idx > 0:
                prev_el = body_elements[idx - 1]
                if prev_el.tag.endswith('p') and len(''.join(prev_el.itertext()).strip()) > 0:
                    issues.append(f"[Table {t_idx}] 数据表格上方未空行！按准则应【上空一行】。")
            if idx < len(body_elements) - 1:
                next_el = body_elements[idx + 1]
                if next_el.tag.endswith('p') and len(''.join(next_el.itertext()).strip()) > 0:
                    issues.append(f"[Table {t_idx}] 数据表格下方未空行！按准则应【下空一行】。")
                    
    # 2. 检查常见通用硬件缩写是否错用 Consolas
    consolas_misused = []
    for p_idx, p in enumerate(doc.paragraphs):
        for run in p.runs:
            rFonts = run._element.find(".//" + qn("w:rFonts"))
            if rFonts is not None:
                ascii_font = rFonts.attrib.get(qn("w:ascii"), "")
                if ascii_font.lower() == "consolas":
                    # 检查是否包含 GPU/CPU/RAM 等纯缩写
                    for bad_acronym in ["GPU", "CPU", "RAM", "LRU"]:
                        if re.search(r'\b' + bad_acronym + r'\b', run.text):
                            consolas_misused.append((p_idx, bad_acronym, run.text))
                            
    for p_idx, bad_acronym, text in consolas_misused[:5]:
        issues.append(f"[Paragraph {p_idx}] 通用缩写 '{bad_acronym}' 被设置为了 Consolas 等宽字体，应使用 Times New Roman。")

    print(f"统计：扫描表格 {table_count} 个（1x1代码框 {code_box_count} 个，数据表 {data_table_count} 个）。")
    if not issues:
        print("[√] 排版规范检查全部通过！符合紧凑流式布局与空行三态法则。")
        return True
    else:
        print(f"[!] 发现 {len(issues)} 处潜在排版偏离项：")
        for iss in issues:
            print(f"  - {iss}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_layout.py <path_to_docx>")
        sys.exit(1)
    check_word_layout(sys.argv[1])
