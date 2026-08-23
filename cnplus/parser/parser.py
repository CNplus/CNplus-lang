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
                               调用表达式, 赋值语句, 返回语句, 导入语句, 成员访问,
                               列表字面量, 字典字面量, 索引访问, 索引赋值语句,
                               遍历语句, 跳出语句, 继续语句, 自增语句,
                               格式串, 多重声明语句, 尝试语句, 抛出语句,
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
    种类.幂: 7,
}

# 右结合的运算符（幂：2**3**2 = 2**(3**2)）
_右结合 = {种类.幂}

_中缀运算: dict[种类, 二元运算] = {
    种类.加: 二元运算.加, 种类.减: 二元运算.减,
    种类.乘: 二元运算.乘, 种类.除: 二元运算.除,
    种类.整除: 二元运算.整除, 种类.取余: 二元运算.取余,
    种类.等于: 二元运算.等于, 种类.不等于: 二元运算.不等于,
    种类.小于: 二元运算.小于, 种类.小于等于: 二元运算.小于等于,
    种类.大于: 二元运算.大于, 种类.大于等于: 二元运算.大于等于,
    种类.与: 二元运算.与, 种类.或: 二元运算.或,
    种类.幂: 二元运算.幂,
}

_调用优先级 = 8

# 语句起始关键字 —— 恐慌模式的同步点
_语句起始 = {种类.令, 种类.如果, 种类.循环, 种类.函数, 种类.返回, 种类.外部,
           种类.导入, 种类.遍历, 种类.跳出, 种类.继续,
           种类.尝试, 种类.抛出}


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
                   self.当前.跨,
                   解释=f"这个位置必须写{什么}，CNplus 才知道你想做什么",
                   提示=f"在这里补上{什么}")
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
        if 种 is 种类.导入:
            return self._导入()
        if 种 is 种类.遍历:
            return self._遍历()
        if 种 is 种类.尝试:
            return self._尝试()
        if 种 is 种类.抛出:
            return self._抛出()
        if 种 is 种类.跳出:
            起 = self._吃().跨
            self._行尾()
            return 跳出语句(跨=起)
        if 种 is 种类.继续:
            起 = self._吃().跨
            self._行尾()
            return 继续语句(跨=起)
        # 标识符 后接 = / += / ++ 等 → 赋值类语句
        if 种 is 种类.标识符:
            下 = self._看种(1)
            if 下 is 种类.赋值:
                return self._赋值()
            if 下 in (种类.加赋, 种类.减赋, 种类.乘赋, 种类.除赋):
                return self._复合赋值()
            if 下 in (种类.自增, 种类.自减):
                return self._自增()
        return self._表达式语句()

    def _行尾(self) -> None:
        """语句必须以换行或文件尾结束。"""
        if self._看种() in (种类.换行, 种类.文件尾, 种类.退缩):
            self._匹配(种类.换行)
            return
        self.袋.报告(CN0202_意外词元, f"这一句已经写完了，后面却还有 {self._描述当前()}",
                   self.当前.跨,
                   解释="CNplus 认为这句到此结束，不知道多出来的部分是什么意思",
                   提示="一行只写一件事；想写两件事就分成两行")
        raise _恢复

    def _声明(self) -> 语句:
        起 = self._吃().跨  # 令
        名词元 = self._期望(种类.标识符, "变量名")
        # 多重声明：设 甲, 乙 = 表达式
        if self._看种() is 种类.逗号:
            名们 = [名词元.文本]
            while self._匹配(种类.逗号):
                名们.append(self._期望(种类.标识符, "变量名").文本)
            self._期望(种类.赋值, "等号 =")
            值 = self._表达式()
            self._行尾()
            return 多重声明语句(名们=tuple(名们), 值=值, 跨=self._跨到此(起))
        self._期望(种类.赋值, "等号 =")
        值 = self._表达式()
        self._行尾()
        return 声明语句(名=名词元.文本, 值=值, 跨=self._跨到此(起), 名跨=名词元.跨)

    def _复合赋值(self) -> 语句:
        起 = self.当前.跨
        名词元 = self._吃()  # 标识符
        符 = self._吃().种   # += -= *= /=
        运 = {种类.加赋: 二元运算.加, 种类.减赋: 二元运算.减,
             种类.乘赋: 二元运算.乘, 种类.除赋: 二元运算.除}[符]
        值 = self._表达式()
        self._行尾()
        return 赋值语句(名=名词元.文本, 值=值, 跨=self._跨到此(起),
                     名跨=名词元.跨, 复合=运)

    def _自增(self) -> 语句:
        起 = self.当前.跨
        名词元 = self._吃()  # 标识符
        符 = self._吃().种   # ++ / --
        self._行尾()
        return 自增语句(名=名词元.文本, 增量=(1 if 符 is 种类.自增 else -1),
                     跨=self._跨到此(起))

    def _导入(self) -> 语句:
        起 = self._吃().跨  # 导入
        模块词元 = self._期望(种类.字符串, "模块名（写在引号里）")
        别名 = None
        if self._看种() is 种类.作为:
            self._吃()
            名 = self._期望(种类.标识符, "别名")
            别名 = 名.文本
        self._行尾()
        return 导入语句(模块=模块词元.值, 别名=别名, 跨=self._跨到此(起))

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
        # 索引赋值：名单[0] = 值 / 字典["键"] = 值
        if isinstance(表, 索引访问) and self._看种() is 种类.赋值:
            self._吃()
            值 = self._表达式()
            self._行尾()
            return 索引赋值语句(对象=表.对象, 下标=表.下标, 值=值,
                           跨=self._跨到此(起))
        # 索引复合赋值：字典[键] += 1 → 字典[键] = 字典[键] + 1
        if isinstance(表, 索引访问) and self._看种() in (
                种类.加赋, 种类.减赋, 种类.乘赋, 种类.除赋):
            符 = self._吃().种
            运 = {种类.加赋: 二元运算.加, 种类.减赋: 二元运算.减,
                 种类.乘赋: 二元运算.乘, 种类.除赋: 二元运算.除}[符]
            右 = self._表达式()
            self._行尾()
            新值 = 二元表达式(运算=运, 左=表, 右=右,
                          跨=合并跨度(表.跨, 右.跨))
            return 索引赋值语句(对象=表.对象, 下标=表.下标, 值=新值,
                           跨=self._跨到此(起))
        self._行尾()
        return 表达式语句(表达=表, 跨=self._跨到此(起))

    def _块(self) -> tuple[语句, ...]:
        """解析缩进块。要求：换行 + 缩进 ... 退缩。"""
        self._匹配(种类.换行)
        if self._看种() is not 种类.缩进:
            self.袋.报告(CN0204_期望缩进, "这里需要一个缩进块", self.当前.跨,
                       解释="属于上一行的内容要往右挪一点，CNplus 靠这个看出「哪些属于它」",
                       提示="把下面这些行的开头加 4 个空格")
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
            # 否则 如果 …：解析成嵌套的 如果，作为否则体的唯一语句（elif）
            if self._看种() is 种类.如果:
                否则体 = (self._如果(),)
            else:
                否则体 = self._块()
        else:
            self.位 = 存位
        return 如果语句(条件=条件, 主体=主体, 否则体=否则体, 跨=self._跨到此(起))

    def _遍历(self) -> 语句:
        起 = self._吃().跨  # 遍历
        可迭代 = self._表达式()
        self._期望(种类.每个, "「每个」")
        变量 = self._期望(种类.标识符, "变量名")
        主体 = self._块()
        return 遍历语句(变量=变量.文本, 可迭代=可迭代, 主体=主体,
                     跨=self._跨到此(起), 变量跨=变量.跨)

    def _尝试(self) -> 语句:
        起 = self._吃().跨  # 尝试
        主体 = self._块()
        捕获变量: str | None = None
        捕获变量跨 = None
        捕获体: tuple[语句, ...] | None = None
        最后体: tuple[语句, ...] | None = None

        # 跳过块之间的空行（与 _如果 同样的处理）
        存位 = self.位
        while self._看种() is 种类.换行:
            self._吃()
        if self._看种() is 种类.捕获:
            self._吃()
            # 捕获 后面可以跟一个变量名接住错误说明，也可以不跟
            if self._看种() is 种类.标识符:
                变 = self._吃()
                捕获变量 = 变.文本
                捕获变量跨 = 变.跨
            捕获体 = self._块()
            存位 = self.位
            while self._看种() is 种类.换行:
                self._吃()
        if self._看种() is 种类.最后:
            self._吃()
            最后体 = self._块()
        else:
            self.位 = 存位

        if 捕获体 is None and 最后体 is None:
            self.袋.报告(CN0201_期望词元,
                       "「尝试」后面需要「捕获」或「最后」", self.当前.跨,
                       解释="光写「尝试」没有意义 —— 要么捕获错误，要么写「最后」收尾",
                       提示="补一段：捕获 错\\n    打印(错)")
        return 尝试语句(主体=主体, 捕获变量=捕获变量, 捕获体=捕获体,
                     最后体=最后体, 跨=self._跨到此(起),
                     捕获变量跨=捕获变量跨)

    def _抛出(self) -> 语句:
        起 = self._吃().跨  # 抛出
        值 = self._表达式()
        self._行尾()
        return 抛出语句(值=值, 跨=self._跨到此(起))

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
        默认值们: list[表达式 | None] = []
        见过默认 = False
        if self._看种() is not 种类.右括号:
            while True:
                p = self._期望(种类.标识符, "参数名")
                形参.append(p.文本)
                形参跨们.append(p.跨)
                # 默认值：参数名 = 表达式
                if self._看种() is 种类.赋值:
                    self._吃()
                    默认值们.append(self._表达式())
                    见过默认 = True
                else:
                    if 见过默认:
                        self.袋.报告(CN0202_意外词元,
                                   f"参数 {p.文本} 没有默认值，但它前面的参数有",
                                   p.跨,
                                   解释="有默认值的参数必须排在没默认值的后面",
                                   提示="把带默认值的参数挪到最后")
                    默认值们.append(None)
                if not self._匹配(种类.逗号):
                    break
        self._期望(种类.右括号, "右括号 )")
        主体 = self._块()
        return 函数声明(名=名词元.文本, 形参=tuple(形参), 主体=主体,
                     跨=self._跨到此(起), 形参跨们=tuple(形参跨们),
                     默认值们=tuple(默认值们))

    def _返回(self) -> 语句:
        起 = self._吃().跨
        值: 表达式 | None = None
        if self._看种() not in (种类.换行, 种类.文件尾, 种类.退缩):
            值 = self._表达式()
            # 多返回值：返回 甲, 乙
            if self._看种() is 种类.逗号:
                多 = [值]
                while self._匹配(种类.逗号):
                    多.append(self._表达式())
                self._行尾()
                return 返回语句(值=None, 跨=self._跨到此(起), 多值=tuple(多))
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
            if 种 is 种类.点 and _调用优先级 > 最小优先级:
                左 = self._成员(左)
                continue
            if 种 is 种类.左方括号 and _调用优先级 > 最小优先级:
                左 = self._索引(左)
                continue
            优 = _中缀优先级.get(种)
            if 优 is None or 优 <= 最小优先级:
                break
            运算 = _中缀运算[种]
            self._吃()
            # 右结合（幂）：右侧用 优-1，让同级运算向右聚合
            右 = self._表达式(优 - 1 if 种 in _右结合 else 优)
            左 = 二元表达式(运算=运算, 左=左, 右=右, 跨=合并跨度(左.跨, 右.跨))
        return 左

    def _成员(self, 对象: 表达式) -> 表达式:
        self._吃()  # .
        名 = self._期望(种类.标识符, "成员名")
        return 成员访问(对象=对象, 属性=名.文本, 跨=合并跨度(对象.跨, 名.跨))

    def _索引(self, 对象: 表达式) -> 表达式:
        self._吃()  # [
        下标 = self._表达式()
        右 = self._期望(种类.右方括号, "右方括号 ]")
        return 索引访问(对象=对象, 下标=下标, 跨=合并跨度(对象.跨, 右.跨))

    def _调用(self, 被调: 表达式) -> 表达式:
        self._吃()  # (
        实参: list[表达式] = []
        关键字: list[tuple[str, 表达式]] = []
        if self._看种() is not 种类.右括号:
            while True:
                # 关键字参数：名字 = 值（名字后紧跟 =）
                if (self._看种() is 种类.标识符
                        and self._看种(1) is 种类.赋值):
                    名 = self._吃()      # 标识符
                    self._吃()           # =
                    关键字.append((名.文本, self._表达式()))
                else:
                    if 关键字:
                        self.袋.报告(CN0202_意外词元,
                                   "普通参数不能排在「名字=值」参数后面",
                                   self.当前.跨,
                                   解释="带名字的参数要放在最后",
                                   提示="把不带名字的参数挪到前面")
                    实参.append(self._表达式())
                if not self._匹配(种类.逗号):
                    break
        右括号 = self._期望(种类.右括号, "右括号 )")
        return 调用表达式(被调=被调, 实参=tuple(实参),
                       跨=合并跨度(被调.跨, 右括号.跨),
                       关键字参数=tuple(关键字))

    def _列表(self) -> 表达式:
        起 = self._吃().跨  # [
        元素: list[表达式] = []
        self._跳过换行()
        if self._看种() is not 种类.右方括号:
            while True:
                self._跳过换行()
                元素.append(self._表达式())
                self._跳过换行()
                if not self._匹配(种类.逗号):
                    break
                self._跳过换行()
                # 允许尾随逗号：[1, 2, 3,]
                if self._看种() is 种类.右方括号:
                    break
        右 = self._期望(种类.右方括号, "右方括号 ]")
        return 列表字面量(元素=tuple(元素), 跨=合并跨度(起, 右.跨))

    def _字典(self) -> 表达式:
        起 = self._吃().跨  # {
        对们: list[tuple[表达式, 表达式]] = []
        self._跳过换行()
        if self._看种() is not 种类.右花括号:
            while True:
                self._跳过换行()
                键 = self._表达式()
                self._期望(种类.冒号, "冒号 :")
                值 = self._表达式()
                对们.append((键, 值))
                self._跳过换行()
                if not self._匹配(种类.逗号):
                    break
                self._跳过换行()
                if self._看种() is 种类.右花括号:
                    break
        右 = self._期望(种类.右花括号, "右花括号 }")
        return 字典字面量(键值对=tuple(对们), 跨=合并跨度(起, 右.跨))

    def _跳过换行(self) -> None:
        """字面量内部允许换行（括号深度已让 lexer 不产生换行词元，这里兜底）。"""
        while self._看种() in (种类.换行, 种类.缩进, 种类.退缩):
            self._吃()

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
        if 种 is 种类.插值符:
            self._吃()
            串 = self._期望(种类.字符串, '字符串（@ 后面要跟 "…"）')
            return self._解析格式串(串.值, 合并跨度(t.跨, 串.跨))
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
        if 种 is 种类.左方括号:
            return self._列表()
        if 种 is 种类.左花括号:
            return self._字典()
        if 种 is 种类.非法:
            # lexer 已报过错，这里静默吃掉，避免重复报告
            self._吃()
            return 错误表达式(跨=t.跨, 说明="非法词元")
        self.袋.报告(CN0203_期望表达式,
                   f"这里需要一个表达式（能算出值的东西），却遇到 {self._描述当前()}",
                   t.跨,
                   解释="这个位置要放一个「有值的东西」，比如 3、\"你好\"、某个名字，或 1 + 2",
                   提示="补上一个值，例如 0 或 \"\"")
        raise _恢复

    def _解析格式串(self, 文本: str, 跨: 跨度) -> 表达式:
        """把 "你好，{名字}，{年+1}岁" 切成 [str, 表达式, str, 表达式, str]。

        {{ 和 }} 是转义，表示字面的 { 和 }。每个 {…} 里的内容当作
        一个完整表达式解析（复用主解析器，跑一个子解析器）。
        """
        部分: list[object] = []
        缓: list[str] = []
        i = 0
        n = len(文本)
        while i < n:
            c = 文本[i]
            if c == "{" and i + 1 < n and 文本[i + 1] == "{":
                缓.append("{"); i += 2; continue
            if c == "}" and i + 1 < n and 文本[i + 1] == "}":
                缓.append("}"); i += 2; continue
            if c == "{":
                j = 文本.find("}", i + 1)
                if j == -1:
                    self.袋.报告(CN0203_期望表达式,
                               "插值字符串里的 { 没有配对的 }", 跨,
                               解释="{ 用来标出「要嵌入的值」，必须有 } 收尾",
                               提示='例如 @"你好，{名字}"')
                    break
                if 缓:
                    部分.append("".join(缓)); 缓 = []
                表达式源 = 文本[i + 1 : j].strip()
                子 = 解析器(源文件(表达式源, "<插值>"), self.袋)
                部分.append(子._表达式())
                i = j + 1
                continue
            缓.append(c); i += 1
        if 缓:
            部分.append("".join(缓))
        return 格式串(部分=tuple(部分), 跨=跨)


def 解析(源: 源文件, 袋: 诊断袋 | None = None) -> tuple[程序, 诊断袋]:
    """便捷入口。**永不抛异常**（D-005）。"""
    return 解析器(源, 袋).解析()
