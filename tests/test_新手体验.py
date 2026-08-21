"""面向新手的质量测试。

两件事：
1. 所有示例程序必须能跑（教程里的东西不能是坏的）
2. 错误信息必须过「新手可读性」检查
"""
import re
from pathlib import Path

import pytest

from cnplus.backends.treewalk import 树遍历后端
from cnplus.checker import 检查
from cnplus.diagnostics import 渲染
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

示例目录 = Path(__file__).parent.parent / "示例"


def 跑(码: str, 名: str = "t.cnp", 输入行=None):
    """输入行：预设的输入序列（列表）。用完返回 None（模拟 EOF）。"""
    源 = 源文件(码, 名)
    程, 袋 = 解析(源)
    if not 袋.有错:
        检查(程, 袋)
    输出 = []
    喂 = None
    if 输入行 is not None:
        剩 = list(输入行)
        def 喂():
            return 剩.pop(0) if 剩 else None
    if not 袋.有错:
        树遍历后端(输出=输出.append, 输入=喂).执行(程, 源, 袋)
    return 输出, 袋, 源


# 需要用户输入的示例：喂给它足够的假输入
_预设输入 = {
    "07-猜数字.cnp": [str(n) for n in range(1, 101)],  # 逐个猜，必中
    "15-待办清单.cnp": ["1", "4", "0"],                 # 看清单 → 统计 → 退出
}


@pytest.mark.parametrize("文件", sorted(示例目录.glob("*.cnp")), ids=lambda p: p.stem)
def test_示例都能跑(文件: Path):
    """教程引用的每个示例都必须无错运行。"""
    输出, 袋, 源 = 跑(文件.read_text(encoding="utf-8"), 文件.name,
                  输入行=_预设输入.get(文件.name))
    assert not 袋.有错, f"{文件.name} 出错：\n{袋.渲染全部(源)}"
    assert 输出, f"{文件.name} 没有任何输出"


@pytest.mark.parametrize("文件", sorted(示例目录.glob("*.cnp")), ids=lambda p: p.stem)
def test_示例两后端输出一致(文件: Path):
    """每个示例在树遍历后端和转译后端的输出必须逐字一致（防语义泄漏）。

    用了「随机数」的示例天生每次结果不同，无法做输出比对，跳过 ——
    它们的一致性由 tests/ 里的定值测试保证。
    """
    from cnplus.backends.python_emit import Python转译后端
    码 = 文件.read_text(encoding="utf-8")
    if "随机数" in 码:
        pytest.skip("含随机数，输出不可复现")
    if "问(" in 码 or "问数字(" in 码:
        pytest.skip("需要用户输入，无法在双后端间做无人比对")
    源 = 源文件(码, 文件.name)
    程, 袋 = 解析(源)
    检查(程, 袋)
    assert not 袋.有错
    树: list[str] = []
    树遍历后端(输出=树.append).执行(程, 源, 袋)
    译: list[str] = []
    Python转译后端(输出=译.append).执行(程, 源, 袋)
    assert 树 == 译, f"{文件.name} 两后端输出不一致\n树:{树}\n译:{译}"


def test_示例覆盖教程提到的编号():
    """教程列了 01–09，实际必须都在。"""
    有 = {p.name[:2] for p in 示例目录.glob("*.cnp")}
    assert {f"{i:02d}" for i in range(1, 10)} <= 有


# ---- 错误信息可读性 ----

坏例子 = [
    ("如果 0\n    打印(1)", "条件不是布尔"),
    ("打印(没这个名字)", "名字不存在"),
    ("打印(1 / 0)", "除以零"),
    ('打印("字" + 1)', "文字加数字"),
    ("设 x = 1\n设 x = 2", "重名"),
    ("y = 1", "没建就改"),
    ('设 s = "没关引号', "引号没关"),
    ("如果 真\n打印(1)", "忘了缩进"),
    ("函数 f(a)\n    返回 a\n\n打印(f(1, 2))", "参数给多了"),
    ("设 x = 1\n打印(x(1))", "把数字当函数用"),
]


@pytest.mark.parametrize("码,情形", 坏例子, ids=[x[1] for x in 坏例子])
def test_错误信息有大白话解释(码: str, 情形: str):
    """每条错误都要有「也就是说」这一层 —— 这是给没有基础的人看的。"""
    _, 袋, 源 = 跑(码)
    assert 袋.有错, f"{情形}：应该报错"
    有解释 = [d for d in 袋 if d.解释]
    assert 有解释, f"{情形}：{[d.码 for d in 袋]} 缺少大白话解释"


@pytest.mark.parametrize("码,情形", 坏例子, ids=[x[1] for x in 坏例子])
def test_错误信息有具体改法(码: str, 情形: str):
    _, 袋, 源 = 跑(码)
    有提示 = [d for d in 袋 if d.提示]
    assert 有提示, f"{情形}：缺少「这样改」"


@pytest.mark.parametrize("码,情形", 坏例子, ids=[x[1] for x in 坏例子])
def test_错误信息不含未解释的黑话(码: str, 情形: str):
    """术语可以出现在「消息」里（对有基础的人有用），
    但「也就是说」那一层必须是人话 —— 不能再堆术语。"""
    黑话 = ["标识符", "词元", "AST", "语法树", "字面量", "作用域",
           "隐式", "转换", "表达式语句", "元数", "实参", "形参"]
    _, 袋, 源 = 跑(码)
    for d in 袋:
        if not d.解释:
            continue
        坏 = [w for w in 黑话 if w in d.解释]
        assert not 坏, f"{情形}：解释里有黑话 {坏}：{d.解释}"


def test_拼写建议():
    """名字打错时要能猜出想写什么 —— 新手最常见的错。"""
    _, 袋, _ = 跑("设 年龄 = 18\n打印(年龄x)")
    提示们 = " ".join(d.提示 or "" for d in 袋)
    assert "年龄" in 提示们 and "是不是" in 提示们


def test_渲染三层齐全():
    _, 袋, 源 = 跑("如果 0\n    打印(1)")
    出 = 渲染(袋.条目[0], 源)
    assert "错误[CN0301]" in 出      # 编号
    assert "^" in 出                 # 位置
    assert "也就是说" in 出           # 人话
    assert "这样改" in 出             # 办法


def test_关键字别名都可用():
    """白话别名和正式写法必须等价。"""
    正式 = "设 x = 5\n如果 x > 3\n    打印(\"大\")\n否则\n    打印(\"小\")"
    白话 = "让 x = 5\n假如 x > 3\n    打印(\"大\")\n要不然\n    打印(\"小\")"
    甲, 袋甲, _ = 跑(正式)
    乙, 袋乙, _ = 跑(白话)
    assert not 袋甲.有错 and not 袋乙.有错
    assert 甲 == 乙 == ["大"]


def test_函数别名():
    for 词, 返 in [("函数", "返回"), ("定义", "给出"), ("过程", "返")]:
        码 = f"{词} 加一(n)\n    {返} n + 1\n\n打印(加一(1))"
        输出, 袋, 源 = 跑(码)
        assert not 袋.有错, f"{词}/{返} 出错：{袋.渲染全部(源)}"
        assert 输出 == ["2"]


def test_循环别名():
    for 词 in ["循环", "当", "重复"]:
        码 = f"设 i = 1\n{词} i <= 2\n    打印(i)\n    i = i + 1"
        输出, 袋, _ = 跑(码)
        assert not 袋.有错 and 输出 == ["1", "2"], 词
