#!/usr/bin/env python3
"""简明技术中文检查器，仅使用 Python 标准库。

用法：python3 stc_check.py [--mode procedural|descriptive|mixed] 文件...
不指定文件时读取标准输入。退出码：0 无结构错误，1 有结构错误，2 输入错误。
本工具只提供启发式检查，不验证事实、安全性或标准合规性。
"""

import argparse
import re
import sys
from pathlib import Path


LIMITS = {"procedural": 40, "descriptive": 50, "mixed": 50}
DEFAULT_WORD_LIST = Path(__file__).resolve().parent.parent / "references" / "word-list.md"
PLACEHOLDER = "\ufffc"
UNITS = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af〇]"
    r"|[A-Za-z0-9]+(?:[._/'’-][A-Za-z0-9]+)*|\ufffc"
)
SENTENCE_END = re.compile(r"[。！？!?]+|\.(?=\s|$)")
LIST_ITEM = re.compile(r"^( *(?:[-*+]|\d+[.)])\s+)(?:\[[ xX]\]\s+)?")
VAGUE = {
    "适当": "确认是否需要给出具体条件或数值",
    "酌情": "确认是否需要给出判断条件和责任人",
    "尽快": "确认是否需要给出明确时限",
    "若干": "确认是否需要给出数量",
    "相关人员": "确认是否需要写明角色",
}


def mask(match):
    """隐藏受保护内容，保留行号和一个计数单位。"""
    value = match.group(0)
    return PLACEHOLDER + re.sub(r"[^\n]", " ", value[1:])


def strip_inline(text):
    """保护常见 Markdown 行内代码、URL 和引号中的原文。"""
    text = re.sub(r"(?<!`)(`+)(?!`)([^\n]*?)(?<!`)\1(?!`)", mask, text)
    text = re.sub(
        r"\[([^\]\n]*)\]\([^\n)]*\)",
        lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))),
        text,
    )
    text = re.sub(
        r"https?://[^\s<>\"'`，。！？；：、（）【】“”‘’]+",
        lambda m: PLACEHOLDER + " " * (len(m.group(0).rstrip(".,!?;:")) - 1)
        + m.group(0)[len(m.group(0).rstrip(".,!?;:")):],
        text,
    )
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|「[^」\n]*」', mask, text)
    # 仅去除成对的强调标记，不拆开标识符中的下划线。
    text = re.sub(r"(\*\*|__|\*|_)(\S(?:.*?\S)?)\1", r"\2", text)
    return text


def count_units(sentence):
    """每个汉字计一单位，英文单词、数字串和受保护内容各计一单位。"""
    return len(UNITS.findall(sentence))


def iter_blocks(text):
    """返回（起始行号，正文块）。保留软换行，将列表项分别处理。"""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(
        r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|$)",
        lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL,
    )
    block = []
    start = 1
    list_indent = None
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + r"{%d,}[ \t]*" % fence[1], line):
                fence = None
            continue

        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        item = LIST_ITEM.match(line)
        indent = len(line) - len(line.lstrip(" "))
        continuation = list_indent is not None and indent >= list_indent
        excluded = (
            not stripped or opening
            or re.match(r"^ {0,3}(?:#{1,6}(?:\s|$)|>|\|)", line)
            or re.fullmatch(r" {0,3}(?:[-*_]\s*){3,}", line)
            or (not continuation and (line.startswith("    ") or line.startswith("\t")))
        )
        if excluded or item or (list_indent is not None and not continuation):
            if block:
                yield start, "\n".join(block)
            block = []
            list_indent = None
        if opening:
            fence = (opening.group(1)[0], len(opening.group(1)))
        if excluded:
            continue
        if not block:
            start = number
        if item:
            list_indent = item.end(1)
            line = line[item.end():]
        block.append(line)
    if block:
        yield start, "\n".join(block)


def iter_sentences(block):
    """返回句子的偏移量和内容，支持中文句末没有空格的情况。"""
    start = 0
    for end in [m.end() for m in SENTENCE_END.finditer(block)] + [len(block)]:
        part = block[start:end]
        offset = start + len(part) - len(part.lstrip())
        if UNITS.search(part):
            yield offset, part.strip()
        start = end


