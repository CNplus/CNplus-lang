"""LSP 阶段 3 收尾：补全 / 悬停 / 跳转定义。

纯函数层测试（不 起 server，直接调 server.py 里的逻辑函数）。
"""
import sys
from pathlib import Path

import pytest

pygls = pytest.importorskip("lsprotocol")  # 无 pygls 的环境跳过

sys.path.insert(0, str(Path(__file__).parents[1]))
from cnplus.lsp import 补全 as 补全模块
from cnplus.lsp import 悬停 as 悬停模块
from cnplus.lsp import 跳转 as 跳转模块


# ==================== 补全 ====================

def test_补全_关键字():
    项们 = 补全模块.补全于("如", 1, 2)  # 光标在「如」后
    名单 = [i.label for i in 项们]
    assert "如果" in 名单
    # 前缀过滤：敲「如」时不再给「循环」等无关候选
    assert "循环" not in 名单


def test_补全_空上下文给全部():
    项们 = 补全模块.补全于("", 1, 1)
    名单 = [i.label for i in 项们]
    assert "如果" in 名单 and "打印" in 名单


def test_补全_内置函数():
    项们 = 补全模块.补全于("打", 1, 1)
    名单 = [i.label for i in 项们]
    assert "打印" in 名单


def test_补全_作用域变量():
    码 = '设 成绩 = 90\n设 名字 = "小明"\n成'
    项们 = 补全模块.补全于(码, 3, 1)
    名单 = [i.label for i in 项们]
    assert "成绩" in 名单
    assert "名字" in 名单


def test_补全_函数与类():
    码 = '函数 算等级(分)\n    返回 分\n类 学生\n    初始化(名字)\n算'
    项们 = 补全模块.补全于(码, 5, 1)
    名单 = [i.label for i in 项们]
    assert "算等级" in 名单


def test_补全_成员方法():
    码 = '设 名单 = [1]\n名单.追'
    项们 = 补全模块.补全于(码, 2, 4)
    名单 = [i.label for i in 项们]
    assert "追加" in 名单


# ==================== 悬停 ====================

def test_悬停_内置函数():
    码 = '打印("你好")'
    位置 = (1, 1)  # 「打」
    文本 = 悬停模块.悬停于(码, *位置)
    assert 文本 and "打印" in 文本


def test_悬停_变量():
    码 = '设 成绩 = 90\n打印(成绩)'
    文本 = 悬停模块.悬停于(码, 2, 4)  # 「成」处（列 1 起）
    assert 文本 and "成绩" in 文本


def test_悬停_关键字():
    码 = '如果 真\n    打印(1)'
    文本 = 悬停模块.悬停于(码, 1, 1)
    assert 文本 and ("如果" in 文本 or "条件" in 文本)


# ==================== 跳转定义 ====================

def test_跳转_变量():
    码 = '设 成绩 = 90\n打印(成绩)'
    位置 = 跳转模块.定义于(码, 2, 4)
    assert 位置 == (1, 1)  # 指向第 1 行的 设


def test_跳转_函数():
    码 = '函数 算等级(分)\n    返回 分\n打印(算等级(80))'
    位置 = 跳转模块.定义于(码, 3, 4)  # 算 的位置
    assert 位置 == (1, 1)


def test_跳转_类():
    码 = '类 学生\n    初始化(名字)\n设 甲 = 学生("小明")'
    位置 = 跳转模块.定义于(码, 3, 7)  # 学 的位置
    assert 位置 == (1, 1)


def test_跳转_未定义返回None():
    码 = '打印(未知)'
    assert 跳转模块.定义于(码, 1, 4) is None
