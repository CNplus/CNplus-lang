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
class 赋值语句(语句):
    名: str
    值: 表达式
    跨: 跨度
    是外部: bool = False
    名跨: 跨度 | None = None


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


@dataclass(frozen=True, slots=True)
class 返回语句(语句):
    值: 表达式 | None
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
