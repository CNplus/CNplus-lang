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
                                CN0306_实参数量不符, CN0307_重复声明,
                                CN0308_下标越界, CN0309_不可遍历,
                                CN0310_输入结束, CN0311_主动抛出, 诊断袋)
from cnplus.parser.ast import (一元运算, 一元表达式, 二元运算, 二元表达式,
                               函数声明, 变量引用, 声明语句, 如果语句, 字符串字面量,
                               小数字面量, 布尔字面量, 循环语句, 整数字面量,
                               程序, 空字面量, 表达式, 表达式语句, 语句,
                               调用表达式, 赋值语句, 返回语句, 导入语句, 成员访问,
                               列表字面量, 字典字面量, 索引访问, 索引赋值语句,
                               遍历语句, 跳出语句, 继续语句, 自增语句,
                               格式串, 多重声明语句, 尝试语句, 抛出语句,
                               错误表达式, 错误语句)
from cnplus.runtime.values import 函数值, 类型名, 显示
from cnplus.source import 源文件


class _返回信号(Exception):
    def __init__(self, 值: object) -> None:
        super().__init__("返回")
        self.值 = 值


class _跳出信号(Exception):
    pass


class _继续信号(Exception):
    pass


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

    def __init__(self, 输出=None, 输入=None) -> None:
        self.输出行: list[str] = []
        self._输出回调 = 输出
        self._输入回调 = 输入

    # ---- 入口 ----
    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        # 内置装在**父环境**，用户顶层是子环境。这样用户可以用
        # `设 查找 = 1` 或 `函数 查找(…)` 遮蔽内置名而不撞「重复声明」，
        # 与静态检查器和转译后端保持一致。
        内置环 = 环境()
        self._装内置(内置环)
        全局 = 环境(内置环)
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
        for 名, 元数, 实现 in 内置表(self._打印, self._输入回调):
            环.声明(名, _内置(名, 元数, 实现))

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
            if s.复合 is not None:
                # x += y：取旧值，用复合运算符算出新值
                有, 旧 = 环.取(s.名)
                if not 有:
                    raise 运行时错误(CN0302_未声明变量,
                                  f"变量 {s.名} 还没有声明过", s.跨,
                                  解释=f"CNplus 不认识 {s.名}，没法在它身上做累加",
                                  提示=(f"两种可能：一是想把「{s.名}」当一段文字，给它加上双引号 "
                              f"（例如 设 名字 = \"{s.名}\"）；二是想用变量，但还没建立它 "
                              f"（先写 设 {s.名} = …）"))
                值 = self._算二元(s.复合, 旧, 值, s.跨)
            if not 环.赋值(s.名, 值):
                raise 运行时错误(CN0302_未声明变量,
                              f"变量 {s.名} 还没有声明过", s.跨,
                              解释=f"CNplus 不认识 {s.名}，因为你还没告诉它这个名字代表什么",
                              提示=(f"两种可能：一是想把「{s.名}」当一段文字，给它加上双引号 "
                              f"（例如 设 名字 = \"{s.名}\"）；二是想用变量，但还没建立它 "
                              f"（先写 设 {s.名} = …）"))
            return
        if isinstance(s, 自增语句):
            有, 旧 = 环.取(s.名)
            if not 有:
                raise 运行时错误(CN0302_未声明变量,
                              f"变量 {s.名} 还没有声明过", s.跨,
                              解释=f"CNplus 不认识 {s.名}，没法给它加减",
                              提示=(f"两种可能：一是想把「{s.名}」当一段文字，给它加上双引号 "
                              f"（例如 设 名字 = \"{s.名}\"）；二是想用变量，但还没建立它 "
                              f"（先写 设 {s.名} = …）"))
            if isinstance(旧, bool) or not isinstance(旧, (int, float)):
                raise 运行时错误(CN0303_类型不匹配,
                              f"{s.名} 是{类型名(旧)}，不能自增/自减", s.跨,
                              解释="++ 和 -- 只能用于数字",
                              提示="确认这个变量是数字")
            环.赋值(s.名, 旧 + s.增量)
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
                try:
                    self._执行块(s.主体, 环境(环))
                except _继续信号:
                    continue
                except _跳出信号:
                    break
            return
        if isinstance(s, 遍历语句):
            self._遍历(s, 环)
            return
        if isinstance(s, 跳出语句):
            raise _跳出信号
        if isinstance(s, 继续语句):
            raise _继续信号
        if isinstance(s, 索引赋值语句):
            对象 = self._求值(s.对象, 环)
            下标 = self._求值(s.下标, 环)
            值 = self._求值(s.值, 环)
            try:
                对象[下标] = 值
            except TypeError:
                raise 运行时错误(CN0303_类型不匹配,
                              f"{类型名(对象)}不能用下标赋值", s.跨,
                              解释="只有列表和字典能这样改内容",
                              提示="检查一下这个东西是不是列表或字典") from None
            except (IndexError, KeyError):
                raise 运行时错误(CN0308_下标越界,
                              f"下标 {显示(下标)} 超出范围", s.跨,
                              解释="这个位置不存在，没法往那里放东西",
                              提示="列表下标从 0 开始；用「长度(…)」看有多少个") from None
            return
        if isinstance(s, 函数声明):
            环.声明(s.名, 函数值(声明=s, 闭包=环))
            return
        if isinstance(s, 导入语句):
            self._导入(s, 环)
            return
        if isinstance(s, 返回语句):
            if s.多值:
                raise _返回信号([self._求值(v, 环) for v in s.多值])
            raise _返回信号(self._求值(s.值, 环) if s.值 is not None else None)
        if isinstance(s, 多重声明语句):
            值 = self._求值(s.值, 环)
            self._解包声明(s, 值, 环)
            return
        if isinstance(s, 尝试语句):
            self._尝试(s, 环)
            return
        if isinstance(s, 抛出语句):
            说明 = self._求值(s.值, 环)
            raise 运行时错误(CN0311_主动抛出, 显示(说明), s.跨,
                          解释="这是程序自己用「抛出」制造的错误",
                          提示="用「尝试 … 捕获」可以接住它")
        raise AssertionError(f"未处理的语句类型 {type(s).__name__}")

    def _尝试(self, s: 尝试语句, 环: 环境) -> None:
        """尝试 / 捕获 / 最后。

        关键语义：「最后」在任何情况下都要执行 —— 正常结束、被捕获、
        错误继续上抛、以及 返回/跳出/继续 穿过时。用 finally 保证。
        """
        try:
            try:
                self._执行块(s.主体, 环境(环))
            except 运行时错误 as 错:
                if s.捕获体 is None:
                    raise          # 没有捕获段：错误继续上抛，但 最后 仍会跑
                捕获环 = 环境(环)
                if s.捕获变量 is not None:
                    捕获环.声明(s.捕获变量, 错.消息)
                self._执行块(s.捕获体, 捕获环)
        finally:
            if s.最后体 is not None:
                self._执行块(s.最后体, 环境(环))

    def _解包声明(self, s: 多重声明语句, 值: object, 环: 环境) -> None:
        if not isinstance(值, (list, tuple)):
            raise 运行时错误(CN0303_类型不匹配,
                          f"右边是{类型名(值)}，没法拆给 {len(s.名们)} 个变量", s.跨,
                          解释="要拆开赋值，右边得是一个列表（或多返回值）",
                          提示="例如：设 甲, 乙 = [1, 2]")
        if len(值) != len(s.名们):
            raise 运行时错误(CN0306_实参数量不符,
                          f"左边有 {len(s.名们)} 个变量，右边有 {len(值)} 个值", s.跨,
                          解释="拆开赋值时两边数量必须一样多",
                          提示=f"左边写 {len(值)} 个变量，或让右边给 {len(s.名们)} 个值")
        for 名, v in zip(s.名们, 值):
            if 环.有本地(名):
                raise 运行时错误(CN0307_重复声明,
                              f"变量 {名} 在这个作用域已经声明过了", s.跨,
                              解释=f"{名} 已经有主了", 提示=f"改值直接写 {名} = 新值")
            环.声明(名, v)

    def _导入(self, s: 导入语句, 环: 环境) -> None:
        """借用 Python 库。模块名是英文，绑定到别名（或末段名）。"""
        import importlib

        try:
            模块 = importlib.import_module(s.模块)
        except Exception as ex:
            raise 运行时错误(CN0303_类型不匹配,
                          f"导入 {s.模块!r} 失败：{ex}", s.跨,
                          解释=f"找不到这个库，或者装的时候出了错",
                          提示=f"先确认它已安装：pip install {s.模块}") from None
        名 = s.别名 or s.模块.rpartition(".")[2] or s.模块
        环.声明(名, 模块)

    def _遍历(self, s: 遍历语句, 环: 环境) -> None:
        目标 = self._求值(s.可迭代, 环)
        try:
            序列 = list(目标)
        except TypeError:
            raise 运行时错误(CN0309_不可遍历,
                          f"{类型名(目标)}不能遍历", s.可迭代.跨,
                          解释="「遍历…每个…」需要一串东西，比如列表、字典或文字",
                          提示="用列表：遍历 [1, 2, 3] 每个 x") from None
        for 项 in 序列:
            局部 = 环境(环)
            局部.声明(s.变量, 项)
            try:
                self._执行块(s.主体, 局部)
            except _继续信号:
                continue
            except _跳出信号:
                break

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
        if isinstance(e, 格式串):
            出 = []
            for 段 in e.部分:
                if isinstance(段, str):
                    出.append(段)
                else:
                    出.append(显示(self._求值(段, 环)))
            return "".join(出)
        if isinstance(e, 错误表达式):
            return None
        if isinstance(e, 变量引用):
            有, 值 = 环.取(e.名)
            if not 有:
                raise 运行时错误(CN0302_未声明变量,
                              f"变量 {e.名} 还没有声明过", e.跨,
                              解释=f"CNplus 不认识 {e.名}，因为你还没告诉它这个名字代表什么",
                              提示=(f"两种可能：一是想把「{e.名}」当一段文字，给它加上双引号 "
                        f"（例如 设 名字 = \"{e.名}\"）；二是想用变量，但还没建立它 "
                        f"（先写 设 {e.名} = …）"))
            return 值
        if isinstance(e, 一元表达式):
            return self._一元(e, 环)
        if isinstance(e, 二元表达式):
            return self._二元(e, 环)
        if isinstance(e, 列表字面量):
            return [self._求值(x, 环) for x in e.元素]
        if isinstance(e, 字典字面量):
            出 = {}
            for 键节点, 值节点 in e.键值对:
                键 = self._求值(键节点, 环)
                try:
                    出[键] = self._求值(值节点, 环)
                except TypeError:
                    raise 运行时错误(CN0303_类型不匹配,
                                  f"{类型名(键)}不能作字典的标签", 键节点.跨,
                                  解释="字典的标签得是文字或数字这类固定不变的东西",
                                  提示='例如 {"名字": "小明"}') from None
            return 出
        if isinstance(e, 索引访问):
            return self._取索引(e, 环)
        if isinstance(e, 成员访问):
            return self._取成员(e, 环)
        if isinstance(e, 调用表达式):
            return self._调用(e, 环)
        raise AssertionError(f"未处理的表达式类型 {type(e).__name__}")

    def _取索引(self, e: 索引访问, 环: 环境) -> object:
        对象 = self._求值(e.对象, 环)
        下标 = self._求值(e.下标, 环)
        try:
            return 对象[下标]
        except TypeError:
            raise 运行时错误(CN0303_类型不匹配,
                          f"{类型名(对象)}不能用下标取值", e.跨,
                          解释="只有列表、字典和文字能用 […] 取里面的东西",
                          提示="检查这个东西的类型") from None
        except IndexError:
            长 = len(对象) if hasattr(对象, "__len__") else "?"
            raise 运行时错误(CN0308_下标越界,
                          f"下标 {显示(下标)} 超出范围（一共 {长} 个）", e.跨,
                          解释="列表下标从 0 开始，最大是「长度 - 1」",
                          提示=f"用「长度(…)」看有多少个") from None
        except KeyError:
            raise 运行时错误(CN0308_下标越界,
                          f"字典里没有标签 {显示(下标)}", e.跨,
                          解释="这个标签不在字典里",
                          提示="检查标签是不是写错了") from None

    def _取成员(self, e: 成员访问, 环: 环境) -> object:
        对象 = self._求值(e.对象, 环)
        try:
            return getattr(对象, e.属性)
        except AttributeError:
            raise 运行时错误(CN0302_未声明变量,
                          f"{e.属性} 在 {类型名(对象)} 里不存在", e.跨,
                          解释=f"这个东西没有叫「{e.属性}」的成员",
                          提示=f"检查成员名是不是写错了") from None

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
        return self._算二元(e.运算, 左, 右, e.跨)

    def _算二元(self, 运, 左, 右, 跨) -> object:
        """纯运算：给定运算符和两个已求值的操作数，算出结果。

        供 二元表达式 和 复合赋值（x += y）共用，保证语义完全一致。
        与/或 的短路在 _二元 里单独处理，不走这里。
        """
        # 相等：跨类型报错，不返回假（语义约定，故意与 Python 不同）
        if 运 in (二元运算.等于, 二元运算.不等于):
            if not self._可比较(左, 右):
                raise 运行时错误(CN0303_类型不匹配,
                              f"不能比较{类型名(左)}和{类型名(右)}", 跨,
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
                              f"不能比较{类型名(左)}和{类型名(右)}的大小", 跨,
                              解释=f"{类型名(左)}和{类型名(右)}没法排先后",
                              提示="数字跟数字比，文字跟文字比")
            return {
                二元运算.小于: 左 < 右, 二元运算.小于等于: 左 <= 右,
                二元运算.大于: 左 > 右, 二元运算.大于等于: 左 >= 右,
            }[运]

        # 算术：只接受数字
        if not (self._是数(左) and self._是数(右)):
            raise 运行时错误(CN0303_类型不匹配,
                          f"{运} 不能用于{类型名(左)}和{类型名(右)}", 跨,
                          解释=self._算术解释(运, 左, 右),
                          提示=self._算术提示(运, 左, 右))
        if 运 is 二元运算.加:
            return 左 + 右
        if 运 is 二元运算.减:
            return 左 - 右
        if 运 is 二元运算.乘:
            return 左 * 右
        if 运 is 二元运算.幂:
            try:
                return 左 ** 右
            except (OverflowError, ZeroDivisionError) as ex:
                raise 运行时错误(CN0303_类型不匹配,
                              f"幂运算出错：{ex}", 跨,
                              解释="结果太大或没有意义") from None
        if 运 in (二元运算.除, 二元运算.整除, 二元运算.取余):
            if 右 == 0:
                raise 运行时错误(CN0304_除以零, "除数不能是零", 跨,
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

    # 列表/字典/字符串上可用「点方法」调用的内置函数：对象作第一个参数
    _可点方法 = {
        "追加", "插入", "移除", "弹出", "排序", "倒序", "包含", "连接", "长度",
        "所有标签", "所有值", "有标签", "删标签",
        "分割", "替换", "查找", "去空白", "大写", "小写", "开头是", "结尾是",
    }

    def _调用(self, e: 调用表达式, 环: 环境) -> object:
        # 成员方法调用：名单.追加(x) —— 对象是 CNplus 集合时，
        # 把它当成 追加(名单, x)。这样既有 追加(名单,x) 也有 名单.追加(x)。
        if isinstance(e.被调, 成员访问):
            对象值 = self._求值(e.被调.对象, 环)
            方法名 = e.被调.属性
            if isinstance(对象值, (list, dict, str)) and 方法名 in self._可点方法:
                有, 内置项 = 环.取(方法名)
                if 有 and isinstance(内置项, _内置):
                    实参 = [对象值] + [self._求值(a, 环) for a in e.实参]
                    try:
                        return 内置项.实现(*实参)
                    except 运行时错误:
                        raise
                    except Exception as ex:
                        raise 运行时错误(CN0303_类型不匹配,
                                      f"调用 {方法名} 出错：{ex}", e.跨) from None

        被调 = self._求值(e.被调, 环)
        实参 = [self._求值(a, 环) for a in e.实参]
        关键字 = {名: self._求值(值, 环) for 名, 值 in e.关键字参数}

        if isinstance(被调, _内置):
            if 关键字:
                raise 运行时错误(CN0306_实参数量不符,
                              f"内置函数 {被调.名} 不支持「名字=值」参数", e.跨,
                              解释="内置函数的参数按位置传",
                              提示=f"直接写 {被调.名}(值1, 值2)")
            if 被调.元数 == -4 and len(实参) > 1:
                raise 运行时错误(CN0306_实参数量不符,
                              f"{被调.名} 最多 1 个参数（提示语），给了 {len(实参)} 个", e.跨,
                              解释=f"{被调.名}() 直接问，{被调.名}(\"提示\") 带提示语",
                              提示=f'例如：{被调.名}("请输入名字：")')
            if 被调.元数 == -2 and not (1 <= len(实参) <= 2):
                raise 运行时错误(CN0306_实参数量不符,
                              f"{被调.名} 需要 1 或 2 个参数，给了 {len(实参)} 个", e.跨,
                              解释=f"{被调.名} 的第二个参数是可选的",
                              提示="检查括号里用逗号隔开的项")
            if 被调.元数 == -3 and not (1 <= len(实参) <= 3):
                raise 运行时错误(CN0306_实参数量不符,
                              f"{被调.名} 需要 1 到 3 个参数，给了 {len(实参)} 个", e.跨,
                              解释=f"{被调.名} 后两个参数是可选的",
                              提示="例如：范围(5)、范围(1, 6)、范围(1, 10, 2)")
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
            except EOFError as ex:
                # 内置函数没有 span，在调用点补上
                raise 运行时错误(CN0310_输入结束, str(ex), e.跨,
                              解释="程序还想要输入，可是没有更多输入了",
                              提示="交互运行时直接输入；用管道喂数据时检查是不是给少了") from None
            except Exception as ex:
                # 内置函数的报错文本直接用异常消息，两后端保持一致
                raise 运行时错误(CN0303_类型不匹配, str(ex), e.跨) from None

        if isinstance(被调, 函数值):
            声明 = 被调.声明
            局部 = self._绑定实参(声明, 实参, 关键字, e.跨)
            局部.父 = 被调.闭包
            try:
                self._执行块(声明.主体, 局部)
            except _返回信号 as r:
                return r.值
            return None

        # 导入的 Python 库里的函数 / 类 / 任何可调用对象
        if callable(被调):
            try:
                return 被调(*实参, **关键字)
            except 运行时错误:
                raise
            except Exception as ex:
                raise 运行时错误(CN0303_类型不匹配,
                              f"调用出错：{ex}", e.跨,
                              解释="这个库的函数被调用时出错了，多半是参数不对",
                              提示="看看传入的参数类型和数量") from None

        raise 运行时错误(CN0305_不可调用,
                      f"{类型名(被调)}不能被调用", e.跨,
                      解释="名字后面加括号表示「执行它」，但只有函数能被执行",
                      提示="检查是不是名字写错了，或者本来不该加括号")

    def _绑定实参(self, 声明, 实参: list, 关键字: dict, 跨) -> "环境":
        """把位置参数、关键字参数、默认值绑定到形参，返回新环境（父稍后设）。"""
        形参 = 声明.形参
        默认们 = 声明.默认值们 or tuple(None for _ in 形参)
        局部 = 环境()
        if len(实参) > len(形参):
            raise 运行时错误(CN0306_实参数量不符,
                          f"{声明.名} 最多 {len(形参)} 个参数，给了 {len(实参)} 个", 跨,
                          解释=f"你定义 {声明.名} 时写了 {len(形参)} 个位置",
                          提示=f"参数有：{'、'.join(形参) or '无'}")
        已填 = {}
        for i, 值 in enumerate(实参):
            已填[形参[i]] = 值
        for 名, 值 in 关键字.items():
            if 名 not in 形参:
                raise 运行时错误(CN0306_实参数量不符,
                              f"{声明.名} 没有叫「{名}」的参数", 跨,
                              解释=f"{声明.名} 的参数是：{'、'.join(形参) or '无'}",
                              提示="检查参数名是不是写错了")
            if 名 in 已填:
                raise 运行时错误(CN0306_实参数量不符,
                              f"参数「{名}」给了两次", 跨,
                              解释="一个参数只能赋值一次",
                              提示="删掉重复的那个")
            已填[名] = 值
        # 填默认值 / 检查缺失
        for i, 名 in enumerate(形参):
            if 名 in 已填:
                局部.表[名] = 已填[名]
            elif 默认们[i] is not None:
                局部.表[名] = self._求值(默认们[i], 局部)
            else:
                raise 运行时错误(CN0306_实参数量不符,
                              f"{声明.名} 缺少参数「{名}」", 跨,
                              解释=f"「{名}」没有默认值，调用时必须给它",
                              提示=f"补上：{声明.名}(…)")
        return 局部


class _内置:
    __slots__ = ("名", "元数", "实现")

    def __init__(self, 名: str, 元数: int, 实现) -> None:
        self.名 = 名
        self.元数 = 元数
        self.实现 = 实现

    def __repr__(self) -> str:
        return f"<内置函数 {self.名}>"


def _转整数(a):
    try:
        return int(a)
    except (ValueError, TypeError):
        raise ValueError(f"没法把 {显示(a)} 变成整数") from None


def _转小数(a):
    try:
        return float(a)
    except (ValueError, TypeError):
        raise ValueError(f"没法把 {显示(a)} 变成小数") from None


def _范围(*参数):
    """范围(5) / 范围(1, 6) / 范围(1, 10, 2) —— 返回列表，方便直接遍历。"""
    return list(range(*[int(x) for x in 参数]))


def _求和(序列):
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in 序列):
        raise TypeError("求和只能用于全是数字的列表")
    return sum(序列)


