"""发射器 —— 把 CNplus AST 翻译成自包含的 Python 源码。

设计要点（决定正确性的地方）：

1. **语义不泄漏**：生成的代码每一步运算都调用运行时（运行时源码.py），
   不直接写 `a + b`。这样严格真值、跨类型比较报错、/ 恒为小数等
   CNplus 语义在转译后端依然成立 —— 黄金语料在两个后端结果一致。

2. **短路**：`与`/`或` 用 Python 的 `and`/`or` 保留短路控制流，
   两侧各自包一层 条件() 强制布尔。

3. **块级作用域**：CNplus 的 如果/循环 主体是独立作用域（像 JS 的 let），
   Python 没有块级作用域，所以每个块生成一个新环境变量挂到父环境链上。

4. **行映射**：记录每条生成行的对应 .cnp 行，用于把 Python 库的异常
   翻译回 CNplus 的位置。
"""
from __future__ import annotations

from pathlib import Path

from cnplus.parser.ast import (一元运算, 一元表达式, 二元运算, 二元表达式,
                               函数声明, 变量引用, 声明语句, 如果语句, 字符串字面量,
                               小数字面量, 布尔字面量, 循环语句, 整数字面量,
                               程序, 空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句, 导入语句, 成员访问,
                               错误表达式, 错误语句)

_运行时路径 = Path(__file__).with_name("运行时源码.py")
_运行时 = _运行时路径.read_text(encoding="utf-8")

# 二元运算 -> 运行时函数名
_二元函数 = {
    二元运算.加: "加", 二元运算.减: "减", 二元运算.乘: "乘",
    二元运算.除: "除", 二元运算.整除: "整除", 二元运算.取余: "取余",
    二元运算.等于: "等于", 二元运算.不等于: "不等于",
    二元运算.小于: "小于", 二元运算.小于等于: "小于等于",
    二元运算.大于: "大于", 二元运算.大于等于: "大于等于",
}


