"""树遍历求值器 —— 阶段 0 的后端。

**语义约定在这里落实，不继承 Python**（见计划第三节「语义泄漏防御」）：
- 严格真值：条件必须是布尔，`如果 0` 报 CN0301
- 跨类型比较报错，不是返回假
- 未声明变量读取报错
- 除以零报错
"""
from __future__ import annotations

from cnplus.backends.base import 后端, 运行时错误
from cnplus.diagnostics import (CN0301_条件必须是布尔, CN0302_未声明变量,
                                CN0303_类型不匹配, CN0304_除以零, CN0305_不可调用,
                                CN0306_实参数量不符, CN0307_重复声明, 诊断袋)
from cnplus.parser.ast import (一元运算, 一元表达式, 二元运算, 二元表达式,
                               函数声明, 变量引用, 声明语句, 如果语句, 字符串字面量,
                               小数字面量, 布尔字面量, 循环语句, 整数字面量,
                               程序, 空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句,
                               错误表达式, 错误语句)
from cnplus.runtime.values import 函数值, 类型名, 显示
from cnplus.source import 源文件


class _返回信号(Exception):
    def __init__(self, 值: object) -> None:
        super().__init__("返回")
        self.值 = 值


class 环境:
    def __init__(self, 父: 环境 | None = None) -> None:
        self.表: dict[str, object] = {}
        self.父 = 父

    def 声明(self, 名: str, 值: object) -> None:
        self.表[名] = 值

    def 取(self, 名: str) -> tuple[bool, object]:
        环 = self
        while 环 is not None:
            if 名 in 环.表:
                return True, 环.表[名]
            环 = 环.父
        return False, None

    def 有本地(self, 名: str) -> bool:
        return 名 in self.表

    def 赋值(self, 名: str, 值: object) -> bool:
        """就地更新已存在的变量。找不到返回 False。"""
        环 = self
        while 环 is not None:
            if 名 in 环.表:
                环.表[名] = 值
                return True
            环 = 环.父
        return False


