"""运行时值与类型名。

语义约定：CNplus 有 整数/小数/字符串/布尔/空/函数 六类值。
类型名用于错误消息，必须是中文。
"""
from __future__ import annotations

from dataclasses import dataclass

from cnplus.parser.ast import 函数声明


@dataclass(slots=True)
class 函数值:
    声明: 函数声明
    闭包: object  # 环境，避免循环导入所以用 object

    def __repr__(self) -> str:
        return f"<函数 {self.声明.名}>"


@dataclass(slots=True)
class 类值:
    """类（D-036 方案 C）：名字 + 方法表 + 构造声明。

    实例化时：先按初始化形参建空字段，再跑初始化块体。
    """
    名: str
    方法表: dict            # 名 -> 函数值
    初始化: object = None   # 函数声明 | None
    闭包环: object = None   # 类定义处的作用域（初始化块体的外层）

    def __repr__(self) -> str:
        return f"<类 {self.名}>"


@dataclass(slots=True)
class 实例值:
    """实例：类指针 + 字段表。字段读写全落在这。"""
    类: 类值
    字段: dict

    def __repr__(self) -> str:
        return f"<{self.类.名} 实例>"


@dataclass(slots=True)
class 绑定方法:
    """实例.方法 取出的值：调用时自动把实例填进「自己」。"""
    函: 函数值
    实例: 实例值

    def __repr__(self) -> str:
        return f"<方法 {self.函.声明.名} of {self.实例.类.名}>"


def 类型名(值: object) -> str:
    if 值 is None:
        return "空"
    if isinstance(值, bool):
        return "布尔"
    if isinstance(值, int):
        return "整数"
    if isinstance(值, float):
        return "小数"
    if isinstance(值, str):
        return "字符串"
    if isinstance(值, list):
        return "列表"
    if isinstance(值, dict):
        return "字典"
    if isinstance(值, 函数值):
        return "函数"
    if isinstance(值, 类值):
        return "类"
    if isinstance(值, 实例值):
        return 值.类.名
    if isinstance(值, 绑定方法):
        return "函数"
    return type(值).__name__


def 显示(值: object) -> str:
    """把值转成用户可见的文本。语义约定：布尔显示为 真/假，空显示为 空。"""
    if 值 is None:
        return "空"
    if 值 is True:
        return "真"
    if 值 is False:
        return "假"
    if isinstance(值, float):
        # 避免 3.0 显示成 3
        return repr(值)
    if isinstance(值, list):
        return "[" + ", ".join(显示(x) for x in 值) + "]"
    if isinstance(值, dict):
        return "{" + ", ".join(f"{显示(k)}: {显示(v)}" for k, v in 值.items()) + "}"
    if isinstance(值, 函数值):
        return repr(值)
    if isinstance(值, 实例值):
        return f"<{值.类.名}>"
    if isinstance(值, 类值):
        return repr(值)
    if isinstance(值, 绑定方法):
        return repr(值)
    return str(值)
