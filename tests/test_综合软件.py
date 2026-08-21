"""综合软件测试：示例/15-待办清单.cnp 的端到端交互测试。

这是「用一个真实程序把所有语法跑一遍」的自动化版本。
喂固定的命令序列，断言完整输出 —— 任何语法回归都会在这里现形。
"""
from pathlib import Path

import pytest

from cnplus.backends.treewalk import 树遍历后端
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

_软件 = Path(__file__).resolve().parent.parent / "示例" / "15-待办清单.cnp"


def 交互跑(输入行: list[str]):
    码 = _软件.read_text(encoding="utf-8")
    源 = 源文件(码, _软件.name)
    程, 袋 = 解析(源)
    检查(程, 袋)
    assert not 袋.有错, f"静态检查失败：{[d.码 for d in 袋]}"
    剩 = list(输入行)

    def 喂():
        return 剩.pop(0) if 剩 else None

    出: list[str] = []
    树遍历后端(输出=出.append, 输入=喂).执行(程, 源, 袋)
    assert not 袋.有错, f"运行出错：{[d.码 for d in 袋]}"
    return 出


def test_看清单():
    出 = 交互跑(["1", "0"])
    文 = "\n".join(出)
    assert "读完 CNplus 教程" in 文
    assert "【高】" in 文 and "【中】" in 文 and "【低】" in 文
    assert "再见！" in 出


def test_加任务():
    出 = 交互跑(["2", "写测试", "3", "1", "0"])
    文 = "\n".join(出)
    assert "已添加 #4：写测试" in 文
    assert "#4 【高】写测试" in 文


def test_加任务_空内容被拒():
    出 = 交互跑(["2", "", "0"])
    assert "内容不能为空，没有添加。" in 出


def test_加任务_优先级越界回退到中():
    出 = 交互跑(["2", "某事", "9", "1", "0"])
    文 = "\n".join(出)
    assert "优先级只能是 1、2、3，按「中」处理。" in 文
    assert "#4 【中】某事" in 文


def test_完成任务():
    出 = 交互跑(["3", "2", "1", "0"])
    文 = "\n".join(出)
    assert "完成 #2：买菜" in 文
    assert "[√] #2" in 文


def test_完成不存在的编号():
    出 = 交互跑(["3", "99", "0"])
    assert "没有编号 99 的任务。" in 出


def test_重复完成():
    出 = 交互跑(["3", "1", "3", "1", "0"])
    assert "这条早就完成了。" in 出


def test_统计():
    出 = 交互跑(["3", "1", "4", "0"])
    文 = "\n".join(出)
    assert "共 3 条，完成 1 条，完成率 33%" in 文


def test_存档是合法JSON():
    import json
    出 = 交互跑(["5", "0"])
    行 = [l for l in 出 if l.startswith("[{")]
    assert 行, "没有找到 JSON 输出"
    数据 = json.loads(行[0])
    assert len(数据) == 3
    assert 数据[0]["内容"] == "读完 CNplus 教程"
    assert 数据[0]["优先级"] == 3


def test_非法命令():
    出 = 交互跑(["abc", "0"])
    assert "不认识命令「abc」，请输入 0-5。" in 出


def test_完整流程():
    """一整套操作：加、完成、统计、存档、退出。"""
    出 = 交互跑(["2", "新任务", "3", "3", "4", "4", "1", "0"])
    文 = "\n".join(出)
    assert "已添加 #4：新任务" in 文
    assert "完成 #4：新任务" in 文
    assert "共 4 条，完成 1 条" in 文
    assert "再见！" in 文
