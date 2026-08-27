"""CNplus 交互式解释器（REPL）—— T10。

复用树遍历后端 + 持久顶层环境（后端.执行 支持注入顶层环境）。

- 逐行读入；块开头语句（函数/类/如果…）继续收行，空行结束
- 表达式自动回显；普通语句静默；错误打印中文诊断后继续
- 退出：`退出` / Ctrl-D
"""
from __future__ import annotations

from cnplus.backends.base import 运行时错误
from cnplus.backends.treewalk.evaluator import 环境, 树遍历后端
from cnplus.checker import 检查器
from cnplus.diagnostics import 诊断袋
from cnplus.lexer.lexer import 词法器
from cnplus.lexer.tokens import 种类
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

_块开头种类 = {
    种类.函数, 种类.类, 种类.如果, 种类.否则, 种类.循环,
    种类.遍历, 种类.对于, 种类.尝试, 种类.捕获, 种类.最后, 种类.初始化,
}


class 交互解释器:
    def __init__(self) -> None:
        self.后端 = 树遍历后端(输出=lambda 行: None)
        内置环 = 环境()
        self.后端._装内置(内置环)
        self.环 = 环境(内置环)   # 持久用户环：变量/函数跨行保留
        self.计数 = 0
        self.输出行: list[str] = []

    def 处理(self, 片段: str) -> list[str]:
        """执行一段完整片段，返回应打印的行（错误则返回诊断文本）。"""
        self.计数 += 1
        源 = 源文件(片段, f"<交互{self.计数}>")
        程, 袋 = 解析(源)
        if not 袋.有错:
            检查器(袋).检查(程, 预填名们=set(self.环.表.keys()))
        if 袋.有错:
            return [袋.渲染全部(源)]
        self.输出行 = []
        self.后端._输出回调 = self.输出行.append
        try:
            # 表达式自动回显：最后一个语句是纯表达式时求值并打印
            回显 = None
            语句们 = list(程.语句们)
            from cnplus.parser.ast import 表达式语句
            if 语句们 and isinstance(语句们[-1], 表达式语句):
                回显 = 语句们[-1].表达
                语句们 = 语句们[:-1]
            if 语句们:
                from cnplus.parser.ast import 程序 as 程序类
                程 = 程序类(语句们=tuple(语句们), 跨=程.跨)
                self.后端.执行(程, 源, 袋, 顶层环境=self.环)
            if 回显 is not None and not 袋.有错:
                值 = self.后端._求值(回显, self.环)
                from cnplus.runtime.values import 显示
                if 值 is not None:
                    self.输出行.append(显示(值))
        except 运行时错误 as 错:
            错源 = 错.源 or 源
            袋.报告(错.码, 错.消息, 错.跨, 提示=错.提示, 解释=错.解释)
            return [袋.渲染全部(错源)]
        finally:
            self.后端._输出回调 = None
        if 袋.有错:
            return [袋.渲染全部(self.后端._最后错误源 or 源)]
        return self.输出行

    @staticmethod
    def 是块开头(行: str) -> bool:
        词们, _袋 = 词法器(源文件(行, "<交互判断>")).扫描()
        首 = next((词.种 for 词 in 词们
                   if 词.种 not in (种类.换行, 种类.缩进, 种类.退缩, 种类.文件尾)), None)
        return 首 in _块开头种类

    @staticmethod
    def 括号未闭合(文本: str) -> bool:
        词法 = 词法器(源文件(文本, "<交互判断>"))
        词法.扫描()
        return 词法.括号深度 > 0


def 交互循环(输入们=None, 输出=None, 提示=None) -> None:
    """主循环。输入们=None 走 stdin（真人交互）；测试时注入迭代器。"""
    写 = 输出 or print
    出提示 = 提示 or (lambda: 写("cnp> ", end=""))
    解释器 = 交互解释器()

    def 读行() -> str | None:
        if 输入们 is None:
            try:
                return input()
            except EOFError:
                return None
        try:
            return next(输入们)
        except StopIteration:
            return None

    写("CNplus 交互模式 —— 输入代码立即执行；输入「退出」或 Ctrl-D 离开")
    缓冲: list[str] = []
    是块 = False
    while True:
        片段: str | None = None
        出提示()
        行 = 读行()
        if 行 is None:
            if 缓冲:
                for 一行 in 解释器.处理("\n".join(缓冲)):
                    写(一行)
            写("")
            break
        if not 缓冲 and 行.strip() in ("退出", "exit", "quit"):
            break
        if not 缓冲:
            缓冲 = [行]
            是块 = 交互解释器.是块开头(行)
        elif 是块 and 行.strip() == "" and not 解释器.括号未闭合("\n".join(缓冲)):
            片段 = "\n".join(缓冲)
            缓冲 = []
            是块 = False
        else:
            缓冲.append(行)
        if 片段 is None:
            当前 = "\n".join(缓冲)
            if 解释器.括号未闭合(当前) or 是块:
                continue
            片段 = 当前
            缓冲 = []
        for 一行 in 解释器.处理(片段):
            写(一行)