def load_word_list(path):
    """从中文三列表格读取：待检查表达 ->（首选表达，说明）。"""
    entries = {}
    in_table = False
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip().startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells == ["首选表达", "待检查表达", "说明"]:
            in_table = True
            continue
        if not in_table or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != 3 or not all(cells):
            raise ValueError(f"词表行格式无效：{line}")
        preferred, alternatives, note = cells
        for alternative in alternatives.split("、"):
            alternative = alternative.strip()
            if not alternative:
                raise ValueError(f"词表包含空的待检查表达：{line}")
            entries[alternative] = (preferred, note)
    if not entries:
        raise ValueError("词表须包含“首选表达 / 待检查表达 / 说明”三列和至少一条记录")
    return entries


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.sentences = 0

    def error(self, loc, rule, message):
        self.errors.append((loc, rule, message))

    def warn(self, loc, rule, message):
        self.warnings.append((loc, rule, message))


def check_sentence(sentence, mode, report, loc, vocabulary):
    size = count_units(sentence)
    head = " ".join(sentence.replace(PLACEHOLDER, "〔原文〕").split())
    if len(head) > 60:
        head = head[:57] + "…"
    limit = LIMITS[mode]
    if size > limit:
        report.error(loc, "STC-3.1", f"句长为 {size} 个计数单位，上限为 {limit}：{head}")
    elif mode == "mixed" and size > LIMITS["procedural"]:
        report.warn(loc, "STC-3.1", f"句长为 {size} 个计数单位。如果是操作步骤，上限为 40：{head}")
    if ";" in sentence or "；" in sentence:
        report.error(loc, "STC-6.1", f"发现分号，请拆成独立句子或列表：{head}")
    for word, advice in VAGUE.items():
        if word in sentence:
            report.warn(loc, "STC-1.4", f"复核“{word}”：{advice}，不要编造缺失信息。")
    for word, (preferred, note) in (vocabulary or {}).items():
        if word in sentence:
            report.warn(loc, "STC-1.2", f"复核“{word}”：可考虑“{preferred}”。{note}。")


def check_text(text, mode, report, name, vocabulary=None):
    for line, block in iter_blocks(text):
        block = strip_inline(block)
        sentences = list(iter_sentences(block))
        report.sentences += len(sentences)
        if len(sentences) > 6:
            report.error(f"{name}:{line}", "STC-4.1", f"段落有 {len(sentences)} 句，上限为 6。")
        for offset, sentence in sentences:
            loc = f"{name}:{line + block[:offset].count(chr(10))}"
            check_sentence(sentence, mode, report, loc, vocabulary)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="检查简明技术中文的句长、段落、标点和常见用词。",
        usage="%(prog)s [选项] [文件 ...]", add_help=False,
        epilog="退出码：0 无结构错误（仍可能有提示），1 有结构错误，2 输入错误。",
    )
    parser._positionals.title = "输入"
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助并退出")
    parser.add_argument("files", nargs="*", metavar="文件", help="UTF-8 文件，默认读取标准输入")
    parser.add_argument("--mode", choices=list(LIMITS), default="mixed",
                        help="procedural 操作型，descriptive 说明型，mixed 混合型（默认）")
    parser.add_argument("--word-list", type=Path, default=DEFAULT_WORD_LIST, metavar="词表",
                        help="中文词表路径，默认使用技能自带词表")
    parser.add_argument("--no-vocab", action="store_true", help="关闭词表提示，保留其他检查")
    args = parser.parse_args(argv)

    report = Report()
    try:
        vocabulary = None if args.no_vocab else load_word_list(args.word_list)
        if args.files:
            for filename in args.files:
                text = Path(filename).read_text(encoding="utf-8-sig")
                check_text(text, args.mode, report, filename, vocabulary)
        else:
            check_text(sys.stdin.read(), args.mode, report, "标准输入", vocabulary)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2

    for loc, rule, message in report.errors:
        print(f"错误  {loc} [{rule}] {message}")
    for loc, rule, message in report.warnings:
        print(f"提示  {loc} [{rule}] {message}")
    print(f"\n结果：检查 {report.sentences} 句，{len(report.errors)} 个错误，{len(report.warnings)} 个提示。")
    if not report.sentences:
        print("未发现可检查的正文。空文件或全部被跳过的内容不代表检查通过。")
    elif not report.errors:
        print("未发现可自动检测的结构错误。请继续复核用词提示、原意和安全要求。")
    print("本工具不验证繁简用字、事实或标准合规性。")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
