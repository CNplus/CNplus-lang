"""LSP 悬停 —— 内置函数说明 / 变量名 / 关键字说明。

纯函数：文本 + 行列 进，Markdown 文本出（None = 无提示）。
"""
from __future__ import annotations

from cnplus.lexer.tokens import 关键字映射
from cnplus.lsp.补全 import 内置说明, 关键字说明
from cnplus.lsp.符号索引 import 光标词, 建索引


def 悬停于(码: str, 行: int, 列: int) -> str | None:
    词 = 光标词(码, 行, 列)
    if not 词:
        return None
    # 1. 用户定义的名字：用户作用域可遮蔽内置函数。
    符 = 建索引(码, "<悬停>").解析符号(词, 行, 列)
    if 符 is not None:
        return f"{符.种类} **{词}**（第 {符.声明跨.起.行} 行声明）"
    # 2. 内置函数
    if 词 in 内置说明:
        return f"```cnp\n{内置说明[词].split(' —— ')[0]}\n```\n\n{内置说明[词].split(' —— ', 1)[1]}"
    # 3. 关键字（主写法或别名）
    映射 = 关键字映射()
    if 词 in 映射 and 词 in 关键字说明:
        return 关键字说明[词]
    return None
