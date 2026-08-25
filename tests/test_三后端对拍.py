"""三后端对拍 —— 阶段 4 的核心保险（T1）。

黄金语料用 树遍历 / Python 转译 / JS 转译 三个后端各跑一遍，
输出逐字一致才算过。JS 后端逐任务点亮，未点亮的语料在
`已点亮` 集合里登记；全部点亮后删除该集合的逐条登记。
"""
from pathlib import Path

import pytest

from cnplus.backends.python_emit import Python转译后端
from cnplus.backends.treewalk import 树遍历后端
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

语料根 = Path(__file__).parent / "golden"

# JS 后端已支持全部正常语料（T4-T9 完成后全量点亮）
已点亮 = {q.parent.name for q in 语料根.glob("*/期望输出.txt")}


def node可用() -> bool:
    import shutil
    return shutil.which("node") is not None


def _收集正常():
    return sorted(p.parent for p in 语料根.glob("*/期望输出.txt"))


def 跑_树遍历(源码: str, 文件名: str) -> list[str]:
    源 = 源文件(源码, 文件名)
    程, 袋 = 解析(源)
    if 袋.有错:
        return []
    后 = 树遍历后端(输出=lambda 行: None)
    后.执行(程, 源, 袋)
    return 后.输出行


def 跑_转译(源码: str, 文件名: str) -> list[str]:
    源 = 源文件(源码, 文件名)
    程, 袋 = 解析(源)
    if 袋.有错:
        return []
    出 = []
    Python转译后端(输出=出.append).执行(程, 源, 袋)
    return 出


def 跑_JS(源码: str, 文件名: str) -> list[str]:
    """生成 JS → node 执行 → 收集 stdout 行。"""
    源 = 源文件(源码, 文件名)
    程, 袋 = 解析(源)
    if 袋.有错:
        return []
    from cnplus.backends.js_emit import 发射 as js发射
    import subprocess, tempfile, os
    with tempfile.TemporaryDirectory() as 目录:
        路径 = Path(目录) / "t.js"
        js = js发射(程)[0]
        路径.write_text(js, encoding="utf-8")
        r = subprocess.run(["node", str(路径)], capture_output=True,
                           text=True, timeout=30)
        return [行 for 行 in r.stdout.split("\n") if 行 != ""]


@pytest.mark.skipif(not node可用(), reason="本机无 node")
@pytest.mark.parametrize("用例",
                         [p for p in _收集正常() if p.name in 已点亮],
                         ids=lambda p: p.name)
def test_三后端对拍(用例: Path):
    源码 = (用例 / "源.cnp").read_text(encoding="utf-8")
    树 = 跑_树遍历(源码, 用例.name)
    译 = 跑_转译(源码, 用例.name)
    js = 跑_JS(源码, 用例.name)
    assert 树 == 译, f"树遍历 vs Python转译 不一致：\n树:{树}\n译:{译}"
    assert 树 == js, f"树遍历 vs JS转译 不一致：\n树:{树}\nJS:{js}"


def test_点亮清单合法():
    """已点亮 必须是真实存在的语料名，防拼错。"""
    名单 = {p.name for p in _收集正常()}
    for 名 in 已点亮:
        assert 名 in 名单, f"已点亮 里有不存在的语料：{名}"
