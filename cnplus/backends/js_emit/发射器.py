"""JS 发射器 —— 阶段 4 T3 骨架。

与 python_emit/发射器.py 同构：
- 每语句一行，每步运算调用运行时函数（语义不泄漏）
- 环境链块级作用域（_环N 变量）
- 行映射记录生成行 → .cnp 行

差异点（JS 特有）：
- 代码块用 {}，语句块发射 `{` / `}` 行
- 小数字面量包 标记小数(...)，保住「这是小数」的类型信息
  （JS Number 层面 2 与 2.0 同值，CNplus 语义要求区分）
- 字符串用 JSON 转义
"""
from __future__ import annotations

import json
from pathlib import Path

from cnplus.parser.ast import (二元运算, 二元表达式, 函数声明, 变量引用,
                               声明语句, 如果语句, 字符串字面量, 小数字面量,
                               布尔字面量, 循环语句, 整数字面量, 程序,
                               空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句, 导入语句, 成员访问,
                               列表字面量, 字典字面量, 索引访问, 索引赋值语句,
                               遍历语句, 跳出语句, 继续语句, 自增语句,
                               格式串, 多重声明语句, 尝试语句, 抛出语句,
                               错误表达式, 错误语句, 类声明, 成员赋值语句,
                               切片访问)

_运行时路径 = Path(__file__).with_name("运行时源码.js")
_运行时 = _运行时路径.read_text(encoding="utf-8")

_二元函数 = {
    二元运算.加: "加", 二元运算.减: "减", 二元运算.乘: "乘", 二元运算.除: "除",
    二元运算.整除: "整除", 二元运算.取余: "取余",
    二元运算.等于: "等于", 二元运算.不等于: "不等于",
    二元运算.小于: "小于", 二元运算.小于等于: "小于等于",
    二元运算.大于: "大于", 二元运算.大于等于: "大于等于",
    二元运算.幂: "幂",
}


class 发射器:
    def __init__(self, 程: 程序) -> None:
        self.程 = 程
        self.行: list[str] = []
        self.行映射: list[int] = []
        self.缩进 = 0
        self.环计数 = 0
        self.函数计数 = 0
        self.在函数内 = False

    def _行(self, 文本: str = "", 源行: int = 0) -> None:
        分行 = (文本 or "").split("\n")
        for 一行 in 分行:
            前缀 = "    " * self.缩进 if len(分行) == 1 else ""
            self.行.append(前缀 + 一行)
            self.行映射.append(源行)

    def _进块(self, 旧环名: str) -> str:
        self.环计数 += 1
        新 = f"_环{self.环计数}"
        self._行(f"const {新} = new 环境({旧环名});")
        return 新

    def _新函数名(self, 原名: str) -> str:
        self.函数计数 += 1
        return f"{原名}_实现_{self.函数计数}"

    def _位置(self, 跨) -> tuple[int, int]:
        return 跨.起.行, 跨.起.列

    # ==================== 入口 ====================
    def 发射(self) -> str:
        self._行("// 由 CNplus 编译生成。可独立运行：node 本文件", 0)
        self._行("", 0)
        self._行(_运行时, 0)
        self._行("", 0)
        self._行("const _全局 = 建全局环境();", 0)
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
            self._行(f"{环名}.声明({js_str(s.名)}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 表达式语句):
            self._行(self._表达式(s.表达, 环名) + ";", 行)
            return
        if isinstance(s, 错误语句):
            return
        raise AssertionError(f"未处理的语句类型 {type(s).__name__}")

    # ==================== 表达式 ====================
    def _表达式(self, e: 表达式, 环名: str) -> str:
        行, 列 = self._位置(e.跨)
        if isinstance(e, 整数字面量):
            return str(e.值)
        if isinstance(e, 小数字面量):
            # 小数标记：JS 的 2 与 2.0 同值，包标记保住类型信息
            return f"标记小数({e.值!r})"
        if isinstance(e, 字符串字面量):
            return js_str(e.值)
        if isinstance(e, 布尔字面量):
            return "true" if e.值 else "false"
        if isinstance(e, 空字面量):
            return "null"
        if isinstance(e, 错误表达式):
            return "null"
        if isinstance(e, 变量引用):
            return f"{环名}.取({js_str(e.名)}, {行}, {列})"
        if isinstance(e, 调用表达式):
            实参 = ", ".join(self._表达式(a, 环名) for a in e.实参)
            关键字 = ", ".join(
                f"[{js_str(名)}, {self._表达式(值, 环名)}]"
                for 名, 值 in e.关键字参数)
            if isinstance(e.被调, 成员访问):
                对象 = self._表达式(e.被调.对象, 环名)
                return (f"点调用(_全局, {对象}, {js_str(e.被调.属性)}, "
                        f"[{实参}], [{关键字}], {行}, {列})")
            被调 = self._表达式(e.被调, 环名)
            return f"调用({被调}, [{实参}], [{关键字}], {行}, {列})"
        raise AssertionError(f"未处理的表达式类型 {type(e).__name__}")


def textwrap_split(text: str) -> list[str]:
    return text.split("\n")


def js_str(s: str) -> str:
    """Python 字符串 → JS 字符串字面量（JSON 转义 + 兼容单引号无碍）。"""
    return json.dumps(s, ensure_ascii=False)


def 发射(程: 程序) -> tuple[str, list[int]]:
    发 = 发射器(程)
    return 发.发射(), 发.行映射
