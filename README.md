# 简明技术中文

让 AI 用清楚、简洁、准确的简体中文编写技术文档。
这个 Agent Skill 支持写作、翻译、改写和审校。
适用于操作步骤、使用手册、技术说明、安全提示和故障报告。

本项目改编自 [Simplified Technical English](https://github.com/0xpili/simplified-technical-english)。
它保留短句、明确动作和统一术语等原则，并按中文习惯重新制定规则。
**这不是 ASD-STE100 的官方中文版本，也不提供合规认证。**

## 改写示例

改写前：

> 在开始进行安装操作之前，应当确保所有组件均已完成全面的损坏情况检查，且任何存在缺陷的部件均须立即予以更换；否则可能导致系统故障。

改写后：

> 安装前，检查所有组件是否损坏。
> 如果发现损坏的组件，立即更换。
> 损坏的组件可能导致系统故障。

改写不改变原文的要求、条件、数值或风险程度。
代码、命令、路径、API 名称和引用原文保持不变。

## 仓库内容

| 文件 | 用途 |
|---|---|
| `SKILL.md` | AI 使用的主要指令 |
| `references/writing-rules.md` | 中文写作规则和示例 |
| `references/word-list.md` | 首选表达、待检查表达和术语约定 |
| `references/substitutions.md` | 常见改写方式及适用条件 |
| `examples/before-after.md` | 操作、说明、警告和软件文档的改写示例 |
| `scripts/stc_check.py` | 简明技术中文检查器 |
| `scripts/ste_check.py` | 兼容旧命令路径的入口，执行中文检查 |
| `tests/test_stc_check.py` | 检查器的回归测试 |
| `NOTICE.md` | 来源、版权和适用范围说明 |

## 安装到 Claude Code

将仓库克隆到个人技能目录：

```sh
git clone https://github.com/Riablo/simplified-technical-chinese.git ~/.claude/skills/simplified-technical-chinese
```

可以直接调用 `/simplified-technical-chinese`，也可以这样提出需求：

```text
用简明技术中文改写这份安装指南。保留命令、参数和所有安全要求。
```

## 在 Amp 或其他支持 Agent Skills 的工具中使用

将整个仓库放入工具支持的技能目录。
例如，在 Amp 中安装到个人技能目录：

```sh
git clone https://github.com/Riablo/simplified-technical-chinese.git ~/.agents/skills/simplified-technical-chinese
```

不要只复制 `SKILL.md`。技能需要同目录下的参考文件和脚本。
对于不支持 Agent Skills 的模型，可以将 `SKILL.md` 放入系统提示词。
再按需要补充 `references/` 中的内容。

## 检查文档

检查器只需要 Python 3.9 或更高版本，不需要安装第三方依赖。
在仓库根目录运行：

```sh
python3 scripts/stc_check.py --mode procedural draft.txt
python3 scripts/stc_check.py --mode descriptive chapter.md
printf '安装前，备份配置文件。\n' | python3 scripts/stc_check.py
```

也可以从其他目录使用脚本的完整路径。
默认词表相对于脚本定位，不依赖当前工作目录。
旧命令 `python3 scripts/ste_check.py` 仍可运行，但现在检查中文，不再检查英文 STE。

检查器会报告：

- 过长的句子：操作型上限为 40 个计数单位，说明型为 50 个。
- 超过 6 句的段落。
- 中文分号或英文分号。
- 需要复核的模糊表达，以及词表中的待检查表达。

每个汉字计 1 个单位，连续的英文单词或数字串计 1 个单位。
例如，正文“检查 API v2 的 3 个节点。”计 9 个单位。
标点和空白不计数。行内代码、URL 和引号中的原文各计 1 个单位。
括号内的普通说明照常计数，不能用括号隐藏长句。
这些是本项目的检查约定，不是国家标准，也不是英文词数的换算结果。

`--mode mixed` 是默认模式。
它对超过 50 个单位的句子报错，对 41～50 个单位的句子提示复核。
工具不会自动判断一个句子是否是操作步骤。

检查器跳过 YAML 前置元数据、围栏代码块、缩进代码块、Markdown 引用块、标题和表格行。
行内代码、URL 和引号中的原文不参与用词检查。
这些内容仍须人工复核。
工具支持常见 Markdown 写法，不是完整的 Markdown 解析器。

其他选项：

```sh
# 关闭词表提示，保留句长、段落、标点和模糊表达检查。
python3 scripts/stc_check.py --no-vocab draft.md

# 使用项目自己的词表，格式见 references/word-list.md。
python3 scripts/stc_check.py --word-list project-words.md draft.md

# 运行回归测试。
python3 -m unittest discover -s tests -v
```

退出码：`0` 表示未发现结构错误，`1` 表示发现结构错误，`2` 表示参数或文件读取错误。
用词提示不改变退出码，不应未经复核就自动替换。

## 使用限制

检查器不能判断事实是否正确、术语是否一致或要求是否被改写。
它也不能完整识别繁体字、歧义、被动表达或安全风险。
简体中文、语义和领域要求由 Skill 的审校流程及人工复核保证。
“没有报错”不代表文档已经准确、安全或符合某项标准。

## 来源和许可

上游项目参考 ASD-STE100 Issue 7（2017）。
本项目借鉴其写作原则，但不沿用英文专用的时态规则和封闭词表。
中文词表是本项目的写作建议，不是 ASD 批准词典的翻译。
官方英文规范可从 https://www.asd-ste100.org 获取。

项目沿用 MIT 许可，保留原作者版权声明。
详情见 [LICENSE](LICENSE) 和 [NOTICE.md](NOTICE.md)。
