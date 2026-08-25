"""LSP 跳转定义 —— 变量/函数/类的声明位置。

纯函数：文本 + 行列进，定义处 (行, 列) 出（1 起；None = 找不到）。
"""
from __future__ import annotations

from cnplus.parser.ast import 声明语句, 函数声明, 类声明, 遍历语句
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


def _光标词(码: str, 行: int, 列: int) -> str:
    """光标处的标识符词——指着哪个词就取整词（与 悬停._光标词 同款）。"""
    行们 = 码.split("\n")
    当前行 = 行们[行 - 1] if 0 < 行 <= len(行们) else ""
    前 = 当前行[:列 - 1] if 列 > 1 else ""
    左词 = ""
    for 字 in reversed(前):
        if 字.isalnum() or 字 == "_":
            左词 = 字 + 左词
        else:
            break
    if 左词:
        起点 = len(前) - len(左词)
        完整 = ""
        for 字 in 当前行[起点:]:
            if 字.isalnum() or 字 == "_":
                完整 += 字
            else:
                break
        return 完整
    后 = 当前行[len(前):]
    词 = ""
    for 字 in 后:
        if 字.isalnum() or 字 == "_":
            词 += 字
        else:
            break
    return 词


def 定义于(码: str, 行: int, 列: int) -> tuple[int, int] | None:
    词 = _光标词(码, 行, 列)
    if not 词:
        return None
    源 = 源文件(码, "<跳转>")
    程, 袋 = 解析(源)
    for s in 程.语句们:
        if isinstance(s, 声明语句) and s.名 == 词:
            return (s.跨.起.行, s.跨.起.列)
        if isinstance(s, 函数声明) and s.名 == 词:
            return (s.跨.起.行, s.跨.起.列)
        if isinstance(s, 类声明) and s.名 == 词:
            return (s.跨.起.行, s.跨.起.列)
        if isinstance(s, 遍历语句) and s.变量 == 词 and s.变量跨 is not None:
            return (s.变量跨.起.行, s.变量跨.起.列)
    return None
