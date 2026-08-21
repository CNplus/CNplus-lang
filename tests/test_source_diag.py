"""source.py 与 diagnostics.py 的测试。"""
from cnplus.diagnostics import (CN0301_条件必须是布尔, 渲染, 诊断袋, 级别)
from cnplus.source import 位置, 合并跨度, 源文件, 跨度


def test_位置基本():
    p = 位置(行=1, 列=1, 偏移=0)
    assert str(p) == "1:1"


def test_跨度长度与单行():
    s = 跨度(位置(1, 1, 0), 位置(1, 4, 3))
    assert s.长度 == 3
    assert s.单行


def test_跨度非法():
    import pytest
    with pytest.raises(ValueError):
        跨度(位置(1, 5, 4), 位置(1, 1, 0))


def test_跨度合并():
    a = 跨度(位置(1, 1, 0), 位置(1, 2, 1))
    b = 跨度(位置(2, 1, 10), 位置(2, 3, 12))
    合 = a.合并(b)
    assert 合.起.偏移 == 0 and 合.止.偏移 == 12
    assert not 合.单行
    # 顺序无关
    assert b.合并(a) == 合
    assert 合并跨度(a, b, a) == 合


def test_源文件行索引():
    源 = 源文件("第一行\n第二行\n第三行", "x.cnp")
    assert 源.行数 == 3
    assert 源.取行(1) == "第一行"
    assert 源.取行(2) == "第二行"
    assert 源.取行(3) == "第三行"
    assert 源.取行(4) == ""
    assert 源.取行(0) == ""


def test_源文件位置换算():
    源 = 源文件("令 x = 1\n打印(x)")
    p = 源.位置于(0)
    assert (p.行, p.列) == (1, 1)
    # "令 x = 1" 共 7 字，换行在偏移 7，故第二行起于偏移 8
    p2 = 源.位置于(8)
    assert (p2.行, p2.列) == (2, 1)
    p3 = 源.位置于(10)
    assert (p3.行, p3.列) == (2, 3)


def test_源文件取原文():
    源 = 源文件("令 x = 1")
    跨 = 源.跨度于(0, 1)
    assert 源.原文(跨) == "令"


def test_诊断袋收集():
    源 = 源文件("如果 0\n    打印(1)", "t.cnp")
    袋 = 诊断袋()
    assert not 袋.有错
    袋.报告(CN0301_条件必须是布尔, "条件必须是布尔值，这里是整数", 源.跨度于(3, 4),
           提示="改成 如果 0 != 0")
    assert 袋.有错
    assert len(袋) == 1


def test_渲染宽字符对齐():
    """中文占两列，波浪线必须落在正确位置 —— 这是最容易错的地方。"""
    源 = 源文件("如果 0", "t.cnp")
    袋 = 诊断袋()
    袋.报告(CN0301_条件必须是布尔, "条件必须是布尔值", 源.跨度于(3, 4))
    出 = 渲染(袋.条目[0], 源)
    行 = 出.split("\n")
    源码行 = [l for l in 行 if l.startswith("1 | ")][0]
    波浪行 = [l for l in 行 if "^" in l][0]
    # "如果 " 显示宽度 = 2+2+1 = 5，故波浪线前应有 5 个空格
    前缀 = 波浪行.split("| ")[1]
    assert 前缀 == " " * 5 + "^", repr(前缀)
    assert "如果 0" in 源码行


def test_渲染含提示():
    源 = 源文件("令 x = 1", "t.cnp")
    袋 = 诊断袋()
    袋.报告("CN9999", "测试消息", 源.跨度于(0, 1), 提示="这是提示")
    出 = 渲染(袋.条目[0], 源)
    assert "这样改: 这是提示" in 出
    assert "t.cnp:1:1" in 出
    assert "错误[CN9999]" in 出


def test_渲染跨行():
    源 = 源文件('令 s = "没闭合\n下一行', "t.cnp")
    袋 = 诊断袋()
    袋.报告("CN0102", "字符串未闭合", 源.跨度于(7, 14))
    出 = 渲染(袋.条目[0], 源)
    assert "错误延续至第 2 行" in 出


def test_级别():
    assert str(级别.错误) == "错误"
    assert str(级别.警告) == "警告"
