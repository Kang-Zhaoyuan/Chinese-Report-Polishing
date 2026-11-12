#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 实验报告排版机械静态检查器 (check_layout.py)
对 .docx 报告进行机械化排版合规检测：
1. 检查表格与 1x1 代码框是否遵循【8523 dxa 居中收窄基准】（留出 302 dxa 呼吸内缩量）
2. 检查表格与代码框是否具有可见边框属性【tblBorders】与内边距
3. 检查核心一级大章节标题是否遵循【强制另起新页】(pageBreakBefore 或 br type="page")
4. 检查 1x1 代码框是否遵循【上不空行、下空一行】
5. 检查 1x1 代码框是否【未设置 cantSplit】（允许自然跨页切分）
6. 检查代码框单行容量是否遵循【68 字符法则】（严禁非必要过早折行）
7. 检查代码框行尾注释是否遵循【VS Code Beautifier 风格垂直列对齐】
8. 检查数据表格与插图是否遵循【上空一行、下空一行】
9. 检查西文字体是否混淆（如将 GPU/CPU/RAM/PTE 设为 Consolas）
"""

import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import os
import re
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from doc_parser import is_code_box_table

# 定死数值基准常量
BOX_BENCHMARK_WIDTH_DXA = 8523
MAX_FULL_PAGE_WIDTH_DXA = 8800  # 接近满版心 9127 dxa 的阈值
CODE_MAX_CHARS = 68  # 8523 dxa 下单行极限安全容量
COMMENT_ALIGN_BASE_COL = 44  # Beautifier 注释基准列


def is_spacer_paragraph(p):
    """判断段落是否为空行 spacer"""
    return len(p.text.strip()) == 0


def check_word_layout(docx_path: str):
    doc = Document(docx_path)
    body_elements = list(doc._body._body)
    
    print(f"=== [排版检查] 开始扫描: {os.path.basename(docx_path)} ===")
    issues = []
    warnings = []
    
    # 建立 xml element 到 index 的映射
    elem_idx = {elem: i for i, elem in enumerate(body_elements)}
    
    # 检查元素物理顺序与 sectPr 边界 (严禁在 sectPr 后出现正文元素导致倒置)
    sect_found = False
    for el_idx, el in enumerate(body_elements):
        if el.tag.endswith('sectPr'):
            sect_found = True
        elif sect_found:
            issues.append(
                f"[Body Element {el_idx}] 文档结构错乱：在 sectPr 分节符之后发现了非法的 '{el.tag.split('}')[-1]}' 元素，导致表格与段落物理显示顺序倒置！"
            )

    table_count = 0
    code_box_count = 0
    data_table_count = 0
    
    # ---------------- 1. 扫描所有表格 ----------------
    for t_idx, table in enumerate(doc.tables):
        table_count += 1
        tbl_el = table._tbl
        idx = elem_idx.get(tbl_el, -1)
        if idx == -1:
            continue
            
        is_code_box = is_code_box_table(tbl_el)
        
        # 1.1 检查表格总宽 (是否收窄至 8523 dxa 基准)
        grid_cols = tbl_el.findall(".//" + qn("w:gridCol"))
        if grid_cols:
            grid_sum = sum(int(c.attrib.get(qn("w:w"), 0)) for c in grid_cols if c.attrib.get(qn("w:w"), "").isdigit())
        else:
            tblW = tbl_el.find(".//" + qn("w:tblW"))
            grid_sum = int(tblW.attrib.get(qn("w:w"), 0)) if tblW is not None and tblW.attrib.get(qn("w:w"), "").isdigit() else 0

        # 检查水平对齐
        jc_el = tbl_el.find(".//" + qn("w:jc"))
        jc_val = jc_el.attrib.get(qn("w:val"), "") if jc_el is not None else ""
        if jc_val != "center":
            issues.append(f"[Table {t_idx}] 表格水平对齐方式为 '{jc_val}'，未设为 'center' 居中。")

        # 检查是否包含边框
        borders_el = tbl_el.find(".//" + qn("w:tblBorders"))
        if borders_el is None:
            issues.append(f"[Table {t_idx}] 表格未设置边框 tblBorders，在渲染或导出时将缺少可见边框线！")

        # 检查是否包含非透明背景底色填充 (w:shd)
        shd_fills = []
        for shd_el in tbl_el.findall(".//" + qn("w:shd")):
            fill_val = shd_el.attrib.get(qn("w:fill"), "").strip().upper()
            if fill_val and fill_val not in ("AUTO", "FFFFFF", "NONE"):
                if fill_val not in shd_fills:
                    shd_fills.append(fill_val)
        if shd_fills:
            box_type = "1x1 代码框" if is_code_box else "数据表格"
            issues.append(
                f"[Table {t_idx}] {box_type}存在非透明背景底色填充 (w:shd fill={shd_fills})，应清除底色保持无色透明背景！"
            )

        if grid_sum > MAX_FULL_PAGE_WIDTH_DXA:
            warnings.append(
                f"[Table {t_idx}] 表格宽度为 {grid_sum} dxa，未收窄至基准宽度 8523 dxa (约150mm)，两侧缺少 302 dxa 呼吸留白。"
            )

        # 1.2 检查 cantSplit (仅代码框不允许 cantSplit)
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
            
            # 检查代码框单行容量与注释对齐
            lines = [p.text for p in table.rows[0].cells[0].paragraphs]
            trailing_comment_cols = []
            for l_idx, line in enumerate(lines):
                # 检查非必要折行 (<= 68 字符)
                if l_idx < len(lines) - 1:
                    cur_str = line.rstrip()
                    nxt_str = lines[l_idx + 1].strip()
                    if cur_str.endswith(('(', '&&', '||', ',')) and nxt_str:
                        merged = cur_str + ' ' + nxt_str
                        if len(merged) <= CODE_MAX_CHARS:
                            warnings.append(
                                f"[Table {t_idx} Code] 代码第 {l_idx+1} 行疑似存在非必要换行与悬挂空格（两行合并仅 {len(merged)} 字符 <= {CODE_MAX_CHARS} 字符容量限制）。"
                            )
                
                # 检查行尾注释垂直列对齐
                if '//' in line and not line.strip().startswith('//'):
                    code_p, comm_p = line.split('//', 1)
                    trailing_comment_cols.append(len(code_p))
            
            if len(trailing_comment_cols) > 1:
                col_span = max(trailing_comment_cols) - min(trailing_comment_cols)
                if col_span > 1:
                    issues.append(
                        f"[Table {t_idx} Code] 包含 {len(trailing_comment_cols)} 处行尾注释 '//' 未列对齐（列偏移跨度 {min(trailing_comment_cols)} ~ {max(trailing_comment_cols)}），应按 Beautifier 风格垂直对齐在同一列。"
                    )

            # 检查前一个元素（上不空行）
            if idx > 0:
                prev_el = body_elements[idx - 1]
                if prev_el.tag.endswith('p'):
                    p_text = ''.join(prev_el.itertext()).strip()
                    if len(p_text) == 0:
                        issues.append(f"[Table {t_idx}] 代码框上方存在空行！按准则应【上不空行】，代码说明段落应紧贴代码框。")
                    else:
                        pPr = prev_el.find(qn("w:pPr"))
                        kwn = pPr.find(qn("w:keepNext")) if pPr is not None else None
                        if kwn is None:
                            issues.append(f"[Table {t_idx}] 代码框上方代码说明段落未设置 keep_with_next，可能在页末发生标题与代码框孤悬断裂。")
                        # 检查代码说明段落是否设置了首行缩进 2 字符
                        ind_el = pPr.find(qn("w:ind")) if pPr is not None else None
                        fl_val = ind_el.attrib.get(qn("w:firstLine"), "") if ind_el is not None else ""
                        if not fl_val or not fl_val.isdigit() or int(fl_val) < 300:
                            warnings.append(f"[Table {t_idx}] 代码框上方代码说明段落段落未设置首行缩进 2 字符 (ind firstLine='{fl_val}')。")
            
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

    # ---------------- 2. 检查核心一级大章节另起新页 ----------------
    for p_idx, p in enumerate(doc.paragraphs):
        p_text = p.text.strip()
        # 匹配一级大标题 (如 "一、回答问题", "二、实验详细设计")
        if re.match(r'^[一二三四五六七八九十]+、', p_text):
            pPr = p._element.find(qn("w:pPr"))
            has_pb_before = pPr.find(qn("w:pageBreakBefore")) is not None if pPr is not None else False
            has_br_page = any(b.attrib.get(qn("w:type")) == "page" for b in p._element.findall(".//" + qn("w:br")))
            
            if not has_pb_before and not has_br_page:
                issues.append(
                    f"[Paragraph {p_idx}] 核心一级大标题 '{p_text}' 未设置强制另起新页 (pageBreakBefore 或 br type='page')，存在页末孤悬隐患。"
                )

    # ---------------- 3. 检查常见通用硬件缩写是否错用 Consolas ----------------
    consolas_misused = []
    for p_idx, p in enumerate(doc.paragraphs):
        for run in p.runs:
            rFonts = run._element.find(".//" + qn("w:rFonts"))
            if rFonts is not None:
                ascii_font = rFonts.attrib.get(qn("w:ascii"), "")
                if ascii_font.lower() == "consolas":
                    for bad_acronym in ["GPU", "CPU", "RAM", "LRU", "PTE", "Sv39"]:
                        if re.search(r'\b' + bad_acronym + r'\b', run.text):
                            consolas_misused.append((p_idx, bad_acronym, run.text))
                            
    for p_idx, bad_acronym, text in consolas_misused[:5]:
        issues.append(f"[Paragraph {p_idx}] 通用缩写 '{bad_acronym}' 被设置为了 Consolas 等宽字体，应使用 Times New Roman。")

    print(f"统计：扫描表格 {table_count} 个（1x1 代码框 {code_box_count} 个，数据表 {data_table_count} 个）。")
    
    if warnings:
        print(f"[*] 提示与建议项 ({len(warnings)} 项)：")
        for w in warnings:
            print(f"  - {w}")

    if not issues:
        print("[√] 排版规范硬性检查全部通过！符合 8523 dxa 居中基准、流式跨页与 Beautifier 对齐法则。")
        return True
    else:
        print(f"[!] 发现 {len(issues)} 处违背排版硬性约束项：")
        for iss in issues:
            print(f"  - {iss}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_layout.py <path_to_docx>")
        sys.exit(1)
    check_word_layout(sys.argv[1])
