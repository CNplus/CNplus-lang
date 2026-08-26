"""JS 子进程诊断标记的结构校验。"""

import pytest

from cnplus.backends.js_emit.后端 import JS转译后端
from cnplus.checker import 检查
from cnplus.diagnostics import 诊断袋
from cnplus.parser.parser import 解析
from cnplus.source import 源文件


def _诊断码(负载: str) -> list[str]:
    袋 = 诊断袋()
    JS转译后端()._处理异常("__CNPLUS__" + 负载, 源文件("", "测试.cnp"), 袋)
    return [诊断.码 for 诊断 in 袋]


def test_诊断标记允许消息里含花括号():
    assert _诊断码('{"码":"CN0303","消息":"例如 {甲: 乙}","行":1,"列":1}') == ["CN0303"]


@pytest.mark.parametrize("负载", [
    "[]", "null", '"文字"', "1",
    '{}', '{"码":1,"消息":"错","行":1,"列":1}',
    '{"码":"CN0303","消息":[],"行":1,"列":1}',
    '{"码":"CN0303","消息":"错","行":"1","列":1}',
    '{"码":"CN0303","消息":"错","行":1,"列":1,"提示":[]}',
])
def test_畸形标记稳定降级CN9001(负载: str):
    assert _诊断码(负载) == ["CN9001"]


@pytest.mark.parametrize("调用", [
    "包含(字典, [1])",
    "字典.有标签(1.5)",
    "删标签(字典, {})",
])
def test_JS字典内置错误定位到调用行(调用: str):
    源 = 源文件(f"设 字典 = {{}}\n{调用}\n", "内置位置.cnp")
    程, 袋 = 解析(源)
    检查(程, 袋)
    JS转译后端().执行(程, 源, 袋)
    错 = [d for d in 袋 if d.码 == "CN0303"]
    assert len(错) == 1
    assert 错[0].跨.起.行 == 2
