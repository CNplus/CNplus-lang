"""LSP 悬停 —— 内置函数说明 / 变量名 / 关键字说明。

纯函数：文本 + 行列 进，Markdown 文本出（None = 无提示）。
"""
from __future__ import annotations

from cnplus.lexer.tokens import 关键字映射
from cnplus.parser.ast import 声明语句, 函数声明, 类声明, 变量引用
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

from cnplus.lsp.补全 import 内置说明, 关键字说明


def _光标词(码: str, 行: int, 列: int) -> str:
    """光标处的标识符词——指着哪个词就取整词。

    光标在词中间取整个词，在词尾/词首也取整词。
    """
    行们 = 码.split("\n")
    当前行 = 行们[行 - 1] if 0 < 行 <= len(行们) else ""
    前 = 当前行[: 列 - 1] if 列 > 1 else ""
    左词 = ""
    for 字 in reversed(前):
        if 字.isalnum() or 字 == "_":
            左词 = 字 + 左词
        else:
            break
    # 从左词起点向右取完整词（覆盖光标在词中间的情况）
    if 左词:
        起点 = len(前) - len(左词)
        完整 = ""
        for 字 in 当前行[起点:]:
            if 字.isalnum() or 字 == "_":
                完整 += 字
            else:
                break
        return 完整
    # 光标在词首（左侧是分隔符）：向右取
    后 = 当前行[len(前):]
    词 = ""
    for 字 in 后:
        if 字.isalnum() or 字 == "_":
            词 += 字
        else:
            break
    return 词


def 悬停于(码: str, 行: int, 列: int) -> str | None:
    词 = _光标词(码, 行, 列)
    if not 词:
        return None
    # 1. 内置函数
    if 词 in 内置说明:
        return f"```cnp\n{内置说明[词].split(' —— ')[0]}\n```\n\n{内置说明[词].split(' —— ', 1)[1]}"
    # 2. 关键字（主写法或别名）
    映射 = 关键字映射()
    if 词 in 映射 and 词 in 关键字说明:
        return 关键字说明[词]
    # 3. 用户定义的名字：给声明的位置
    源 = 源文件(码, "<悬停>")
    程, 袋 = 解析(源)
    for s in 程.语句们:
        if isinstance(s, 声明语句) and s.名 == 词:
            return f"变量 **{词}**（第 {s.跨.起.行} 行声明）"
        if isinstance(s, 函数声明) and s.名 == 词:
            形参 = ", ".join(s.形参)
            return f"函数 **{词}({形参})**（第 {s.跨.起.行} 行定义）"
        if isinstance(s, 类声明) and s.名 == 词:
            return f"类 **{词}**（第 {s.跨.起.行} 行定义）"
    return None
