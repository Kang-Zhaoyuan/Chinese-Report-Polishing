#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 紧凑排版工程引擎 (Word Layout Engine)
作为 Chinese-Report-Polishing 的可选后处理脚手架，实现：
1. 双轨西文字体 (Consolas / Times New Roman) 与宋体混排
2. Word 原生公式 (OMML m:oMath) 自动分词与注入
3. 1x1 代码框表格 (支持跨页切分、软回车折行、首行绑定)
4. 空行三态法则 (代码框上不空下空、图表上下皆空)
5. Word COM / PowerShell 无损格式导出 (.doc / .pdf)
"""

from copy import deepcopy
import os
from pathlib import Path
import re
import textwrap
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.text.paragraph import Paragraph
from docx.enum.text import WD_ALIGN_PARAGRAPH

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def set_run_font(run, ascii_font: str = "Times New Roman", size_pt: float = 11.0, bold: bool = False):
    """设置单个 Run 的中西文字体、字号与粗体属性。"""
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:cs"), ascii_font)
    rFonts.set(qn("w:eastAsia"), "宋体")


def create_omath_element(expr: str, size_pt: float = 11.0):
    """
    将数学表达式字符串转换为 Word 原生 OMML (<m:oMath>) 节点。
    单字母变量默认斜体，多字母标识符、运算符与数字直立体 (<m:sty m:val="p"/>)。
    """
    half_pts = int(round(size_pt * 2))
    omath = parse_xml(f'<m:oMath {nsdecls("m", "w")}/>')
    tokens = re.findall(r'[A-Za-z_]+|\d+|->|[∈≤≥≠=+\-*/(),\[\]]|\s+|.', expr)
    for tok in tokens:
        if not tok:
            continue
        is_single_var = bool(re.fullmatch(r'[A-Za-z]', tok))
        sty_xml = '' if is_single_var else '<m:sty m:val="p"/>'
        r_xml = (
            f'<m:r {nsdecls("m", "w")}>'
            f'<m:rPr>{sty_xml}</m:rPr>'
            f'<w:rPr>'
            f'<w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math" w:eastAsia="宋体" w:cs="Cambria Math"/>'
            f'<w:sz w:val="{half_pts}"/><w:szCs w:val="{half_pts}"/>'
            f'</w:rPr>'
            f'<m:t xml:space="preserve">{tok}</m:t>'
            f'</m:r>'
        )
        omath.append(parse_xml(r_xml))
    return omath


def append_rich_text(p: Paragraph, markup_text: str, size_pt: float = 11.0, bold: bool = False):
    """
    解析 Markdown 内联标记并应用双轨字体：
    - `code` -> Consolas 等宽字体
    - $math$ -> Word 原生 m:oMath 公式
    - 其余文本 -> Times New Roman + 宋体
    """
    pattern = re.compile(r'(`[^`]+`|\$[^$]+\$)')
    pos = 0
    for m in pattern.finditer(markup_text):
        if m.start() > pos:
            plain = markup_text[pos:m.start()]
            r = p.add_run(plain)
            set_run_font(r, "Times New Roman", size_pt=size_pt, bold=bold)
        token = m.group(0)
        if token.startswith('`') and token.endswith('`'):
            code_str = token[1:-1]
            r = p.add_run(code_str)
            set_run_font(r, "Consolas", size_pt=size_pt, bold=bold)
        elif token.startswith('$') and token.endswith('$'):
            math_str = token[1:-1]
            p._p.append(create_omath_element(math_str, size_pt=size_pt))
        pos = m.end()
    if pos < len(markup_text):
        plain = markup_text[pos:]
        r = p.add_run(plain)
        set_run_font(r, "Times New Roman", size_pt=size_pt, bold=bold)


def make_code_box(doc: Document, table_template_elem, code_text: str, allow_split: bool = True):
    """
    构建符合流式跨页原则的 1x1 代码框：
    - 绝不设置 cantSplit，允许跨页平滑断开
    - 仅首 1~2 行与上一段落建立软连接，其余行允许自然跨页
    - 段内软回车折行，避免长行撑破表格边界
    """
    tbl_el = deepcopy(table_template_elem)
    tc = tbl_el.find(".//" + qn("w:tc"))
    for child in list(tc):
        if child.tag != qn("w:tcPr"):
            tc.remove(child)

    # 显式移除行级 cantSplit，确保允许跨页
    tr = tbl_el.find(".//" + qn("w:tr"))
    if tr is not None:
        trPr = tr.find(qn("w:trPr"))
        if trPr is not None:
            cantSplit = trPr.find(qn("w:cantSplit"))
            if cantSplit is not None and allow_split:
                trPr.remove(cantSplit)

    raw_lines = [ln.rstrip() for ln in code_text.strip("\n").splitlines()]
    return_types = {"static uint", "static void", "void", "static struct buf *", "static struct buf*"}
    for idx, raw_line in enumerate(raw_lines):
        p_el = OxmlElement("w:p")
        tc.append(p_el)
        p = Paragraph(p_el, doc._body)
        fmt = p.paragraph_format
        if not raw_line.strip():
            fmt.left_indent = Pt(0)
            fmt.first_line_indent = Pt(0)
            fmt.space_before = Pt(0)
            fmt.space_after = Pt(0)
            fmt.line_spacing = 1
            fmt.keep_together = True
            fmt.keep_with_next = False
            r = p.add_run("")
            set_run_font(r, "Consolas", size_pt=11.0, bold=False)
            continue

        leading_spaces = len(raw_line) - len(raw_line.lstrip(" "))
        indent = 2 * leading_spaces
        fmt.left_indent = Pt((indent + 4) * 6.05)
        fmt.first_line_indent = Pt(-4 * 6.05)
        fmt.right_indent = Pt(0)
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1
        fmt.keep_together = True
        
        # 仅前两行或特殊签名行与下一行绑定，避免整表被推下页
        stripped_cur = raw_line.strip()
        prev_stripped = raw_lines[idx - 1].strip() if idx > 0 else ""
        next_stripped = raw_lines[idx + 1].strip() if idx + 1 < len(raw_lines) else ""
        keep_line = (
            idx in (0, 1)
            or stripped_cur in return_types
            or prev_stripped in return_types
            or next_stripped == "{"
        ) and (idx < len(raw_lines) - 1)
        fmt.keep_with_next = keep_line
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        clean_line = re.sub(r"\s+(//)", r"  \1", raw_line.strip())
        chunks = textwrap.wrap(
            clean_line,
            width=max(20, 58 - indent),
            subsequent_indent="    ",
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        if len(chunks) > 1 and chunks[-1].strip() == "{":
            chunks[-2] += " {"
            chunks.pop()
        display = "\n".join([chunks[0]] + [x[4:] for x in chunks[1:]]) if chunks else ""
        r = p.add_run(display)
        set_run_font(r, "Consolas", size_pt=11.0, bold=False)

    return tbl_el


def make_spacer(doc: Document, base_p_elem):
    """创建一个标准 11pt 单倍行距空行段落。"""
    el = deepcopy(base_p_elem)
    for child in list(el):
        if child.tag != qn("w:pPr"):
            el.remove(child)
    p = Paragraph(el, doc._body)
    fmt = p.paragraph_format
    fmt.left_indent = Pt(0)
    fmt.first_line_indent = Pt(0)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = 1.0
    fmt.keep_with_next = False
    r = p.add_run("")
    set_run_font(r, "Times New Roman", size_pt=11.0)
    return el


def export_formats_via_word(docx_path: str, doc_path: str = None, pdf_path: str = None):
    """通过 Word COM 导出无损 .doc 与 .pdf。"""
    import win32com.client as win32
    w = win32.gencache.EnsureDispatch('Word.Application')
    w.Visible = False
    try:
        d = w.Documents.Open(os.path.abspath(docx_path))
        if doc_path:
            d.SaveAs2(os.path.abspath(doc_path), 0)
        if pdf_path:
            d.ExportAsFixedFormat(os.path.abspath(pdf_path), 17)
        d.Close(0)
    finally:
        w.Quit()
