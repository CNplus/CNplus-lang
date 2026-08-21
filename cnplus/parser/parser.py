"""Pratt 解析器 + 错误恢复。

**恒返回 (程序, 诊断袋)，永不抛异常** —— 这是 D-005，编辑器依赖此性质：
你敲的代码永远是半成品，一遇错就死会让高亮和补全全部消失。

恢复策略：恐慌模式。报错后跳到同步点（换行 / 退缩 / 语句起始关键字 / 文件尾），
在原地填入 错误语句/错误表达式 占位，继续解析后面的内容。
"""
from __future__ import annotations

from cnplus.diagnostics import (CN0201_期望词元, CN0202_意外词元,
                                CN0203_期望表达式, CN0204_期望缩进, 诊断袋)
from cnplus.lexer.lexer import 扫描
from cnplus.lexer.tokens import 种类, 词元
from cnplus.parser.ast import (一元运算, 一元表达式, 二元运算, 二元表达式,
                               函数声明, 变量引用, 声明语句, 如果语句, 字符串字面量,
                               小数字面量, 布尔字面量, 循环语句, 整数字面量,
                               程序, 空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句,
                               错误表达式, 错误语句)
from cnplus.source import 合并跨度, 源文件, 跨度

# 中缀优先级（越大越紧）
_中缀优先级: dict[种类, int] = {
    种类.或: 1,
    种类.与: 2,
    种类.等于: 3, 种类.不等于: 3,
    种类.小于: 4, 种类.小于等于: 4, 种类.大于: 4, 种类.大于等于: 4,
    种类.加: 5, 种类.减: 5,
    种类.乘: 6, 种类.除: 6, 种类.整除: 6, 种类.取余: 6,
}

_中缀运算: dict[种类, 二元运算] = {
    种类.加: 二元运算.加, 种类.减: 二元运算.减,
    种类.乘: 二元运算.乘, 种类.除: 二元运算.除,
    种类.整除: 二元运算.整除, 种类.取余: 二元运算.取余,
    种类.等于: 二元运算.等于, 种类.不等于: 二元运算.不等于,
    种类.小于: 二元运算.小于, 种类.小于等于: 二元运算.小于等于,
    种类.大于: 二元运算.大于, 种类.大于等于: 二元运算.大于等于,
    种类.与: 二元运算.与, 种类.或: 二元运算.或,
}

_调用优先级 = 7

# 语句起始关键字 —— 恐慌模式的同步点
_语句起始 = {种类.令, 种类.如果, 种类.循环, 种类.函数, 种类.返回, 种类.外部}


class _恢复(Exception):
    """内部信号：当前语句放弃，跳到同步点。绝不逃出 解析()。"""


