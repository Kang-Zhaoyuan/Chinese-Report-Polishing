#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文稿解析与纯文本镜像导出模块 (doc_parser.py)

职责：
1. 读取 .docx 文件：递归提取正文段落与非代码框表格（数据表、布局表、嵌套表）中的单元格文本，
   仅跳过 1x1 代码框与终端输出框。
2. 读取 .md / .txt 文件：跳过 YAML Frontmatter 与代码块，按空行及块级元素边界合并跨行自然段，
   保留原始起止行号（如 L12-L15）。
3. 将解析结果导出为带位置编号（[P1]、[T1R1C2]）的纯文本镜像文件，供各专职审核子线程读取。
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy

W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

HEADING_PATTERN = re.compile(
    r'^([一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+\.\d+\s+|#{1,6}\s+)'
)

BLOCK_START_PATTERN = re.compile(
    r'^(#{1,6}\s+|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|[-*+]\s+|\d+\.\s+|\|\s*|>\s*)'
)


def is_likely_code_paragraph(text):
    """判断文本是否为代码段（C/C++/CUDA/Python/MATLAB/DSP/Verilog）或终端/仿真/抓包输出日志。"""
    code_indicators = [
        ';', '{', '}', '#include', '#pragma', '__shared__', '__m256',
        'PASS ', 'Total Errors', 'for (', 'if (', 'float ', 'int ', 'dim3 ',
        'clc;', 'clear;', 'close all', 'subplot(', 'plot(', 'fft(', 'randn(',
        'freqz(', 'butter(', 'fir1(', 'cheby1(', 'conv(', 'filter(', 'hamming(',
        'module ', 'endmodule', 'always @(', 'assign ',
        '64 bytes from', 'icmp_seq=', 'ttl=', 'traceroute', 'tcpdump'
    ]
    hits = sum(1 for ind in code_indicators if ind in text)
    return hits >= 2


def is_code_box_table(tbl_elem):
    """
    判断 Word 表格是否为 1x1 代码框或终端输出框：
    仅当表格为 1 行 1 列，且内部含代码/终端特征或主要使用等宽代码字体时返回 True。
    支持传入 xml Element 或 docx.table.Table 对象。
    """
    if hasattr(tbl_elem, '_tbl'):
        tbl_elem = tbl_elem._tbl
    rows = tbl_elem.findall(f'./{W_NS}tr')
    if len(rows) != 1:
        return False
    cells = rows[0].findall(f'./{W_NS}tc')
    if len(cells) != 1:
        return False

    full_text = ''.join(tbl_elem.itertext()).strip()
    if is_likely_code_paragraph(full_text):
        return True

    code_font_runs = 0
    total_runs = 0
    for r in tbl_elem.findall(f'.//{W_NS}r'):
        r_text = ''.join(r.itertext()).strip()
        if not r_text:
            continue
        total_runs += 1
        rfonts = r.find(f'./{W_NS}rPr/{W_NS}rFonts')
        if rfonts is not None:
            font_vals = ' '.join(rfonts.attrib.values()).lower()
            if any(f in font_vals for f in ('consolas', 'courier', 'mono', 'menlo')):
                code_font_runs += 1

    return total_runs > 0 and (code_font_runs / total_runs) >= 0.6


def _extract_table_elements(tbl_elem, tbl_prefix, items):
    """递归提取非代码框表格中的单元格文本（支持嵌套表格）。"""
    rows = tbl_elem.findall(f'./{W_NS}tr')
    for r_idx, row in enumerate(rows, 1):
        cells = row.findall(f'./{W_NS}tc')
        for c_idx, cell in enumerate(cells, 1):
            cell_prefix = f"{tbl_prefix}R{r_idx}C{c_idx}"
            p_list = []
            for child in cell:
                tag = child.tag.split('}')[-1]
                if tag == 'p':
                    t = ''.join(child.itertext()).strip()
                    if t:
                        p_list.append(t)
                elif tag == 'tbl':
                    if not is_code_box_table(child):
                        _extract_table_elements(child, f"{cell_prefix}_T", items)
            if len(p_list) == 1:
                items.append((cell_prefix, p_list[0], 'tbl'))
            elif len(p_list) > 1:
                for p_i, p_text in enumerate(p_list, 1):
                    items.append((f"{cell_prefix}P{p_i}", p_text, 'tbl'))


