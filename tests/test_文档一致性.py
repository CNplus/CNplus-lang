"""面向贡献者的文档必须与当前源码能力一致。"""
import json
import re
import tomllib
from pathlib import Path

from cnplus.backends.注册表 import 对拍后端们


根 = Path(__file__).parents[1]


def test_README能力来自当前后端和产品入口():
    文本 = (根 / "README.md").read_text(encoding="utf-8")
    for 后端 in 对拍后端们():
        assert 后端.名称 in 文本
    assert re.search(r"REPL \+ LSP 补全/悬停/跳转\s*\|\s*✅", 文本)
    assert re.search(r"JS 转译后端\s*\|\s*✅", 文本)
    assert re.search(r"字节码 VM\s*\|\s*⬜", 文本)


def test_README安装和示例数来自仓库事实():
    文本 = (根 / "README.md").read_text(encoding="utf-8")
    数量 = len(list((根 / "示例").glob("*.cnp")))
    文档数量 = re.search(r"(\d+) 个可直接运行的例子", 文本)
    assert 文档数量 and int(文档数量.group(1)) == 数量
    assert "ln -s" not in 文本
    assert "code --install-extension" in 文本
    assert "cnplus-*.vsix" in 文本
    assert "字典[键]" not in 文本
    assert "运行 --js` 需要 Node.js" in 文本


def test_README诊断示例匹配当前稳定格式():
    文本 = (根 / "README.md").read_text(encoding="utf-8")
    for 片段 in ("CN0302", "= 也就是说:", "= 这样改:", "发现 1 个问题。"):
        assert 片段 in 文本


def test_语义规范列出当前值类别与未定义边界():
    文本 = (根 / "docs/spec/00-语义约定.md").read_text(encoding="utf-8")
    for 名 in ("整数", "小数", "字符串", "布尔", "空", "列表", "字典", "函数", "类", "实例"):
        assert re.search(rf"^\| {名} \|", 文本, re.MULTILINE)
    assert "实例的类型名是所属类名" in 文本
    assert "字典的遍历顺序当前未定义" in 文本
    assert "尚未引入这些类型" not in 文本
    值源码 = (根 / "cnplus/runtime/values.py").read_text(encoding="utf-8")
    assert "六类值" not in 值源码


def test_规范索引状态对应文件系统():
    文本 = (根 / "docs/spec/README.md").read_text(encoding="utf-8")
    for 名 in ("00-语义约定.md", "03-诊断码.md"):
        行 = next(行 for 行 in 文本.splitlines() if f"`{名}`" in 行)
        assert "当前合同" in 行
        assert (根 / "docs/spec" / 名).exists()
    assert not list((根 / "docs/spec").glob("01-*"))
    assert not list((根 / "docs/spec").glob("02-*"))


def test_版本三处同步():
    项目 = tomllib.loads((根 / "pyproject.toml").read_text(encoding="utf-8"))
    初始 = (根 / "cnplus/__init__.py").read_text(encoding="utf-8")
    扩展 = json.loads((根 / "editors/vscode/package.json").read_text(encoding="utf-8"))
    初始版本 = re.search(r'__version__ = "([^"]+)"', 初始)
    assert 初始版本
    assert 项目["project"]["version"] == 初始版本.group(1) == 扩展["version"]


def test_CHANGELOG补记v082且保持版本倒序():
    文本 = (根 / "CHANGELOG.md").read_text(encoding="utf-8")
    assert 文本.count("## [0.8.2]") == 1
    assert 文本.index("## [0.9.0]") < 文本.index("## [0.8.2]") < 文本.index("## [0.8.1]")
    段 = 文本.split("## [0.8.2]", 1)[1].split("## [0.8.1]", 1)[0]
    assert "2026-08-24" in 段 and "452 个测试全绿" in 段
    assert "语言运行时与 VSCode 扩展代码没有变化" in 段


def test_本地Markdown链接有效():
    for 路径 in (根 / "README.md", 根 / "docs/spec/README.md", 根 / "docs/spec/00-语义约定.md"):
        for 目标 in re.findall(r"\[[^]]+\]\(([^)]+)\)", 路径.read_text(encoding="utf-8")):
            if "://" in 目标 or 目标.startswith("#"):
                continue
            assert (路径.parent / 目标.split("#", 1)[0]).exists(), (路径, 目标)


def test_本单元中文文档和门禁没有替换字符():
    路径们 = [根 / "README.md", 根 / "CHANGELOG.md", 根 / "cnplus/runtime/values.py"]
    路径们 += list((根 / "docs/spec").glob("*.md"))
    路径们 += list((根 / "tests").glob("*.py"))
    for 路径 in 路径们:
        assert "\ufffd" not in 路径.read_text(encoding="utf-8"), 路径