class 发射器:
    def __init__(self, 程: 程序) -> None:
        self.程 = 程
        self.行: list[str] = []
        self.行映射: list[int] = []  # 生成行(1 起) -> .cnp 行
        self.缩进 = 0
        self.环计数 = 0
        self.函数计数 = 0
        self.在函数内 = False

    def _行(self, 文本: str = "", 源行: int = 0) -> None:
        # 文本可能含内嵌换行（如整块运行时源码）。必须逐行拆开，
        # 否则一条映射对应多个物理行，行映射与生成行数错位。
        分行 = 文本.split("\n")
        for i, 一行 in enumerate(分行):
            # 只对单行片段加缩进；多行块（运行时源码）自带缩进，不再加
            前缀 = "    " * self.缩进 if len(分行) == 1 else ""
            self.行.append(前缀 + 一行)
            self.行映射.append(源行)

    def _进块(self, 旧环名: str) -> str:
        """进入新块作用域：生成新环境变量并挂到父环境链上。

        之前只起名字不发射赋值，导致 _环2/_环3 未定义 —— 这是核心 bug。
        """
        self.环计数 += 1
        新 = f"_环{self.环计数}"
        self._行(f"{新} = 环境({旧环名})")
        return 新

    def _新函数名(self, 原名: str) -> str:
        self.函数计数 += 1
        # 中文是合法 Python 标识符，保留原名可读，加序号防重名
        return f"{原名}_实现_{self.函数计数}"

    def _位置(self, 跨) -> tuple[int, int]:
        return 跨.起.行, 跨.起.列

    # ==================== 入口 ====================
    def 发射(self) -> str:
        self._行(f"# 由 CNplus 编译生成。可独立运行：python3 本文件", 0)
        self._行("", 0)
        self._行(_运行时, 0)
        self._行("", 0)
        self._行("_全局 = 建全局环境()", 0)
        self._行("", 0)
        self._块(self.程.语句们, "_全局")
        return "\n".join(self.行) + "\n"

    # ==================== 语句 ====================
    def _块(self, 语句们: tuple[语句, ...], 环名: str) -> None:
        for s in 语句们:
            self._语句(s, 环名)

    def _语句(self, s: 语句, 环名: str) -> None:
        if isinstance(s, 错误语句):
            return
        行, 列 = self._位置(s.跨)

        if isinstance(s, 声明语句):
            值 = self._表达式(s.值, 环名)
            self._行(f"{环名}.声明({s.名!r}, {值}, {行}, {列})", 行)
            return
        if isinstance(s, 赋值语句):
            值 = self._表达式(s.值, 环名)
            法 = "赋外层" if s.是外部 else "赋值"
            self._行(f"{环名}.{法}({s.名!r}, {值}, {行}, {列})", 行)
            return
        if isinstance(s, 表达式语句):
            self._行(self._表达式(s.表达, 环名), 行)
            return
        if isinstance(s, 如果语句):
            self._如果(s, 环名)
            return
        if isinstance(s, 循环语句):
            条件 = f"条件({self._表达式(s.条件, 环名)}, {行}, {列})"
            self._行(f"while {条件}:", 行)
            self.缩进 += 1
            self._块(s.主体, self._进块(环名))
            self.缩进 -= 1
            return
        if isinstance(s, 函数声明):
            self._函数(s, 环名)
            return
        if isinstance(s, 返回语句):
            if self.在函数内:
                值 = self._表达式(s.值, 环名) if s.值 is not None else "None"
                self._行(f"return {值}", 行)
            elif s.值 is not None:
                # 顶层 返回：求值但不返回（与树遍历一致：值被丢弃）
                self._行(self._表达式(s.值, 环名), 行)
            return
        if isinstance(s, 导入语句):
            名 = s.别名 or s.模块.rpartition(".")[2] or s.模块
            self._行(f"{环名}.声明({名!r}, 导入({s.模块!r}, {行}, {列}), {行}, {列})", 行)
            return
        raise AssertionError(f"未处理的语句类型 {type(s).__name__}")

    def _如果(self, s: 如果语句, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        条件 = f"条件({self._表达式(s.条件, 环名)}, {行}, {列})"
        self._行(f"if {条件}:", 行)
        self.缩进 += 1
        self._块(s.主体, self._进块(环名))
        self.缩进 -= 1
        if s.否则体:
            self._行("else:", 行)
            self.缩进 += 1
            self._块(s.否则体, self._进块(环名))
            self.缩进 -= 1

    def _函数(self, s: 函数声明, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        函数名 = self._新函数名(s.名)
        # def 函数名_实现_序号(_环):
        self._行(f"def {函数名}(_环):", 行)
        self.缩进 += 1
        旧在函数内 = self.在函数内
        self.在函数内 = True
        self._块(s.主体, "_环")
        self.在函数内 = 旧在函数内
        self.缩进 -= 1
        形参 = ", ".join(repr(p) for p in s.形参)
        self._行(f"{环名}.声明({s.名!r}, 函数值({函数名}, {环名}, [{形参}], {s.名!r}), {行}, {列})", 行)

    # ==================== 表达式 ====================
    def _表达式(self, e: 表达式, 环名: str) -> str:
        行, 列 = self._位置(e.跨)
        if isinstance(e, 整数字面量):
            return str(e.值)
        if isinstance(e, 小数字面量):
            return repr(e.值)
        if isinstance(e, 字符串字面量):
            return repr(e.值)
        if isinstance(e, 布尔字面量):
            return "True" if e.值 else "False"
        if isinstance(e, 空字面量):
            return "None"
        if isinstance(e, 错误表达式):
            return "None"
        if isinstance(e, 变量引用):
            return f"{环名}.取({e.名!r}, {行}, {列})"
        if isinstance(e, 一元表达式):
            操作数 = self._表达式(e.操作数, 环名)
            法 = "负" if e.运算 is 一元运算.负 else "非"
            return f"{法}({操作数}, {行}, {列})"
        if isinstance(e, 二元表达式):
            return self._二元(e, 环名)
        if isinstance(e, 成员访问):
            对象 = self._表达式(e.对象, 环名)
            return f"取成员({对象}, {e.属性!r}, {行}, {列})"
        if isinstance(e, 调用表达式):
            被调 = self._表达式(e.被调, 环名)
            实参 = ", ".join(self._表达式(a, 环名) for a in e.实参)
            return f"调用({被调}, [{实参}], {行}, {列})"
        raise AssertionError(f"未处理的表达式类型 {type(e).__name__}")

    def _二元(self, e: 二元表达式, 环名: str) -> str:
        行, 列 = self._位置(e.跨)
        # 与/或：短路 + 两侧强制布尔
        if e.运算 is 二元运算.与:
            左 = f"条件({self._表达式(e.左, 环名)}, {行}, {列})"
            右 = f"条件({self._表达式(e.右, 环名)}, {行}, {列})"
            return f"({左} and {右})"
        if e.运算 is 二元运算.或:
            左 = f"条件({self._表达式(e.左, 环名)}, {行}, {列})"
            右 = f"条件({self._表达式(e.右, 环名)}, {行}, {列})"
            return f"({左} or {右})"
        法 = _二元函数[e.运算]
        左 = self._表达式(e.左, 环名)
        右 = self._表达式(e.右, 环名)
        return f"{法}({左}, {右}, {行}, {列})"


def 发射(程: 程序) -> tuple[str, list[int]]:
    """返回 (Python 源码, 行映射)。行映射[i] = 生成第 i 行对应的 .cnp 行。"""
    器 = 发射器(程)
    源码 = 器.发射()
    return 源码, 器.行映射
