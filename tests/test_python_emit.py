"""Python 转译后端测试。

核心是**对拍**：同一段程序，树遍历后端和转译后端的输出必须完全一致。
这是防「语义泄漏」的关键 —— 如果转译后端偷偷用了 Python 语义
（比如 if 0 当假、1=="1" 返回假），对拍就会失败。

外加：生成的 .py 必须能独立运行（不依赖 cnplus 包）。
"""
import subprocess
import sys
from pathlib import Path

import pytest

from cnplus.backends.python_emit import Python转译后端, 编译到文件
from cnplus.backends.treewalk import 树遍历后端
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

语料根 = Path(__file__).parent / "golden"
示例根 = Path(__file__).parent.parent / "示例"


def _跑(码: str, 后端类, 文件名="t.cnp"):
    源 = 源文件(码, 文件名)
    程, 袋 = 解析(源)
    if 袋.有错:
        return None, [d.码 for d in 袋]
    检查(程, 袋)
    if 袋.有错:
        return None, [d.码 for d in 袋]
    输出 = []
    后 = 后端类(输出=输出.append)
    后.执行(程, 源, 袋)
    if 袋.有错:
        return None, [d.码 for d in 袋]
    return 输出, []


# ==================== 对拍：两后端结果一致 ====================

正常语料 = sorted(语料根.glob("*/期望输出.txt"))


@pytest.mark.parametrize("用例", [p.parent for p in 正常语料],
                         ids=lambda p: p.name)
def test_对拍_正常语料(用例: Path):
    码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    树输出, 树错 = _跑(码, 树遍历后端, 用例.name)
    译输出, 译错 = _跑(码, Python转译后端, 用例.name)
    assert 树错 == [] and 译错 == [], f"不该报错：树{树错} 译{译错}"
    assert 树输出 == 译输出, (
        f"\n{用例.name} 两后端输出不一致（语义泄漏！）\n"
        f"树遍历: {树输出}\n转译  : {译输出}")


@pytest.mark.parametrize("用例", [p.parent for p in 正常语料],
                         ids=lambda p: p.name)
def test_对拍_匹配期望输出(用例: Path):
    码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望 = (用例 / "期望输出.txt").read_text(encoding="utf-8")
    译输出, 译错 = _跑(码, Python转译后端, 用例.name)
    assert 译错 == []
    实际 = "".join(行 + "\n" for 行 in 译输出)
    assert 实际 == 期望


示例文件 = sorted(示例根.glob("*.cnp"))


@pytest.mark.parametrize("文件", 示例文件, ids=lambda p: p.stem)
def test_对拍_示例(文件: Path):
    码 = 文件.read_text(encoding="utf-8")
    # 需要用户输入的示例无法在无人环境下跑，跳过（交互性由手动/专项测试覆盖）
    if "询问(" in 码 or "询问数值(" in 码:
        pytest.skip("需要用户输入")
    # 猜数字/随机数结果每次不同，用固定种子的例子才对拍;含随机的只查不报错
    含随机 = "随机数" in 码 or "random" in 码
    树输出, 树错 = _跑(码, 树遍历后端, 文件.name)
    译输出, 译错 = _跑(码, Python转译后端, 文件.name)
    assert 树错 == [] and 译错 == [], f"{文件.name}: 树{树错} 译{译错}"
    if not 含随机:
        assert 树输出 == 译输出, f"{文件.name} 输出不一致"


# ==================== 错误语料：转译后端也要报同样的码 ====================

错误语料 = sorted(语料根.glob("*/期望诊断码.txt"))


@pytest.mark.parametrize("用例", [p.parent for p in 错误语料],
                         ids=lambda p: p.name)
def test_转译后端报同样的错误码(用例: Path):
    码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望码 = (用例 / "期望诊断码.txt").read_text(encoding="utf-8").strip()
    _, 译错 = _跑(码, Python转译后端, 用例.name)
    assert 期望码 in 译错, f"{用例.name}: 期望 {期望码}，得到 {译错}"


# ==================== 生成的 .py 独立运行 ====================

