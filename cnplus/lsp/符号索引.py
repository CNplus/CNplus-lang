"""LSP 共用的词法作用域与符号索引。"""
from __future__ import annotations

from dataclasses import dataclass, field

from cnplus.parser.ast import (声明语句, 函数声明, 类声明, 遍历语句,
                               尝试语句, 如果语句, 循环语句, 多重声明语句,
                               导入语句)
from cnplus.parser.parser import 解析
from cnplus.source import 源文件, 跨度


@dataclass(frozen=True, slots=True)
class 符号:
    名: str
    种类: str
    声明跨: 跨度
    可见起点: int


@dataclass(slots=True)
class 作用域:
    跨: 跨度
    上级: 作用域 | None = None
    符号们: list[符号] = field(default_factory=list)
    下级们: list[作用域] = field(default_factory=list)

    def 包含(self, 偏移: int) -> bool:
        return self.跨.起.偏移 <= 偏移 <= self.跨.止.偏移


@dataclass(frozen=True, slots=True)
class 索引:
    源: 源文件
    根: 作用域

    def _光标作用域(self, 偏移: int) -> 作用域:
        当前 = self.根
        while True:
            更深 = next((域 for 域 in 当前.下级们 if 域.包含(偏移)), None)
            if 更深 is None:
                return 当前
            当前 = 更深

    def 解析符号(self, 名: str, 行: int, 列: int) -> 符号 | None:
        偏移 = _偏移于(self.源.文本, 行, 列)
        当前: 作用域 | None = self._光标作用域(偏移)
        while 当前 is not None:
            for 项 in reversed(当前.符号们):
                if 项.名 == 名 and 项.可见起点 <= 偏移:
                    return 项
            当前 = 当前.上级
        return None

    def 可见符号(self, 行: int, 列: int) -> list[符号]:
        """返回光标处可见的符号；内层同名项遮蔽外层。"""
        偏移 = _偏移于(self.源.文本, 行, 列)
        当前: 作用域 | None = self._光标作用域(偏移)
        出: list[符号] = []
        已见: set[str] = set()
        while 当前 is not None:
            for 项 in reversed(当前.符号们):
                if 项.名 not in 已见 and 项.可见起点 <= 偏移:
                    出.append(项)
                    已见.add(项.名)
            当前 = 当前.上级
        return 出


def _偏移于(文本: str, 行: int, 列: int) -> int:
    行们 = 文本.splitlines(keepends=True)
    if 行 < 1:
        return 0
    if 行 > len(行们):
        return len(文本)
    行首 = sum(len(项) for 项 in 行们[:行 - 1])
    行长 = len(行们[行 - 1].rstrip("\r\n"))
    return 行首 + min(max(列 - 1, 0), 行长)


def 光标词(码: str, 行: int, 列: int) -> str:
    """取 1 起行列指向的完整标识符。"""
    行们 = 码.split("\n")
    当前行 = 行们[行 - 1] if 0 < 行 <= len(行们) else ""
    前 = 当前行[:列 - 1] if 列 > 1 else ""
    左词 = ""
    for 字 in reversed(前):
        if 字.isalnum() or 字 == "_":
            左词 = 字 + 左词
        else:
            break
    起点 = len(前) - len(左词)
    if not 左词:
        起点 = len(前)
    完整 = ""
    for 字 in 当前行[起点:]:
        if 字.isalnum() or 字 == "_":
            完整 += 字
        else:
            break
    return 完整


def _加函数作用域(上级: 作用域, 声明: 函数声明) -> None:
    体跨 = (声明.主体跨 or
           (声明.主体[0].跨.合并(声明.主体[-1].跨) if 声明.主体
            else 跨度(声明.跨.止, 声明.跨.止)))
    域 = 作用域(跨=体跨, 上级=上级)
    上级.下级们.append(域)
    for 名, 名跨 in zip(声明.形参, 声明.形参跨们):
        域.符号们.append(符号(名=名, 种类="参数", 声明跨=名跨,
                           可见起点=体跨.起.偏移))
    _收集块(域, 声明.主体)


def _加类(域: 作用域, 声明: 类声明) -> None:
    域.符号们.append(符号(声明.名, "类", 声明.名跨 or 声明.跨,
                       声明.跨.起.偏移))
    if 声明.初始化 is not None:
        _加函数作用域(域, 声明.初始化)
    for 方法 in 声明.方法们:
        _加函数作用域(域, 方法)


def _收集块(域: 作用域, 语句们: tuple, *, 顶层: bool = False) -> None:
    for 句 in 语句们:
        if isinstance(句, 声明语句) and 句.名跨 is not None:
            域.符号们.append(符号(句.名, "变量", 句.名跨,
                               句.跨.止.偏移))
        elif isinstance(句, 多重声明语句):
            for 名, 名跨 in zip(句.名们, 句.名跨们):
                域.符号们.append(符号(名, "变量", 名跨, 句.跨.止.偏移))
        elif isinstance(句, 导入语句):
            名 = 句.别名 or 句.模块.rpartition(".")[2] or 句.模块
            名跨 = 句.别名跨 or 句.模块跨
            if 名跨 is not None:
                域.符号们.append(符号(名, "导入", 名跨, 句.跨.止.偏移))
        elif isinstance(句, 函数声明):
            if not 顶层:
                域.符号们.append(符号(句.名, "函数", 句.名跨 or 句.跨,
                                   句.跨.起.偏移))
            _加函数作用域(域, 句)
        elif isinstance(句, 类声明):
            _加类(域, 句)
        elif isinstance(句, 遍历语句) and 句.主体 and 句.变量跨 is not None:
            体跨 = 句.主体[0].跨.合并(句.主体[-1].跨)
            子域 = 作用域(跨=体跨, 上级=域)
            域.下级们.append(子域)
            子域.符号们.append(符号(句.变量, "变量", 句.变量跨,
                                   体跨.起.偏移))
            _收集块(子域, 句.主体)
        elif isinstance(句, 尝试语句):
            _收集子块(域, 句.主体)
            if 句.捕获体:
                体跨 = 句.捕获体[0].跨.合并(句.捕获体[-1].跨)
                子域 = 作用域(跨=体跨, 上级=域)
                域.下级们.append(子域)
                if 句.捕获变量 is not None and 句.捕获变量跨 is not None:
                    子域.符号们.append(符号(
                        句.捕获变量, "变量", 句.捕获变量跨, 体跨.起.偏移))
                _收集块(子域, 句.捕获体)
            if 句.最后体:
                _收集子块(域, 句.最后体)
        elif isinstance(句, 如果语句):
            _收集子块(域, 句.主体)
            _收集子块(域, 句.否则体)
        elif isinstance(句, 循环语句):
            _收集子块(域, 句.主体)


def _收集子块(上级: 作用域, 语句们: tuple) -> None:
    if not 语句们:
        return
    体跨 = 语句们[0].跨.合并(语句们[-1].跨)
    子域 = 作用域(跨=体跨, 上级=上级)
    上级.下级们.append(子域)
    _收集块(子域, 语句们)


def 建索引(码: str, 文件名: str = "<LSP>") -> 索引:
    源 = 源文件(码, 文件名)
    程, _袋 = 解析(源)
    根 = 作用域(跨=源.跨度于(0, len(码)))
    # 与 checker 一致：只有顶层函数预收集，以支持互相调用和前向引用。
    for 句 in 程.语句们:
        if isinstance(句, 函数声明):
            根.符号们.append(符号(句.名, "函数", 句.名跨 or 句.跨, 0))
    _收集块(根, 程.语句们, 顶层=True)
    return 索引(源=源, 根=根)
