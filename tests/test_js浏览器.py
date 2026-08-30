"""JS 生成物在 Node 与浏览器式宿主中的产品边界。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cnplus.backends.js_emit import JS转译后端, 编译到文件 as 编译JS
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


示例根 = Path(__file__).parents[1] / "示例"
浏览器排除示例 = {
    "07-猜数字.cnp": "需要交互输入",
    "10-读写文件.cnp": "使用导入",
    "15-待办清单.cnp": "需要交互输入并使用导入",
    "17-通讯录.cnp": "使用导入",
}
浏览器适用示例 = [
    路径 for 路径 in sorted(示例根.glob("*.cnp"))
    if 路径.name not in 浏览器排除示例
]


def _编译(码: str, 路径):
    源 = 源文件(码, "浏览器.cnp")
    程, 袋 = 解析(源)
    检查(程, 袋)
    assert not 袋.有错
    return 编译JS(程, 路径)


def test_JS后端显式声明产品能力():
    能力 = JS转译后端.能力
    assert 能力.运行环境们 == ("Node", "浏览器")
    assert 能力.支持交互输入
    assert not 能力.支持导入


def test_JS直通交互不设置固定超时(tmp_path, monkeypatch):
    源 = 源文件("打印(1)", "直通.cnp")
    程, 袋 = 解析(源)
    检查(程, 袋)
    assert not 袋.有错
    观察 = {}

    def 假运行(*参数, **选项):
        观察["timeout"] = 选项.get("timeout")
        return subprocess.CompletedProcess(参数[0], 0, stdout=None, stderr="")

    monkeypatch.setattr(subprocess, "run", 假运行)
    后 = JS转译后端(直通输出=True)
    后.执行(程, 源, 袋)
    assert 观察["timeout"] is None


def test_生成js在浏览器式宿主支持询问(tmp_path):
    生成物 = _编译(
        '设 名字 = 询问("名字：")\n'
        '设 数值 = 询问数值("数字：")\n'
        '打印(@"你好，{名字}")\n'
        '打印(数值 + 1)',
        tmp_path / "程序.js",
    )
    驱动 = tmp_path / "浏览器沙箱.js"
    驱动.write_text(
        'const fs = require("fs");\n'
        'const vm = require("vm");\n'
        'const 输出 = [];\n'
        'const 回答 = ["小明", "41"];\n'
        'const 沙箱 = {\n'
        '  console: { log: (...a) => 输出.push(["输出", a.join(" ")]),\n'
        '             error: (...a) => 输出.push(["错误", a.join(" ")]) },\n'
        '  prompt: (提示) => { 输出.push(["提示", 提示]); return 回答.shift(); },\n'
        '};\n'
        'vm.runInNewContext("if (typeof process !== \'undefined\' || typeof Buffer !== \'undefined\' || typeof require !== \'undefined\') throw new Error(\'泄漏 Node 全局\')", 沙箱);\n'
        'vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), 沙箱);\n'
        'process.stdout.write(JSON.stringify(输出));\n',
        encoding="utf-8",
    )

    结果 = subprocess.run(["node", 驱动, 生成物], text=True,
                        capture_output=True, timeout=10)
    assert 结果.returncode == 0, 结果.stderr
    assert json.loads(结果.stdout) == [
        ["提示", "名字："], ["提示", "数字："],
        ["输出", "你好，小明"], ["输出", "42"],
    ]


@pytest.mark.parametrize("示例", 浏览器适用示例, ids=lambda 路径: 路径.stem)
def test_生成js在浏览器式宿主跑通适用示例(tmp_path, 示例):
    生成物 = _编译(示例.read_text(encoding="utf-8"), tmp_path / "程序.js")
    驱动 = tmp_path / "浏览器沙箱.js"
    驱动.write_text(
        'const fs = require("fs");\n'
        'const vm = require("vm");\n'
        'const 输出 = [];\n'
        'const 沙箱 = { console: { log: (...a) => 输出.push(a.join(" ")), error: () => {} },\n'
        '  prompt: () => { throw new Error("不应询问"); } };\n'
        'vm.runInNewContext("if (typeof process !== \'undefined\' || typeof Buffer !== \'undefined\' || typeof require !== \'undefined\') throw new Error(\'泄漏 Node 全局\')", 沙箱);\n'
        'vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), 沙箱);\n'
        'process.stdout.write(JSON.stringify(输出));\n',
        encoding="utf-8",
    )
    结果 = subprocess.run(["node", 驱动, 生成物], text=True,
                        capture_output=True, timeout=10)
    assert 结果.returncode == 0, f"{示例.name}\n{结果.stderr}"
    assert json.loads(结果.stdout), f"{示例.name} 没有产生输出"


def test_浏览器示例排除清单没有过期():
    文件名们 = {路径.name for 路径 in 示例根.glob("*.cnp")}
    assert set(浏览器排除示例) <= 文件名们