def iter_body_elements(body, skip_first_page=False):
    """按保存的分页标记跳过封面，保留原正文元素序号。"""
    started = not skip_first_page
    for index, original in enumerate(body):
        element = original
        if not started:
            before = element.find(f'./{W_NS}pPr/{W_NS}pageBreakBefore')
            if before is not None and before.get(W_NS + 'val', '1') not in ('0', 'false', 'off'):
                started = True
            else:
                def is_break(node):
                    return (node.tag == W_NS + 'lastRenderedPageBreak' or
                            node.tag == W_NS + 'br' and node.get(W_NS + 'type') == 'page')
                if any(is_break(node) for node in element.iter()):
                    element = deepcopy(element)

                    def trim(parent):
                        for child in list(parent):
                            if is_break(child):
                                parent.remove(child)
                                return True
                            if trim(child):
                                return True
                            parent.remove(child)
                        return False

                    trim(element)
                    started = True
                else:
                    section = element.find(f'./{W_NS}pPr/{W_NS}sectPr')
                    section_type = section.find(W_NS + 'type') if section is not None else None
                    if section is not None and (section_type is None or section_type.get(W_NS + 'val') in ('nextPage', 'evenPage', 'oddPage')):
                        started = True
                    continue
        yield index, element
    if skip_first_page and not started:
        raise ValueError('PAGE_BOUNDARY_MISSING: 文档未保存分页标记；请更新分页，或用 --include-cover 检查全文。')


def extract_from_docx(path, skip_first_page=False):
    """
    从 .docx 提取正文段落及数据表/布局表单元格文本，仅排除 1x1 代码框。
    返回列表: [(loc_id, text, kind), ...] 其中 kind in ('p', 'tbl', 'code_box')
    """
    items = []
    p_counter = 0
    tbl_counter = 0
    with zipfile.ZipFile(path, 'r') as z:
        root = ET.fromstring(z.read('word/document.xml'))
        body = root.find(f'{W_NS}body')
        selected = dict(iter_body_elements(body, skip_first_page))
        for index, original in enumerate(body):
            elem = selected.get(index)
            if original.tag == W_NS + 'p' and ''.join(original.itertext()).strip():
                p_counter += 1
            if original.tag == W_NS + 'tbl':
                tbl_counter += 1
            if elem is None:
                continue
            tag = elem.tag.split('}')[-1]
            if tag == 'p':
                text = ''.join(elem.itertext()).strip()
                if text:
                    items.append((f"P{p_counter}", text, 'p'))
            elif tag == 'tbl':
                if is_code_box_table(elem):
                    items.append((f"T{tbl_counter}", "[1x1 代码/终端输出框]", 'code_box'))
                else:
                    _extract_table_elements(elem, f"T{tbl_counter}", items)
    return items


def extract_from_text(path):
    """
    从 .md 或 .txt 提取自然段：
    按空行及块级元素边界切分自然段，合并跨行折行文本，保留原始起止行号。
    """
    items = []
    in_code_block = False
    buf_lines = []
    start_line = None
    end_line = None

    def flush_buffer():
        nonlocal buf_lines, start_line, end_line
        if not buf_lines:
            return
        merged = ' '.join(buf_lines).strip()
        merged = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', merged)
        loc_id = f"L{start_line}" if start_line == end_line else f"L{start_line}-L{end_line}"
        kind = 'tbl' if merged.startswith('|') else 'p'
        items.append((loc_id, merged, kind))
        buf_lines = []
        start_line = None
        end_line = None

    with open(path, 'r', encoding='utf-8') as f:
        in_frontmatter = False
        for idx, raw_line in enumerate(f, 1):
            stripped = raw_line.strip()
            if idx == 1 and stripped == '---':
                in_frontmatter = True
                continue
            if in_frontmatter:
                if stripped == '---':
                    in_frontmatter = False
                continue
            if stripped.startswith('```'):
                flush_buffer()
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if not stripped or re.match(r'^[-=]{3,}$', stripped):
                flush_buffer()
                continue

            if BLOCK_START_PATTERN.match(stripped):
                flush_buffer()
                buf_lines.append(stripped)
                start_line = idx
                end_line = idx
                if stripped.startswith('#') or stripped.startswith('|') or HEADING_PATTERN.match(stripped):
                    flush_buffer()
            else:
                if start_line is None:
                    start_line = idx
                buf_lines.append(stripped)
                end_line = idx

    flush_buffer()
    return items


def load_document_items(path, skip_first_page=False):
    """根据扩展名加载文稿条目列表 [(loc_id, text, kind), ...]。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        return extract_from_docx(path, skip_first_page)
    return extract_from_text(path)


def is_heading_item(text, kind):
    """判断条目是否为正文各级标题。"""
    return kind == 'p' and bool(HEADING_PATTERN.match(text)) and len(text) <= 35


def iter_clean_items(items):
    """遍历非代码块、非 Markdown 表格分隔符的有效文本条目。"""
    for loc_id, text, kind in items:
        if kind == 'code_box' or is_likely_code_paragraph(text):
            continue
        if kind == 'tbl' and re.match(r'^[\s|:\-]+$', text):
            continue
        yield loc_id, text, kind


def write_extracted_view(items, out_path, src_name):
    """将提取出的段落与表格单元输出为带位置编号的纯文本镜像。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# 文稿结构化提取视图: {src_name}\n\n")
        for loc_id, text, kind in items:
            f.write(f"[{loc_id}] {text}\n")
