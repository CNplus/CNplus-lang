"""CLI 产品入口合同。"""
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from cnplus.cli import main


示例根 = Path(__file__).parents[1] / "示例"
JS排除示例 = {
    "07-猜数字.cnp": "需要交互输入",
    "10-读写文件.cnp": "使用导入",
    "15-待办清单.cnp": "需要交互输入并使用导入",
    "17-通讯录.cnp": "使用导入",
}
JS适用示例 = [
    路径 for 路径 in sorted(示例根.glob("*.cnp"))
    if 路径.name not in JS排除示例
]


def test_运行_js使用js后端(tmp_path, capfd):
    源 = tmp_path / "示例.cnp"
    源.write_text("打印(40 + 2)", encoding="utf-8")

    assert main(["运行", "--js", str(源)]) == 0
    捕获 = capfd.readouterr()
    assert 捕获.out.strip() == "42"
    assert 捕获.err == ""


def test_运行_js保留中文诊断映射(tmp_path, capfd):
    源 = tmp_path / "错误.cnp"
    源.write_text('函数 零()\n    返回 0\n打印(1 / 零())', encoding="utf-8")

    assert main(["运行", "--js", str(源)]) == 1
    捕获 = capfd.readouterr()
    assert "CN0304" in 捕获.err
    assert "除数不能是零" in 捕获.err
    assert "Node.js v" not in 捕获.err


def test_编译_js缺文件返回用法错误(capsys):
    assert main(["编译", "--js"]) == 2
    捕获 = capsys.readouterr()
    assert "编译 --js 需要一个文件名" in 捕获.err


@pytest.mark.parametrize("参数", [
    ["运行", "{源}", "--未知"],
    ["编译", "--未知", "{源}"],
])
def test_未知选项不被静默忽略(tmp_path, capsys, 参数):
    源 = tmp_path / "示例.cnp"
    源.write_text("打印(1)", encoding="utf-8")
    实参 = [项.format(源=源) for 项 in 参数]

    assert main(实参) == 2
    assert "不认识的选项 '--未知'" in capsys.readouterr().err


def test_help列出交互和js入口(capsys):
    assert main(["--help"]) == 0
    文本 = capsys.readouterr().out
    assert "cnp 交互" in 文本
    assert "cnp 运行 --js <文件.cnp>" in 文本
    assert "cnp 编译 --js <文件.cnp>" in 文本
    assert "JS 后端暂不支持「导入」" in 文本


def test_运行后端选项放在文件后会明确报错(tmp_path, capsys):
    源 = tmp_path / "示例.cnp"
    源.write_text("打印(1)", encoding="utf-8")

    assert main(["运行", str(源), "--js"]) == 2
    assert "后端选项要写在文件名前" in capsys.readouterr().err


@pytest.mark.parametrize("参数", [
    ["运行", "--js", "--python"],
    ["运行", "--python", "--js"],
    ["运行", "--js", "--js"],
])
def test_运行拒绝重复或冲突后端选项(capsys, 参数):
    assert main(参数) == 2
    assert "一次只能选择一个后端选项" in capsys.readouterr().err


@pytest.mark.parametrize("参数", [
    ["运行", "{源}", "多余"],
    ["编译", "{源}", "{目标}", "多余"],
    ["检查", "{源}", "多余"],
])
def test_多余位置参数不被静默忽略(tmp_path, capsys, 参数):
    源 = tmp_path / "示例.cnp"
    源.write_text("打印(1)", encoding="utf-8")
    实参 = [项.format(源=源, 目标=tmp_path / "输出.py") for 项 in 参数]

    assert main(实参) == 2
    assert "多余的参数" in capsys.readouterr().err


def test_版本不忽略多余参数(capsys):
    assert main(["版本", "多余"]) == 2
    assert "多余的参数" in capsys.readouterr().err


def test_运行_js在读取输入前显示提示(tmp_path):
    源 = tmp_path / "询问.cnp"
    源.write_text('设 名字 = 询问("名字：")\n打印(@"你好，{名字}")', encoding="utf-8")
    进程 = subprocess.Popen(
        [sys.executable, "-m", "cnplus.cli", "运行", "--js", str(源)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    标准输入, 标准输出 = 进程.stdin, 进程.stdout
    assert 标准输入 is not None and 标准输出 is not None
    提示盒: list[bytes] = []
    读线程 = threading.Thread(
        target=lambda: 提示盒.append(
            os.read(标准输出.fileno(), len("名字：".encode("utf-8")))
        ),
        daemon=True,
    )
    try:
        读线程.start()
        读线程.join(timeout=2)
        if 读线程.is_alive():
            进程.kill()
            进程.communicate()
            pytest.fail("JS 子进程读取输入前没有显示提示")
        assert 提示盒[0].decode("utf-8") == "名字："
        标准输入.write("小明\n".encode("utf-8"))
        标准输入.flush()
        输出, 错误 = 进程.communicate(timeout=10)
    finally:
        if 进程.poll() is None:
            进程.kill()
            进程.communicate()
    assert 进程.returncode == 0, 错误.decode("utf-8")
    assert 输出.decode("utf-8").strip() == "你好，小明"


@pytest.mark.parametrize("示例", JS适用示例, ids=lambda 路径: 路径.stem)
def test_运行_js跑通适用示例(示例):
    结果 = subprocess.run(
        [sys.executable, "-m", "cnplus.cli", "运行", "--js", str(示例)],
        text=True, capture_output=True, timeout=10,
    )
    assert 结果.returncode == 0, f"{示例.name}\n{结果.stderr}"


def test_JS示例排除清单没有过期():
    文件名们 = {路径.name for 路径 in 示例根.glob("*.cnp")}
    assert set(JS排除示例) <= 文件名们
