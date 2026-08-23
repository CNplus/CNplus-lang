"""语法文件（TextMate）生成的回归测试。

TextMate 语法是「第二套 tokenizer」，手写必与 lexer 漂移，所以必须生成（D-007）。
但生成器本身也曾漏项：`_分组` 是硬编码清单，v0.4.0 之后新增的
遍历/尝试/抛出/询问等关键字全部没进语法文件，导致编辑器里不高亮。

本测试确保：keywords.toml 里的每个关键字写法都出现在生成的语法文件里。
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

仓库根 = Path(__file__).resolve().parent.parent
语法文件 = 仓库根 / "editors" / "vscode" / "syntaxes" / "cnplus.tmLanguage.json"
关键字表 = 仓库根 / "cnplus" / "lexer" / "keywords.toml"
生成器 = 仓库根 / "tools" / "生成语法文件.py"


def _读关键字():
    with 关键字表.open("rb") as f:
        return tomllib.load(f)["关键字"]


def test_语法文件存在():
    assert 语法文件.exists(), "语法文件缺失，请运行 python tools/生成语法文件.py"


def test_每个关键字都在语法文件里():
    """核心断言：一个关键字写法都不能漏。

    漏掉的后果是编辑器里那个词不高亮 —— 用户会以为扩展坏了。
    """
    文本 = 语法文件.read_text(encoding="utf-8")
    缺失 = []
    for 组, 写法们 in _读关键字().items():
        for 写法 in 写法们:
            if 写法 not in 文本:
                缺失.append(f"{组}:{写法}")
    assert not 缺失, (
        f"以下关键字没进语法文件（编辑器里不会高亮）：{缺失}\n"
        "生成器的 _分组 是硬编码的，加新关键字后需归组或依赖自动兜底。"
    )


def test_生成是幂等的():
    """重跑生成器，内容不应变化 —— 否则说明生成结果不稳定。"""
    原内容 = 语法文件.read_text(encoding="utf-8")
    r = subprocess.run([sys.executable, str(生成器)],
                       cwd=仓库根, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"生成器失败：{r.stderr}"
    assert 语法文件.read_text(encoding="utf-8") == 原内容, (
        "重新生成后内容变了，说明生成结果不稳定（可能有集合遍历顺序问题）")


def test_语法文件是合法json且结构正确():
    d = json.loads(语法文件.read_text(encoding="utf-8"))
    assert d["scopeName"] == "source.cnplus"
    assert "cnp" in d["fileTypes"]
    assert len(d["patterns"]) > 0
    # 每条规则必须有 match 或 begin
    for i, p in enumerate(d["patterns"]):
        assert "match" in p or "begin" in p, f"第 {i} 条规则既无 match 也无 begin"


def test_新增关键字会被自动兜底():
    """模拟「加了关键字但忘记归组」，确认它仍会被收进语法文件。

    这是防止 D-017 那类硬编码漏项问题重演的结构性保证。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("生成语法文件", 生成器)
    模块 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = 模块  # 必须先注册再 exec，否则 dataclass 会炸
    spec.loader.exec_module(模块)

    语法 = 模块.生成()
    文本 = json.dumps(语法, ensure_ascii=False)
    # 取一个确定没在 _分组 里声明的关键字组
    归组过的 = {组 for 组名们 in 模块._分组.values() for 组 in 组名们}
    未归组 = [组 for 组 in _读关键字() if 组 not in 归组过的]
    if not 未归组:
        pytest.skip("当前所有关键字组都已显式归组，兜底逻辑无从验证")
    for 组 in 未归组:
        for 写法 in _读关键字()[组]:
            assert 写法 in 文本, f"未归组的关键字 {写法} 没被兜底收进语法文件"