class 解析器:
    def __init__(self, 源: 源文件, 袋: 诊断袋 | None = None) -> None:
        self.源 = 源
        self.袋 = 袋 if 袋 is not None else 诊断袋()
        self.词元们, _ = 扫描(源, self.袋)
        self.位 = 0

    # ---- 词元游标 ----
    @property
    def 当前(self) -> 词元:
        return self.词元们[min(self.位, len(self.词元们) - 1)]

    def _看种(self, 偏: int = 0) -> 种类:
        i = min(self.位 + 偏, len(self.词元们) - 1)
        return self.词元们[i].种

    def _到头(self) -> bool:
        return self._看种() is 种类.文件尾

    def _吃(self) -> 词元:
        t = self.当前
        if not self._到头():
            self.位 += 1
        return t

    def _匹配(self, *种: 种类) -> bool:
        if self._看种() in 种:
            self._吃()
            return True
        return False

    def _期望(self, 种: 种类, 什么: str) -> 词元:
        if self._看种() is 种:
            return self._吃()
        self.袋.报告(CN0201_期望词元, f"这里需要{什么}，却遇到 {self._描述当前()}",
                   self.当前.跨, 提示=f"补上{什么}")
        raise _恢复

    def _描述当前(self) -> str:
        t = self.当前
        if t.种 is 种类.文件尾:
            return "文件结尾"
        if t.种 is 种类.换行:
            return "行尾"
        if t.种 is 种类.缩进:
            return "缩进"
        if t.种 is 种类.退缩:
            return "缩进结束"
        return f"{t.文本!r}"

    def _跨到此(self, 起: 跨度) -> 跨度:
        末 = self.词元们[max(0, self.位 - 1)].跨
        return 合并跨度(起, 末)

    # ---- 恐慌模式恢复 ----
    def _同步(self) -> None:
        """跳到下一个安全点，让后续语句还能正常解析。"""
        while not self._到头():
            if self._看种() in (种类.换行, 种类.退缩):
                self._吃()
                return
            if self._看种() in _语句起始:
                return
            self._吃()

    # ---- 入口 ----
    def 解析(self) -> tuple[程序, 诊断袋]:
        语句们: list[语句] = []
        起跨 = self.当前.跨
        while not self._到头():
            if self._匹配(种类.换行, 种类.缩进, 种类.退缩):
                continue
            前位 = self.位
            try:
                语句们.append(self._语句())
            except _恢复:
                坏跨 = self.当前.跨
                self._同步()
                语句们.append(错误语句(跨=坏跨, 说明="语句解析失败"))
            # 保险：确保推进，绝不死循环
            if self.位 == 前位:
                self._吃()
        末跨 = self.当前.跨
        return 程序(语句们=tuple(语句们), 跨=合并跨度(起跨, 末跨)), self.袋

    # ---- 语句 ----
    def _语句(self) -> 语句:
        种 = self._看种()
        if 种 is 种类.令:
            return self._声明()
        if 种 is 种类.如果:
            return self._如果()
        if 种 is 种类.循环:
            return self._循环()
        if 种 is 种类.函数:
            return self._函数()
        if 种 is 种类.返回:
            return self._返回()
        if 种 is 种类.外部:
            return self._赋值(是外部=True)
        # 标识符 = ... 是赋值；否则是表达式语句
        if 种 is 种类.标识符 and self._看种(1) is 种类.赋值:
            return self._赋值()
        return self._表达式语句()

    def _行尾(self) -> None:
        """语句必须以换行或文件尾结束。"""
        if self._看种() in (种类.换行, 种类.文件尾, 种类.退缩):
            self._匹配(种类.换行)
            return
        self.袋.报告(CN0202_意外词元, f"语句写完了，但后面还有 {self._描述当前()}",
                   self.当前.跨, 提示="一行只写一条语句")
        raise _恢复

    def _声明(self) -> 语句:
        起 = self._吃().跨  # 令
        名词元 = self._期望(种类.标识符, "变量名")
        self._期望(种类.赋值, "等号 =")
        值 = self._表达式()
        self._行尾()
        return 声明语句(名=名词元.文本, 值=值, 跨=self._跨到此(起), 名跨=名词元.跨)

    def _赋值(self, 是外部: bool = False) -> 语句:
        起 = self.当前.跨
        if 是外部:
            self._吃()  # 外部
        名词元 = self._期望(种类.标识符, "变量名")
        self._期望(种类.赋值, "等号 =")
        值 = self._表达式()
        self._行尾()
        return 赋值语句(名=名词元.文本, 值=值, 跨=self._跨到此(起),
                     是外部=是外部, 名跨=名词元.跨)

    def _表达式语句(self) -> 语句:
        起 = self.当前.跨
        表 = self._表达式()
        self._行尾()
        return 表达式语句(表达=表, 跨=self._跨到此(起))

    def _块(self) -> tuple[语句, ...]:
        """解析缩进块。要求：换行 + 缩进 ... 退缩。"""
        self._匹配(种类.换行)
        if self._看种() is not 种类.缩进:
            self.袋.报告(CN0204_期望缩进, "这里需要一个缩进块", self.当前.跨,
                       提示="把块内的语句往右缩进 4 个空格")
            raise _恢复
        self._吃()  # 缩进
        语句们: list[语句] = []
        while not self._到头() and self._看种() is not 种类.退缩:
            if self._匹配(种类.换行):
                continue
            前位 = self.位
            try:
                语句们.append(self._语句())
            except _恢复:
                坏跨 = self.当前.跨
                self._同步()
                语句们.append(错误语句(跨=坏跨, 说明="块内语句解析失败"))
            if self.位 == 前位:
                self._吃()
        self._匹配(种类.退缩)
        return tuple(语句们)

    def _如果(self) -> 语句:
        起 = self._吃().跨  # 如果
        条件 = self._表达式()
        主体 = self._块()
        否则体: tuple[语句, ...] = ()
        # 跳过块之间的空行
        存位 = self.位
        while self._看种() is 种类.换行:
            self._吃()
        if self._看种() is 种类.否则:
            self._吃()
            否则体 = self._块()
        else:
            self.位 = 存位
        return 如果语句(条件=条件, 主体=主体, 否则体=否则体, 跨=self._跨到此(起))

    def _循环(self) -> 语句:
        起 = self._吃().跨
        条件 = self._表达式()
        主体 = self._块()
        return 循环语句(条件=条件, 主体=主体, 跨=self._跨到此(起))

    def _函数(self) -> 语句:
        起 = self._吃().跨
        名词元 = self._期望(种类.标识符, "函数名")
        self._期望(种类.左括号, "左括号 (")
        形参: list[str] = []
        形参跨们: list[跨度] = []
        if self._看种() is not 种类.右括号:
            while True:
                p = self._期望(种类.标识符, "参数名")
                形参.append(p.文本)
                形参跨们.append(p.跨)
                if not self._匹配(种类.逗号):
                    break
        self._期望(种类.右括号, "右括号 )")
        主体 = self._块()
        return 函数声明(名=名词元.文本, 形参=tuple(形参), 主体=主体,
                     跨=self._跨到此(起), 形参跨们=tuple(形参跨们))

    def _返回(self) -> 语句:
        起 = self._吃().跨
        值: 表达式 | None = None
        if self._看种() not in (种类.换行, 种类.文件尾, 种类.退缩):
            值 = self._表达式()
        self._行尾()
        return 返回语句(值=值, 跨=self._跨到此(起))

    # ---- 表达式（Pratt） ----
    def _表达式(self, 最小优先级: int = 0) -> 表达式:
        左 = self._前缀()
        while True:
            种 = self._看种()
            if 种 is 种类.左括号 and _调用优先级 > 最小优先级:
                左 = self._调用(左)
                continue
            优 = _中缀优先级.get(种)
            if 优 is None or 优 <= 最小优先级:
                break
            运算 = _中缀运算[种]
            self._吃()
            右 = self._表达式(优)
            左 = 二元表达式(运算=运算, 左=左, 右=右, 跨=合并跨度(左.跨, 右.跨))
        return 左

    def _调用(self, 被调: 表达式) -> 表达式:
        self._吃()  # (
        实参: list[表达式] = []
        if self._看种() is not 种类.右括号:
            while True:
                实参.append(self._表达式())
                if not self._匹配(种类.逗号):
                    break
        右括号 = self._期望(种类.右括号, "右括号 )")
        return 调用表达式(被调=被调, 实参=tuple(实参),
                       跨=合并跨度(被调.跨, 右括号.跨))

    def _前缀(self) -> 表达式:
        t = self.当前
        种 = t.种
        if 种 is 种类.整数:
            self._吃()
            return 整数字面量(值=t.值, 跨=t.跨)
        if 种 is 种类.小数:
            self._吃()
            return 小数字面量(值=t.值, 跨=t.跨)
        if 种 is 种类.字符串:
            self._吃()
            return 字符串字面量(值=t.值, 跨=t.跨)
        if 种 in (种类.真, 种类.假):
            self._吃()
            return 布尔字面量(值=(种 is 种类.真), 跨=t.跨)
        if 种 is 种类.空:
            self._吃()
            return 空字面量(跨=t.跨)
        if 种 is 种类.标识符:
            self._吃()
            return 变量引用(名=t.文本, 跨=t.跨)
        if 种 is 种类.减:
            self._吃()
            操作数 = self._表达式(_调用优先级)
            return 一元表达式(运算=一元运算.负, 操作数=操作数,
                          跨=合并跨度(t.跨, 操作数.跨))
        if 种 is 种类.非:
            self._吃()
            操作数 = self._表达式(2)
            return 一元表达式(运算=一元运算.非, 操作数=操作数,
                          跨=合并跨度(t.跨, 操作数.跨))
        if 种 is 种类.左括号:
            self._吃()
            内 = self._表达式()
            self._期望(种类.右括号, "右括号 )")
            return 内
        if 种 is 种类.非法:
            # lexer 已报过错，这里静默吃掉，避免重复报告
            self._吃()
            return 错误表达式(跨=t.跨, 说明="非法词元")
        self.袋.报告(CN0203_期望表达式, f"这里需要一个表达式，却遇到 {self._描述当前()}",
                   t.跨, 提示="表达式可以是数字、字符串、变量名或括号表达式")
        raise _恢复


def 解析(源: 源文件, 袋: 诊断袋 | None = None) -> tuple[程序, 诊断袋]:
    """便捷入口。**永不抛异常**（D-005）。"""
    return 解析器(源, 袋).解析()
