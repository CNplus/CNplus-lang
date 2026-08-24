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
                               调用表达式, 赋值语句, 返回语句, 导入语句, 成员访问,
                               列表字面量, 字典字面量, 索引访问, 索引赋值语句,
                               遍历语句, 跳出语句, 继续语句, 自增语句,
                               格式串, 多重声明语句, 尝试语句, 抛出语句,
                               错误表达式, 错误语句, 一元表达式)

def _取内置名() -> set[str]:
    """从内置表自动取名单，避免加了内置函数忘了同步（曾漏 8 个）。"""
    from cnplus.backends.treewalk.evaluator import 内置表
    return {名 for 名, _, _ in 内置表(lambda *a: None)}


_内置名 = _取内置名()


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


def _相似度(甲: str, 乙: str) -> int:
    """编辑距离，用来猜「你是不是想写…」。"""
    if abs(len(甲) - len(乙)) > 2:
        return 99
    上一行 = list(range(len(乙) + 1))
    for i, a in enumerate(甲, 1):
        这一行 = [i]
        for j, b in enumerate(乙, 1):
            这一行.append(min(上一行[j] + 1, 这一行[j - 1] + 1,
                            上一行[j - 1] + (a != b)))
        上一行 = 这一行
    return 上一行[-1]


def 提示_未声明(名: str) -> str:
    """CN0302 的兜底提示：两种常见意图并列，让用户对号入座。

    - 想当一段文字用 → 忘了加引号（`设 名字 = 小明` 这种，八成想写 "小明"）
    - 想当变量用 → 还没用「设」建立过
    """
    return (f"两种可能：一是想把「{名}」当一段文字，给它加上双引号 "
            f"（例如 设 名字 = \"{名}\"）；二是想用变量，但还没建立它 "
            f"（先写 设 {名} = …）")


