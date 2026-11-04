import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文实验报告语言静态扫描总控入口 (check_prose.py)

职责：
作为顶层调度者（Orchestrator）的统一命令行入口，支持按当前激活的“审核者分身”定向输出专项扫描报告，
同时支持将 .docx 文稿导出为带位置编号的纯文本镜像。

用法示例：
1. 导出纯文本镜像并生成【工序一：宏观结构审核者】专属线索：
   python scripts/check_prose.py report.docx --extract .polish_workspace/draft_view.md --stage structure
2. 生成【工序二：信息冗余审核者】专属线索：
   python scripts/check_prose.py report.docx --stage redundancy
3. 生成【工序三：段落逻辑审核者】专属线索：
   python scripts/check_prose.py report.docx --stage logic
4. 生成【工序四：句法词法审核者】专属线索：
   python scripts/check_prose.py report.docx --stage syntax
5. 一次性输出全量四道工序扫描报告（默认）：
   python scripts/check_prose.py report.docx --stage all
"""

import os
import argparse
from doc_parser import load_document_items, write_extracted_view
from scan_structure import scan_structure, print_structure_report
from scan_redundancy import scan_redundancy, print_redundancy_report
from scan_logic import scan_logic, print_logic_report
from scan_syntax import scan_syntax, print_syntax_report


def main():
    parser = argparse.ArgumentParser(description="中文实验报告专职分身静态扫描与提取总控脚本")
    parser.add_argument("path", help="待扫描文稿路径 (.docx / .md / .txt)")
    parser.add_argument(
        "--stage",
        choices=['structure', 'redundancy', 'logic', 'syntax', 'all'],
        default='all',
        help="指定当前激活的审核者分身工序（默认 all 输出全部四道工序报告）"
    )
    parser.add_argument(
        "--extract",
        dest="extract_out",
        default=None,
        help="可选：将文稿提取为带位置编号的纯文本镜像文件（供审核子线程读取）"
    )
    args = parser.parse_args()

    items = load_document_items(args.path)
    src_name = os.path.basename(args.path)

    if args.extract_out:
        write_extracted_view(items, args.extract_out, src_name)

    stages = ['structure', 'redundancy', 'logic', 'syntax'] if args.stage == 'all' else [args.stage]

    for idx, st in enumerate(stages):
        if idx > 0:
            print("\n" + "=" * 60 + "\n")
        if st == 'structure':
            print_structure_report(scan_structure(items), src_name)
        elif st == 'redundancy':
            print_redundancy_report(scan_redundancy(items), src_name)
        elif st == 'logic':
            print_logic_report(scan_logic(items), src_name)
        elif st == 'syntax':
            print_syntax_report(scan_syntax(items), src_name)


if __name__ == '__main__':
    main()
