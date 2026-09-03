"""解析器测试。重点：错误恢复（D-005）—— 永不抛异常。"""
import pytest

from cnplus.parser.ast import (二元运算, 二元表达式, 函数声明, 变量引用, 声明语句,
                               如果语句, 整数字面量, 循环语句, 表达式语句,
                               调用表达式, 赋值语句, 返回语句, 错误语句, 格式串,
                               字符串字面量, 切片访问)
from cnplus.parser.parser import 解析
from cnplus.source import 位置, 源文件


def 析(码: str):
    return 解析(源文件(码, "t.cnp"))


def test_切片第三段保存步长表达式():
    程, 袋 = 析("打印([1, 2, 3][::2])")
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    调用 = 语句.表达
    assert isinstance(调用, 调用表达式)
    切片 = 调用.实参[0]
    assert isinstance(切片, 切片访问)
    assert isinstance(切片.步长, 整数字面量)
    assert 切片.步长.值 == 2


def test_声明():
    程, 袋 = 析("令 x = 1")
    assert not 袋.有错
    s = 程.语句们[0]
    assert isinstance(s, 声明语句) and s.名 == "x"
    assert isinstance(s.值, 整数字面量) and s.值.值 == 1


def test_优先级():
    程, 袋 = 析("令 x = 1 + 2 * 3")
    assert not 袋.有错
    值 = 程.语句们[0].值
    assert isinstance(值, 二元表达式) and 值.运算 is 二元运算.加
    assert isinstance(值.右, 二元表达式) and 值.右.运算 is 二元运算.乘


def test_左结合():
    程, _ = 析("令 x = 1 - 2 - 3")
    值 = 程.语句们[0].值
    # (1-2)-3
    assert isinstance(值.左, 二元表达式) and 值.左.运算 is 二元运算.减
    assert isinstance(值.右, 整数字面量) and 值.右.值 == 3


def test_括号改变优先级():
    程, _ = 析("令 x = (1 + 2) * 3")
    值 = 程.语句们[0].值
    assert 值.运算 is 二元运算.乘
    assert 值.左.运算 is 二元运算.加


def test_比较与逻辑优先级():
    程, 袋 = 析("令 x = 1 < 2 与 3 > 2")
    assert not 袋.有错
    值 = 程.语句们[0].值
    assert 值.运算 is 二元运算.与
    assert 值.左.运算 is 二元运算.小于
    assert 值.右.运算 is 二元运算.大于


def test_调用():
    程, 袋 = 析("打印(1, 2)")
    assert not 袋.有错
    s = 程.语句们[0]
    assert isinstance(s, 表达式语句)
    assert isinstance(s.表达, 调用表达式)
    assert len(s.表达.实参) == 2


def test_嵌套调用():
    程, 袋 = 析("打印(阶乘(3))")
    assert not 袋.有错
    外 = 程.语句们[0].表达
    assert isinstance(外.实参[0], 调用表达式)


def test_插值表达式必须完整消费():
    _程, 袋 = 析('打印(@"值：{1 2}")')
    assert 袋.有错


def test_插值子表达式跨度映射回原文件():
    程, 袋 = 析('打印(@"前{未声明}后")')
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    调用 = 语句.表达
    assert isinstance(调用, 调用表达式)
    串 = 调用.实参[0]
    assert isinstance(串, 格式串)
    名 = 串.部分[1]
    assert isinstance(名, 变量引用)
    assert 名.跨.起.行 == 1
    assert 名.跨.起.列 == 8


def test_插值转义前缀不改变原文件跨度():
    程, 袋 = 析('打印(@"\\n{未声明}")')
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    调用 = 语句.表达
    assert isinstance(调用, 调用表达式)
    串 = 调用.实参[0]
    assert isinstance(串, 格式串)
    名 = 串.部分[1]
    assert isinstance(名, 变量引用)
    assert 名.跨.起.列 == 9


def test_插值里的转义引号不会提前结束字符串():
    程, 袋 = 析(r'''打印(@"{'a\' } b'}")''')
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    调用 = 语句.表达
    assert isinstance(调用, 调用表达式)
    串 = 调用.实参[0]
    assert isinstance(串, 格式串)
    assert len(串.部分) == 1
    值 = 串.部分[0]
    assert isinstance(值, 字符串字面量)
    assert 值.值 == "a' } b"


def test_插值表达式内部转义后的变量跨度():
    程, 袋 = 析(r'''打印(@"{造('\t', 甲)}")''')
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    外调用 = 语句.表达
    assert isinstance(外调用, 调用表达式)
    串 = 外调用.实参[0]
    assert isinstance(串, 格式串)
    内调用 = 串.部分[0]
    assert isinstance(内调用, 调用表达式)
    名 = 内调用.实参[1]
    assert isinstance(名, 变量引用)
    assert 名.跨.起.列 == 15


def test_插值在非零基位置源码中不重复偏移():
    源 = 源文件('打印(@"前{甲}")', "嵌入.cnp", 基位置=位置(3, 5, 100))
    程, 袋 = 解析(源)
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    调用 = 语句.表达
    assert isinstance(调用, 调用表达式)
    串 = 调用.实参[0]
    assert isinstance(串, 格式串)
    名 = 串.部分[1]
    assert isinstance(名, 变量引用)
    assert 名.跨.起 == 位置(行=3, 列=12, 偏移=107)


