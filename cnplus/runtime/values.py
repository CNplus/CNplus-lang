"""运行时值与类型名。

语义约定：CNplus 有 整数/小数/字符串/布尔/空/函数 六类值。
类型名用于错误消息，必须是中文。
"""
from __future__ import annotations

from dataclasses import dataclass

from cnplus.parser.ast import 函数声明


@dataclass(frozen=True, slots=True)
class 字典标签:
    """宿主字典内部标签；类别参与相等，避免 Python 把 真 与 1 合并。"""
    类别: str
    值: object


def 规范字典标签(值: object) -> 字典标签:
    """把语言标签变成带类型的稳定宿主标签。整数值小数与整数同标签。"""
    if 值 is None:
        return 字典标签("空", None)
    if isinstance(值, bool):
        return 字典标签("布尔", 值)
    if isinstance(值, int):
        return 字典标签("整数", 值)
    if isinstance(值, float) and 值.is_integer():
        return 字典标签("整数", int(值))
    if isinstance(值, str):
        return 字典标签("字符串", 值)
    raise TypeError


def 还原字典标签(标签: 字典标签) -> object:
    return 标签.值


class 宿主边界错误(TypeError):
    """CNplus 容器无法无损表示为 Python 容器，或反向转换失败。"""


def _含语言字典(值: object, 已见: set[int]) -> bool:
    if isinstance(值, dict):
        return True
    if not isinstance(值, list) or id(值) in 已见:
        return False
    已见.add(id(值))
    return any(_含语言字典(x, 已见) for x in 值)


def _到宿主值(值: object, 已转: dict[int, object]) -> object:
    if not isinstance(值, (list, dict)):
        return 值
    if id(值) in 已转:
        return 已转[id(值)]
    if isinstance(值, list):
        出: list[object] = []
        已转[id(值)] = 出
        出.extend(_到宿主值(x, 已转) for x in 值)
        return 出
    出字典: dict[object, object] = {}
    已转[id(值)] = 出字典
    for 标签, 项 in 值.items():
        if not isinstance(标签, 字典标签):
            raise 宿主边界错误("语言字典含有损坏的内部标签")
        宿主标签 = 还原字典标签(标签)
        if 宿主标签 in 出字典:
            raise 宿主边界错误(
                "字典含有在 Python 中会合并的不同标签，不能无损传给宿主库")
        出字典[宿主标签] = _到宿主值(项, 已转)
    return 出字典


def 到宿主值(值: object) -> object:
    """跨入 Python 库前无损转换语言字典；纯列表保留原身份。"""
    if not _含语言字典(值, set()):
        return 值
    return _到宿主值(值, {})


def _含宿主字典(值: object, 已见: set[int]) -> bool:
    if isinstance(值, dict):
        return True
    if isinstance(值, tuple):
        return True
    if not isinstance(值, list) or id(值) in 已见:
        return False
    已见.add(id(值))
    return any(_含宿主字典(x, 已见) for x in 值)


def _从宿主值(值: object, 已转: dict[int, object]) -> object:
    if not isinstance(值, (list, tuple, dict)):
        return 值
    if id(值) in 已转:
        return 已转[id(值)]
    if isinstance(值, (list, tuple)):
        出: list[object] = []
        已转[id(值)] = 出
        出.extend(_从宿主值(x, 已转) for x in 值)
        return 出
    出字典: dict[字典标签, object] = {}
    已转[id(值)] = 出字典
    for 标签, 项 in 值.items():
        try:
            语言标签 = 规范字典标签(标签)
        except TypeError as ex:
            raise 宿主边界错误(
                f"Python 字典的 {type(标签).__name__} 标签不能转换成 CNplus 标签") from ex
        出字典[语言标签] = _从宿主值(项, 已转)
    return 出字典


def 从宿主值(值: object) -> object:
    """把宿主字典纳入标签合同、元组转为列表；纯列表保留身份。"""
    if not _含宿主字典(值, set()):
        return 值
    return _从宿主值(值, {})


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


@dataclass(slots=True, eq=False)
class 实例值:
    """实例：类指针 + 字段表；相等采用身份，不按字段展开比较。"""
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
    if callable(值):
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
        return "{" + ", ".join(
            f"{显示(还原字典标签(k))}: {显示(v)}" for k, v in 值.items()) + "}"
    if isinstance(值, 函数值):
        return repr(值)
    if isinstance(值, 实例值):
        return f"<{值.类.名}>"
    if isinstance(值, 类值):
        return repr(值)
    if isinstance(值, 绑定方法):
        return repr(值)
    return str(值)
