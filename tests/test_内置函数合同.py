"""内置函数的规范、后端登记与共享黄金语料合同矩阵。"""
from dataclasses import fields, is_dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import Any, NotRequired, TypedDict, cast

import pytest

from cnplus.backends.注册表 import 对拍后端们
from cnplus.backends.python_emit.运行时源码 import _可点方法 as PYTHON可点方法
from cnplus.backends.python_emit.运行时源码 import 内置们 as PYTHON内置们
from cnplus.backends.treewalk.evaluator import 内置表, 树遍历后端
from cnplus.checker import 检查
from cnplus.parser.ast import 函数声明, 声明语句, 成员访问, 调用表达式, 类声明, 变量引用
from cnplus.parser.parser import 解析
from cnplus.source import 源文件
from test_三后端对拍 import _输入文本, 跑_后端


根 = Path(__file__).parents[1]
规范文件 = 根 / "docs/spec/04-内置函数.md"
语料根 = Path(__file__).parent / "golden"
JS运行时文件 = 根 / "cnplus/backends/js_emit/运行时源码.js"
合同矩阵文件 = Path(__file__).parent / "内置函数合同.toml"


def _后端参数们():
    for 登记 in 对拍后端们():
        标记 = ()
        if "Node" in 登记.后端类.能力.运行环境们 and shutil.which("node") is None:
            标记 = (pytest.mark.skip(reason="本机无 node"),)
        yield pytest.param(登记, marks=标记, id=登记.名称)


后端参数们 = tuple(_后端参数们())


def _运行错误源码(登记, 源码: str, 文件名: str, 输入文本: str = ""):
    源 = 源文件(源码, 文件名)
    程序, 诊断们 = 解析(源)
    检查(程序, 诊断们)
    assert not 诊断们.有错, 登记.名称

    后端类 = cast(Any, 登记.后端类)
    后端 = 后端类(输出=lambda _: None, 输入文本=输入文本)
    后端.执行(程序, 源, 诊断们)
    return 后端, 诊断们


def _断言子进程错误(登记, 后端, 诊断码: str) -> None:
    if not 登记.是子进程:
        return
    退出码 = getattr(后端, "最后退出码", None)
    assert 退出码 is not None, f"{登记.名称} 没有记录子进程退出码"
    assert 退出码 != 0, f"{登记.名称} 报错后仍以成功状态退出"
    错误输出 = getattr(后端, "最后错误输出", "")
    assert 诊断码 in 错误输出
    assert "CN9001" not in 错误输出


class 合同行(TypedDict):
    name: str
    min_args: int
    max_args: int
    dimensions: list[str]
    evidence: dict[str, str]
    forms: list[str]
    form_evidence: dict[str, str]
    fixtures: list[str]
    receiver: NotRequired[str]
    invalid_call: NotRequired[str]
    invalid_calls: NotRequired[list[str]]


