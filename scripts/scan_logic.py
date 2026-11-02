#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序三专职扫描器：段落逻辑与归因扫描 (scan_logic.py)
配合角色：【段落逻辑审核者】（负责第 10、12 类错误，专职“理逻辑、补机理”）

输出线索：
1. 第 10 类：空洞归因句式嫌疑（贴标签式归因、名词罗列兜底式归因、笼统黑盒动词归因、代词指代归因，
   以及“长现象铺垫 + 极短段末归因”的段落结构失衡检测）；
2. 第 12 类：多句自然段缺乏显式逻辑连接词或时序状语嫌疑（辅助定位句间逻辑断层）。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

# 通用空洞归因句式模式（不绑定特定实验名词，匹配句末/段末笼统归因结构）
HOLLOW_ATTRIBUTION_PATTERNS = [
    (
        '第 10 类：贴标签式空洞归因（仅称某事物是“可能/主要因素”而未展开）',
        r'(?:是|作为)(?:影响|决定|导致|制约|引起)[^，。；]{2,18}的(?:可能|主要|重要|关键|潜在)?(?:因素|原因)(?:之一)?(?=[。；.]|$)'
    ),
    (
        '第 10 类：罗列名词兜底式归因（仅称“受 A、B 等因素影响/有关”而未解释机理）',
        r'(?:受|受到|与|同|归因于|源于)[^，。；]{2,32}等(?:多种|诸多|多方面)?'
        r'(?:因素|条件|开销|机制|参数|效应|损耗|噪声|干扰|失真|特性|阶数)(?:的)?(?:影响|有关|相关|制约|作用)(?=[。；.]|$)'
    ),
    (
        '第 10 类：黑盒动词笼统归因（仅称“改变了某方式/提升了某效率”而未说明具体变化）',
        r'(?:改变|优化|改善|提高|提升|降低|减少|抑制|展宽|充分发挥|充分利用)了[^，。；]{2,20}'
        r'(?:组织|访问|访存|调度|分配|存储|通信|同步|计算|执行|传输|映射|调制|解调|滤波|选频|谐振|匹配|旁瓣|通带|阻带|过渡带|转发|拥塞控制)?'
        r'(?:方式|模式|结构|策略|效率|局部性|利用率|并行度|吞吐率|开销|能力|特性|性能|质量|分辨率|平坦度|衰减|宽度|系数)(?=[。；.]|$)'
    ),
    (
        '第 10 类：代词指代笼统归因（“这些因素/处理可能影响结果”）',
        r'(?:这些|上述|以上|该)(?:因素|处理|操作|开销|差异|现象|机制|参数|误差|噪声|干扰|谐波|分量)'
        r'(?:可能|共同|均会|都会|在一定程度上)?(?:影响|决定|改变|导致|引起)(?:了)?[^，。；]{0,12}'
        r'(?:结果|性能|耗时|速度|效率|表现|差异|偏差|误差|失真|衰减|波动|频偏|丢包|时延)(?=[。；.]|$)'
    ),
]

# 句首逻辑连接词与时序状语正则（用于检查后续句子开头是否具备句间衔接）
SENTENCE_HEAD_TRANSITION = re.compile(
    r'^(?:因此|因而|从而|进而|故|由此|可见|这表明|说明|表明|这意味着|'
    r'这一[^，。；：]{1,10}(?:与|可能与|源于|来自)|可能的因素是|原因在于|究其原因|'
    r'具体而言|具体来说|例如|比如|由于|因为|鉴于|随着|'
    r'相比之下|相反|然而|但|但是|不过|同时|此外|另外|进一步|'
    r'随后|此时|接着|在此基础上|在[^，。；]{1,12}(?:前|后|中|时|下|基础上)|当[^，。；]{1,12}时)'
)

CAUSAL_TAIL_KEYWORDS = ('因素', '原因', '有关', '影响', '得益于', '归因于', '所致', '误差', '偏差', '失真', '偏移', '衰减', '泄露')


def split_sentences(text):
    """按中文句号或非数字/非标识符英文句点切分自然段内的句子。"""
    return [s.strip() for s in re.split(r'(?:。|(?<!\d)\.(?!\d|[A-Za-z]))+', text) if s.strip()]


def scan_logic(items):
    hollow_hits = []
    disconnected_paras = []

    for loc_id, text, kind in iter_clean_items(items):
        if is_heading_item(text, kind) or kind == 'tbl':
            continue

        # 1. 正则匹配四类通用空洞归因结构
        matched_in_para = False
        for cat_name, pat in HOLLOW_ATTRIBUTION_PATTERNS:
            m = re.search(pat, text)
            if m:
                hollow_hits.append((loc_id, cat_name, m.group(0), text))
                matched_in_para = True

        sentences = split_sentences(text)

        # 2. 结构化失衡检测：“前文长篇数据现象铺垫 + 段末单句简短归因”
        if not matched_in_para and len(sentences) >= 3:
            prefix_text = '。'.join(sentences[:-1])
            last_sent = sentences[-1]
            prefix_nums = re.findall(r'\b\d+(?:\.\d+)?\b', prefix_text)
            if (
                len(prefix_text) >= 55
                and len(prefix_nums) >= 3
                and len(last_sent) <= 38
                and any(k in last_sent for k in CAUSAL_TAIL_KEYWORDS)
            ):
                hollow_hits.append((
                    loc_id,
                    '第 10 类：结构失衡嫌疑（前文长篇罗列数据现象，段末仅一句简短归因）',
                    last_sent,
                    text
                ))

        # 3. 第 12 类：含 3 句以上但后续句子均缺乏句首逻辑/时序过渡词的自然段
        if len(sentences) >= 3 and len(text) >= 55:
            has_head_transition = any(
                bool(SENTENCE_HEAD_TRANSITION.search(s)) for s in sentences[1:]
            )
            if not has_head_transition:
                disconnected_paras.append((loc_id, len(sentences), text))

    return {
        'hollow_hits': hollow_hits,
        'disconnected_paras': disconnected_paras,
    }


def print_logic_report(res, src_name):
    print(f"=== [工序三：段落逻辑审核] 静态扫描线索: {src_name} ===")
    print("说明：本报告仅供【段落逻辑审核者】参考，聚焦第 10 类（空洞归因）与第 12 类（句间逻辑断层）。\n")

    print(f"[1. 第 10 类：空洞归因与重现象轻分析嫌疑] ({len(res['hollow_hits'])} 处)")
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
