"""中文检查器回归测试：python3 -m unittest discover -s tests -v。"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import stc_check as checker


ROOT = Path(__file__).resolve().parents[1]


class CheckerTests(unittest.TestCase):
    def check(self, text, mode="mixed", vocabulary=None):
        report = checker.Report()
        checker.check_text(text, mode, report, "文档.md", vocabulary)
        return report

    def test_count_chinese_and_mixed_text(self):
        # 独立计数：检查(2)、API(1)、v2(1)、的(1)、3(1)、个(1)、节点(2)。
        for text, expected in [
            ("检查 API v2 的 3 个节点。", 9),
            ("设为 3.14 V。", 4),
            ("读取 max_retry_count 和 retry-count。", 5),
            ("确认（包括备份）。", 6),
            ("〇𠀀阀门", 4),
        ]:
            with self.subTest(text=text):
                self.assertEqual(checker.count_units(checker.strip_inline(text)), expected)

    def test_sentence_length_boundaries(self):
        for mode, count, errors, warnings in [
            ("procedural", 40, 0, 0), ("procedural", 41, 1, 0),
            ("descriptive", 50, 0, 0), ("descriptive", 51, 1, 0),
            ("mixed", 40, 0, 0), ("mixed", 41, 0, 1),
            ("mixed", 50, 0, 1), ("mixed", 51, 1, 0),
        ]:
            with self.subTest(mode=mode, count=count):
                report = self.check("甲" * count + "。", mode)
                self.assertEqual(len(report.errors), errors)
                self.assertEqual(len(report.warnings), warnings)
                if errors or warnings:
                    finding = (report.errors + report.warnings)[0]
                    self.assertEqual(finding[1], "STC-3.1")
                    self.assertIn(f"{count} 个计数单位", finding[2])

    def test_chinese_punctuation_without_spaces(self):
        text = "检查阀门。是否关闭？停止操作！电压为 3.14 V. Read v2.1."
        self.assertEqual(
            [sentence for _, sentence in checker.iter_sentences(text)],
            ["检查阀门。", "是否关闭？", "停止操作！", "电压为 3.14 V.", "Read v2.1."],
        )

    def test_paragraph_boundary_and_soft_line_breaks(self):
        for separator in ("", "\n"):
            self.assertEqual(self.check(separator.join(["检查。"] * 6)).errors, [])
            report = self.check(separator.join(["检查。"] * 7))
            self.assertEqual(report.errors, [("文档.md:1", "STC-4.1", "段落有 7 句，上限为 6。")])
        self.assertEqual(self.check("\n\n".join(["检查。"] * 7)).errors, [])

    def test_semicolons_and_real_line_numbers(self):
        text = "# 标题\n检查阀门。\n关闭电源；拆下盖板。\n\n停止服务;保存日志。"
        report = self.check(text)
        self.assertEqual([(f[0], f[1]) for f in report.errors],
                         [("文档.md:3", "STC-6.1"), ("文档.md:5", "STC-6.1")])

    def test_markdown_exclusions_do_not_hide_following_prose(self):
        text = (
            "\ufeff---\r\n描述: 进行安装；尽快\r\n---\r\n"
            "# 进行安装；尽快\r\n"
            "```sh\r\n进行安装；尽快\r\n```\r\n"
            "~~~\r\n进行安装；尽快\r\n~~~\r\n"
            "> 进行安装；尽快\r\n"
            "| 进行安装；尽快 |\r\n"
            "    进行安装；尽快\r\n"
            "检查电源；停止操作。"
        )
        report = self.check(text, vocabulary=checker.load_word_list(checker.DEFAULT_WORD_LIST))
        self.assertEqual(report.sentences, 1)
        self.assertEqual(report.warnings, [])
        self.assertEqual([(f[0], f[1]) for f in report.errors], [("文档.md:14", "STC-6.1")])

    def test_fence_length_and_unclosed_fence(self):
        text = "````markdown\n```\n进行安装；尽快\n```\n````\n检查；停止。"
        self.assertEqual(len(self.check(text).errors), 1)
        self.assertEqual(self.check("```\n进行安装；尽快").sentences, 0)

    def test_inline_protection_and_link_labels(self):
        vocabulary = checker.load_word_list(checker.DEFAULT_WORD_LIST)
        protected = (
            "运行 `进行安装；尽快`。显示“进行安装；尽快”。"
            '显示 "进行安装;尽快"。运行 ``echo `进行安装；尽快` ``。'
            "访问 https://example.com/进行安装?q=尽快。"
        )
        report = self.check(protected, vocabulary=vocabulary)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual(report.sentences, 5)
        self.assertEqual(checker.count_units(checker.strip_inline("运行 `echo hello; exit`。")), 3)
        report = self.check("[进行安装](https://example.com/尽快)", vocabulary=vocabulary)
        self.assertEqual([f[1] for f in report.warnings], ["STC-1.2"])

    def test_url_does_not_swallow_chinese_punctuation_or_next_sentence(self):
        report = self.check("访问 https://example.com；停止操作。尽快重试。")
        self.assertEqual([f[1] for f in report.errors], ["STC-6.1"])
        self.assertEqual([f[1] for f in report.warnings], ["STC-1.4"])
        self.assertEqual(report.sentences, 2)

    def test_lists_are_separate_but_continuations_count(self):
        self.assertEqual(self.check("\n".join(["- 检查阀门。"] * 7)).errors, [])
        for marker in ("- ", "1. ", "12) ", "- [ ] "):
            with self.subTest(marker=marker):
                indent = " " * (2 if marker.startswith("-") else len(marker))
                text = marker + "甲" * 23 + "\n" + indent + "乙" * 18 + "。"
                report = self.check(text, "procedural")
                self.assertEqual(len(report.errors), 1)
                self.assertIn("41 个计数单位", report.errors[0][2])

    def test_no_english_grammar_or_closed_vocabulary_restrictions(self):
        vocabulary = checker.load_word_list(checker.DEFAULT_WORD_LIST)
        text = "建议备份。必须断电。故障可能导致停机。请求已被拒绝。用 Kubernetes 配置 routing。"
        report = self.check(text, vocabulary=vocabulary)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_vocabulary_is_advisory_and_has_expected_mapping(self):
        vocabulary = checker.load_word_list(checker.DEFAULT_WORD_LIST)
        self.assertEqual(vocabulary["进行安装"], ("安装", "不改变安装对象和前置条件"))
        report = self.check("尽快进行安装。", vocabulary=vocabulary)
        self.assertEqual(report.errors, [])
        self.assertEqual([f[1] for f in report.warnings], ["STC-1.4", "STC-1.2"])

    def test_rewritten_examples_as_prose_not_ignored_quotes(self):
        text = (ROOT / "examples/before-after.md").read_text(encoding="utf-8")
        examples = re.findall(r"(?:改写后|译文)：\n\n((?:>[^\n]*\n)+)", text)
        self.assertEqual(len(examples), 7)
        vocabulary = checker.load_word_list(checker.DEFAULT_WORD_LIST)
        for example in examples:
            with self.subTest(example=example):
                prose = re.sub(r"^> ?", "", example, flags=re.MULTILINE)
                report = self.check(prose, "procedural", vocabulary)
                self.assertGreater(report.sentences, 0)
                self.assertEqual(report.errors, [])
                self.assertEqual(report.warnings, [])


class CommandTests(unittest.TestCase):
    def run_checker(self, *args, text="", script="stc_check.py", cwd=ROOT):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
            input=text, capture_output=True, text=True, encoding="utf-8", cwd=cwd,
        )

    def test_stdin_exit_codes_and_chinese_output(self):
        for text, code, output in [
            ("备份配置文件。", 0, "检查 1 句，0 个错误，0 个提示"),
            ("备份文件；重启服务。", 1, "[STC-6.1]"),
            ("进行安装。", 0, "0 个错误，1 个提示"),
        ]:
            with self.subTest(text=text):
                result = self.run_checker(text=text)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(output, result.stdout)

    def test_no_vocab_keeps_other_checks(self):
        result = self.run_checker("--no-vocab", text="尽快进行安装；重启服务。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("[STC-6.1]", result.stdout)
        self.assertIn("[STC-1.4]", result.stdout)
        self.assertNotIn("[STC-1.2]", result.stdout)

    def test_multiple_files_and_default_vocabulary_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "正常.md", Path(tmp) / "错误.md"
            first.write_text("检查电源。", encoding="utf-8-sig")
            second.write_text("进行安装；重启服务。", encoding="utf-8")
            result = self.run_checker(first, second, cwd=tmp)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(f"{second}:1 [STC-6.1]", result.stdout)
            self.assertIn("[STC-1.2]", result.stdout)
            self.assertIn("检查 2 句", result.stdout)

    def test_custom_word_list_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            words = Path(tmp) / "词表.md"
            words.write_text(
                "| 首选表达 | 待检查表达 | 说明 |\n|---|---|---|\n"
                "| 客户端 | 客户机、client | 以项目命名为准 |\n", encoding="utf-8",
            )
            result = self.run_checker("--word-list", words, text="启动客户机。")
            self.assertEqual(result.returncode, 0)
            self.assertIn("可考虑“客户端”", result.stdout)
            words.write_text("不是词表", encoding="utf-8")
            result = self.run_checker("--word-list", words, text="检查电源。")
            self.assertEqual(result.returncode, 2)
            self.assertIn("输入错误", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            words.write_bytes(b"\xff\xfe")
            self.assertEqual(self.run_checker(words).returncode, 2)
            self.assertEqual(self.run_checker(Path(tmp) / "不存在.md").returncode, 2)

    def test_legacy_entry_point(self):
        text = "进行安装；重启服务。"
        current = self.run_checker(text=text)
        legacy = self.run_checker(text=text, script="ste_check.py")
        self.assertEqual(legacy.returncode, current.returncode)
        self.assertEqual(legacy.stdout, current.stdout)

    def test_no_prose_does_not_claim_success(self):
        result = self.run_checker(text="```\n甲；乙\n```")
        self.assertEqual(result.returncode, 0)
        self.assertIn("未发现可检查的正文", result.stdout)
        self.assertNotIn("未发现可自动检测的结构错误", result.stdout)

    def test_help_and_invalid_mode(self):
        result = self.run_checker("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("检查简明技术中文", result.stdout)
        self.assertEqual(self.run_checker("--mode", "invalid").returncode, 2)


if __name__ == "__main__":
    unittest.main()