def _分割(文字, 分隔符=None):
    return 文字.split(分隔符) if 分隔符 is not None else 文字.split()


def _询问(提示, 读一行):
    """向用户要一段文字。提示可省略。

    返回 None 表示输入已结束（EOF），调用方必须处理，
    否则会陷入死循环 —— 这是真实踩过的坑。
    """
    if 提示 is not None:
        print(显示(提示), end="", flush=True)
    return 读一行()


def _询问数值(提示, 读一行):
    """向用户要一个数字，输错会一直问到对为止。

    输入结束（EOF）时不能继续重试，否则死循环。抛 EOFError，
    由 _调用 就地包装成带 span 的诊断（内置函数自己没有 span）。
    """
    while True:
        文 = _询问(提示, 读一行)
        if 文 is None:
            raise EOFError("还需要一个数字，但输入已经结束了")
        试 = 文.strip()
        try:
            if "." in 试:
                return float(试)
            return int(试)
        except ValueError:
            print(f"「{试}」不是数字，请重新输入。", flush=True)


def 内置表(打印实现, 读一行=None):
    """(名, 元数, 实现) 列表。元数 -1 表示任意个，-2 表示 1~2 个，-3 表示 1~3 个。

    这张表是内置函数的唯一来源，两个后端都从这里取，保证行为一致。
    读一行 可注入（测试用假输入）；默认从标准输入读。
    """
    import random

    if 读一行 is None:
        def 读一行():
            try:
                return input()
            except EOFError:
                return None  # None = 输入结束，不能当空串

    return [
        # ---- 输出与类型 ----
        ("打印", -1, 打印实现),
        # ---- 输入 ----
        ("询问", -4, lambda *a: (_询问(a[0] if a else None, 读一行) or "")),
        ("询问数值", -4, lambda *a: _询问数值(a[0] if a else None, 读一行)),
        ("类型", 1, 类型名),
        ("文本", 1, 显示),
        ("整数", 1, _转整数),
        ("小数", 1, _转小数),
        # ---- 通用 ----
        ("长度", 1, len),
        ("范围", -3, _范围),
        ("随机数", 2, lambda a, b: random.randint(int(a), int(b))),
        # ---- 数学 ----
        ("绝对值", 1, abs),
        ("最大", -1, lambda *a: max(a[0]) if len(a) == 1 else max(a)),
        ("最小", -1, lambda *a: min(a[0]) if len(a) == 1 else min(a)),
        ("求和", 1, _求和),
        ("四舍五入", -2, lambda *a: round(*a)),
        ("平方根", 1, lambda a: a ** 0.5),
        # ---- 列表 ----
        ("追加", 2, lambda 表, 项: 表.append(项)),
        ("插入", 3, lambda 表, 位, 项: 表.insert(int(位), 项)),
        ("移除", 2, lambda 表, 项: 表.remove(项)),
        ("弹出", -2, lambda *a: a[0].pop(int(a[1])) if len(a) > 1 else a[0].pop()),
        ("排序", 1, lambda 表: sorted(表)),
        ("倒序", 1, lambda 表: list(reversed(表))),
        ("包含", 2, lambda 容器, 项: 项 in 容器),
        ("连接", 2, lambda 表, 隔: 隔.join(显示(x) for x in 表)),
        # ---- 字典 ----
        ("所有标签", 1, lambda 字: list(字.keys())),
        ("所有值", 1, lambda 字: list(字.values())),
        ("有标签", 2, lambda 字, 标签: 标签 in 字),
        ("删标签", 2, lambda 字, 标签: 字.pop(标签, None)),
        # ---- 字符串 ----
        ("分割", -2, _分割),
        ("替换", 3, lambda 文, 旧, 新: 文.replace(旧, 新)),
        ("查找", 2, lambda 文, 子: 文.find(子)),
        ("去空白", 1, lambda 文: 文.strip()),
        ("大写", 1, lambda 文: 文.upper()),
        ("小写", 1, lambda 文: 文.lower()),
        ("开头是", 2, lambda 文, 前: 文.startswith(前)),
        ("结尾是", 2, lambda 文, 后: 文.endswith(后)),
    ]
