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


def test_REPL_有副作用的表达式只执行一次():
    出 = 跑会话(["设 a = []", "a.追加(1)", "a", "退出"])
    assert "[1, 1]" not in 出
    assert "[1]" in 出


def test_REPL_变量跨行保留():
    出 = 跑会话(["设 x = 10", "x * 2", "退出"])
    assert "20" in 出


def test_REPL_函数定义多行():
    输入们 = ["函数 双倍(n)", "    返回 n * 2", "", "双倍(21)", "退出"]
    出 = 跑会话(输入们)
    assert "42" in 出


def test_REPL_块关键字别名进入多行模式():
    输入们 = ["定义 双倍(n)", "    返回 n * 2", "", "双倍(5)", "退出"]
    出 = 跑会话(输入们)
    assert 出.endswith("10")


def test_REPL_函数体错误指向定义片段():
    输入们 = ["函数 相除(n)", "    返回 1 / n", "", "相除(0)", "退出"]
    出 = 跑会话(输入们)
    assert "CN0304" in 出
    assert "<交互1>:2" in 出


def test_REPL_嵌套调用保留最内层定义片段():
    输入们 = [
        "函数 内(n)", "    返回 1 / n", "",
        "函数 外(n)", "    返回 内(n)", "",
        "外(0)", "退出",
    ]
    出 = 跑会话(输入们)
    assert "CN0304" in 出
    assert "<交互1>:2" in 出


def test_REPL_初始化错误指向类定义片段():
    输入们 = [
        "类 箱子", "    初始化(n)", "        自己.值 = 1 / n", "",
        "箱子(0)", "退出",
    ]
    出 = 跑会话(输入们)
    assert "CN0304" in 出
    assert "<交互1>:3" in 出


def test_REPL_括号内多行表达式():
    出 = 跑会话(["设 x = (", "    1 + 2", ")", "x", "退出"])
    assert "错误[" not in 出
    assert 出.endswith("3")


def test_REPL_未闭合括号遇EOF会报错():
    出 = 跑会话(["设 x = ("])
    assert "错误[" in 出


def test_REPL_块关键字前缀不是块():
    出 = 跑会话(["设 函数值 = 1", "函数值", "退出"])
    assert "错误[" not in 出
    assert 出.endswith("1")


def test_REPL_错误不致命():
    出 = 跑会话(["设 x = 1 / 0", "打印(\"还活着\")", "退出"])
    # 第一行报错（除零），会话继续，第二行正常执行
    assert "CN0304" in 出 or "除数" in 出
    assert "还活着" in 出


def test_REPL_纯表达式动态错误不致命():
    出 = 跑会话(["1 / 0", '打印("还活着")', "退出"])
    assert "CN0304" in 出 or "除数" in 出
    assert "还活着" in 出


def test_REPL_打印语句():
    出 = 跑会话(['打印("你好")', "退出"])
    assert "你好" in 出


def test_REPL_字符串字面量回显():
    出 = 跑会话(['"嗨"', "退出"])
    assert "嗨" in 出
