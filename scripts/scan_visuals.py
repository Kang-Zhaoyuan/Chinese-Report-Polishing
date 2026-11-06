#!/usr/bin/env python3
"""图文审核材料清单：相邻正文、完整数据表和实际图片；不自动判定语义重复。"""

import os
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
from doc_parser import is_code_box_table, load_document_items, iter_body_elements
from scan_redundancy import scan_redundancy


def _text(element):
    return ''.join(element.itertext()).strip()


def scan_visuals(path, assets_dir=None, skip_first_page=False):
    blocks = []
    pending = []
    if Path(path).suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
            rels = {}
            if 'word/_rels/document.xml.rels' in archive.namelist():
                rels = {r.get('Id'): r for r in ET.fromstring(
                    archive.read('word/_rels/document.xml.rels'))}
            for index, element in iter_body_elements(root.find(f'{W}body'), skip_first_page):
                location = f'body[{index}]'
                if element.tag == W + 'tbl':
                    if is_code_box_table(element):
                        continue
                    rows = [' | '.join(_text(c) for c in row.findall(f'{W}tc'))
                            for row in element.findall(f'{W}tr')]
                    blocks.append({'location': location, 'kind': 'table',
                                   'text': '\n'.join(rows), 'images': []})
                    continue
                if element.tag != W + 'p':
                    continue
                images = []
                for node in element.iter():
                    if node.tag.split('}')[-1] not in ('blip', 'imagedata'):
                        continue
                    rel_id = node.get(R + 'embed') or node.get(R + 'id') or node.get(R + 'link')
                    relation = rels.get(rel_id)
                    if relation is None:
                        pending.append(f'{location}: 图片关系 {rel_id} 缺失')
                        continue
                    target = relation.get('Target', '')
                    if relation.get('TargetMode') == 'External':
                        images.append(target)
                        pending.append(f'{location}: 需实际读取外部图片 {target}')
                        continue
                    member = (target.lstrip('/') if target.startswith('/') else
                              posixpath.normpath(posixpath.join('word', target)))
                    if member not in archive.namelist():
                        pending.append(f'{location}: 图片部件 {member} 缺失')
                        continue
                    if assets_dir:
                        extension = Path(member).suffix.lower()
                        output = Path(assets_dir) / (f'image_{len(blocks)}_{len(images)}' + extension)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_bytes(archive.read(member))
                        images.append(str(output.resolve()))
                    else:
                        images.append(f'{os.path.abspath(path)}::{member}')
                        pending.append(f'{location}: 使用 --visual-assets 导出图片后再查看')
                blocks.append({'location': location, 'kind': 'image' if images else 'p',
                               'text': _text(element), 'images': images})
    else:
        in_code = False
        for index, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code or not line.strip():
                continue
            images = []
            for match in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', line):
                target = match[1].strip('<>')
                if re.match(r'https?://', target):
                    images.append(target)
                    pending.append(f'L{index}: 需实际读取外部图片 {target}')
                else:
                    image = (Path(path).parent / target).resolve()
                    images.append(str(image))
                    if not image.is_file():
                        pending.append(f'L{index}: 图片不存在 {image}')
            if re.search(r'<!--\s*(?:FIGURE|IMAGE)', line, re.I):
                pending.append(f'L{index}: 图片仍为占位符')
            kind = 'image' if images else 'table' if line.lstrip().startswith('|') else 'p'
            if kind == 'table' and blocks and blocks[-1]['kind'] == 'table':
                blocks[-1]['text'] += '\n' + line.strip()
            else:
                blocks.append({'location': f'L{index}', 'kind': kind,
                               'text': line.strip(), 'images': images})
    groups = []
    for index, block in enumerate(blocks):
        if block['kind'] not in ('table', 'image'):
            continue
        before = [b for b in blocks[:index] if b['kind'] == 'p' and b['text']][-2:]
        after = [b for b in blocks[index + 1:] if b['kind'] == 'p' and b['text']][:2]
        groups.append({**block, 'before': before, 'after': after})
    cues = scan_redundancy(load_document_items(path, skip_first_page), include_visuals=True)
    return {'groups': groups, 'pending': pending,
            'pattern_hits': [hit for hit in cues['pattern_hits']
                             if hit[1].startswith(('第 7 类', '第 8 类'))],
            'numeric_recap_suspects': cues['numeric_recap_suspects']}


def print_visuals_report(result, src_name):
    print(f'=== [工序五：图文重复审核] 材料清单: {src_name} ===')
    print('审核者须查看实际图片，并比较相邻正文与表格。清单本身不代表审核通过。')
    for loc, category, hit, context in result['pattern_hits']:
        print(f'图文措辞线索 [{loc}] {category}: {hit}\n  {context}')
    for loc, values, context in result['numeric_recap_suspects']:
        print(f'密集数据复述线索 [{loc}]: {values}\n  {context}')
    if result['pending']:
        print('MATERIALS_PENDING:')
        for message in result['pending']:
            print('  - ' + message)
    for group in result['groups']:
        print(f"\n[{group['location']}] {group['kind']}")
        for before in group['before']:
            print(f"前文 [{before['location']}]: {before['text']}")
        print(group['text'])
        for image in group['images']:
            print('实际图片: ' + image)
        for after in group['after']:
            print(f"后文 [{after['location']}]: {after['text']}")
    if not result['groups'] and not result['pending']:
        print('NO_VISUALS: 无图表，可跳过本工序。')
