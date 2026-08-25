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

from cnplus.parser.ast import (二元运算, 二元表达式, 一元运算, 一元表达式,
                               函数声明, 变量引用,
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
    二元运算.与: "与", 二元运算.或: "或",
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
        if isinstance(s, 多重声明语句):
            值 = self._表达式(s.值, 环名)
            名列 = "[" + ", ".join(js_str(n) for n in s.名们) + "]"
            self._行(f"解包声明({环名}, {名列}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 赋值语句):
            值 = self._表达式(s.值, 环名)
            法 = "赋外层" if s.是外部 else "赋值"
            if s.复合 is not None:
                旧 = f"{环名}.取({js_str(s.名)}, {行}, {列})"
                运名 = _二元函数[s.复合]
                值 = f"{运名}({旧}, {值}, {行}, {列})"
            self._行(f"{环名}.{法}({js_str(s.名)}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 自增语句):
            旧 = f"{环名}.取({js_str(s.名)}, {行}, {列})"
            值 = f"自增值({旧}, {s.增量}, {行}, {列})"
            self._行(f"{环名}.赋值({js_str(s.名)}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 表达式语句):
            self._行(self._表达式(s.表达, 环名) + ";", 行)
            return
        if isinstance(s, 如果语句):
            self._如果(s, 环名)
            return
        if isinstance(s, 循环语句):
            条件 = f"条件({self._表达式(s.条件, 环名)}, {行}, {列})"
            self._行(f"while ({条件}) {{", 行)
            self.缩进 += 1
            self._块(s.主体, self._进块(环名))
            self.缩进 -= 1
            self._行("}", 行)
            return
        if isinstance(s, 函数声明):
            self._函数(s, 环名)
            return
        if isinstance(s, 返回语句):
            if s.多值:
                多 = "[" + ", ".join(self._表达式(v, 环名) for v in s.多值) + "]"
                if self.在函数内:
                    self._行(f"return {多};", 行)
                else:
                    self._行(多 + ";", 行)
                return
            if self.在函数内:
                值 = self._表达式(s.值, 环名) if s.值 is not None else "null"
                self._行(f"return {值};", 行)
            elif s.值 is not None:
                # 顶层 返回：求值但不返回（与树遍历一致：值被丢弃）
                self._行(self._表达式(s.值, 环名) + ";", 行)
            return
        if isinstance(s, 遍历语句):
            self._遍历(s, 环名)
            return
        if isinstance(s, 跳出语句):
            self._行("break;", 行)
            return
        if isinstance(s, 继续语句):
            self._行("continue;", 行)
            return
        if isinstance(s, 索引赋值语句):
            对象 = self._表达式(s.对象, 环名)
            下标 = self._表达式(s.下标, 环名)
            值 = self._表达式(s.值, 环名)
            self._行(f"设索引({对象}, {下标}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 成员赋值语句):
            对象 = self._表达式(s.对象, 环名)
            值 = self._表达式(s.值, 环名)
            self._行(f"设成员({对象}, {js_str(s.属性)}, {值}, {行}, {列});", 行)
            return
        if isinstance(s, 类声明):
            self._类(s, 环名)
            return
        if isinstance(s, 尝试语句):
            self._尝试(s, 环名)
            return
        if isinstance(s, 抛出语句):
            值 = self._表达式(s.值, 环名)
            self._行(f"抛出({值}, {行}, {列});", 行)
            return
        if isinstance(s, 导入语句):
            self._行(f"{环名}.声明({js_str(s.别名 or s.模块)}, "
                     f"不支持导入({js_str(s.模块)}, {行}, {列}), {行}, {列});", 行)
            return
        if isinstance(s, 错误语句):
            return
        raise AssertionError(f"未处理的语句类型 {type(s).__name__}")

    def _尝试(self, s: 尝试语句, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        self._行("try {", 行)
        self.缩进 += 1
        self._块(s.主体, self._进块(环名))
        self.缩进 -= 1
        if s.捕获体 is not None:
            # 只捕 CNplus 的错误，其他异常原样重抛（与 Python 后端一致）
            self._行("} catch (_错) {", 行)
            self.缩进 += 1
            self._行("if (!(_错 instanceof CNplus错误)) { throw _错; }", 行)
            捕获环 = self._进块(环名)
            if s.捕获变量 is not None:
                self._行(f"{捕获环}.声明({js_str(s.捕获变量)}, "
                         f"_错.消息, {行}, {列});", 行)
            self._块(s.捕获体, 捕获环)
            self.缩进 -= 1
        if s.最后体 is not None:
            self._行("} finally {", 行)
            self.缩进 += 1
            self._块(s.最后体, self._进块(环名))
            self.缩进 -= 1
        self._行("}", 行)

    def _如果(self, s: 如果语句, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        条件 = f"条件({self._表达式(s.条件, 环名)}, {行}, {列})"
        self._行(f"if ({条件}) {{", 行)
        self.缩进 += 1
        self._块(s.主体, self._进块(环名))
        self.缩进 -= 1
        if s.否则体:
            self._行("} else {", 行)
            self.缩进 += 1
            self._块(s.否则体, self._进块(环名))
            self.缩进 -= 1
        self._行("}", 行)

    def _遍历(self, s: 遍历语句, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        可迭代 = self._表达式(s.可迭代, 环名)
        循环变 = f"_项{self.环计数}"
        self._行(f"for (const {循环变} of 遍历项({可迭代}, {行}, {列})) {{", 行)
        self.缩进 += 1
        新环 = self._进块(环名)
        self._行(f"{新环}.声明({js_str(s.变量)}, {循环变}, {行}, {列});", 行)
        self._块(s.主体, 新环)
        self.缩进 -= 1
        self._行("}", 行)

    def _函数(self, s: 函数声明, 环名: str) -> None:
        行, 列 = self._位置(s.跨)
        函数名 = self._新函数名(s.名)
        self._行(f"function {函数名}(_环) {{", 行)
        self.缩进 += 1
        旧在函数内 = self.在函数内
        self.在函数内 = True
        self._块(s.主体, "_环")
        self.在函数内 = 旧在函数内
        self.缩进 -= 1
        self._行("}", 行)
        形参 = ", ".join(js_str(p) for p in s.形参)
        默认们 = s.默认值们 or tuple(None for _ in s.形参)
        默认串 = ", ".join(
            (self._表达式(d, 环名) if d is not None else "缺省")
            for d in 默认们)
        self._行(
            f"{环名}.声明({js_str(s.名)}, new 函数值({函数名}, {环名}, "
            f"[{形参}], {js_str(s.名)}, [{默认串}]), {行}, {列});", 行)

    def _类(self, s: 类声明, 环名: str) -> None:
        """类声明 → 方法函数 + 类值（D-036，与 Python 后端同构）。"""
        行, 列 = self._位置(s.跨)
        旧在函数内 = self.在函数内
        self.在函数内 = True
        项们 = []  # (名, 实现名, 形参, 默认串)
        for m in s.方法们:
            项们.append(self._方法函数(m, 环名, s.名))
        if s.初始化 is not None:
            项们.append(self._方法函数(s.初始化, 环名, s.名, 内部名="__初始化__"))
        self.在函数内 = 旧在函数内
        对们 = ", ".join(
            f"{js_str(名)}: new 函数值({实现}, {环名}, [{', '.join(js_str(p) for p in 形参)}], "
            f"{js_str('初始化' if 名 == '__初始化__' else 名)}, [{默认}])"
            for 名, 实现, 形参, 默认 in 项们)
        表达 = "{" + 对们 + "}" if 对们 else "{}"
        初形参 = list(s.初始化.形参) if s.初始化 else []
        形参串 = ", ".join(js_str(p) for p in 初形参)
        self._行(f"{环名}.声明({js_str(s.名)}, new 类值({js_str(s.名)}, "
                 f"new Map(Object.entries({表达})), [{形参串}]), {行}, {列});", 行)

    def _方法函数(self, m: 函数声明, 环名: str, 类名: str,
                内部名: str | None = None) -> tuple[str, str, list, str]:
        """生成一个方法体函数。空方法体生成 pass 等价物。"""
        行, 列 = self._位置(m.跨)
        函数名 = self._新函数名(内部名 or m.名)
        self._行(f"function {函数名}(_环) {{", 行)
        self.缩进 += 1
        旧 = self.在函数内
        self.在函数内 = True
        if m.主体:
            self._块(m.主体, "_环")
        else:
            self._行("", 行)
        self.在函数内 = 旧
        self.缩进 -= 1
        self._行("}", 行)
        形参 = list(m.形参)
        默认们 = m.默认值们 or tuple(None for _ in m.形参)
        默认串 = ", ".join(
            (self._表达式(d, 环名) if d is not None else "缺省")
            for d in 默认们)
        return (内部名 or m.名, 函数名, 形参, 默认串)

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
        if isinstance(e, 一元表达式):
            运名 = {一元运算.负: "负", 一元运算.非: "非"}[e.运算]
            return f"{运名}({self._表达式(e.操作数, 环名)}, {行}, {列})"
        if isinstance(e, 二元表达式):
            运名 = _二元函数[e.运算]
            左 = self._表达式(e.左, 环名)
            右 = self._表达式(e.右, 环名)
            if e.运算 is 二元运算.与:
                return f"与({左}, {右}, {行}, {列})"
            if e.运算 is 二元运算.或:
                return f"或({左}, {右}, {行}, {列})"
            return f"{运名}({左}, {右}, {行}, {列})"
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
        if isinstance(e, 列表字面量):
            元素 = ", ".join(self._表达式(x, 环名) for x in e.元素)
            return f"[{元素}]"
        if isinstance(e, 字典字面量):
            对们 = ", ".join(
                f"[{self._表达式(k, 环名)}, {self._表达式(v, 环名)}]"
                for k, v in e.键值对)
            return f"造字典([{对们}], {行}, {列})"
        if isinstance(e, 索引访问):
            对象 = self._表达式(e.对象, 环名)
            下标 = self._表达式(e.下标, 环名)
            return f"取索引({对象}, {下标}, {行}, {列})"
        if isinstance(e, 切片访问):
            对象 = self._表达式(e.对象, 环名)
            起 = self._表达式(e.起, 环名) if e.起 is not None else "null"
            止 = self._表达式(e.止, 环名) if e.止 is not None else "null"
            return f"取切片({对象}, {起}, {止}, {行}, {列})"
        if isinstance(e, 成员访问):
            对象 = self._表达式(e.对象, 环名)
            return f"取成员({对象}, {js_str(e.属性)}, {行}, {列})"
        if isinstance(e, 格式串):
            片段 = []
            for 段 in e.部分:
                if isinstance(段, str):
                    片段.append(js_str(段))
                else:
                    片段.append(f"显示({self._表达式(段, 环名)})")
            return "加连接([" + ", ".join(片段) + "])" if 片段 else "''"
        raise AssertionError(f"未处理的表达式类型 {type(e).__name__}")


def _加连接(片段们) -> str:
    return "".join(片段们)


def textwrap_split(text: str) -> list[str]:
    return text.split("\n")


def js_str(s: str) -> str:
    """Python 字符串 → JS 字符串字面量（JSON 转义 + 兼容单引号无碍）。"""
    return json.dumps(s, ensure_ascii=False)


def 发射(程: 程序) -> tuple[str, list[int]]:
    发 = 发射器(程)
    return 发.发射(), 发.行映射
