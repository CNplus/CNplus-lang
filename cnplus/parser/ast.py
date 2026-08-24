"""CNplus 自有 AST —— 铁律 1。

不用 Python 的 `ast` 模块，不用裸 dict。节点是 CNplus 的语义单位，
字段结构由 CNplus 的语义决定，不照抄宿主。

铁律 2：每个节点都带 `跨`。父节点的跨度由子节点合并得出。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cnplus.source import 跨度


class 节点:
    """所有 AST 节点的基类。子类都是 frozen dataclass 且带 `跨` 字段。"""

    跨: 跨度


# ==================== 表达式 ====================

class 表达式(节点):
    pass


@dataclass(frozen=True, slots=True)
class 整数字面量(表达式):
    值: int
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 小数字面量(表达式):
    值: float
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 字符串字面量(表达式):
    值: str
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 布尔字面量(表达式):
    值: bool
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 空字面量(表达式):
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 变量引用(表达式):
    名: str
    跨: 跨度


class 二元运算(Enum):
    加 = "+"
    减 = "-"
    乘 = "*"
    除 = "/"
    整除 = "//"
    取余 = "%"
    幂 = "**"
    等于 = "=="
    不等于 = "!="
    小于 = "<"
    小于等于 = "<="
    大于 = ">"
    大于等于 = ">="
    与 = "与"
    或 = "或"

    def __str__(self) -> str:
        return self.value


class 一元运算(Enum):
    负 = "-"
    非 = "非"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class 二元表达式(表达式):
    运算: 二元运算
    左: 表达式
    右: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 一元表达式(表达式):
    运算: 一元运算
    操作数: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 调用表达式(表达式):
    被调: 表达式
    实参: tuple[表达式, ...]
    跨: 跨度
    关键字参数: tuple[tuple[str, 表达式], ...] = ()  # (名, 值) 对


@dataclass(frozen=True, slots=True)
class 成员访问(表达式):
    """对象.成员 —— 用于访问导入的 Python 库，例如 数学.sqrt。"""
    对象: 表达式
    属性: str
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 列表字面量(表达式):
    """[1, 2, 3]"""
    元素: tuple[表达式, ...]
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 字典字面量(表达式):
    """{"名": "小明", "岁": 18}"""
    键值对: tuple[tuple[表达式, 表达式], ...]
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 索引访问(表达式):
    """名单[0] / 字典["键"]"""
    对象: 表达式
    下标: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 切片访问(表达式):
    """a[起:止] —— 左闭右开，起/止可省略，负数从尾数（D-037）。"""
    对象: 表达式
    起: 表达式 | None      # None = 省略（从头）
    止: 表达式 | None      # None = 省略（到尾）
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 格式串(表达式):
    """@"你好，{名字}" —— 部分是 str（原文）或 表达式（要嵌入的值）交替。"""
    部分: tuple[object, ...]  # 每项是 str 或 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 错误表达式(表达式):
    """占位节点 —— 解析失败时填这个，让 AST 仍然可用（D-005）。"""
    跨: 跨度
    说明: str = ""


# ==================== 语句 ====================

class 语句(节点):
    pass


@dataclass(frozen=True, slots=True)
class 声明语句(语句):
    """令 名 = 值"""
    名: str
    值: 表达式
    跨: 跨度
    名跨: 跨度 | None = None


@dataclass(frozen=True, slots=True)
class 多重声明语句(语句):
    """设 甲, 乙 = 值 —— 解包，值必须是长度匹配的列表。"""
    名们: tuple[str, ...]
    值: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 赋值语句(语句):
    名: str
    值: 表达式
    跨: 跨度
    是外部: bool = False
    名跨: 跨度 | None = None
    复合: 二元运算 | None = None  # 非空表示 x += y 之类（复合运算符）


@dataclass(frozen=True, slots=True)
class 表达式语句(语句):
    表达: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 如果语句(语句):
    条件: 表达式
    主体: tuple[语句, ...]
    否则体: tuple[语句, ...]
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 循环语句(语句):
    条件: 表达式
    主体: tuple[语句, ...]
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 函数声明(语句):
    名: str
    形参: tuple[str, ...]
    主体: tuple[语句, ...]
    跨: 跨度
    形参跨们: tuple[跨度, ...] = ()
    默认值们: tuple[表达式 | None, ...] = ()  # 与形参一一对应，None=必填


@dataclass(frozen=True, slots=True)
class 类声明(语句):
    """类 名 —— 方案 C（无继承），D-036。

    初始化: 名为「初始化」的函数声明，其形参自动转存为字段；
    无初始化方法时字段为空。方法是普通函数声明。
    """
    名: str
    方法们: tuple[函数声明, ...]
    初始化: 函数声明 | None      # 括号参数自动成字段；块体可选
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 返回语句(语句):
    值: 表达式 | None
    跨: 跨度
    多值: tuple[表达式, ...] = ()  # 非空表示 返回 甲, 乙（多返回值）


@dataclass(frozen=True, slots=True)
class 导入语句(语句):
    """导入 "模块名" [作为 别名] —— 借用 Python 库。"""
    模块: str
    别名: str | None
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 遍历语句(语句):
    """遍历 可迭代对象 每个 变量 —— 遍历列表/字典/字符串。"""
    变量: str
    可迭代: 表达式
    主体: tuple[语句, ...]
    跨: 跨度
    变量跨: 跨度 | None = None


@dataclass(frozen=True, slots=True)
class 跳出语句(语句):
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 继续语句(语句):
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 索引赋值语句(语句):
    """名单[0] = 值 / 字典["键"] = 值"""
    对象: 表达式
    下标: 表达式
    值: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 成员赋值语句(语句):
    """对象.字段 = 值 —— 类实例写字段（D-036）。"""
    对象: 表达式
    属性: str
    值: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 自增语句(语句):
    """x++ / x-- —— 变量自增或自减 1。"""
    名: str
    增量: int  # +1 或 -1
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 尝试语句(语句):
    """尝试 … 捕获 错 … 最后 …

    捕获变量 为 None 表示 `捕获` 后面没写变量名（不关心错误内容）。
    捕获体 为 None 表示没有 捕获 段（只有 最后）。
    最后体 为 None 表示没有 最后 段。
    """
    主体: tuple[语句, ...]
    捕获变量: str | None
    捕获体: tuple[语句, ...] | None
    最后体: tuple[语句, ...] | None
    跨: 跨度
    捕获变量跨: 跨度 | None = None


@dataclass(frozen=True, slots=True)
class 抛出语句(语句):
    """抛出 "出错说明" —— 主动制造一个错误。"""
    值: 表达式
    跨: 跨度


@dataclass(frozen=True, slots=True)
class 错误语句(语句):
    """占位节点 —— 语句解析失败时填这个。"""
    跨: 跨度
    说明: str = ""


@dataclass(frozen=True, slots=True)
class 程序(节点):
    语句们: tuple[语句, ...]
    跨: 跨度