def test_生成的py能独立运行(tmp_path: Path):
    """生成的文件不依赖 cnplus 包，任意 python3 都能跑。"""
    码 = '打印("独立运行成功")\n设 x = 6 * 7\n打印(文本(x))'
    源 = 源文件(码, "t.cnp")
    程, 袋 = 解析(源)
    assert not 袋.有错
    目标 = tmp_path / "out.py"
    编译到文件(程, 目标)
    # 用一个干净的 cwd 跑，确保不是碰巧 import 到 cnplus
    结果 = subprocess.run([sys.executable, str(目标)],
                        capture_output=True, text=True, cwd=str(tmp_path))
    assert 结果.returncode == 0, 结果.stderr
    assert 结果.stdout == "独立运行成功\n42\n"


def test_生成的py不含cnplus导入(tmp_path: Path):
    码 = '打印("你好")'
    源 = 源文件(码, "t.cnp")
    程, 袋 = 解析(源)
    目标 = tmp_path / "out.py"
    编译到文件(程, 目标)
    文本 = 目标.read_text(encoding="utf-8")
    # 只看行首的真实导入语句，排除文档字符串里的说明文字
    导入行 = [l for l in 文本.splitlines()
            if l.lstrip().startswith(("import cnplus", "from cnplus"))]
    assert 导入行 == [], f"生成的文件不该依赖 cnplus：{导入行}"


# ==================== 导入 Python 库 ====================

def test_导入标准库():
    码 = '导入 "math" 作为 数学\n打印(文本(数学.sqrt(144)))'
    输出, 错 = _跑(码, Python转译后端)
    assert 错 == []
    assert 输出 == ["12.0"]


def test_导入无别名用末段名():
    码 = '导入 "math"\n打印(文本(math.floor(3.7)))'
    输出, 错 = _跑(码, Python转译后端)
    assert 错 == [] and 输出 == ["3"]


def test_导入不存在的库报错():
    码 = '导入 "根本没有这个库xyz"'
    _, 错 = _跑(码, Python转译后端)
    assert 错  # 报错而非崩溃


def test_库异常定位到正确的源行():
    """math.sqrt(-1) 在第 3 行出错，诊断必须指向第 3 行而不是导入行。

    这是行映射的回归测试：运行时源码是一整块多行文本，
    若不逐行拆开映射，所有行号都会错位。
    """
    from cnplus.diagnostics import 诊断袋
    码 = '导入 "math" 作为 数学\n打印("开始")\n设 x = 数学.sqrt(-1)\n'
    源 = 源文件(码, "t.cnp")
    程, 袋 = 解析(源)
    检查(程, 袋)
    后 = Python转译后端(输出=lambda x: None)
    后.执行(程, 源, 袋)
    错误们 = [d for d in 袋 if d.码 == "CN9001"]
    assert 错误们, "应报库异常"
    assert 错误们[0].跨.起.行 == 3, f"应指向第 3 行，实际第 {错误们[0].跨.起.行} 行"


# ==================== 语义不泄漏（转译后端也守约定）====================

def test_转译_严格真值():
    _, 错 = _跑("如果 0\n    打印(1)", Python转译后端)
    assert "CN0301" in 错


def test_转译_除法恒为小数():
    输出, 错 = _跑("打印(4 / 2)", Python转译后端)
    assert 错 == [] and 输出 == ["2.0"]


def test_转译_跨类型比较报错():
    _, 错 = _跑('打印(1 == "1")', Python转译后端)
    assert "CN0303" in 错


def test_转译_短路():
    输出, 错 = _跑("打印(真 或 1 > 0)\n打印(假 与 1 > 0)", Python转译后端)
    assert 错 == [] and 输出 == ["真", "假"]


def test_转译_块级作用域():
    码 = "如果 真\n    设 x = 1\n如果 真\n    设 x = 2\n打印(\"好\")"
    输出, 错 = _跑(码, Python转译后端)
    assert 错 == [] and 输出 == ["好"]


def test_转译_重复声明报错():
    _, 错 = _跑("设 x = 1\n设 x = 2", Python转译后端)
    assert "CN0307" in 错


def test_转译_未声明变量报错():
    _, 错 = _跑("打印(没这个)", Python转译后端)
    assert "CN0302" in 错