class 检查器:
    def __init__(self, 袋: 诊断袋) -> None:
        self.袋 = 袋

    @staticmethod
    def _近似提示(名: str, 域: "_作用域") -> str:
        """名字写错时，猜猜用户想写哪个已有的名字。

        中文的编辑距离区分度差（小明/小写距离也是 1），所以
        只在「真的很像」时才猜：距离 ≤1，且与候选共享的前缀
        覆盖了名字的大半。否则给两种常见意图的并列提示。
        """
        候选 = []
        环 = 域
        while 环 is not None:
            候选.extend(环.名字)
            环 = 环.父
        # 「真的很像」只认两种铁证：
        # 1) 名字是候选的扩展（年龄x ⊃ 年龄 —— 手滑多打了字）
        # 2) 纯 ASCII 名距离 ≤2（英文拼写错误，如 helo/hello）
        # 中文之间不做模糊猜测：小明/小写/小数 距离同为 1，
        # 数学上无法区分，猜了就是误导。
        最好, 最近 = None, 99
        for c in 候选:
            d = _相似度(名, c)
            if d < 最近:
                最好, 最近 = c, d
        if 最好 is not None:
            if len(名) > len(最好) and 名.startswith(最好):
                return f"是不是想写「{最好}」？（多打了后面的字符）"
            if 名.isascii() and 最好.isascii() and 最近 <= 2:
                return f"是不是想写「{最好}」？"
        return 提示_未声明(名)

    def _只查名字(self, e: 表达式, 域: _作用域) -> None:
        """短路右侧：只检查变量是否声明，不做「必然出错」判断。"""
        if isinstance(e, 变量引用):
            if not 域.有(e.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {e.名} 还没有声明过", e.跨,
                          解释=f"CNplus 不认识 {e.名}，因为你还没告诉它这个名字代表什么",
                          提示=self._近似提示(e.名, 域))
            return
        if isinstance(e, 一元表达式):
            self._只查名字(e.操作数, 域)
            return
        if isinstance(e, 二元表达式):
            self._只查名字(e.左, 域)
            self._只查名字(e.右, 域)
            return
        if isinstance(e, 调用表达式):
            self._只查名字(e.被调, 域)
            for a in e.实参:
                self._只查名字(a, 域)
            return
        if isinstance(e, 索引访问):
            self._只查名字(e.对象, 域)
            self._只查名字(e.下标, 域)
            return
        if isinstance(e, 成员访问):
            self._只查名字(e.对象, 域)
            return
        if isinstance(e, 列表字面量):
            for x in e.元素:
                self._只查名字(x, 域)
            return
        if isinstance(e, 字典字面量):
            for 键, 值 in e.键值对:
                self._只查名字(键, 域)
                self._只查名字(值, 域)
            return

    def 检查(self, 程: 程序) -> None:
        # 内置名放在**父作用域**，用户顶层是它的子作用域。
        # 这样 `设 查找 = 1` / `函数 查找(...)` 都能遮蔽内置名而不报
        # CN0307 —— 遮蔽是允许的，只有用户自己重复声明才算重复。
        内置域 = _作用域()
        for 名 in _内置名:
            内置域.加(名)
        顶层 = _作用域(内置域)
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
                          解释=f"{s.名} 这个名字已经有主了，同一层里不能再建一个同名的",
                          提示=f"想改它的值，直接写 {s.名} = 新值（不要再写「设」）")
            域.加(s.名)
            return
        if isinstance(s, 赋值语句):
            self._表达式(s.值, 域)
            if not 域.有(s.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {s.名} 还没有声明过", s.跨,
                          解释=f"CNplus 不认识 {s.名}，因为你还没告诉它这个名字代表什么",
                          提示=提示_未声明(s.名))
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
            # 默认值在定义处的外层作用域求值，先检查
            默认们 = s.默认值们 or ()
            for d in 默认们:
                if d is not None:
                    self._表达式(d, 域)
            for p in s.形参:
                内.加(p)
            # 允许递归
            内.加(s.名)
            self._块(s.主体, 内)
            return
        if isinstance(s, 自增语句):
            if not 域.有(s.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {s.名} 还没有声明过", s.跨,
                          解释=f"CNplus 不认识 {s.名}，没法给它加减",
                          提示=self._近似提示(s.名, 域))
            return
        if isinstance(s, 多重声明语句):
            self._表达式(s.值, 域)
            for 名 in s.名们:
                域.加(名)
            return
        if isinstance(s, 尝试语句):
            self._块(s.主体, _作用域(域))
            if s.捕获体 is not None:
                捕获域 = _作用域(域)
                if s.捕获变量 is not None:
                    捕获域.加(s.捕获变量)
                self._块(s.捕获体, 捕获域)
            if s.最后体 is not None:
                self._块(s.最后体, _作用域(域))
            return
        if isinstance(s, 抛出语句):
            self._表达式(s.值, 域)
            return
        if isinstance(s, 导入语句):
            # 模块名不是变量；只把别名登记进作用域，之后就能用 别名.成员
            名 = s.别名 or s.模块.rpartition(".")[2] or s.模块
            域.加(名)
            return
        if isinstance(s, 遍历语句):
            self._表达式(s.可迭代, 域)
            内 = _作用域(域)
            内.加(s.变量)
            self._块(s.主体, 内)
            return
        if isinstance(s, (跳出语句, 继续语句)):
            return
        if isinstance(s, 索引赋值语句):
            self._表达式(s.对象, 域)
            self._表达式(s.下标, 域)
            self._表达式(s.值, 域)
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
                      f"条件必须是布尔值（真 或 假），这里是{类型}", e.跨,
                      解释="判断的位置只能放「成立/不成立」的问题，不能直接放一个数或一段文字",
                      提示="写成一句能回答真/假的话，例如 x > 0、x != 0、名字 == \"小明\"")

    def _表达式(self, e: 表达式, 域: _作用域) -> None:
        if isinstance(e, 错误表达式):
            return
        if isinstance(e, 变量引用):
            if not 域.有(e.名):
                self.袋.报告(CN0302_未声明变量,
                          f"变量 {e.名} 还没有声明过", e.跨,
                          解释=f"CNplus 不认识 {e.名}，因为你还没告诉它这个名字代表什么",
                          提示=self._近似提示(e.名, 域))
            return
        if isinstance(e, 一元表达式):
            self._表达式(e.操作数, 域)
            return
        if isinstance(e, 二元表达式):
            self._表达式(e.左, 域)
            # 与/或 短路：右侧可能永不执行，只查变量名不查「必然出错」类问题，
            # 否则 `真 或 1 / 0` 会被误报。宁可漏报也不误报。
            if e.运算 in (二元运算.与, 二元运算.或):
                self._只查名字(e.右, 域)
                return
            self._表达式(e.右, 域)
            # 除以字面量零 —— 能百分百确定
            if e.运算 in (二元运算.除, 二元运算.整除, 二元运算.取余):
                零 = ((isinstance(e.右, 整数字面量) and e.右.值 == 0)
                     or (isinstance(e.右, 小数字面量) and e.右.值 == 0.0))
                if 零:
                    self.袋.报告(CN0304_除以零, "除数不能是零", e.跨,
                              解释="东西没法平均分给 0 个人，这在数学上没有答案",
                              提示="把除数改成非零的数")
            return
        if isinstance(e, 调用表达式):
            self._表达式(e.被调, 域)
            for a in e.实参:
                self._表达式(a, 域)
            for _名, 值 in e.关键字参数:
                self._表达式(值, 域)
            return
        if isinstance(e, 成员访问):
            self._表达式(e.对象, 域)
            return
        if isinstance(e, 格式串):
            for 段 in e.部分:
                if not isinstance(段, str):
                    self._表达式(段, 域)
            return
        if isinstance(e, 列表字面量):
            for x in e.元素:
                self._表达式(x, 域)
            return
        if isinstance(e, 字典字面量):
            for 键, 值 in e.键值对:
                self._表达式(键, 域)
                self._表达式(值, 域)
            return
        if isinstance(e, 索引访问):
            self._表达式(e.对象, 域)
            self._表达式(e.下标, 域)
            return


def 检查(程: 程序, 袋: 诊断袋) -> 诊断袋:
    """在诊断袋里追加静态检查发现的问题。"""
    检查器(袋).检查(程)
    return 袋
