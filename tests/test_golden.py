"""黄金语料驱动测试 —— 铁律 5。

每个用例一个目录：
  源.cnp          输入
  期望输出.txt     期望的标准输出（正常用例）
  期望诊断码.txt   期望出现的诊断码（错误用例）

**语料只增不删。** 这是将来敢重写后端的唯一保险。
"""
from pathlib import Path

import pytest

from cnplus.backends.treewalk import 树遍历后端
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

语料根 = Path(__file__).parent / "golden"


def _收集(标记文件: str):
    return sorted(p.parent for p in 语料根.glob(f"*/{标记文件}"))


def 跑(源码: str, 文件名: str):
    源 = 源文件(源码, 文件名)
    程, 袋 = 解析(源)
    后 = 树遍历后端(输出=lambda 行: None)
    if not 袋.有错:
        后.执行(程, 源, 袋)
    return 后.输出行, 袋, 源


@pytest.mark.parametrize("用例", _收集("期望输出.txt"), ids=lambda p: p.name)
def test_正常语料(用例: Path):
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望 = (用例 / "期望输出.txt").read_text(encoding="utf-8")
    输出行, 袋, 源 = 跑(源码, 用例.name)
    assert not 袋.有错, "不该有错，实际：\n" + 袋.渲染全部(源)
    实际 = "".join(行 + "\n" for 行 in 输出行)
    assert 实际 == 期望, f"\n期望:\n{期望!r}\n实际:\n{实际!r}"


@pytest.mark.parametrize("用例", _收集("期望诊断码.txt"), ids=lambda p: p.name)
def test_错误语料(用例: Path):
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望码 = (用例 / "期望诊断码.txt").read_text(encoding="utf-8").strip()
    输出行, 袋, 源 = 跑(源码, 用例.name)
    码们 = [d.码 for d in 袋]
    assert 期望码 in 码们, f"期望诊断码 {期望码}，实际得到 {码们}"


def test_语料非空():
    """防止语料被误删 —— 铁律 5「只增不删」的守卫。"""
    assert len(_收集("期望输出.txt")) >= 15
    assert len(_收集("期望诊断码.txt")) >= 10


def test_所有语料的诊断都能渲染():
    """每条诊断都必须能渲染出带波浪线的报告，不能崩。"""
    for 用例 in _收集("期望诊断码.txt"):
        源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
        _, 袋, 源 = 跑(源码, 用例.name)
        出 = 袋.渲染全部(源)
        assert "^" in 出, f"{用例.name} 的诊断没有波浪线"
