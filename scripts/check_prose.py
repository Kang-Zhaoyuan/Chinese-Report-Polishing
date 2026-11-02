#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文实验报告语言静态扫描与文本提取脚本 (check_prose.py)

功能：
1. 支持读取 .docx、.md 或 .txt 文稿：
   - 对 .docx：递归提取正文段落与数据表/布局表单元格文本，仅跳过 1x1 代码框与终端日志框；
   - 对 .md/.txt：按空行与块级元素边界合并跨行自然段，保留原始起止行号。
2. 支持 --extract <path> 参数，将 .docx 导出为带段落定位编号的纯文本镜像，供审核子线程读取。
3. 输出四类客观语言线索供审核子线程参考：
   - 含有并列连词（与、及、和、以及）的标题；
   - 两个标点符号之间超过 20 个阅读单位的超长单句；
   - 同一自然段内重复出现 3 次以上的高频词；
   - 疑似 AI 过拟合词汇、防御性局限声明、自我证实表述及图表引导冗余。
"""

import sys
import os
import re
import argparse
import zipfile
import xml.etree.ElementTree as ET

W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# 1. 高危 AI 过拟合词汇与工程行话迁移词
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

# 2. 疑似句式正则模式（名称 -> 正则表达式）
SUSPECT_PATTERNS = [
    ('防御性局限声明', r'(现有|本次|当前)(测试|实验|数据|日志|记录).*?(没有|未|无法|难以).*?(记录|测量|确定|拆分|区分|得知)'),
    ('防御性局限声明', r'(具体|内部).*?(分块|策略|贡献|实现)无法从.*?(程序|日志|测试|结果).*?确定'),
    ('防御性局限声明', r'效果需要结合具体(规模|场景|情况)判断'),
    ('无信息增益的自我证实表述', r'实际测试|根据实验\s*\d+\s*的实现要求|数据分别来自两次测试|生成文本保持一致'),
    ('冗余的图表引导与自评', r'为了直观(比较|展示)|根据表\s*[\d\-]+\s*的数据展示|从表\s*[\d\-]+\s*和图\s*[\d\-]+\s*可以看出|如(?:图|表)\s*[\d\-]+\s*所示'),
    ('空洞归因', r'是影响(运行时间|计算性能|推理速度)的可能因素|改变了线程组织和数据访问方式'),
    ('自然语言算术', r'\d+\s*除以\s*\d+\s*余\s*\d+|由.*?(平均速度|时间)除以.*?(平均速度|时间)'),
    ('欧化翻译腔句式', r'不仅.*?而且|一方面.*?另一方面|基于.*?而言|在.*?的背景下'),
    ('伪拟人主语嫌疑', r'实验选择该|本文选择该'),
]

# 3. 同段高频词监控表（单段出现 >= 3 次时提示检查是否呆板）
TRACKED_REPEAT_WORDS = [
    '程序', '实验', '线程', '矩阵', '模型', '平均', '在', '通过', '使用', '计算'
]

HEADING_PATTERN = re.compile(
    r'^([一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+\.\d+\s+|#{1,6}\s+)'
)

BLOCK_START_PATTERN = re.compile(
    r'^(#{1,6}\s+|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|[-*+]\s+|\d+\.\s+|\|\s*|>\s*)'
)


def is_likely_code_paragraph(text):
    """判断文本是否为代码段或终端输出日志。"""
    code_indicators = [
        ';', '{', '}', '#include', '#pragma', '__shared__', '__m256',
        'PASS ', 'Total Errors', 'for (', 'if (', 'float ', 'int ', 'dim3 '
    ]
    hits = sum(1 for ind in code_indicators if ind in text)
    return hits >= 2


def is_code_box_table(tbl_elem):
    """
    判断 Word 表格是否为 1x1 代码框或终端输出框：
    仅当表格为 1 行 1 列，且内部含代码/终端特征或全部使用等宽代码字体时返回 True。
    """
    rows = tbl_elem.findall(f'./{W_NS}tr')
    if len(rows) != 1:
        return False
    cells = rows[0].findall(f'./{W_NS}tc')
    if len(cells) != 1:
        return False

    full_text = ''.join(tbl_elem.itertext()).strip()
    if is_likely_code_paragraph(full_text):
        return True

    # 检查是否显式设置了等宽代码字体（如 Consolas / Courier New）
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


def extract_paragraphs_from_docx(path):
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
        for elem in body:
            tag = elem.tag.split('}')[-1]
            if tag == 'p':
                text = ''.join(elem.itertext()).strip()
                if text:
                    p_counter += 1
                    items.append((f"P{p_counter}", text, 'p'))
            elif tag == 'tbl':
                tbl_counter += 1
                if is_code_box_table(elem):
                    items.append((f"T{tbl_counter}", "[1x1 代码/终端输出框]", 'code_box'))
                else:
                    _extract_table_elements(elem, f"T{tbl_counter}", items)
    return items


def extract_paragraphs_from_text(path):
    """
    从 .md 或 .txt 提取自然段：
    按空行及块级元素（标题、列表项、表格行、引用块、代码块）边界切分自然段，
    将跨行折行的同一自然段合并，并保留原始起止行号（如 L12 或 L12-L15）。
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
        # 消除中文字符之间因换行产生的多余空格
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

            # 若当前行为标题、表格行或新列表项，先刷新上一段缓冲
            if BLOCK_START_PATTERN.match(stripped):
                flush_buffer()
                buf_lines.append(stripped)
                start_line = idx
                end_line = idx
                # 标题与表格行单行独立成块
                if stripped.startswith('#') or stripped.startswith('|') or HEADING_PATTERN.match(stripped):
                    flush_buffer()
            else:
                if start_line is None:
                    start_line = idx
                buf_lines.append(stripped)
                end_line = idx

    flush_buffer()
    return items


