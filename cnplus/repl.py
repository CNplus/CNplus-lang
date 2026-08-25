"""CNplus 交互式解释器（REPL）—— T10。

复用树遍历后端 + 持久顶层环境（后端.执行 支持注入顶层环境）。

- 逐行读入；块开头语句（函数/类/如果…）继续收行，空行结束
- 表达式自动回显；普通语句静默；错误打印中文诊断后继续
- 退出：`退出` / Ctrl-D
"""
from __future__ import annotations

from cnplus.backends.treewalk.evaluator import 环境, 树遍历后端
from cnplus.checker import 检查器
from cnplus.diagnostics import 诊断袋
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

_块开头词 = ("函数", "类", "如果", "否则", "循环", "遍历", "尝试", "初始化")


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
            else:
                袋2 = 诊断袋()
                self.后端.执行(程, 源, 袋2, 顶层环境=self.环)
            if 回显 is not None and not 袋.有错:
                值 = self.后端._求值(回显, self.环)
                from cnplus.runtime.values import 显示
                if 值 is not None:
                    self.输出行.append(显示(值))
        finally:
            self.后端._输出回调 = None
        if 袋.有错:
            return [袋.渲染全部(源)]
        return self.输出行

    @staticmethod
    def 是块开头(行: str) -> bool:
        首 = 行.strip()
        return any(首.startswith(词) for 词 in _块开头词)


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
    在块内 = False
    while True:
        出提示()
        行 = 读行()
        if 行 is None:
            写("")
            break
        if not 在块内 and 行.strip() in ("退出", "exit", "quit"):
            break
        if not 在块内 and 交互解释器.是块开头(行):
            在块内 = True
            缓冲 = [行]
            continue
        if 在块内:
            if 行.strip() == "":
                片段 = "\n".join(缓冲)
                在块内 = False
                缓冲 = []
            else:
                缓冲.append(行)
                continue
        else:
            片段 = 行
        for 一行 in 解释器.处理(片段):
            写(一行)
