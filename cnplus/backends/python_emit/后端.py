"""Python 转译后端 —— 阶段 1。

把 AST 翻译成自包含的 Python 源码再执行，借用整个 pip 生态。
生成的 .py 文件可独立运行。
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

from cnplus.backends.base import 后端
from cnplus.backends.python_emit.发射器 import 发射
from cnplus.diagnostics import 诊断袋
from cnplus.parser.ast import 程序
from cnplus.source import 源文件


class Python转译后端(后端):
    名称 = "Python 转译"

    def __init__(self, 输出=None) -> None:
        self.输出行: list[str] = []
        self._输出回调 = 输出
        self.最后源码: str = ""

    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        源码, 行映射 = 发射(程)
        self.最后源码 = 源码
        缓冲 = io.StringIO()
        文件名 = 源.文件名 + ".py"
        try:
            with contextlib.redirect_stdout(缓冲):
                exec(compile(源码, 文件名, "exec"), {})
        except Exception as e:
            self._处理异常(e, 源, 袋, 文件名, 行映射)
        for 行 in 缓冲.getvalue().splitlines():
            self.输出行.append(行)
            if self._输出回调:
                self._输出回调(行)
            else:
                print(行)

    def _处理异常(self, e: Exception, 源: 源文件, 袋: 诊断袋,
                  文件名: str, 行映射: list[int]) -> None:
        # 生成代码里内联的 CNplus错误 是另一个类对象，用鸭子类型识别
        if e.__class__.__name__ == "CNplus错误" and hasattr(e, "码"):
            跨 = 源.跨度于行列(getattr(e, "行"), getattr(e, "列"))
            袋.报告(e.码, e.消息, 跨,
                   提示=getattr(e, "提示", None), 解释=getattr(e, "解释", None))
            return
        # Python 库抛的异常：用行映射尽力定位回 CNplus
        cnplus行 = self._定位(e, 文件名, 行映射)
        跨 = 源.跨度于行列(cnplus行, 1) if cnplus行 else 源.跨度于(0, 1)
        袋.报告("CN9001", f"调用 Python 库时出错：{type(e).__name__}: {e}", 跨,
              解释="这个错误来自你导入的 Python 库，不是 CNplus 本身",
              提示="检查传给库的参数类型和数量，或参考该库的文档")

    @staticmethod
    def _定位(e: Exception, 文件名: str, 行映射: list[int]) -> int:
        """遍历整条调用栈，取最后一个属于生成文件的帧。

        库函数抛异常时，最内层帧在库里；我们要的是生成代码里
        「调用那个库」的位置，即栈里最深的生成文件帧。
        """
        回溯 = e.__traceback__
        命中 = 0
        while 回溯 is not None:
            if 回溯.tb_frame.f_code.co_filename == 文件名:
                行 = 回溯.tb_lineno
                if 0 < 行 <= len(行映射):
                    源行 = 行映射[行 - 1]
                    # 只在映射到真实源码行(非 0)时更新。运行时块映射到 0，
                    # 它是最内层帧，不能让它覆盖掉外层真正的调用位置。
                    if 源行:
                        命中 = 源行
            回溯 = 回溯.tb_next
        return 命中


def 编译到文件(程: 程序, 目标: str | Path) -> Path:
    """发射并写到磁盘，返回路径。生成的 .py 可独立运行。"""
    源码, _ = 发射(程)
    目标 = Path(目标)
    目标.write_text(源码, encoding="utf-8")
    return 目标
