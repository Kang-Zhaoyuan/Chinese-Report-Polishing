#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文实验报告语言静态扫描脚本 (check_prose.py)

功能：
支持读取 .docx、.md 或 .txt 文稿，提取正文自然段，并输出四类客观语言线索供审核者线程参考：
1. 含有并列连词（与、及、和、以及）的标题；
2. 两个标点符号之间长度超过 20 个字符的超长单句；
3. 同一自然段内重复出现 3 次以上的高频词；
4. 疑似 AI 过拟合词汇、防御性局限声明、自我证实表述及图表引导冗余。

注意：本脚本输出仅作为定位参考，最终修改决策须由模型结合上下文语义作出。
"""

import sys
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

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
    ('冗余的图表引导与自评', r'为了直观(比较|展示)|根据表\s*[\d\-]+\s*的数据展示|从表\s*[\d\-]+\s*和图\s*[\d\-]+\s*可以看出|如[图|表]\s*[\d\-]+\s*所示'),
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


def extract_paragraphs_from_docx(path):
    """从 .docx 文件提取非空正文段落（跳过 1x1 代码框表格，仅提取正文段落）。"""
    paragraphs = []
    with zipfile.ZipFile(path, 'r') as z:
        root = ET.fromstring(z.read('word/document.xml'))
        body = root.find(f'{W_NS}body')
        for idx, elem in enumerate(body):
            tag = elem.tag.split('}')[-1]
            if tag == 'p':
                text = ''.join(elem.itertext()).strip()
                if text:
                    paragraphs.append((idx + 1, text))
    return paragraphs


def extract_paragraphs_from_text(path):
    """从 .md 或 .txt 文件提取非空正文段落（跳过代码块）。"""
    paragraphs = []
    in_code_block = False
    with open(path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            if not in_code_block and stripped:
                paragraphs.append((idx, stripped))
    return paragraphs


def is_likely_code_paragraph(text):
    """判断段落是否为裸排的代码段，避免对代码行报错。"""
    code_indicators = [';', '{', '}', '#include', '#pragma', '__shared__', '__m256']
    hits = sum(1 for ind in code_indicators if ind in text)
    return hits >= 2


def measure_clause_length(clause):
    """
    计算分句的阅读长度：
    将连续的英文单词、函数名或数字序列计为 1 个阅读单元，中文字符每个计为 1 个单元。
    """
    collapsed = re.sub(r'[A-Za-z0-9_.\-+/*=<>()\[\]]+', 'X', clause)
    collapsed = re.sub(r'\s+', '', collapsed)
    return len(collapsed)


def analyze_document(path, max_clause_len=20, repeat_threshold=3):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        paragraphs = extract_paragraphs_from_docx(path)
    else:
        paragraphs = extract_paragraphs_from_text(path)

    heading_issues = []
    long_clauses = []
    repeat_issues = []
    pattern_issues = []

    split_punct = re.compile(r'[，。；：？！、,.;:?!（）()|]+')

    for p_num, text in paragraphs:
        if is_likely_code_paragraph(text):
            continue

        # 1. 检查标题并列连词
        if HEADING_PATTERN.match(text) and len(text) <= 35:
            conj_match = re.findall(r'(与|及|和|以及)', text)
            if conj_match:
                heading_issues.append((p_num, text, conj_match))
            continue

        # 2. 检查超长单句
        clauses = [c.strip() for c in split_punct.split(text) if c.strip()]
        for c in clauses:
            c_len = measure_clause_length(c)
            if c_len > max_clause_len:
                long_clauses.append((p_num, c_len, c))

        # 3. 检查同段高频重复词
        # 仅对长度超过 30 字的正文自然段进行统计
        if len(text) >= 30:
            found_repeats = []
            for w in TRACKED_REPEAT_WORDS:
                if w == '在':
                    # 统计作为介词短语开头的“在”
                    count = len(re.findall(r'(?:^|[，。；\s])在', text))
                else:
                    count = text.count(w)
                if count >= repeat_threshold:
                    found_repeats.append(f"“{w}”({count}次)")
            if found_repeats:
                repeat_issues.append((p_num, ', '.join(found_repeats), text))

        # 4. 检查高危词汇与疑似句式
        hit_words = [w for w in AI_OVERFIT_WORDS if w in text]
        if hit_words:
            pattern_issues.append((p_num, 'AI 过拟合与翻译腔词汇', f"命中词汇: {hit_words}", text))

        for pat_name, regex in SUSPECT_PATTERNS:
            m = re.search(regex, text)
            if m:
                pattern_issues.append((p_num, pat_name, f"命中片段: “{m.group(0)}”", text))

    # 输出扫描报告
    print(f"=== 语言静态扫描报告: {os.path.basename(path)} ===")
    print("说明：以下结果由脚本规则生成，仅作为定位线索，请审核者结合上下文语义判断。\n")

    print(f"[一] 双中心并列标题嫌疑 ({len(heading_issues)} 处)")
    for p_num, h_text, conjs in heading_issues:
        print(f"  - 段落 P{p_num}: 「{h_text}」 (含并列连词: {conjs})")
    if not heading_issues:
        print("  - 无")

    print(f"\n[二] 超过 {max_clause_len} 字符的超长单句 ({len(long_clauses)} 处)")
    for p_num, c_len, c_text in long_clauses:
        print(f"  - 段落 P{p_num} (长度 {c_len}): 「{c_text}」")
    if not long_clauses:
        print("  - 无")

    print(f"\n[三] 同段高频重复词 (单段 >= {repeat_threshold} 次, 共 {len(repeat_issues)} 处)")
    for p_num, rep_info, p_text in repeat_issues:
        preview = p_text if len(p_text) <= 80 else p_text[:77] + '...'
        print(f"  - 段落 P{p_num} [{rep_info}]: {preview}")
    if not repeat_issues:
        print("  - 无")

    print(f"\n[四] 高危词汇与典型病灶句式嫌疑 ({len(pattern_issues)} 处)")
    for p_num, cat, detail, p_text in pattern_issues:
        preview = p_text if len(p_text) <= 85 else p_text[:82] + '...'
        print(f"  - 段落 P{p_num} [{cat}] {detail}\n    上下文: {preview}")
    if not pattern_issues:
        print("  - 无")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python check_prose.py <文稿路径.docx/.md/.txt>")
        sys.exit(1)
    analyze_document(sys.argv[1])
