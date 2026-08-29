"""诊断系统 —— 中文错误信息 + 源码摘录 + 波浪线。

诊断码稳定，一旦发布不再改含义。分段：
  CN01xx 词法    CN02xx 语法    CN03xx 语义/运行时
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from cnplus.source import 源文件, 跨度


class 级别(Enum):
    错误 = "错误"
    警告 = "警告"

    def __str__(self) -> str:
        return self.value


# ---- 诊断码表（稳定，只增不改） ----
CN0101_非法字符 = "CN0101"
CN0102_未闭合字符串 = "CN0102"
CN0103_非法数字 = "CN0103"

CN0201_期望词元 = "CN0201"
CN0202_意外词元 = "CN0202"
CN0203_期望表达式 = "CN0203"
CN0204_期望缩进 = "CN0204"

CN0301_条件必须是布尔 = "CN0301"
CN0302_未声明变量 = "CN0302"
CN0303_类型不匹配 = "CN0303"
CN0304_除以零 = "CN0304"
CN0305_不可调用 = "CN0305"
CN0306_实参数量不符 = "CN0306"
CN0307_重复声明 = "CN0307"
CN0308_下标越界 = "CN0308"
CN0309_不可遍历 = "CN0309"
CN0310_输入结束 = "CN0310"
CN0311_主动抛出 = "CN0311"
CN0312_初始化不能返回值 = "CN0312"
CN0310_跳出在循环外 = "CN0310"


@dataclass(frozen=True, slots=True)
class 诊断:
    """一条诊断。

    三层结构，照顾不同水平的读者：
      消息 —— 精确说明，保留「声明」「布尔值」这类术语，有基础的人一眼看懂
      解释 —— 同一件事的大白话版本，没学过编程也能懂
      提示 —— 具体怎么改，尽量给出可直接照抄的代码
    """

    码: str
    消息: str
    跨: 跨度
    级 : 级别 = 级别.错误
    提示: str | None = None
    解释: str | None = None

    def __str__(self) -> str:
        return f"{self.跨.起} {self.级}[{self.码}]: {self.消息}"


def _显示宽度(文本: str) -> int:
    """中文/全角字符占两列，用于波浪线对齐。"""
    宽 = 0
    for 字 in 文本:
        宽 += 2 if unicodedata.east_asian_width(字) in ("W", "F") else 1
    return 宽


def 渲染(诊: 诊断, 源: 源文件) -> str:
    """渲染成人类可读的多行报告。"""
    行号 = 诊.跨.起.行
    行文本 = 源.取行(行号)
    行号宽 = len(str(行号))

    前缀空白 = " " * 行号宽
    头 = f"{诊.级}[{诊.码}]: {诊.消息}"
    位置行 = f"{前缀空白}--> {源.文件名}:{诊.跨.起}"

    缩进 = " " * _显示宽度(行文本[: 诊.跨.起.列 - 1])
    if 诊.跨.单行:
        宽 = _显示宽度(源.原文(诊.跨)) or 1
    else:
        宽 = max(_显示宽度(行文本) - _显示宽度(行文本[: 诊.跨.起.列 - 1]), 1)
    波浪 = "^" * 宽

    行 = [
        头,
        位置行,
        f"{前缀空白} |",
        f"{行号} | {行文本}",
        f"{前缀空白} | {缩进}{波浪}",
    ]
    if not 诊.跨.单行:
        行.append(f"{前缀空白} | （错误延续至第 {诊.跨.止.行} 行）")
    if 诊.解释:
        行.append(f"{前缀空白} = 也就是说: {诊.解释}")
    if 诊.提示:
        行.append(f"{前缀空白} = 这样改: {诊.提示}")
    return "\n".join(行)


@dataclass
class 诊断袋:
    """收集诊断。parser 恒返回 (AST, 诊断袋)，永不抛异常 —— 见 D-005。"""

    条目: list[诊断] = field(default_factory=list)

    def 报告(self, 码: str, 消息: str, 跨: 跨度, 提示: str | None = None,
             级 : 级别 = 级别.错误, 解释: str | None = None) -> None:
        self.条目.append(
            诊断(码=码, 消息=消息, 跨=跨, 级=级, 提示=提示, 解释=解释))

    @property
    def 有错(self) -> bool:
        return any(d.级 is 级别.错误 for d in self.条目)

    def __len__(self) -> int:
        return len(self.条目)

    def __iter__(self):
        return iter(self.条目)

    def 渲染全部(self, 源: 源文件) -> str:
        return "\n\n".join(渲染(d, 源) for d in self.条目)
