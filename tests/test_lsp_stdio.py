"""真实 stdio 协议冒烟：锁定 pygls API 与 UTF-16 输入边界。"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest


def _帧(内容: dict) -> bytes:
    正文 = json.dumps(内容, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(正文)}\r\n\r\n".encode("ascii") + 正文


def _解帧(数据: bytes) -> list[dict]:
    消息们: list[dict] = []
    位置 = 0
    while 位置 < len(数据):
        头尾 = 数据.index(b"\r\n\r\n", 位置)
        头 = 数据[位置:头尾].decode("ascii")
        长度 = int(next(行.split(":", 1)[1] for 行 in 头.split("\r\n")
                      if 行.lower().startswith("content-length:")))
        正文起点 = 头尾 + 4
        正文止点 = 正文起点 + 长度
        消息们.append(json.loads(数据[正文起点:正文止点]))
        位置 = 正文止点
    return 消息们


def test_stdio定义跳转接收utf16位置():
    pytest.importorskip("pygls")
    代码 = '函数 取值(名字)\n    打印("😀", 名字)\n'
    前缀 = '    打印("😀", '
    uri = "file:///tmp/cnplus-lsp-test.cnp"
    输入 = b"".join(_帧(消息) for 消息 in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"processId": None, "rootUri": None, "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen",
         "params": {"textDocument": {
             "uri": uri, "languageId": "cnplus", "version": 1, "text": 代码}}},
        {"jsonrpc": "2.0", "id": 2, "method": "textDocument/definition",
         "params": {"textDocument": {"uri": uri},
                    "position": {"line": 1,
                                 "character": len(前缀.encode("utf-16-le")) // 2}}},
        {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": None},
        {"jsonrpc": "2.0", "method": "exit", "params": None},
    ])

    结果 = subprocess.run(
        [sys.executable, "-m", "cnplus.lsp.server"], input=输入,
        capture_output=True, timeout=10, check=False,
    )
    assert 结果.returncode == 0, 结果.stderr.decode("utf-8", errors="replace")
    回复们 = {消息["id"]: 消息 for 消息 in _解帧(结果.stdout) if "id" in 消息}
    assert "result" in 回复们[1]
    assert 回复们[2]["result"]["range"] == {
        "start": {"line": 0, "character": 6},
        "end": {"line": 0, "character": 8},
    }
    assert 回复们[3].get("result") is None