def _规范内置名们() -> set[str]:
    内容 = 规范文件.read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([^`]+)` \|", 内容, re.MULTILINE))


def _JS运行时登记() -> dict[str, object]:
    标记 = "__CNPLUS_BUILTINS__"
    脚本 = JS运行时文件.read_text(encoding="utf-8") + f"""
console.log({标记!r} + JSON.stringify({{
    names: Object.keys(内置们),
    ranges: _内置参数范围,
    dot: [..._可点方法],
}}));
"""
    结果 = subprocess.run(
        ["node", "-e", 脚本], capture_output=True, text=True, timeout=30)
    assert 结果.returncode == 0, 结果.stderr
    行 = next(行 for 行 in 结果.stdout.splitlines() if 行.startswith(标记))
    return cast(dict[str, object], json.loads(行.removeprefix(标记)))


def _树遍历登记名们() -> set[str]:
    return {名 for 名, _, _ in 内置表(lambda *args: None, None)}


def _活动语料们() -> list[Path]:
    return sorted({
        标记.parent
        for 文件名 in ("期望输出.txt", "期望诊断码.txt")
        for 标记 in 语料根.glob(f"*/{文件名}")
    })


def _遍历节点(节点):
    if is_dataclass(节点):
        yield 节点
        if isinstance(节点, (函数声明, 类声明)):
            return
        for 字段 in fields(节点):
            yield from _遍历节点(getattr(节点, 字段.name))
    elif isinstance(节点, (tuple, list)):
        for 项 in 节点:
            yield from _遍历节点(项)


def _用例调用形式(用例: Path) -> dict[str, set[str]]:
    直接: set[str] = set()
    点调用: set[str] = set()
    别名: set[str] = set()
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    程序, 诊断们 = 解析(源文件(源码, 用例.name))
    if 诊断们.有错:
        return {"直接": 直接, "点调用": 点调用, "别名": 别名}
    节点们 = tuple(_遍历节点(程序))
    别名表 = {
        节点.名: 节点.值.名
        for 节点 in 节点们
        if isinstance(节点, 声明语句)
        and isinstance(节点.值, 变量引用)
    }
    for 节点 in 节点们:
        if not isinstance(节点, 调用表达式):
            continue
        if isinstance(节点.被调, 变量引用):
            名 = 节点.被调.名
            if 名 in 别名表:
                别名.add(别名表[名])
            else:
                直接.add(名)
        elif isinstance(节点.被调, 成员访问):
            点调用.add(节点.被调.属性)
    return {"直接": 直接, "点调用": 点调用, "别名": 别名}


def _共享调用形式(用例们=None) -> tuple[set[str], set[str]]:
    直接: set[str] = set()
    点调用: set[str] = set()
    for 用例 in (_活动语料们() if 用例们 is None else 用例们):
        形式 = _用例调用形式(用例)
        直接.update(形式["直接"])
        点调用.update(形式["点调用"])
    return 直接, 点调用


def _参数范围(元数: int) -> tuple[int, int]:
    if 元数 >= 0:
        return 元数, 元数
    return {
        -1: (0, -1),
        -2: (1, 2),
        -3: (1, 3),
        -4: (0, 1),
    }[元数]


def _合同矩阵行们() -> list[合同行]:
    数据 = tomllib.loads(合同矩阵文件.read_text(encoding="utf-8"))
    return cast(list[合同行], 数据["builtin"])


def _黄金证据用例们():
    for 行 in _合同矩阵行们():
        for 维度, 证据 in 行["evidence"].items():
            if 证据.startswith("fixture:"):
                yield pytest.param(
                    行["name"], 维度, 语料根 / 证据.removeprefix("fixture:"),
                    id=f"{行['name']}-{维度}-{证据.removeprefix('fixture:')}",
                )


def _错误参数数量用例们():
    for 行 in _合同矩阵行们():
        最少 = 行["min_args"]
        最多 = 行["max_args"]
        for 形式 in 行["forms"]:
            接收者数 = 1 if 形式 == "点调用" else 0
            最少实参 = 最少 - 接收者数
            最多实参 = 最多 - 接收者数 if 最多 >= 0 else -1
            if 最少实参 > 0:
                yield 行, 形式, 最少实参 - 1
            if 最多实参 >= 0:
                yield 行, 形式, 最多实参 + 1


def _错误参数源码(行: 合同行, 形式: str, 数量: int) -> tuple[str, int]:
    实参 = ", ".join("空" for _ in range(数量))
    名 = 行["name"]
    if 形式 == "点调用":
        return f'设 接收者 = {行.get("receiver", "")}\n接收者.{名}({实参})', 2
    if 形式 == "别名":
        return f"设 别名 = {名}\n别名({实参})", 2
    return f"{名}({实参})", 1


def test_规范与树遍历及Python登记相同的内置名():
    规范 = _规范内置名们()
    assert _树遍历登记名们() == 规范
    assert set(PYTHON内置们) == 规范


def test_内置关键字参数明确禁止():
    内容 = 规范文件.read_text(encoding="utf-8")
    assert "只接受位置参数" in 内容
    assert "直接调用、函数别名和点调用" in 内容
    assert "关键字参数是未定义行为" not in 内容


def test_树遍历与Python登记相同的点调用名():
    树遍历 = set(树遍历后端._可点方法)
    assert set(PYTHON可点方法) == 树遍历
    assert 树遍历 <= _规范内置名们()


@pytest.mark.skipif(shutil.which("node") is None, reason="本机无 node")
def test_JS实际运行时登记与合同相同():
    登记 = _JS运行时登记()
    范围 = {
        行["name"]: [行["min_args"], 行["max_args"]]
        for 行 in _合同矩阵行们()
    }
    assert set(cast(list[str], 登记["names"])) == _规范内置名们()
    assert cast(dict[str, list[int]], 登记["ranges"]) == 范围
    assert set(cast(list[str], 登记["dot"])) == set(树遍历后端._可点方法)


def test_合同矩阵逐项关联真实语料与登记():
    行们 = _合同矩阵行们()
    名们 = [行["name"] for 行 in 行们]
    assert len(名们) == len(set(名们)), "合同矩阵中的名字不能重复"
    assert set(名们) == _规范内置名们()

    允许维度 = {
        "正常输入", "参数数量", "错误类型", "空值或越界", "Unicode",
        "可变值相等", "修改原值", "返回值", "输入结束", "求值顺序", "诊断详情",
    }
    活动语料 = {用例.name: 用例 for 用例 in _活动语料们()}
    实际范围 = {
        名: _参数范围(元数)
        for 名, 元数, _ in 内置表(lambda *args: None, None)
    }
    矩阵范围 = {
        行["name"]: (行["min_args"], 行["max_args"])
        for 行 in 行们
    }
    PYTHON范围 = {
        名: (函数.最少参数, 函数.最多参数)
        for 名, 函数 in PYTHON内置们.items()
    }
    assert 矩阵范围 == 实际范围 == PYTHON范围
    可点 = set(树遍历后端._可点方法)

    for 行 in 行们:
        名 = 行["name"]
        必需字段 = {
            "name", "min_args", "max_args", "dimensions", "evidence",
            "forms", "form_evidence", "fixtures",
        }
        可选字段 = {"receiver", "invalid_call", "invalid_calls"}
        assert 必需字段 <= set(行) <= 必需字段 | 可选字段
        assert (行["min_args"], 行["max_args"]) == 实际范围[名]
        assert 行["dimensions"]
        assert set(行["dimensions"]) <= 允许维度
        assert set(行["evidence"]) == set(行["dimensions"]), (
            f"{名} 的每个合同维度都必须绑定一条具体证据")
        assert 行["fixtures"]

        for 语料名 in 行["fixtures"]:
            assert 语料名 in 活动语料, f"{名} 引用了非活动语料 {语料名}"

        assert set(行["form_evidence"]) == set(行["forms"]), (
            f"{名} 的每种调用形式都必须绑定正常语料")
        for 形式名, 语料名 in 行["form_evidence"].items():
            assert 语料名 in 行["fixtures"]
            用例 = 活动语料[语料名]
            assert (用例 / "期望输出.txt").exists(), (
                f"{名} 的 {形式名} 形式必须由正常执行语料证明")
            assert 名 in _用例调用形式(用例)[形式名], (
                f"{名} 的 {形式名} 形式没有在 {语料名} 中实际调用")

        for 维度, 证据 in 行["evidence"].items():
            if 证据 == "dynamic:arity":
                assert 维度 == "参数数量"
                continue
            if 证据 == "dynamic:invalid-types":
                assert 维度 == "错误类型"
                assert 行.get("invalid_call")
                continue
            if 证据.startswith("test:"):
                测试名 = 证据.removeprefix("test:")
                assert 维度 == "诊断详情"
                专项源码 = (Path(__file__).parent / "test_倒序.py").read_text(
                    encoding="utf-8")
                assert f"def {测试名}(" in 专项源码
                continue

            assert 证据.startswith("fixture:"), f"{名} 的 {维度} 证据格式无效"
            语料名 = 证据.removeprefix("fixture:")
            assert 语料名 in 行["fixtures"]
            用例 = 活动语料[语料名]
            调用名们 = set().union(*_用例调用形式(用例).values())
            assert 名 in 调用名们, f"{语料名} 没有实际调用 {名}"
            if 维度 in {
                "正常输入", "Unicode", "可变值相等", "修改原值",
                "返回值", "求值顺序",
            }:
                assert (用例 / "期望输出.txt").exists(), (
                    f"{名} 的 {维度} 必须由正常执行及期望输出证明")
            if 维度 == "Unicode":
                源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
                assert any(ord(字符) > 0xFFFF for 字符 in 源码) or any(
                    字符 in 源码 for 字符 in "ßİ"), (
                    f"{名} 的 Unicode 证据没有非 BMP 或特殊大小写字符")

        assert "直接" in 行["forms"]
        if 名 in 可点:
            assert "点调用" in 行["forms"]
            assert 行.get("receiver")
        else:
            assert "receiver" not in 行
        if "错误类型" not in 行["dimensions"]:
            assert "invalid_call" not in 行


@pytest.mark.parametrize(("内置名", "维度", "用例"), tuple(_黄金证据用例们()))
@pytest.mark.parametrize("登记", 后端参数们)
def test_合同矩阵黄金证据逐后端执行(内置名: str, 维度: str, 用例: Path, 登记):
    """矩阵中的每条黄金证据都有独立、可收集的真实执行节点。"""
    if (用例 / "输入.txt").exists() and not 登记.后端类.能力.支持交互输入:
        pytest.skip(f"{登记.名称} 声明不支持交互输入")
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    结果 = 跑_后端(源码, f"{内置名}-{维度}-{用例.name}", 登记, _输入文本(用例))
    输出文件 = 用例 / "期望输出.txt"
    if 输出文件.exists():
        期望输出 = 输出文件.read_text(encoding="utf-8").splitlines()
        assert 结果.诊断码们 == []
        assert 结果.输出行 == 期望输出
        if 登记.是子进程:
            assert 结果.子进程退出码 == 0, 结果.子进程错误输出
        return

    期望码 = (用例 / "期望诊断码.txt").read_text(encoding="utf-8").strip()
    assert 期望码 in 结果.诊断码们
    if 登记.是子进程 and 结果.后端已执行:
        assert 结果.子进程退出码 is not None
        assert 结果.子进程退出码 != 0
        assert 期望码 in 结果.子进程错误输出
        assert "CN9001" not in 结果.子进程错误输出


@pytest.mark.parametrize(
    ("行", "形式", "数量"),
    tuple(_错误参数数量用例们()),
    ids=lambda 值: 值["name"] if isinstance(值, dict) else str(值),
)
@pytest.mark.parametrize("登记", 后端参数们)
def test_内置错误参数数量统一报告CN0306(行, 形式: str, 数量: int, 登记):
    源码, 调用行 = _错误参数源码(行, 形式, 数量)
    后端, 诊断们 = _运行错误源码(
        登记, 源码, f"{行['name']}-{形式}-{数量}.cnp")

    assert [诊断.码 for 诊断 in 诊断们.条目] == ["CN0306"], (
        f"{登记.名称}：{源码} 实际诊断 "
        f"{[(诊断.码, 诊断.消息) for 诊断 in 诊断们.条目]}")
    诊断 = 诊断们.条目[0]
    assert 行["name"] in 诊断.消息
    报告数量 = 数量 + (1 if 形式 == "点调用" else 0)
    assert str(报告数量) in 诊断.消息
    assert (诊断.跨.起.行, 诊断.跨.起.列) == (调用行, 1)
    _断言子进程错误(登记, 后端, "CN0306")


def _非法类型用例们():
    用例们 = []
    for 行 in _合同矩阵行们():
        if "错误类型" not in 行["dimensions"]:
            continue
        调用们 = [行.get("invalid_call", ""), *行.get("invalid_calls", [])]
        for 序号, 源码 in enumerate(调用们, 1):
            用例们.append(pytest.param(行, 源码, id=f"{行['name']}-{序号}"))
    return tuple(用例们)


@pytest.mark.parametrize(("行", "源码"), _非法类型用例们())
@pytest.mark.parametrize("登记", 后端参数们)
def test_内置非法类型统一报告CN0303(行: 合同行, 源码: str, 登记):
    后端, 诊断们 = _运行错误源码(登记, 源码, f"{行['name']}-非法类型.cnp")

    assert [诊断.码 for 诊断 in 诊断们.条目] == ["CN0303"], (
        f"{登记.名称}：{源码} 实际诊断 "
        f"{[(诊断.码, 诊断.消息) for 诊断 in 诊断们.条目]}")
    诊断 = 诊断们.条目[0]
    assert (诊断.跨.起.行, 诊断.跨.起.列) == (1, 1)
    _断言子进程错误(登记, 后端, "CN0303")


@pytest.mark.parametrize("登记", 后端参数们)
def test_询问数值输入结束诊断落在调用处(登记):
    if not 登记.后端类.能力.支持交互输入:
        pytest.skip(f"{登记.名称} 声明不支持交互输入")
    后端, 诊断们 = _运行错误源码(
        登记, "询问数值()", "询问数值-输入结束.cnp")

    assert [诊断.码 for 诊断 in 诊断们.条目] == ["CN0310"], 登记.名称
    诊断 = 诊断们.条目[0]
    assert (诊断.跨.起.行, 诊断.跨.起.列) == (1, 1), 登记.名称
    _断言子进程错误(登记, 后端, "CN0310")


@pytest.mark.parametrize("登记", 后端参数们)
def test_点调用非法类型统一报告CN0303(登记):
    源码 = "设 表 = [1]\n表.连接(2)"
    后端, 诊断们 = _运行错误源码(登记, 源码, "点调用非法类型.cnp")

    assert [诊断.码 for 诊断 in 诊断们.条目] == ["CN0303"], 登记.名称
    诊断 = 诊断们.条目[0]
    assert (诊断.跨.起.行, 诊断.跨.起.列) == (2, 1), 登记.名称
    _断言子进程错误(登记, 后端, "CN0303")


@pytest.mark.parametrize("源码", (
    "打印(平方根(真))",
    "打印(最大(真))",
    '打印(随机数("甲", 1))',
))
@pytest.mark.parametrize("登记", 后端参数们)
def test_嵌套内置错误落在内层调用(源码: str, 登记):
    后端, 诊断们 = _运行错误源码(登记, 源码, "嵌套内置错误.cnp")

    assert [诊断.码 for 诊断 in 诊断们.条目] == ["CN0303"], 登记.名称
    诊断 = 诊断们.条目[0]
    assert (诊断.跨.起.行, 诊断.跨.起.列) == (1, 4), 登记.名称
    _断言子进程错误(登记, 后端, "CN0303")


def test_每个规范内置都有共享直接调用():
    正常语料 = sorted(p.parent for p in 语料根.glob("*/期望输出.txt"))
    直接, _ = _共享调用形式(正常语料)
    assert _规范内置名们() <= 直接, (
        f"缺少共享直接调用：{sorted(_规范内置名们() - 直接)}")


def test_每个点都有共享直接与点调用():
    正常语料 = sorted(p.parent for p in 语料根.glob("*/期望输出.txt"))
    直接, 点调用 = _共享调用形式(正常语料)
    可点 = set(PYTHON可点方法)
    assert 可点 <= 直接, f"缺少直接调用：{sorted(可点 - 直接)}"
    assert 可点 <= 点调用, f"缺少点调用：{sorted(可点 - 点调用)}"