def measure_clause_length(clause):
    """
    计算分句的阅读长度：
    将连续的英文单词、函数名、带上下标的变量或数字算式计为 1 个阅读单元，中文字符每个计为 1 个单元。
    """
    collapsed = re.sub(r'[A-Za-z0-9_.\-+/*=<>()\[\]\u2070-\u209f\u00b2\u00b3\u00b9×÷±≈≠≤≥]+', 'X', clause)
    collapsed = re.sub(r'\s+', '', collapsed)
    return len(collapsed)


def write_extracted_view(items, out_path, src_name):
    """将提取出的段落与表格单元输出为带编号的纯文本文件，供审核子线程读取。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# 文稿结构化提取视图: {src_name}\n\n")
        for loc_id, text, kind in items:
            f.write(f"[{loc_id}] {text}\n")


def analyze_document(path, extract_out=None, max_clause_len=20, repeat_threshold=3):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        items = extract_paragraphs_from_docx(path)
    else:
        items = extract_paragraphs_from_text(path)

    if extract_out:
        write_extracted_view(items, extract_out, os.path.basename(path))

    heading_issues = []
    long_clauses = []
    repeat_issues = []
    pattern_issues = []

    split_punct = re.compile(r'(?:[，。；：？！、,;?!（）()|]|\.(?![A-Za-z0-9_]))+')

    for loc_id, text, kind in items:
        if kind == 'code_box' or is_likely_code_paragraph(text):
            continue

        # 跳过 Markdown 表格分隔行（如 | :--- | :---: |）
        if kind == 'tbl' and re.match(r'^[\s|:\-]+$', text):
            continue

        # 1. 检查标题并列连词（仅针对正文标题，不将表格内短文本误判为章节标题）
        if kind == 'p' and HEADING_PATTERN.match(text) and len(text) <= 35:
            conj_match = re.findall(r'(与|及|和|以及)', text)
            if conj_match:
                heading_issues.append((loc_id, text, conj_match))
            continue

        # 2. 检查超长单句（仅对含中文叙述的分句计长，避免纯数字/符号串误报）
        clauses = [c.strip() for c in split_punct.split(text) if c.strip()]
        for c in clauses:
            if len(re.findall(r'[\u4e00-\u9fff]', c)) < 4:
                continue
            c_len = measure_clause_length(c)
            if c_len > max_clause_len:
                long_clauses.append((loc_id, c_len, c))

        # 3. 检查同段高频重复词（仅对长度 >= 30 字的自然段进行统计）
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

        # 4. 检查高危词汇与疑似句式（含正文及表格单元格）
        hit_words = [w for w in AI_OVERFIT_WORDS if w in text]
        if hit_words:
            pattern_issues.append((loc_id, 'AI 过拟合与翻译腔词汇', f"命中词汇: {hit_words}", text))

        for pat_name, regex in SUSPECT_PATTERNS:
            m = re.search(regex, text)
            if m:
                pattern_issues.append((loc_id, pat_name, f"命中片段: “{m.group(0)}”", text))

    # 输出扫描报告
    print(f"=== 语言静态扫描报告: {os.path.basename(path)} ===")
    print("说明：以下结果由脚本规则生成，仅作为定位线索，请审核者结合上下文语义判断。\n")

    print(f"[一] 双中心并列标题嫌疑 ({len(heading_issues)} 处)")
    for loc_id, h_text, conjs in heading_issues:
        print(f"  - 位置 {loc_id}: 「{h_text}」 (含并列连词: {conjs})")
    if not heading_issues:
        print("  - 无")

    print(f"\n[二] 超过 {max_clause_len} 字符的超长单句 ({len(long_clauses)} 处)")
    for loc_id, c_len, c_text in long_clauses:
        print(f"  - 位置 {loc_id} (长度 {c_len}): 「{c_text}」")
    if not long_clauses:
        print("  - 无")

    print(f"\n[三] 同段高频重复词 (单段 >= {repeat_threshold} 次, 共 {len(repeat_issues)} 处)")
    for loc_id, rep_info, p_text in repeat_issues:
        preview = p_text if len(p_text) <= 80 else p_text[:77] + '...'
        print(f"  - 位置 {loc_id} [{rep_info}]: {preview}")
    if not repeat_issues:
        print("  - 无")

    print(f"\n[四] 高危词汇与典型病灶句式嫌疑 ({len(pattern_issues)} 处)")
    for loc_id, cat, detail, p_text in pattern_issues:
        preview = p_text if len(p_text) <= 85 else p_text[:82] + '...'
        print(f"  - 位置 {loc_id} [{cat}] {detail}\n    上下文: {preview}")
    if not pattern_issues:
        print("  - 无")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="中文实验报告语言静态扫描与提取脚本")
    parser.add_argument("path", help="待扫描文稿路径 (.docx / .md / .txt)")
    parser.add_argument("--extract", dest="extract_out", default=None,
                        help="可选：将文稿提取为带位置编号的纯文本视图文件")
    args = parser.parse_args()
    analyze_document(args.path, extract_out=args.extract_out)
