"""后端接口 —— 铁律 3。

第一天就定义这个抽象基类，哪怕只有一个实现。有它，第二个后端
（Python 转译、字节码 VM、JS）才是「加文件」而不是「改架构」。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from cnplus.diagnostics import 诊断袋
from cnplus.parser.ast import 程序
from cnplus.source import 源文件


class 后端(ABC):
    """把 AST 变成行为的东西。"""

    名称: str = "未命名"

    @abstractmethod
    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        """运行程序。运行时错误报告进 袋，不抛异常给调用方。"""
        raise NotImplementedError


class 运行时错误(Exception):
    """内部信号：由后端捕获转成诊断，不逃到用户面前。"""

    def __init__(self, 码: str, 消息: str, 跨, 提示: str | None = None) -> None:
        super().__init__(消息)
        self.码 = 码
        self.消息 = 消息
        self.跨 = 跨
        self.提示 = 提示
