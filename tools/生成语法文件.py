#!/usr/bin/env python3
"""从 keywords.toml 生成 VSCode 的 TextMate 语法文件。

TextMate 语法技术上是**第二套 tokenizer**（VSCode 在 LSP 连上之前用它做
即时高亮）。手写必然与 lexer 漂移 —— 加了关键字忘同步是经典 bug。
所以它必须生成，不能手写（D-007）。这是铁律 4「关键字表是数据」的第二次分红。

用法：python tools/生成语法文件.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnplus.lexer.tokens import 读表  # noqa: E402

输出路径 = (Path(__file__).resolve().parent.parent
          / "editors" / "vscode" / "syntaxes" / "cnplus.tmLanguage.json")

# 关键字分组 -> TextMate scope
#
# 只在这里声明「需要特殊配色」的组；**其余关键字由下方自动兜底**，
# 避免重演硬编码名单漏项的老问题（D-017：静态检查器曾因硬编码
# 内置名单漏认 8 个函数）。加新关键字时若忘了归组，它仍会被高亮，
# 只是用通用的 keyword.other 配色。
_分组 = {
    "keyword.control.conditional.cnplus": ["如果", "否则"],
    "keyword.control.loop.cnplus": ["循环", "遍历", "每个", "跳出", "继续"],
    "keyword.control.exception.cnplus": ["尝试", "捕获", "最后", "抛出"],
    "keyword.control.flow.cnplus": ["返回"],
    "keyword.control.import.cnplus": ["导入", "作为"],
    "keyword.declaration.cnplus": ["令", "函数", "外部"],
    "constant.language.boolean.cnplus": ["真", "假"],
    "constant.language.null.cnplus": ["空"],
    "keyword.operator.logical.cnplus": ["与", "或", "非"],
}


def 生成() -> dict:
    表 = 读表()
    关键字 = 表["关键字"]

    模式 = []

    # 注释
    模式.append({
        "name": "comment.line.number-sign.cnplus",
        "match": "#.*$",
    })

    # 字符串
    模式.append({
        "name": "string.quoted.double.cnplus",
        "begin": '"', "end": '"',
        "patterns": [{"name": "constant.character.escape.cnplus",
                      "match": r"\\\\."}],
    })
    模式.append({
        "name": "string.quoted.single.cnplus",
        "begin": "'", "end": "'",
        "patterns": [{"name": "constant.character.escape.cnplus",
                      "match": r"\\\\."}],
    })

    # 关键字（按分组，每组把所有别名一起收进去）
    已归组 = set()
    for scope, 组名们 in _分组.items():
        写法 = []
        for 组 in 组名们:
            写法.extend(关键字.get(组, []))
            已归组.add(组)
        if not 写法:
            continue
        # 长的写法排前面，避免「不」先匹配掉「不然」
        写法.sort(key=len, reverse=True)
        模式.append({"name": scope, "match": "|".join(写法)})

    # 自动兜底：关键字表里没被归组的，一律给通用 scope。
    # 这样加了新关键字忘记归组时，高亮仍然生效（只是配色通用），
    # 而不是像以前那样彻底不高亮 —— 硬编码名单必漏，见 D-017。
    漏掉的 = []
    for 组, 写法们 in 关键字.items():
        if 组 in 已归组:
            continue
        漏掉的.extend(写法们)
    if 漏掉的:
        漏掉的.sort(key=len, reverse=True)
        模式.append({
            "name": "keyword.other.cnplus",
            "match": "|".join(漏掉的),
        })

    # 函数定义名
    函数写法 = "|".join(sorted(关键字.get("函数", []), key=len, reverse=True))
    模式.append({
        "match": f"(?:{函数写法})\\s+([^\\s(（]+)",
        "captures": {"1": {"name": "entity.name.function.cnplus"}},
    })

    # 函数调用
    模式.append({
        "match": r"([^\s(（），,+\-*/%<>=!]+)\s*[(（]",
        "captures": {"1": {"name": "entity.name.function.call.cnplus"}},
    })

    # 数字
    模式.append({
        "name": "constant.numeric.cnplus",
        "match": r"\b\d+(\.\d+)?\b",
    })

    # 运算符（长的先来）
    运算符 = sorted(表["运算符"].keys(), key=len, reverse=True)
    转义 = [c.replace("\\", "\\\\").replace("+", r"\+").replace("*", r"\*")
          .replace("/", r"\/").replace("%", r"\%").replace("-", r"\-")
          for c in 运算符]
    模式.append({
        "name": "keyword.operator.cnplus",
        "match": "|".join(转义),
    })

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "CNplus",
        "scopeName": "source.cnplus",
        "fileTypes": ["cnp"],
        "_生成说明": "本文件由 tools/生成语法文件.py 从 keywords.toml 生成，请勿手改",
        "patterns": 模式,
    }


def main() -> int:
    语法 = 生成()
    输出路径.parent.mkdir(parents=True, exist_ok=True)
    输出路径.write_text(
        json.dumps(语法, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {输出路径.relative_to(Path.cwd()) if 输出路径.is_relative_to(Path.cwd()) else 输出路径}")
    print(f"  {len(语法['patterns'])} 条规则")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
