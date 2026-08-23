"""词元种类与词元。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path

from cnplus.source import 跨度

_表路径 = Path(__file__).with_name("keywords.toml")


class 种类(Enum):
    # 字面量与标识符
    整数 = auto()
    小数 = auto()
    字符串 = auto()
    标识符 = auto()
    # 关键字
    令 = auto()
    如果 = auto()
    否则 = auto()
    循环 = auto()
    函数 = auto()
    返回 = auto()
    外部 = auto()
    真 = auto()
    假 = auto()
    空 = auto()
    与 = auto()
    或 = auto()
    非 = auto()
    导入 = auto()
    作为 = auto()
    遍历 = auto()
    每个 = auto()
    插值符 = auto()
    尝试 = auto()
    捕获 = auto()
    最后 = auto()
    抛出 = auto()
    跳出 = auto()
    继续 = auto()
    # 运算符
    加 = auto()
    减 = auto()
    乘 = auto()
    除 = auto()
    整除 = auto()
    取余 = auto()
    幂 = auto()
    等于 = auto()
    不等于 = auto()
    小于 = auto()
    小于等于 = auto()
    大于 = auto()
    大于等于 = auto()
    赋值 = auto()
    加赋 = auto()      # +=
    减赋 = auto()      # -=
    乘赋 = auto()      # *=
    除赋 = auto()      # /=
    自增 = auto()      # ++
    自减 = auto()      # --
    # 标点
    左括号 = auto()
    右括号 = auto()
    逗号 = auto()
    冒号 = auto()
    点 = auto()
    左方括号 = auto()
    右方括号 = auto()
    左花括号 = auto()
    右花括号 = auto()
    # 结构
    换行 = auto()
    缩进 = auto()
    退缩 = auto()
    文件尾 = auto()
    # 错误恢复用
    非法 = auto()

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class 词元:
    种: 种类
    文本: str
    跨: 跨度
    值: object = None  # 字面量的解析结果

    def __str__(self) -> str:
        return f"{self.种}({self.文本!r})@{self.跨}"


@lru_cache(maxsize=1)
def 读表() -> dict:
    with _表路径.open("rb") as f:
        return tomllib.load(f)


@lru_cache(maxsize=1)
def 关键字映射() -> dict[str, 种类]:
    """所有关键字写法（含别名）-> 种类。"""
    出 = {}
    for 名, 写法们 in 读表()["关键字"].items():
        种 = 种类[名]
        for 写 in 写法们:
            出[写] = 种
    return 出


@lru_cache(maxsize=1)
def 运算符映射() -> dict[str, 种类]:
    return {符: 种类[名] for 符, 名 in 读表()["运算符"].items()}


@lru_cache(maxsize=1)
def 标点映射() -> dict[str, 种类]:
    return {符: 种类[名] for 符, 名 in 读表()["标点"].items()}


@lru_cache(maxsize=1)
def 归一化表() -> dict[str, str]:
    return dict(读表()["归一化"])
