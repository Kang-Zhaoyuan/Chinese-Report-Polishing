#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工序一专职扫描器：宏观结构扫描 (scan_structure.py)
配合角色：【宏观结构审核者】（负责第 1、2、3 类错误）

输出线索：
1. 全文章节标题大纲树（供审核者对照任务要求核查章节划分与序号连续性）；
2. 第 3 类：双中心并列标题嫌疑（含“与”、“及”、“和”、“以及”的标题）；
3. 第 1 类：冗余的非核心过程描述嫌疑（硬件环境、编译器版本、脚本控制参数、日志落盘、独立正确性测试或总结展望小节）。
"""

import re
import sys
import os
from doc_parser import load_document_items, iter_clean_items, is_heading_item

NON_CORE_PATTERNS = [
    (
        '硬件平台、DSP芯片/实验箱与电子通信测量仪器型号（若任务未要求应整段删除）',
        r'Intel\s+Core|AMD\s+Ryzen|NVIDIA|GeForce|RTX\s*\d+|GTX\s*\d+|Tesla|A100|V100|H100|'
        r'Compute\s+Capability|Ubuntu|CentOS|Debian|WSL|Linux\s*内核|主频为?\s*\d|内存(?:容量|大小)?为?\s*\d+\s*GB|'
        r'TMS320\w*|C6748|F28335|ADSP-\w*|XDS\d{3}|(?:高频电子线路|通信电子电路|通信原理|数字信号处理|DSP)\s*实验箱|'
        r'Tektronix|泰克|Keysight|是德科技|Agilent|安捷伦|Rigol|普源|Siglent|鼎阳|Fluke|福禄克|'
        r'(?:示波器|频谱分析仪|矢量网络分析仪|扫频仪|频率特性测试仪|高频信号源|信号发生器|函数发生器|超高频毫伏表|毫伏表|Q表|稳压电源|万用表|逻辑分析仪)(?:型号|编号)'
    ),
    (
        '编译器、DSP/EDA、高频电路仿真与网络工具版本（若任务未要求应整段删除）',
        r'GCC\s*\d|Clang\s*\d|MSVC|CUDA\s+Toolkit|nvcc|Python\s*3\.\d+|PyTorch\s*\d|TensorFlow\s*\d|CMake\s*\d|'
        r'Code\s+Composer\s+Studio|CCS\s*v?\d+|FDATool|Filter\s+Designer|SPTool|CMSIS-DSP|'
        r'MATLAB(?:\s*R?\d{4}[ab]?)?|Simulink|SciPy|NumPy|Octave|Origin\s*\d*|'
        r'Multisim\s*\d*|LTspice|PSpice|Proteus\s*\d*|ADS\s*\d+|HFSS|Cadence|OrCAD|Altium\s+Designer|'
        r'Quartus(?:\s*II|\s*Prime)?|Vivado\s*\d*|ModelSim|Keil\s*(?:uVision|C51|MDK)?|LabVIEW|GNU\s+Radio|'
        r'Wireshark\s*\d*|Packet\s+Tracer|eNSP|GNS3|Mininet|NS-?[23]|OMNeT\+\+|iperf3?|VMware|VirtualBox'
    ),
    (
        '脚本/仿真控制参数、抓包/日志保存与常规一致性自证（若任务未要求应删除）',
        r'随机(?:数)?种子|seed\s*[=为]|rng\(\d+\)|温度(?:参数)?设为|temperature\s*[=为]|'
        r'(?:保存|写入|导出|重定向|上传|记录)到?[^，。；]{0,12}(?:日志|文件|目录|脚本|\.pcap(?:ng)?|\.mat|\.csv)|'
        r'生成文本(?:保持)?一致|均显示(?:文本|结果|输出|波形)一致|通过了?(?:全部|所有)?(?:单元|连通性)?测试'
    ),
    (
        '非核心独立小节标题嫌疑（建议删除或并入测试结果节）',
        r'^(?:[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+(?:\.\d+)?\s*|#{1,4}\s*)'
        r'(?:实验环境|运行环境|软硬件环境|仿真环境|仪器与设备|实验仪器|测试环境|环境配置|'
        r'正确性(?:测试|验证|检查)|连通性测试|实验总结|总结|总结与展望|结论与展望|心得体会|实验体会)$'
    ),
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
            m = re.search(pat, text, re.IGNORECASE)
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
