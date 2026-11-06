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
5. 一次性输出全量五道工序扫描报告（默认）：
   python scripts/check_prose.py report.docx --stage all
"""

import os
import argparse
from doc_parser import load_document_items, write_extracted_view
from scan_structure import scan_structure, print_structure_report
from scan_redundancy import scan_redundancy, print_redundancy_report
from scan_logic import scan_logic, print_logic_report
from scan_syntax import scan_syntax, print_syntax_report
from scan_visuals import scan_visuals, print_visuals_report
from prose_metrics import comma_only_changes
from doc_parser import iter_clean_items, is_heading_item


def main():
    parser = argparse.ArgumentParser(description="中文实验报告专职分身静态扫描与提取总控脚本")
    parser.add_argument("path", help="待扫描文稿路径 (.docx / .md / .txt)")
    parser.add_argument(
        "--stage",
        choices=['structure', 'redundancy', 'logic', 'syntax', 'visuals', 'all'],
        default='all',
        help="指定当前激活的审核者分身工序（默认 all 输出全部五道工序报告）"
    )
    parser.add_argument('--max-clause-len', type=int, default=15,
                        help='分句长度硬上限（阅读单位，默认15）')
    parser.add_argument('--visual-assets', help='将docx实际图片导出到指定目录供图文审核')
    parser.add_argument('--include-cover', action='store_true', help='检查docx全文；默认从第二页开始')
    parser.add_argument('--check', action='store_true',
                        help='syntax/all 分句超限时返回退出码1，供改写后复检')
    parser.add_argument('--length-exempt', action='append', default=[], metavar='位置:原分句',
                        help='审核者确认的个别句长例外，使用 位置:原分句 精确匹配，可重复指定')
    parser.add_argument('--compare-to', help='与改写前文稿比较，复查仅新增逗号的超限段落')
    parser.add_argument(
        "--extract",
        dest="extract_out",
        default=None,
        help="可选：将文稿提取为带位置编号的纯文本镜像文件（供审核子线程读取）"
    )
    args = parser.parse_args()
    if args.max_clause_len < 1:
        parser.error('--max-clause-len 必须为正整数')
    if (args.check or args.compare_to or args.length_exempt) and args.stage not in ('syntax', 'all'):
        parser.error('--check、--compare-to 和 --length-exempt 适用于 syntax/all 工序')

    def load_items(path):
        try:
            return load_document_items(path, skip_first_page=not args.include_cover)
        except ValueError as error:
            parser.error(str(error))

    items = load_items(args.path)
    src_name = os.path.basename(args.path)

    if args.extract_out:
        write_extracted_view(items, args.extract_out, src_name)

    stages = ['structure', 'redundancy', 'logic', 'syntax', 'visuals'] if args.stage == 'all' else [args.stage]
    length_failed = False
    materials_pending = False

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
            result = scan_syntax(items, max_clause_len=args.max_clause_len)
            print_syntax_report(result, src_name)
            exempt = set(args.length_exempt)
            length_failed = any(f'{loc}:{text}' not in exempt for loc, _, text in result['long_clauses'])
            for loc, length, text in result['long_clauses']:
                if f'{loc}:{text}' in exempt:
                    print(f'  审核者已确认个别例外 [{loc}] ({length}): {text}')
            if args.compare_to:
                def prose_rows(rows):
                    return [(loc, text) for loc, text, kind in iter_clean_items(rows)
                            if kind == 'p' and not is_heading_item(text, kind)]
                changes = comma_only_changes(prose_rows(load_items(args.compare_to)),
                                             prose_rows(items), args.max_clause_len)
                print(f'\n[改写复检：原超限段落仅改变逗号/空白] ({len(changes)} 处，须继续改写)')
                for change in changes:
                    print(f"  - {change['location']}: {change['after']}")
                length_failed = length_failed or bool(changes)
        elif st == 'visuals':
            result = scan_visuals(args.path, args.visual_assets, skip_first_page=not args.include_cover)
            print_visuals_report(result, src_name)
            materials_pending = bool(result['pending'])
    if materials_pending:
        raise SystemExit(3)
    if args.check and length_failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