class 树遍历后端(后端):
    名称 = "树遍历"

    def __init__(self, 输出=None) -> None:
        self.输出行: list[str] = []
        self._输出回调 = 输出

    # ---- 入口 ----
    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        全局 = 环境()
        self._装内置(全局)
        try:
            self._执行块(程.语句们, 全局)
        except 运行时错误 as e:
            袋.报告(e.码, e.消息, e.跨, 提示=e.提示, 解释=e.解释)
        except _返回信号 as e:
            del e  # 顶层 返回 直接结束程序

    def _打印(self, *值们: object) -> None:
        行 = " ".join(显示(v) for v in 值们)
        self.输出行.append(行)
        if self._输出回调:
            self._输出回调(行)
        else:
            print(行)

    def _装内置(self, 环: 环境) -> None:
        import random

        环.声明("打印", _内置("打印", -1, lambda *a: self._打印(*a)))
        环.声明("随机数", _内置("随机数", 2, lambda a, b: random.randint(a, b)))
        环.声明("长度", _内置("长度", 1, lambda a: len(a)))
        环.声明("类型", _内置("类型", 1, lambda a: 类型名(a)))
        环.声明("整数", _内置("整数", 1, lambda a: int(a)))
        环.声明("小数", _内置("小数", 1, lambda a: float(a)))
        环.声明("文本", _内置("文本", 1, lambda a: 显示(a)))

    # ---- 语句 ----
    def _执行块(self, 语句们: tuple[语句, ...], 环: 环境) -> None:
        for s in 语句们:
            self._执行语句(s, 环)

    def _执行语句(self, s: 语句, 环: 环境) -> None:
        if isinstance(s, 错误语句):
            return  # 解析已报错，跳过
        if isinstance(s, 声明语句):
            if 环.有本地(s.名):
                raise 运行时错误(CN0307_重复声明,
                              f"变量 {s.名} 在这个作用域已经声明过了", s.跨,
                              解释=f"{s.名} 这个名字已经有主了，同一层里不能再建一个同名的",
                              提示=f"想改它的值，直接写 {s.名} = 新值（不要再写「设」）")
            环.声明(s.名, self._求值(s.值, 环))
            return
        if isinstance(s, 赋值语句):
            值 = self._求值(s.值, 环)
            if not 环.赋值(s.名, 值):
                raise 运行时错误(CN0302_未声明变量,
                              f"变量 {s.名} 还没有声明过", s.跨,
                              解释=f"CNplus 不认识 {s.名}，因为你还没告诉它这个名字代表什么",
                              提示=f"先用「设」建立它，例如：设 {s.名} = 0")
            return
        if isinstance(s, 表达式语句):
            self._求值(s.表达, 环)
            return
        if isinstance(s, 如果语句):
            if self._条件(s.条件, 环):
                self._执行块(s.主体, 环境(环))
            elif s.否则体:
                self._执行块(s.否则体, 环境(环))
            return
        if isinstance(s, 循环语句):
            while self._条件(s.条件, 环):
                self._执行块(s.主体, 环境(环))
            return
        if isinstance(s, 函数声明):
            环.声明(s.名, 函数值(声明=s, 闭包=环))
            return
        if isinstance(s, 返回语句):
            raise _返回信号(self._求值(s.值, 环) if s.值 is not None else None)
        raise AssertionError(f"未处理的语句类型 {type(s).__name__}")

    def _条件(self, 表: 表达式, 环: 环境) -> bool:
        """严格真值 —— 语义约定，故意与 Python 不同。"""
        值 = self._求值(表, 环)
        if not isinstance(值, bool):
            raise 运行时错误(CN0301_条件必须是布尔,
                          f"条件必须是布尔值（真 或 假），这里是{类型名(值)}", 表.跨,
                          解释="判断的位置只能放「成立/不成立」的问题，不能直接放一个数或一段文字",
                          提示="写成一句能回答真/假的话，例如 x > 0、x != 0、名字 == \"小明\"")
        return 值

    # ---- 表达式 ----
    def _求值(self, e: 表达式, 环: 环境) -> object:
        if isinstance(e, 整数字面量):
            return e.值
        if isinstance(e, 小数字面量):
            return e.值
        if isinstance(e, 字符串字面量):
            return e.值
        if isinstance(e, 布尔字面量):
            return e.值
        if isinstance(e, 空字面量):
            return None
        if isinstance(e, 错误表达式):
            return None
        if isinstance(e, 变量引用):
            有, 值 = 环.取(e.名)
            if not 有:
                raise 运行时错误(CN0302_未声明变量,
                              f"变量 {e.名} 还没有声明过", e.跨,
                              解释=f"CNplus 不认识 {e.名}，因为你还没告诉它这个名字代表什么",
                              提示=f"先用「设」建立它，例如：设 {e.名} = 0；也检查一下是不是打错字了")
            return 值
        if isinstance(e, 一元表达式):
            return self._一元(e, 环)
        if isinstance(e, 二元表达式):
            return self._二元(e, 环)
        if isinstance(e, 调用表达式):
            return self._调用(e, 环)
        raise AssertionError(f"未处理的表达式类型 {type(e).__name__}")

    def _一元(self, e: 一元表达式, 环: 环境) -> object:
        值 = self._求值(e.操作数, 环)
        if e.运算 is 一元运算.负:
            if isinstance(值, bool) or not isinstance(值, (int, float)):
                raise 运行时错误(CN0303_类型不匹配,
                              f"负号只能用于数字，这里是{类型名(值)}", e.跨,
                              解释=f"{类型名(值)}没法取负数")
            return -值
        # 非
        if not isinstance(值, bool):
            raise 运行时错误(CN0303_类型不匹配,
                          f"「非」只能用于布尔值（真 或 假），这里是{类型名(值)}", e.跨,
                          解释="「非」是把「成立」翻成「不成立」，所以它后面得跟一个真/假",
                          提示="例如：非 (x > 0)")
        return not 值

    def _二元(self, e: 二元表达式, 环: 环境) -> object:
        # 与/或 短路，且两侧必须是布尔
        if e.运算 in (二元运算.与, 二元运算.或):
            左 = self._求值(e.左, 环)
            self._要布尔(左, e.左, e.运算)
            if e.运算 is 二元运算.与:
                if not 左:
                    return False
                右 = self._求值(e.右, 环)
                self._要布尔(右, e.右, e.运算)
                return bool(右)
            if 左:
                return True
            右 = self._求值(e.右, 环)
            self._要布尔(右, e.右, e.运算)
            return bool(右)

        左 = self._求值(e.左, 环)
        右 = self._求值(e.右, 环)
        运 = e.运算

        # 相等：跨类型报错，不返回假（语义约定，故意与 Python 不同）
        if 运 in (二元运算.等于, 二元运算.不等于):
            if not self._可比较(左, 右):
                raise 运行时错误(CN0303_类型不匹配,
                              f"不能比较{类型名(左)}和{类型名(右)}", e.跨,
                              解释=f"{类型名(左)}和{类型名(右)}是两类不同的东西，"
                                 "比它们相不相等没有意义（CNplus 宁可报错，也不悄悄给你一个「不相等」）",
                              提示="先用「文本(…)」或「整数(…)」把它们转成同一类再比")
            结果 = 左 == 右
            return 结果 if 运 is 二元运算.等于 else not 结果

        # 字符串拼接与重复
        if 运 is 二元运算.加 and isinstance(左, str) and isinstance(右, str):
            return 左 + 右
        if 运 is 二元运算.乘 and isinstance(左, str) and self._是数(右):
            return 左 * int(右)

        # 大小比较：字符串可比，数字可比，混合报错
        if 运 in (二元运算.小于, 二元运算.小于等于, 二元运算.大于, 二元运算.大于等于):
            if isinstance(左, str) and isinstance(右, str):
                pass
            elif self._是数(左) and self._是数(右):
                pass
            else:
                raise 运行时错误(CN0303_类型不匹配,
                              f"不能比较{类型名(左)}和{类型名(右)}的大小", e.跨,
                              解释=f"{类型名(左)}和{类型名(右)}没法排先后",
                              提示="数字跟数字比，文字跟文字比")
            return {
                二元运算.小于: 左 < 右, 二元运算.小于等于: 左 <= 右,
                二元运算.大于: 左 > 右, 二元运算.大于等于: 左 >= 右,
            }[运]

        # 算术：只接受数字
        if not (self._是数(左) and self._是数(右)):
            raise 运行时错误(CN0303_类型不匹配,
                          f"{运} 不能用于{类型名(左)}和{类型名(右)}", e.跨,
                          解释=self._算术解释(运, 左, 右),
                          提示=self._算术提示(运, 左, 右))
        if 运 is 二元运算.加:
            return 左 + 右
        if 运 is 二元运算.减:
            return 左 - 右
        if 运 is 二元运算.乘:
            return 左 * 右
        if 运 in (二元运算.除, 二元运算.整除, 二元运算.取余):
            if 右 == 0:
                raise 运行时错误(CN0304_除以零, "除数不能是零", e.跨,
                              解释="东西没法平均分给 0 个人，这在数学上没有答案",
                              提示="先确认除数不是 0，例如：如果 除数 != 0")
            if 运 is 二元运算.除:
                return 左 / 右          # 语义约定：/ 恒为小数
            if 运 is 二元运算.整除:
                return 左 // 右
            return 左 % 右
        raise AssertionError(f"未处理的二元运算 {运}")

    @staticmethod
    def _是数(值: object) -> bool:
        return isinstance(值, (int, float)) and not isinstance(值, bool)

    @staticmethod
    def _算术解释(运, 左: object, 右: object) -> str:
        """针对最常见的「文字 + 数字」给出对症解释。"""
        有文字 = isinstance(左, str) or isinstance(右, str)
        if 有文字 and 运 is 二元运算.加:
            return "「+」要么把两个数字相加，要么把两段文字接起来，不能一边数字一边文字"
        if 有文字:
            return f"文字不能做「{运}」这种算术运算"
        return f"「{运}」两边都得是数字"

    @staticmethod
    def _算术提示(运, 左: object, 右: object) -> str | None:
        if 运 is 二元运算.加 and (isinstance(左, str) or isinstance(右, str)):
            数 = 右 if isinstance(左, str) else 左
            return f'把数字转成文字再接起来：… + 文本({显示(数)})'
        return None

    def _可比较(self, 左: object, 右: object) -> bool:
        if 左 is None or 右 is None:
            return True  # 空 可以和任何东西比
        if isinstance(左, bool) or isinstance(右, bool):
            return isinstance(左, bool) and isinstance(右, bool)
        if self._是数(左) and self._是数(右):
            return True   # 1 == 1.0 为真（语义约定）
        return type(左) is type(右)

    def _要布尔(self, 值: object, 节, 运) -> None:
        if not isinstance(值, bool):
            raise 运行时错误(CN0303_类型不匹配,
                          f"「{运}」两侧必须是布尔值（真 或 假），这里是{类型名(值)}", 节.跨,
                          解释=f"「{运}」是用来连接两个「成立/不成立」的判断的",
                          提示="例如：x > 0 与 y > 0")

    def _调用(self, e: 调用表达式, 环: 环境) -> object:
        被调 = self._求值(e.被调, 环)
        实参 = [self._求值(a, 环) for a in e.实参]

        if isinstance(被调, _内置):
            if 被调.元数 >= 0 and len(实参) != 被调.元数:
                raise 运行时错误(CN0306_实参数量不符,
                              f"{被调.名} 需要 {被调.元数} 个参数，给了 {len(实参)} 个",
                              e.跨,
                              解释=f"括号里该填几个东西是固定的，{被调.名} 要 {被调.元数} 个",
                              提示="数一数括号里用逗号隔开的项")
            try:
                return 被调.实现(*实参)
            except 运行时错误:
                raise
            except Exception as ex:
                raise 运行时错误(CN0303_类型不匹配,
                              f"调用 {被调.名} 出错：{ex}", e.跨) from None

        if isinstance(被调, 函数值):
            声明 = 被调.声明
            if len(实参) != len(声明.形参):
                raise 运行时错误(CN0306_实参数量不符,
                              f"{声明.名} 需要 {len(声明.形参)} 个参数，"
                              f"给了 {len(实参)} 个", e.跨,
                              解释=f"你定义 {声明.名} 时写了 {len(声明.形参)} 个位置"
                                 f"（{'、'.join(声明.形参) or '无'}），调用时要一一对上",
                              提示=f"改成 {声明.名}(" + ", ".join(声明.形参) + ")")
            局部 = 环境(被调.闭包)
            for 名, 值 in zip(声明.形参, 实参):
                局部.声明(名, 值)
            try:
                self._执行块(声明.主体, 局部)
            except _返回信号 as r:
                return r.值
            return None

        raise 运行时错误(CN0305_不可调用,
                      f"{类型名(被调)}不能被调用", e.跨,
                      解释="名字后面加括号表示「执行它」，但只有函数能被执行",
                      提示="检查是不是名字写错了，或者本来不该加括号")


class _内置:
    __slots__ = ("名", "元数", "实现")

    def __init__(self, 名: str, 元数: int, 实现) -> None:
        self.名 = 名
        self.元数 = 元数
        self.实现 = 实现

    def __repr__(self) -> str:
        return f"<内置函数 {self.名}>"
