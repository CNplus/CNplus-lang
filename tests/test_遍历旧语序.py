"""遍历旧语序别名（D-021 复活为别名）—— 对于 x 在 y ≡ 遍历 y 每个 x。

历史：v0.4.2 之前的主写法是 `对于 名字 在 成绩`（直译 for x in y），
D-021 因语序生硬改为 `遍历 成绩 每个 名字`，旧写法连别名一起删除。
2026-08-25 用户拍板：旧语序作为别名复活——本意就是别名，删过头了。
"""
import pytest

from cnplus.backends.python_emit import Python转译后端
from cnplus.backends.treewalk import 树遍历后端
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


def _跑(码: str, 后端类):
    源 = 源文件(码, "t.cnp")
    程, 袋 = 解析(源)
    if 袋.有错:
        return None, [d.码 for d in 袋]
    出 = []
    后端类(输出=出.append).执行(程, 源, 袋)
    return 出, []


def 对拍(码: str) -> list[str]:
    树, 树错 = _跑(码, 树遍历后端)
    译, 译错 = _跑(码, Python转译后端)
    assert 树错 == [] and 译错 == [], f"不该报错：树{树错} 译{译错}"
    assert 树 == 译, f"两后端不一致：\n树:{树}\n译:{译}"
    return 树


def test_旧语序_基本():
    码 = '''对于 x 在 [1, 2, 3]
    打印(x)'''
    assert 对拍(码) == ["1", "2", "3"]


def test_旧语序_与新语序等价():
    旧 = '''对于 x 在 [10, 20]
    打印(x)'''
    新 = '''遍历 [10, 20] 每个 x
    打印(x)'''
    assert 对拍(旧) == 对拍(新)


def test_旧语序_字符串遍历():
    码 = '''对于 字 在 "你好"
    打印(字)'''
    assert 对拍(码) == ["你", "好"]


def test_旧语序_字典遍历():
    码 = '''对于 名 在 {"甲": 1, "乙": 2}
    打印(名)'''
    assert 对拍(码) == ["甲", "乙"]


def test_旧语序_嵌套():
    码 = '''对于 行 在 [[1, 2], [3, 4]]
    对于 格 在 行
        打印(格)'''
    assert 对拍(码) == ["1", "2", "3", "4"]


def test_旧语序_块作用域():
    码 = '''设 总 = 0
对于 x 在 [1, 2, 3]
    设 总 = 总 + x
打印(总)'''
    # 块内 设 是新声明，外层 总 不变——与遍历语义一致
    输出, 错 = _跑(码, 树遍历后端)
    assert 错 == []
    assert 输出 == ["0"]
