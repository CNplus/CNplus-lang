"""共享语料对拍 —— 多后端语义的发布门槛。

每个可对拍后端均走「解析 → 检查 → 执行」完整路径。正常语料要求
无诊断、输出等于期望，子进程后端还必须成功退出；错误语料要求诊断码
符合期望，已实际启动的子进程必须以失败状态退出。
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from cnplus.backends.base import 后端
from cnplus.backends.注册表 import 对拍后端们
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

语料根 = Path(__file__).parent / "golden"

def node可用() -> bool:
    import shutil
    return shutil.which("node") is not None


def test_对拍后端注册表合法():
    """新增后端只需登记，不要在每个对拍测试里另写名称或数量。"""
    登记们 = 对拍后端们()
    assert 登记们
    assert len({登记.名称 for 登记 in 登记们}) == len(登记们)
    assert all(登记.名称 and issubclass(登记.后端类, 后端) for 登记 in 登记们)


@dataclass(frozen=True)
class 运行结果:
    输出行: list[str]
    诊断码们: list[str]
    子进程退出码: int | None
    子进程错误输出: str


def _收集(标记文件: str):
    return sorted(p.parent for p in 语料根.glob(f"*/{标记文件}"))


def 跑_后端(源码: str, 文件名: str, 登记) -> 运行结果:
    """让每个后端独立走完整前端与执行路径。"""
    源 = 源文件(源码, 文件名)
    程, 袋 = 解析(源)
    if not 袋.有错:
        检查(程, 袋)

    后 = None
    if not 袋.有错:
        后 = 登记.后端类(输出=lambda _: None)
        后.执行(程, 源, 袋)

    return 运行结果(
        输出行=[] if 后 is None else 后.输出行,
        诊断码们=[d.码 for d in 袋],
        子进程退出码=None if 后 is None else getattr(后, "最后退出码", None),
        子进程错误输出="" if 后 is None else getattr(后, "最后错误输出", ""),
    )


def _收集正常():
    return sorted(p.parent for p in 语料根.glob("*/期望输出.txt"))


@pytest.mark.skipif(not node可用(), reason="本机无 node")
@pytest.mark.parametrize("用例",
                         _收集正常(),
                         ids=lambda p: p.name)
def test_三后端对拍(用例: Path):
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望 = (用例 / "期望输出.txt").read_text(encoding="utf-8").splitlines()
    for 登记 in 对拍后端们():
        结果 = 跑_后端(源码, 用例.name, 登记)
        assert 结果.诊断码们 == [], f"{登记.名称} 不该报错：{结果.诊断码们}"
        assert 结果.输出行 == 期望, (
            f"{用例.name}：{登记.名称} 输出不等于期望\n"
            f"期望: {期望}\n实际: {结果.输出行}")
        if 登记.是子进程:
            assert 结果.子进程退出码 == 0, (
                f"{用例.name}：{登记.名称} 未成功退出\n"
                f"stderr: {结果.子进程错误输出}")


@pytest.mark.skipif(not node可用(), reason="本机无 node")
@pytest.mark.parametrize("用例", _收集("期望诊断码.txt"), ids=lambda p: p.name)
def test_三后端错误语料对拍(用例: Path):
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    期望码 = (用例 / "期望诊断码.txt").read_text(encoding="utf-8").strip()
    for 登记 in 对拍后端们():
        结果 = 跑_后端(源码, 用例.name, 登记)
        assert 期望码 in 结果.诊断码们, (
            f"{用例.name}：{登记.名称} 应报 {期望码}，实际 {结果.诊断码们}")
        if 登记.是子进程 and 结果.子进程退出码 is not None:
            assert 结果.子进程退出码 != 0, (
                f"{用例.name}：{登记.名称} 已运行并报告错误，却成功退出")


def test_点亮清单合法():
    """正常语料必须全量进入对拍，不能用临时清单静默排除。"""
    assert _收集正常()
