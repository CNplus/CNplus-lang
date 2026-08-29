"""LSP 跳转定义 —— 变量/函数/类的声明位置。

纯函数：文本 + 行列进，定义处 (行, 列) 出（1 起；None = 找不到）。
"""
from __future__ import annotations

from cnplus.lsp.符号索引 import 光标词, 建索引
from cnplus.source import 跨度


def 定义跨度于(码: str, 行: int, 列: int) -> 跨度 | None:
    词 = 光标词(码, 行, 列)
    if not 词:
        return None
    符 = 建索引(码, "<跳转>").解析符号(词, 行, 列)
    if 符 is None:
        return None
    return 符.声明跨


def 定义于(码: str, 行: int, 列: int) -> tuple[int, int] | None:
    跨 = 定义跨度于(码, 行, 列)
    if 跨 is None:
        return None
    return (跨.起.行, 跨.起.列)
