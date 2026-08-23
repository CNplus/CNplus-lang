"""词法器测试。"""
from cnplus.lexer.lexer import 扫描
from cnplus.lexer.normalize import 归一化
from cnplus.lexer.tokens import 关键字映射, 种类
from cnplus.source import 源文件


def 种类们(码: str) -> list[种类]:
    词元们, _ = 扫描(源文件(码))
    return [t.种 for t in 词元们]


def 扫(码: str):
    return 扫描(源文件(码, "t.cnp"))


def test_关键字别名同种类():
    m = 关键字映射()
    assert m["如果"] is m["若"] is 种类.如果
    assert m["循环"] is m["当"] is 种类.循环
    assert m["函数"] is m["定义"] is m["过程"] is 种类.函数
    assert m["设"] is m["令"] is m["让"] is 种类.令
    assert m["如果"] is m["假如"] is 种类.如果
    assert m["循环"] is m["重复"] is 种类.循环


def test_归一化保持长度():
    原 = "打印（1，2）"
    出 = 归一化(原)
    assert 出 == "打印(1,2)"
    assert len(出) == len(原)  # 偏移必须仍然对得上


def test_全角源码可扫描():
    词元们, 袋 = 扫("打印（1，2）")
    assert not 袋.有错
    assert [t.种 for t in 词元们][:6] == [
        种类.标识符, 种类.左括号, 种类.整数, 种类.逗号, 种类.整数, 种类.右括号]


def test_中文标识符():
    词元们, 袋 = 扫("令 计数器 = 1")
    assert not 袋.有错
    assert 词元们[0].种 is 种类.令
    assert 词元们[1].种 is 种类.标识符 and 词元们[1].文本 == "计数器"
    assert 词元们[3].种 is 种类.整数 and 词元们[3].值 == 1


def test_数字():
    词元们, 袋 = 扫("1 2.5 100")
    assert not 袋.有错
    数 = [t for t in 词元们 if t.种 in (种类.整数, 种类.小数)]
    assert [t.值 for t in 数] == [1, 2.5, 100]


def test_非法数字():
    词元们, 袋 = 扫("123abc")
    assert 袋.有错
    assert 袋.条目[0].码 == "CN0103"


def test_字符串与转义():
    词元们, 袋 = 扫(r'"你好\n世界"')
    assert not 袋.有错
    assert 词元们[0].种 is 种类.字符串
    assert 词元们[0].值 == "你好\n世界"


def test_未闭合字符串():
    词元们, 袋 = 扫('令 s = "没闭合')
    assert 袋.有错
    assert 袋.条目[0].码 == "CN0102"
    # 关键：报告了错但没崩，且仍产出词元流
    assert 词元们[-1].种 is 种类.文件尾


def test_非法字符不崩():
    # 用 $ 当非法字符（@ 自 v0.8.0 起是插值前缀，已合法）
    词元们, 袋 = 扫("令 x = 1 $ 2")
    assert 袋.有错
    assert 袋.条目[0].码 == "CN0101"
    assert 词元们[-1].种 is 种类.文件尾


def test_运算符最长匹配():
    词元们, 袋 = 扫("1 <= 2 >= 3 != 4 == 5")
    assert not 袋.有错
    符 = [t.种 for t in 词元们 if t.种 in (
        种类.小于等于, 种类.大于等于, 种类.不等于, 种类.等于, 种类.小于, 种类.大于)]
    assert 符 == [种类.小于等于, 种类.大于等于, 种类.不等于, 种类.等于]


def test_注释被忽略():
    词元们, 袋 = 扫("令 x = 1  # 这是注释\n打印(x)")
    assert not 袋.有错
    assert not any("注释" in t.文本 for t in 词元们)


def test_缩进产生词元():
    码 = "如果 真\n    打印(1)\n打印(2)"
    种 = 种类们(码)
    assert 种类.缩进 in 种
    assert 种类.退缩 in 种


def test_嵌套缩进配平():
    码 = "如果 真\n    如果 真\n        打印(1)\n打印(2)"
    种 = 种类们(码)
    assert 种.count(种类.缩进) == 2
    assert 种.count(种类.退缩) == 2


def test_括号内换行不断句():
    词元们, 袋 = 扫("打印(1,\n     2)")
    assert not 袋.有错
    # 括号内不应有换行词元
    右括号位 = [i for i, t in enumerate(词元们) if t.种 is 种类.右括号][0]
    assert not any(t.种 is 种类.换行 for t in 词元们[:右括号位])


def test_空行与注释行不影响缩进():
    码 = "如果 真\n    打印(1)\n\n    # 注释\n    打印(2)\n打印(3)"
    词元们, 袋 = 扫(码)
    assert not 袋.有错
    种 = [t.种 for t in 词元们]
    assert 种.count(种类.缩进) == 1
    assert 种.count(种类.退缩) == 1


def test_布尔字面量值():
    词元们, _ = 扫("真 假")
    assert 词元们[0].值 is True
    assert 词元们[1].值 is False


def test_每个词元都有跨度():
    词元们, _ = 扫("令 x = 1\n打印(x)")
    for t in 词元们:
        assert t.跨 is not None
        assert t.跨.起.行 >= 1 and t.跨.起.列 >= 1


def test_跨度指向原文():
    源 = 源文件("令 计数器 = 42", "t.cnp")
    词元们, _ = 扫描(源)
    标 = [t for t in 词元们 if t.种 is 种类.标识符][0]
    assert 源.原文(标.跨) == "计数器"
