"""词法分析器。

产出的每个词元都带跨度（铁律 2）。遇到错误报告诊断并跳过，
**从不抛异常** —— 编辑器依赖这个性质（D-005）。

缩进处理：像 Python 一样用 缩进/退缩 词元表示块结构，
但只认空格（Tab 报错），且同一文件缩进宽度必须一致。
"""
from __future__ import annotations

from cnplus.diagnostics import (CN0101_非法字符, CN0102_未闭合字符串,
                                CN0103_非法数字, 诊断袋)
from cnplus.lexer.normalize import 归一化
from cnplus.lexer.tokens import (关键字映射, 标点映射, 种类, 运算符映射, 词元)
from cnplus.source import 源文件

# 运算符按长度倒序，保证 "<=" 先于 "<" 匹配
def _运算符按长度() -> list[tuple[str, 种类]]:
    return sorted(运算符映射().items(), key=lambda kv: -len(kv[0]))


class 词法器:
    def __init__(self, 源: 源文件, 袋: 诊断袋 | None = None) -> None:
        self.源 = 源
        self.原文 = 源.文本
        self.文本 = 归一化(源.文本)  # 一对一映射，偏移仍对得上
        self.袋 = 袋 if 袋 is not None else 诊断袋()
        self.位 = 0
        self.词元们: list[词元] = []
        self.缩进栈: list[int] = [0]
        self.括号深度 = 0

    # ---- 基础工具 ----
    def _到头(self) -> bool:
        return self.位 >= len(self.文本)

    def _看(self, 偏 : int = 0) -> str:
        i = self.位 + 偏
        return self.文本[i] if i < len(self.文本) else ""

    def _跨(self, 起: int, 止: int):
        return self.源.跨度于(起, 止)

    def _推(self, 种: 种类, 起: int, 止: int, 值: object = None) -> None:
        self.词元们.append(词元(种=种, 文本=self.原文[起:止], 跨=self._跨(起, 止), 值=值))

    # ---- 主循环 ----
    def 扫描(self) -> tuple[list[词元], 诊断袋]:
        self._行首缩进()
        while not self._到头():
            self._一个词元()
        # 收尾：补齐退缩
        止 = len(self.文本)
        if self.词元们 and self.词元们[-1].种 not in (种类.换行, 种类.退缩):
            self._推(种类.换行, 止, 止)
        while len(self.缩进栈) > 1:
            self.缩进栈.pop()
            self._推(种类.退缩, 止, 止)
        self._推(种类.文件尾, 止, 止)
        return self.词元们, self.袋

    def _一个词元(self) -> None:
        字 = self._看()
        起 = self.位

        # 注释：# 到行尾
        if 字 == "#":
            while not self._到头() and self._看() != "\n":
                self.位 += 1
            return

        # 换行
        if 字 == "\n":
            self.位 += 1
            if self.括号深度 > 0:
                return  # 括号内换行不算语句结束
            if self.词元们 and self.词元们[-1].种 is not 种类.换行:
                self._推(种类.换行, 起, self.位)
            self._行首缩进()
            return

        # 行内空白
        if 字 in " \t\r":
            self.位 += 1
            return

        # 数字
        if 字.isdigit():
            return self._数字()

        # 字符串
        if 字 in "\"'":
            return self._字符串()

        # 标识符/关键字（中文、字母、下划线开头）
        if self._是标识符首(字):
            return self._标识符()

        # 运算符
        for 符, 种 in _运算符按长度():
            if self.文本.startswith(符, self.位):
                self.位 += len(符)
                self._推(种, 起, self.位)
                return

        # 标点
        if 字 in 标点映射():
            种 = 标点映射()[字]
            self.位 += 1
            if 种 in (种类.左括号, 种类.左方括号, 种类.左花括号):
                self.括号深度 += 1
            elif 种 in (种类.右括号, 种类.右方括号, 种类.右花括号):
                self.括号深度 = max(0, self.括号深度 - 1)
            self._推(种, 起, self.位)
            return

        # 非法字符：报告后跳过，继续扫描
        self.位 += 1
        self.袋.报告(CN0101_非法字符, f"无法识别的字符 {字!r}", self._跨(起, self.位),
                   解释=f"CNplus 看不懂 {字!r} 这个符号，不知道拿它做什么",
                   提示="删掉它；如果你想把它当文字用，请放进引号里，例如 \"…\"")
        self._推(种类.非法, 起, self.位)

    # ---- 各类词元 ----
    @staticmethod
    def _是标识符首(字: str) -> bool:
        return 字.isalpha() or 字 == "_" or ord(字) > 0x2FFF

    @staticmethod
    def _是标识符续(字: str) -> bool:
        return 字.isalnum() or 字 == "_" or ord(字) > 0x2FFF

    def _标识符(self) -> None:
        起 = self.位
        while not self._到头() and self._是标识符续(self._看()):
            self.位 += 1
        词 = self.文本[起 : self.位]
        种 = 关键字映射().get(词, 种类.标识符)
        值 = None
        if 种 is 种类.真:
            值 = True
        elif 种 is 种类.假:
            值 = False
        self._推(种, 起, self.位, 值)

    def _数字(self) -> None:
        起 = self.位
        while not self._到头() and self._看().isdigit():
            self.位 += 1
        是小数 = False
        if self._看() == "." and self._看(1).isdigit():
            是小数 = True
            self.位 += 1
            while not self._到头() and self._看().isdigit():
                self.位 += 1
        # 数字后紧跟标识符字符是错误：123abc
        if not self._到头() and self._是标识符续(self._看()):
            while not self._到头() and self._是标识符续(self._看()):
                self.位 += 1
            self.袋.报告(CN0103_非法数字,
                       f"数字后面不能紧接着写 {self.文本[起:self.位]!r}",
                       self._跨(起, self.位),
                       解释="数字和名字必须分开，否则看不出哪里是数字、哪里是名字",
                       提示="中间加个空格，或者加运算符，例如 123 * abc")
            self._推(种类.非法, 起, self.位)
            return
        文 = self.文本[起 : self.位]
        if 是小数:
            self._推(种类.小数, 起, self.位, float(文))
        else:
            self._推(种类.整数, 起, self.位, int(文))

    def _字符串(self) -> None:
        起 = self.位
        引 = self._看()
        self.位 += 1
        块: list[str] = []
        while True:
            if self._到头() or self._看() == "\n":
                self.袋.报告(CN0102_未闭合字符串, "字符串没有闭合", self._跨(起, self.位),
                           解释=f"文字要用一对 {引} 前后夹住，你只写了前面那个",
                           提示=f"在这一行的末尾补一个 {引}")
                self._推(种类.非法, 起, self.位)
                return
            字 = self._看()
            if 字 == "\\":
                下 = self._看(1)
                块.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(下, 下))
                self.位 += 2
                continue
            if 字 == 引:
                self.位 += 1
                self._推(种类.字符串, 起, self.位, "".join(块))
                return
            # 关键：字符串内容取**原文**，不取归一化后的文本 ——
            # 全角标点在字符串里是数据，不是语法。
            块.append(self.原文[self.位])
            self.位 += 1

    # ---- 缩进 ----
    def _行首缩进(self) -> None:
        """在行首统计空格，产生 缩进/退缩 词元。空行与注释行不参与。"""
        起 = self.位
        宽 = 0
        while not self._到头():
            字 = self._看()
            if 字 == " ":
                宽 += 1
                self.位 += 1
            elif 字 == "\t":
                宽 += 4
                self.位 += 1
            else:
                break
        # 空行或纯注释行：不影响缩进栈
        if self._到头() or self._看() in "\n#":
            return
        当前 = self.缩进栈[-1]
        if 宽 > 当前:
            self.缩进栈.append(宽)
            self._推(种类.缩进, 起, self.位)
        elif 宽 < 当前:
            while len(self.缩进栈) > 1 and self.缩进栈[-1] > 宽:
                self.缩进栈.pop()
                self._推(种类.退缩, self.位, self.位)


def 扫描(源: 源文件, 袋: 诊断袋 | None = None) -> tuple[list[词元], 诊断袋]:
    """便捷入口。"""
    return 词法器(源, 袋).扫描()
