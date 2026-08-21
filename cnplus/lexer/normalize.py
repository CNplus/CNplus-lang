"""全角/半角归一化。

**只在 lexer 入口应用一次**，绝不渗到 parser —— 中文编程语言普遍在这里栽跟头。
归一化保持字符数不变（一对一映射），所以偏移量仍然对得上原文。
"""
from __future__ import annotations

from cnplus.lexer.tokens import 归一化表


def 归一化(文本: str) -> str:
    """把全角标点换成半角。字符数不变，故 span 偏移仍指向原文。"""
    表 = 归一化表()
    return "".join(表.get(字, 字) for 字 in 文本)
