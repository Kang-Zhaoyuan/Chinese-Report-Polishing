#!/usr/bin/env python3
"""可复用的中文阅读单位、句子切分与超限复检。"""

import re

# 先保护标识符，使文件名中的点、调用参数中的逗号不成为断句位置。
ATOM = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*(?:(?:\.|->|::|[/\\])[A-Za-z_][A-Za-z0-9_]*)*[/\\]?'
    r'(?:\[[^\]\u4e00-\u9fff\r\n]*\])*'
    r'(?:\([^()\u4e00-\u9fff\r\n]*\))?'
    r'|0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)*'
)
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff]')
END = re.compile(r'[。！？!?]+|\.(?![A-Za-z0-9_])')
CLAUSE_END = re.compile(r'[，。；：？！、,;:?!（）()|]+|\.(?![A-Za-z0-9_])')


def _protected(text):
    atoms = []

    def replace(match):
        atoms.append(match.group())
        return '\ue000' + str(len(atoms) - 1) + '\ue001'

    return ATOM.sub(replace, text), atoms


def _split(text, delimiter):
    protected, atoms = _protected(text)
    parts = delimiter.split(protected)
    return [re.sub(r'\ue000(\d+)\ue001', lambda m: atoms[int(m[1])], p).strip()
            for p in parts if p.strip()]


def split_sentences(text):
    """完整句仅按句末标点切分；段末未加句末标点的文本仍计一句。"""
    return _split(text, END)


def split_clauses(text):
    return _split(text, CLAUSE_END)


def reading_length(text):
    """汉字各计1；普通英文/数字各计1；代码、路径、空白标点不计。"""
    text = re.sub(r'`+[^`\n]+`+', '', text)
    rest, atoms = _protected(text)
    rest = re.sub(r'\ue000\d+\ue001', '', rest)
    code_markers = re.compile(r'[/\\_.\[\]()]|->|::')
    counted_atoms = sum(not code_markers.search(a) or a[0].isdigit() for a in atoms)
    return counted_atoms + sum(ch.isalnum() for ch in rest)



def comma_only_changes(before, after, limit=15):
    """定位原来超限、修改时仅增加逗号/空白的段落。句号拆句不会被误判。"""
    normalize = lambda s: re.sub(r'[，,\s]', '', s)
    originals = {normalize(text): (loc, text) for loc, text in before
                 if any(reading_length(c) > limit for c in split_clauses(text))}
    changes = []
    for loc, text in after:
        original = originals.get(normalize(text))
        if original and original[1] != text:
            changes.append({'location': loc, 'before_location': original[0],
                            'before': original[1], 'after': text})
    return changes
