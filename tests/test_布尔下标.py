"""布尔值不能作为列表或文字下标。"""
import pytest

from cnplus.backends.注册表 import 对拍后端们
from cnplus.checker import 检查
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


@pytest.mark.parametrize("源码", [
    "打印([10, 20][真])",
    "打印([10, 20][假])",
    '打印("甲乙"[真])',
    '打印("甲乙"[假])',
    "设 名单 = [10, 20]\n名单[真] = 99",
    "设 名单 = [10, 20]\n名单[假] = 99",
    "设 名单 = [10, 20]\n名单[真] += 1",
    "设 名单 = [10, 20]\n名单[假] += 1",
])
def test_布尔序列下标三后端统一诊断(源码: str):
    下标文字 = "真" if "真]" in 源码 else "假"
    调用行 = 2 if "\n" in 源码 else 1
    调用文字 = 源码.splitlines()[调用行 - 1]
    期望列 = 调用文字.index(下标文字) + 1

    for 登记 in 对拍后端们():
        源 = 源文件(源码, "t.cnp")
        程, 袋 = 解析(源)
        检查(程, 袋)
        assert not 袋.有错

        后 = 登记.后端类()
        后.执行(程, 源, 袋)

        assert len(袋.条目) == 1, 登记.名称
        诊 = 袋.条目[0]
        assert 诊.码 == "CN0303", 登记.名称
        assert 诊.消息 == "下标必须是整数，这里是布尔", 登记.名称
        assert 诊.解释 == "方括号里要写「第几个」，用整数（负数表示从尾数）", 登记.名称
        assert 诊.提示 == "把下标改成整数，例如 0、1 或 -1", 登记.名称
        assert (诊.跨.起.行, 诊.跨.起.列) == (调用行, 期望列), 登记.名称

        if 登记.是子进程:
            assert getattr(后, "最后退出码", None) != 0, 登记.名称
            错误输出 = getattr(后, "最后错误输出", "")
            assert "CN0303" in 错误输出, 登记.名称
            assert "CN9001" not in 错误输出, 登记.名称
