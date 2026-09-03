"""静态检查与 LSP 诊断测试。

关键：编辑器不执行代码，所以求值期才发现的错必须有静态版本。
但也不能有假阳性 —— 编辑器里误报比漏报更烦人。
"""
import pytest

from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


def 查(码: str) -> list[str]:
    源 = 源文件(码, "t.cnp")
    程, 袋 = 解析(源)
    if not 袋.有错:
        检查(程, 袋)
    return [d.码 for d in 袋]


# ---- 应该报错 ----

def test_条件字面量非布尔():
    assert "CN0301" in 查("如果 0\n    打印(1)")
    assert "CN0301" in 查('如果 "字"\n    打印(1)')
    assert "CN0301" in 查("循环 1\n    打印(1)")


def test_未声明变量():
    assert "CN0302" in 查("打印(没这个)")
    assert "CN0302" in 查("y = 1")


def test_切片四个子表达式都会检查名字():
    码们 = 查("打印(没对象[没起:没止:没步长])")
    assert 码们.count("CN0302") == 4


def test_除以字面量零():
    assert "CN0304" in 查("打印(1 / 0)")
    assert "CN0304" in 查("打印(1 // 0)")
    assert "CN0304" in 查("打印(1.0 / 0.0)")


def test_重复声明():
    assert "CN0307" in 查("令 x = 1\n令 x = 2")


# ---- 不该报错（假阳性防护）----

def test_布尔条件不报():
    assert 查("如果 真\n    打印(1)") == []
    assert 查("令 x = 1\n如果 x > 0\n    打印(1)") == []


def test_变量条件不报():
    """变量的值静态不可知，必须沉默。"""
    assert 查("令 x = 1\n如果 x\n    打印(1)") == []


def test_除以变量不报():
    assert 查("令 x = 0\n打印(1 / x)") == []


def test_递归函数不报():
    码 = """函数 阶乘(n)
    如果 n <= 1
        返回 1
    否则
        返回 n * 阶乘(n - 1)

打印(阶乘(5))
"""
    assert 查(码) == []


def test_函数前向引用不报():
    """顶层函数可以互相调用，不管定义顺序。"""
    码 = """函数 甲()
    返回 乙()

函数 乙()
    返回 1

打印(甲())
"""
    assert 查(码) == []


def test_块内声明不影响块外重复():
    码 = """如果 真
    令 x = 1
如果 真
    令 x = 2
"""
    assert 查(码) == []


def test_形参可用():
    assert 查("函数 f(a, b)\n    返回 a + b") == []


def test_内置函数不报未声明():
    assert 查("打印(长度(\"abc\"))") == []
    assert 查("打印(类型(1))") == []


def test_语法错误时不做静态检查():
    """残缺 AST 上做静态检查会产生噪音。"""
    码们 = 查("令 x =")
    assert "CN0201" in 码们 or "CN0203" in 码们
    # 不应因残缺 AST 冒出一堆未声明变量之类的噪音
    assert 码们.count("CN0302") == 0


# ---- LSP 层 ----

def test_lsp可选依赖只声明pygls二代():
    import tomllib
    from pathlib import Path

    配置 = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert 配置["project"]["optional-dependencies"]["lsp"] == ["pygls>=2,<3"]


def test_vscode探测会验证语言服务依赖():
    from pathlib import Path

    扩展 = (Path(__file__).parents[1] / "editors/vscode/extension.js").read_text()
    assert "import cnplus,cnplus.lsp.server,sys" in 扩展


def test_lsp诊断文本():
    pytest.importorskip("pygls")
    from cnplus.lsp.server import 诊断文本
    ds = 诊断文本("如果 0\n    打印(1)\n", "t.cnp")
    assert len(ds) == 1
    d = ds[0]
    assert d.code == "CN0301"
    assert d.source == "cnplus"
    # LSP 行列从 0 起
    assert d.range.start.line == 0
    # 波浪线必须有宽度，否则 VSCode 不画
    assert d.range.end.character > d.range.start.character
    assert "提示" in d.message


@pytest.mark.parametrize("码", ["函数", '打印("😀"', "设 名字 =", "如果 真\n"])
def test_lsp诊断范围不越过行尾(码):
    pytest.importorskip("pygls")
    from cnplus.lsp.server import 诊断文本

    行长们 = [len(行.encode("utf-16-le")) // 2 for 行 in 码.split("\n")]
    for 诊断 in 诊断文本(码):
        assert 诊断.range.end.character <= 行长们[诊断.range.end.line]


def test_lsp诊断列按utf16计算():
    pytest.importorskip("pygls")
    from cnplus.lsp.server import 诊断文本

    码 = '打印("😀", 未知)'
    d = next(项 for 项 in 诊断文本(码, "t.cnp") if 项.code == "CN0302")
    前缀 = '打印("😀", '
    assert d.range.start.character == len(前缀.encode("utf-16-le")) // 2
    assert d.range.end.character == len((前缀 + "未知").encode("utf-16-le")) // 2


def test_lsp输入列从utf16转为内部码点列():
    pytest.importorskip("pygls")
    from cnplus.lsp.server import _LSP列转内部列

    assert _LSP列转内部列("😀名字", 2) == 2
    assert _LSP列转内部列("😀名字", 4) == 4


def test_lsp范围覆盖完整标识符():
    pytest.importorskip("pygls")
    from cnplus.lsp.server import _跨度转LSP范围

    源 = 源文件("函数 算等级")
    范围 = _跨度转LSP范围(源, 源.跨度于(3, 6))
    assert (范围.start.character, 范围.end.character) == (3, 6)


@pytest.mark.parametrize("码", [
    "", "令", "令 x =", "函数 f(", "如果", "打印(", "@#$", "\n\n",
    "如果 真\n", "循环", "返回 返回",
])
def test_lsp半成品代码永不崩(码):
    """编辑器里代码永远是半成品 —— D-005 在 LSP 路径上的兑现。"""
    pytest.importorskip("pygls")
    from cnplus.lsp.server import 诊断文本
    ds = 诊断文本(码, "t.cnp")
    assert isinstance(ds, list)


def test_lsp所有语料不崩():
    """全部黄金语料过一遍 LSP 路径。"""
    pytest.importorskip("pygls")
    from pathlib import Path

    from cnplus.lsp.server import 诊断文本
    根 = Path(__file__).parent / "golden"
    for 用例 in sorted(根.glob("*/源.cnp")):
        ds = 诊断文本(用例.read_text(encoding="utf-8"), 用例.parent.name)
        assert isinstance(ds, list)
