#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 紧凑排版工程引擎 (Word Layout Engine)
作为 Chinese-Report-Polishing 的可选后处理脚手架，实现：
1. 8523 dxa 表格与代码框收窄居中几何基准（留出 302 dxa 呼吸内缩量）
2. 容器边框 (tblBorders: #D9D9D9 细实线) 与单元格内边距 (tblCellMar: 80/100 dxa) 规范
3. 核心大章节另起新页（Page Break Before）强制硬约束
4. 代码框单行容量极限（68 字符法则，严禁非必要过早折行）
5. VS Code Beautifier 风格行尾注释垂直列对齐与单行长注释顶格分工
6. 1x1 代码框流式跨页（绝不设置 cantSplit，仅首行防悬挂）
7. 空行三态法则（代码框上不空下空、数据表与图表上下皆空）
8. 双轨西文字体 (Consolas / Times New Roman) 与宋体混排
9. Word 原生公式 (OMML m:oMath) 自动分词与注入
10. Word COM / PowerShell 无损格式导出 (.doc / .pdf)
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

# 基准定死数值常量 (基于用户批注与 A4 版心精确计算)
PAGE_BODY_WIDTH_DXA = 9127  # A4 纸张在左右边距 1418/1361 dxa 下的正文版心宽度
BOX_BENCHMARK_WIDTH_DXA = 8523  # 表格与代码框收窄基准宽度 (约 150.3 mm / 426.15 pt)
BREATHING_PAD_DXA = 302  # 两侧呼吸留白内边距 (9127 - 8523) / 2
CODE_MAX_CHARS = 68  # Consolas 11pt 在 8523 dxa 下的最大单行安全字符容量
COMMENT_ALIGN_BASE_COL = 44  # VS Code Beautifier 风格行尾注释默认参考列
BORDER_COLOR_HEX = "D9D9D9"  # 边框默认统一浅灰色


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
    使用 XML 元素 API 设置文本节点，避免直接拼接未经转义的内容。
    """
    half_pts = int(round(size_pt * 2))
    omath = parse_xml(f'<m:oMath {nsdecls("m", "w")}/>')
    tokens = re.findall(r'[A-Za-z_]+|\d+|->|[∈≤≥≠=+\-*/(),\[\]<>≤≥&|]|\s+|.', expr)
    for tok in tokens:
        if not tok:
            continue
        is_single_var = bool(re.fullmatch(r'[A-Za-z]', tok))
        
        r = OxmlElement('m:r')
        rPr = OxmlElement('m:rPr')
        if not is_single_var:
            sty = OxmlElement('m:sty')
            sty.set(qn('m:val'), 'p')
            rPr.append(sty)
        r.append(rPr)
        
        w_rPr = OxmlElement('w:rPr')
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:ascii'), 'Cambria Math')
        rFonts.set(qn('w:hAnsi'), 'Cambria Math')
        rFonts.set(qn('w:eastAsia'), '宋体')
        rFonts.set(qn('w:cs'), 'Cambria Math')
        w_rPr.append(rFonts)
        
        sz = OxmlElement('w:sz')
        sz.set(qn('w:val'), str(half_pts))
        w_rPr.append(sz)
        
        szCs = OxmlElement('w:szCs')
        szCs.set(qn('w:val'), str(half_pts))
        w_rPr.append(szCs)
        r.append(w_rPr)
        
        t = OxmlElement('m:t')
        t.set(qn('xml:space'), 'preserve')
        t.text = tok
        r.append(t)
        
        omath.append(r)
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


def apply_table_borders_and_margins(tbl_el, border_color: str = BORDER_COLOR_HEX):
    """确保表格拥有标准的 0.5pt 浅灰边框与紧凑内边距。"""
    tblPr = tbl_el.find(".//" + qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl_el.insert(0, tblPr)
    
    # 边框设置
    borders = tblPr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)
    for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        b = borders.find(qn(f"w:{border_name}"))
        if b is None:
            b = OxmlElement(f"w:{border_name}")
            borders.append(b)
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), border_color)

    # 单元格默认内边距: 上下 80 dxa, 左右 100 dxa
    cellMar = tblPr.find(qn("w:tblCellMar"))
    if cellMar is None:
        cellMar = OxmlElement("w:tblCellMar")
        tblPr.append(cellMar)
    for side, val in [("top", "80"), ("bottom", "80"), ("left", "100"), ("right", "100")]:
        m = cellMar.find(qn(f"w:{side}"))
        if m is None:
            m = OxmlElement(f"w:{side}")
            cellMar.append(m)
        m.set(qn("w:w"), val)
        m.set(qn("w:type"), "dxa")


def align_code_comments(raw_lines, max_chars: int = CODE_MAX_CHARS, base_col: int = COMMENT_ALIGN_BASE_COL):
    """
    针对代码块执行 VS Code Beautifier 风格的注释垂直对齐与双轨分工：
    1. 独立单行长注释（整行以 // 开头）：顶格或保持原缩进，绝不向右推移；
    2. 行尾跟随注释（代码语句后的 //）：在垂直方向列对齐（根据最长代码自适应确定基准列）；
    3. 绝不简单将空格压缩为 2 格。
    """
    parsed = []
    max_code_len = 0
    max_comment_len = 0
    has_trailing_comment = False

    for line in raw_lines:
        stripped = line.rstrip()
        if not stripped:
            parsed.append(('empty', ''))
            continue
        
        # 独立单行长注释 (整行以 // 开头)
        l_stripped = stripped.lstrip()
        if l_stripped.startswith('//'):
            parsed.append(('full_comment', stripped))
            continue
        
        # 包含行尾注释
        if '//' in stripped:
            parts = stripped.split('//', 1)
            code_part = parts[0].rstrip()
            comment_part = '//' + parts[1]
            parsed.append(('trailing', code_part, comment_part))
            if len(code_part) > max_code_len:
                max_code_len = len(code_part)
            if len(comment_part) > max_comment_len:
                max_comment_len = len(comment_part)
            has_trailing_comment = True
        else:
            parsed.append(('code', stripped))

    # 自适应确定行尾注释对齐列：以最长代码长度 + 4 确定基准列，兼顾不超过 max_chars
    if has_trailing_comment:
        target_col = max(max_code_len + 4, base_col)
        if target_col + max_comment_len > max_chars:
            target_col = max(max_code_len + 2, max_chars - max_comment_len)
    else:
        target_col = base_col

    formatted_lines = []
    for item in parsed:
        kind = item[0]
        if kind == 'empty':
            formatted_lines.append('')
        elif kind == 'full_comment':
            formatted_lines.append(item[1])
        elif kind == 'code':
            formatted_lines.append(item[1])
        elif kind == 'trailing':
            code_p = item[1]
            comm_p = item[2]
            pad_spaces = max(2, target_col - len(code_p))
            formatted_lines.append(f"{code_p}{' ' * pad_spaces}{comm_p}")

    return formatted_lines


def make_code_box(doc: Document, table_template_elem, code_text: str, allow_split: bool = True, width_dxa: int = BOX_BENCHMARK_WIDTH_DXA):
    """
    构建符合 8523 dxa 基准、带外边框与流式跨页原则的 1x1 代码框：
    - 总宽度定死为 width_dxa (默认 8523 dxa)，水平居中
    - 包含单实线浅灰外边框 (tblBorders) 与标准内边距
    - 绝不设置 cantSplit，允许跨页平滑断开
    - 仅首 1~2 行与上一段落建立软连接，其余行允许自然跨页
    - 单行容量严格遵循 68 字符法则，严禁非必要过早折行
    - VS Code Beautifier 风格行尾注释垂直列对齐
    """
    tbl_el = deepcopy(table_template_elem)
    
    # 1. 规范表格宽度与对齐 (定死 8523 dxa 居中)
    tblPr = tbl_el.find(".//" + qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl_el.insert(0, tblPr)
    
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(width_dxa))
    tblW.set(qn("w:type"), "dxa")
    
    jc = tblPr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        tblPr.append(jc)
    jc.set(qn("w:val"), "center")
    
    # 补全标准边框与边距
    apply_table_borders_and_margins(tbl_el, border_color=BORDER_COLOR_HEX)
    
    # 规范网格列宽
    tblGrid = tbl_el.find(".//" + qn("w:tblGrid"))
    if tblGrid is None:
        tblGrid = OxmlElement("w:tblGrid")
        tbl_el.append(tblGrid)
    cols = tblGrid.findall(qn("w:gridCol"))
    if not cols:
        col = OxmlElement("w:gridCol")
        tblGrid.append(col)
        cols = [col]
    cols[0].set(qn("w:w"), str(width_dxa))

    tc = tbl_el.find(".//" + qn("w:tc"))
    for child in list(tc):
        if child.tag != qn("w:tcPr"):
            tc.remove(child)

    # 规范单元格宽度
    tcPr = tc.find(qn("w:tcPr"))
    if tcPr is None:
        tcPr = OxmlElement("w:tcPr")
        tc.insert(0, tcPr)
    tcW = tcPr.find(qn("w:tcW"))
    if tcW is None:
        tcW = OxmlElement("w:tcW")
        tcPr.append(tcW)
    tcW.set(qn("w:w"), str(width_dxa))
    tcW.set(qn("w:type"), "dxa")

    # 显式移除行级 cantSplit，确保允许跨页
    tr = tbl_el.find(".//" + qn("w:tr"))
    if tr is not None:
        trPr = tr.find(qn("w:trPr"))
        if trPr is not None:
            cantSplit = trPr.find(qn("w:cantSplit"))
            if cantSplit is not None and allow_split:
                trPr.remove(cantSplit)

    raw_lines = [ln.rstrip() for ln in code_text.strip("\n").splitlines()]
    # 执行 VS Code Beautifier 风格注释对齐
    aligned_lines = align_code_comments(raw_lines, max_chars=CODE_MAX_CHARS, base_col=COMMENT_ALIGN_BASE_COL)

    return_types = {"static uint", "static void", "void", "static struct buf *", "static struct buf*"}
    for idx, raw_line in enumerate(aligned_lines):
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
        prev_stripped = aligned_lines[idx - 1].strip() if idx > 0 else ""
        next_stripped = aligned_lines[idx + 1].strip() if idx + 1 < len(aligned_lines) else ""
        keep_line = (
            idx in (0, 1)
            or stripped_cur in return_types
            or prev_stripped in return_types
            or next_stripped == "{"
        ) and (idx < len(aligned_lines) - 1)
        fmt.keep_with_next = keep_line
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # 单行容量法则：<= 68 字符绝对不进行折行；只有真实超出 68 字符时才折行
        if len(raw_line) <= CODE_MAX_CHARS:
            display = raw_line
        else:
            chunks = textwrap.wrap(
                raw_line,
                width=CODE_MAX_CHARS,
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


def format_table_width(table_elem, width_dxa: int = BOX_BENCHMARK_WIDTH_DXA, align: str = "center"):
    """
    将任意多行多列数据表格按 8523 dxa 基准进行宽度收窄、边框补全与居中重调：
    - tblW[@w="8523"][@type="dxa"]
    - jc[@val="center"]
    - 补全单实线浅灰边框 (tblBorders) 与内边距
    - 等比例重算各列 gridCol 与 tcW，确保列宽总和精确等于 8523 dxa
    """
    tblPr = table_elem.find(".//" + qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        table_elem.insert(0, tblPr)
    
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(width_dxa))
    tblW.set(qn("w:type"), "dxa")
    
    jc = tblPr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        tblPr.append(jc)
    jc.set(qn("w:val"), align)

    # 补全标准边框与边距
    apply_table_borders_and_margins(table_elem, border_color=BORDER_COLOR_HEX)

    tblGrid = table_elem.find(".//" + qn("w:tblGrid"))
    if tblGrid is not None:
        cols = tblGrid.findall(qn("w:gridCol"))
        if cols:
            widths = [int(c.attrib.get(qn("w:w"), 0)) for c in cols]
            total_w = sum(widths) if sum(widths) > 0 else len(cols)
            new_widths = [int(round(w * width_dxa / total_w)) for w in widths]
            # 保证总和精确等于 width_dxa
            diff = width_dxa - sum(new_widths)
            new_widths[-1] += diff
            for c, nw in zip(cols, new_widths):
                c.set(qn("w:w"), str(nw))

            # 同步更新各行的单元格宽度
            for tr in table_elem.findall(".//" + qn("w:tr")):
                tcs = tr.findall(".//" + qn("w:tc"))
                for tc, nw in zip(tcs, new_widths):
                    tcPr = tc.get_or_add_tcPr()
                    tcW = tcPr.find(qn("w:tcW"))
                    if tcW is None:
                        tcW = OxmlElement("w:tcW")
                        tcPr.append(tcW)
                    tcW.set(qn("w:w"), str(nw))
                    tcW.set(qn("w:type"), "dxa")


def set_major_section_page_break(paragraph: Paragraph):
    """为核心一级大章节段落设置强制另起新页 (pageBreakBefore)。"""
    pPr = paragraph._element.get_or_add_pPr()
    pb = pPr.find(qn("w:pageBreakBefore"))
    if pb is None:
        pb = OxmlElement("w:pageBreakBefore")
        pPr.append(pb)


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
