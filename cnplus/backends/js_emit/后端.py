"""JS 转译后端 —— 阶段 4 路线 C。

把 AST 翻译成自包含的 JavaScript 源码（内联运行时），
用 node 执行。生成的 .js 可独立运行（node 与现代浏览器）。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from cnplus.backends.base import 后端
from cnplus.backends.js_emit.发射器 import 发射
from cnplus.diagnostics import 诊断袋
from cnplus.parser.ast import 程序
from cnplus.source import 源文件


class JS转译后端(后端):
    名称 = "JS 转译"

    def __init__(self, 输出=None) -> None:
        self.输出行: list[str] = []
        self._输出回调 = 输出
        self.最后源码: str = ""

    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        源码, _行映射 = 发射(程)
        self.最后源码 = 源码
        with tempfile.NamedTemporaryFile("w", suffix=".js",
                                         delete=False, encoding="utf-8") as f:
            f.write(源码)
            路径 = f.name
        try:
            r = subprocess.run(["node", 路径], capture_output=True,
                               text=True, timeout=30)
        finally:
            Path(路径).unlink(missing_ok=True)
        if r.returncode != 0:
            self._处理异常(r.stderr, 源, 袋)
            return
        for 行 in r.stdout.splitlines():
            self.输出行.append(行)
            if self._输出回调:
                self._输出回调(行)
            else:
                print(行)

    def _处理异常(self, stderr: str, 源: 源文件, 袋: 诊断袋) -> None:
        """node 的 stderr 里找 CNplus错误（JSON 行），映射回 .cnp 位置。"""
        import re
        # 运行时最后抛错前会 console.error 一行 JSON：{"码":..., "行":..., "列":...}
        m = re.search(r"__CNPLUS__(\{.*?\})", stderr, re.S)
        if m:
            信息 = json.loads(m.group(1))
            跨 = 源.跨度于行列(信息.get("行", 1), 信息.get("列", 1))
            袋.报告(信息.get("码", "CN9001"), 信息.get("消息", "未知错误"), 跨,
                  提示=信息.get("提示"), 解释=信息.get("解释"))
            return
        袋.报告("CN9001", f"JS 运行时错误：{stderr.strip()[:200]}", 源.跨度于(0, 1),
              解释="这个错误来自 JS 运行环境，不是 CNplus 本身",
              提示="把生成代码保存下来（cnp 编译 --js）看看具体位置")


def 编译到文件(程: 程序, 目标: str | Path) -> Path:
    源码, _ = 发射(程)
    目标 = Path(目标)
    目标.write_text(源码, encoding="utf-8")
    return 目标
