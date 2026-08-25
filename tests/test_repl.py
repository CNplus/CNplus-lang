"""REPL 测试 —— cnp 交互（T10）。

用 subprocess 管道模拟用户输入，断言输出。
"""
import subprocess
import sys

import pytest

from cnplus.repl import 交互循环


def 跑会话(输入们: list[str]) -> str:
    """喂输入行，返回全部输出。"""
    import io
    from contextlib import redirect_stdout
    出 = io.StringIO()
    with redirect_stdout(出):
        交互循环(输入们=iter(输入们), 输出=出.write, 提示=lambda: None)
    return 出.getvalue()


def test_REPL_表达式回显():
    出 = 跑会话(["1 + 1", "退出"])
    assert "2" in 出


def test_REPL_变量跨行保留():
    出 = 跑会话(["设 x = 10", "x * 2", "退出"])
    assert "20" in 出


def test_REPL_函数定义多行():
    输入们 = ["函数 双倍(n)", "    返回 n * 2", "", "双倍(21)", "退出"]
    出 = 跑会话(输入们)
    assert "42" in 出


def test_REPL_错误不致命():
    出 = 跑会话(["设 x = 1 / 0", "打印(\"还活着\")", "退出"])
    # 第一行报错（除零），会话继续，第二行正常执行
    assert "CN0304" in 出 or "除数" in 出
    assert "还活着" in 出


def test_REPL_打印语句():
    出 = 跑会话(['打印("你好")', "退出"])
    assert "你好" in 出


def test_REPL_字符串字面量回显():
    出 = 跑会话(['"嗨"', "退出"])
    assert "嗨" in 出
