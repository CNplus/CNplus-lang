"""静态检查 —— 不执行程序就能发现的问题。

为什么需要它：`如果 0` 这类错误在求值器里检查，但编辑器不会执行你的代码。
不做这一遍，编辑器里最该报的错反而报不出来。

原则：**只报能百分百确定的错**。拿不准就沉默 —— 编辑器里的假阳性
比漏报更烦人。所以这里只检查字面量层面可判定的情况。
"""
from __future__ import annotations

from cnplus.diagnostics import (CN0301_条件必须是布尔, CN0302_未声明变量,
                                CN0304_除以零, CN0307_重复声明, 诊断袋)
from cnplus.parser.ast import (二元运算, 二元表达式, 函数声明, 变量引用,
                               声明语句, 如果语句, 字符串字面量, 小数字面量,
                               布尔字面量, 循环语句, 整数字面量, 程序,
                               空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句,
                               错误表达式, 错误语句, 一元表达式)

_内置名 = {"打印", "随机数", "长度", "类型", "整数", "小数", "文本"}


def _字面量类型(e: 表达式) -> str | None:
    """能静态确定类型就返回中文类型名，否则 None。"""
    if isinstance(e, 布尔字面量):
        return "布尔"
    if isinstance(e, 整数字面量):
        return "整数"
    if isinstance(e, 小数字面量):
        return "小数"
    if isinstance(e, 字符串字面量):
        return "字符串"
    if isinstance(e, 空字面量):
        return "空"
    return None


class _作用域:
    def __init__(self, 父: "_作用域 | None" = None) -> None:
        self.名字: set[str] = set()
        self.父 = 父

    def 有(self, 名: str) -> bool:
        环 = self
        while 环 is not None:
            if 名 in 环.名字:
                return True
            环 = 环.父
        return False

    def 有本地(self, 名: str) -> bool:
        return 名 in self.名字

    def 加(self, 名: str) -> None:
        self.名字.add(名)


class 检查器:
    def __init__(self, 袋: 诊断袋) -> None:
        self.袋 = 袋

    def 检查(self, 程: 程序) -> None:
        顶层 = _作用域()
        for 名 in _内置名:
            顶层.加(名)
        # 先收集所有顶层函数名，允许函数间互相调用与前向引用
        for s in 程.语句们:
            if isinstance(s, 函数声明):
                顶层.加(s.名)
        self._块(程.语句们, 顶层)

    def _块(self, 语句们: tuple[语句, ...], 域: _作用域) -> None:
        for s in 语句们:
            self._语句(s, 域)

    def _语句(self, s: 语句, 域: _作用域) -> None:
        if isinstance(s, 错误语句):
            return
        if isinstance(s, 声明语句):
            self._表达式(s.值, 域)
            if 域.有本地(s.名):
                self.袋.报告(CN0307_重复声明,
                          f"变量 {s.名} 在这个作用域已经声明过了", s.跨,
                          提示=f"直接写 {s.名} = ... 来改它的值")
            域.加(s.名)
            return
        if isinstance(s, 赋值语句):
            self._表达式(s.值, 域)
            if not 域.有(s.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {s.名} 还没有声明过", s.跨,
                          提示=f"先写 令 {s.名} = ... 来声明它")
            return
        if isinstance(s, 表达式语句):
            self._表达式(s.表达, 域)
            return
        if isinstance(s, 如果语句):
            self._条件(s.条件, 域)
            self._块(s.主体, _作用域(域))
            if s.否则体:
                self._块(s.否则体, _作用域(域))
            return
        if isinstance(s, 循环语句):
            self._条件(s.条件, 域)
            self._块(s.主体, _作用域(域))
            return
        if isinstance(s, 函数声明):
            域.加(s.名)
            内 = _作用域(域)
            for p in s.形参:
                内.加(p)
            # 允许递归
            内.加(s.名)
            self._块(s.主体, 内)
            return
        if isinstance(s, 返回语句):
            if s.值 is not None:
                self._表达式(s.值, 域)
            return

    def _条件(self, e: 表达式, 域: _作用域) -> None:
        self._表达式(e, 域)
        类型 = _字面量类型(e)
        if 类型 is not None and 类型 != "布尔":
            self.袋.报告(CN0301_条件必须是布尔,
                      f"条件必须是布尔值，这里是{类型}", e.跨,
                      提示="CNplus 不做隐式真值转换，请写成比较式，例如 x != 0")

    def _表达式(self, e: 表达式, 域: _作用域) -> None:
        if isinstance(e, 错误表达式):
            return
        if isinstance(e, 变量引用):
            if not 域.有(e.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {e.名} 还没有声明过", e.跨,
                          提示=f"先写 令 {e.名} = ... 来声明它")
            return
        if isinstance(e, 一元表达式):
            self._表达式(e.操作数, 域)
            return
        if isinstance(e, 二元表达式):
            self._表达式(e.左, 域)
            self._表达式(e.右, 域)
            # 除以字面量零 —— 能百分百确定
            if e.运算 in (二元运算.除, 二元运算.整除, 二元运算.取余):
                if isinstance(e.右, 整数字面量) and e.右.值 == 0:
                    self.袋.报告(CN0304_除以零, "除数不能是零", e.跨)
                elif isinstance(e.右, 小数字面量) and e.右.值 == 0.0:
                    self.袋.报告(CN0304_除以零, "除数不能是零", e.跨)
            return
        if isinstance(e, 调用表达式):
            self._表达式(e.被调, 域)
            for a in e.实参:
                self._表达式(a, 域)
            return


def 检查(程: 程序, 袋: 诊断袋) -> 诊断袋:
    """在诊断袋里追加静态检查发现的问题。"""
    检查器(袋).检查(程)
    return 袋