def test_嵌套插值保留原文件跨度():
    程, 袋 = 析("打印(@'外{@\"内{甲}\"}尾')")
    assert not 袋.有错
    语句 = 程.语句们[0]
    assert isinstance(语句, 表达式语句)
    外调用 = 语句.表达
    assert isinstance(外调用, 调用表达式)
    外串 = 外调用.实参[0]
    assert isinstance(外串, 格式串)
    内串 = 外串.部分[1]
    assert isinstance(内串, 格式串)
    名 = 内串.部分[1]
    assert isinstance(名, 变量引用)
    assert 名.跨.起 == 位置(行=1, 列=12, 偏移=11)


def test_如果否则():
    程, 袋 = 析("如果 真\n    打印(1)\n否则\n    打印(2)")
    assert not 袋.有错
    s = 程.语句们[0]
    assert isinstance(s, 如果语句)
    assert len(s.主体) == 1 and len(s.否则体) == 1


def test_如果无否则():
    程, 袋 = 析("如果 真\n    打印(1)")
    assert not 袋.有错
    assert 程.语句们[0].否则体 == ()


def test_循环():
    程, 袋 = 析("循环 真\n    打印(1)")
    assert not 袋.有错
    assert isinstance(程.语句们[0], 循环语句)


def test_函数声明与返回():
    程, 袋 = 析("函数 加(a, b)\n    返回 a + b")
    assert not 袋.有错
    f = 程.语句们[0]
    assert isinstance(f, 函数声明)
    assert f.名 == "加" and f.形参 == ("a", "b")
    assert isinstance(f.主体[0], 返回语句)


def test_无参函数():
    程, 袋 = 析("函数 哈()\n    返回")
    assert not 袋.有错
    f = 程.语句们[0]
    assert f.形参 == ()
    assert f.主体[0].值 is None


def test_赋值与外部():
    程, 袋 = 析("x = 1\n外部 y = 2")
    assert not 袋.有错
    a, b = 程.语句们
    assert isinstance(a, 赋值语句) and not a.是外部
    assert isinstance(b, 赋值语句) and b.是外部


def test_一元负与非():
    程, 袋 = 析("令 x = -1\n令 y = 非 真")
    assert not 袋.有错


def test_递归函数完整程序():
    码 = """函数 阶乘(n)
    如果 n <= 1
        返回 1
    否则
        返回 n * 阶乘(n - 1)

令 i = 1
循环 i <= 5
    打印(阶乘(i))
    i = i + 1
"""
    程, 袋 = 析(码)
    assert not 袋.有错, 袋.渲染全部(源文件(码, "t.cnp"))
    assert len(程.语句们) == 3


# ==================== 错误恢复（D-005 核心）====================

@pytest.mark.parametrize("码", [
    "",
    "令",
    "令 x",
    "令 x =",
    "令 = 1",
    "如果",
    "如果 真",
    "如果 真\n打印(1)",
    "函数",
    "函数 f",
    "函数 f(",
    "函数 f(a",
    "函数 f(a,",
    "打印(",
    "打印(1,",
    "1 + ",
    "+ 1",
    ")",
    "循环",
    "返回 返回",
    "令 x = @",
    "令 x = 1 2",
    "@#$%",
    "如果 真\n    ",
    "\n\n\n",
    "        打印(1)",
])
def test_残缺输入永不抛异常(码):
    """D-005：任何输入都必须返回 (程序, 诊断袋)，绝不抛异常、绝不死循环。"""
    程, 袋 = 析(码)
    assert 程 is not None
    assert hasattr(程, "语句们")


def test_错误后仍解析后续语句():
    """关键性质：一处错误不能毁掉整个文件。"""
    程, 袋 = 析("令 x =\n令 y = 2\n令 z = 3")
    assert 袋.有错
    好的 = [s for s in 程.语句们 if isinstance(s, 声明语句)]
    assert len(好的) == 2, f"应恢复出 2 条好语句，实际 {len(好的)}"
    assert {s.名 for s in 好的} == {"y", "z"}


def test_块内错误不毁掉块外():
    程, 袋 = 析("如果 真\n    令 a =\n    令 b = 2\n令 c = 3")
    assert 袋.有错
    顶层声明 = [s for s in 程.语句们 if isinstance(s, 声明语句)]
    assert any(s.名 == "c" for s in 顶层声明)


def test_错误节点带跨度():
    程, 袋 = 析("令 x =")
    错 = [s for s in 程.语句们 if isinstance(s, 错误语句)]
    assert 错
    assert 错[0].跨 is not None


def test_缺缩进报诊断():
    程, 袋 = 析("如果 真\n打印(1)")
    assert 袋.有错
    assert any(d.码 == "CN0204" for d in 袋)


def test_每个节点都有跨度():
    程, _ = 析("令 x = 1 + 2\n打印(x)")

    def 查(节):
        assert getattr(节, "跨", None) is not None, f"{type(节).__name__} 缺跨度"
        for 名 in getattr(节, "__slots__", ()):
            v = getattr(节, 名)
            if hasattr(v, "跨"):
                查(v)
            elif isinstance(v, tuple):
                for x in v:
                    if hasattr(x, "跨"):
                        查(x)

    for s in 程.语句们:
        查(s)


def test_跨度覆盖原文():
    源 = 源文件("令 计数 = 1 + 2", "t.cnp")
    程, _ = 解析(源)
    s = 程.语句们[0]
    assert 源.原文(s.值.跨) == "1 + 2"
