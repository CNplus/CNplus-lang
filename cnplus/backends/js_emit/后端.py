"""JS 转译后端 —— 阶段 4 路线 C。

把 AST 翻译成自包含的 JavaScript 源码（内联运行时），
用 node 执行。生成的 .js 可独立运行（node 与现代浏览器）。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from cnplus.backends.base import 后端, 后端能力
from cnplus.backends.js_emit.发射器 import 发射
from cnplus.diagnostics import 诊断袋
from cnplus.parser.ast import 程序
from cnplus.source import 源文件


class JS转译后端(后端):
    名称 = "JS 转译"
    能力 = 后端能力(("Node", "浏览器"), 支持导入=False, 支持交互输入=True)

    def __init__(self, 输出=None, *, 直通输出: bool = False) -> None:
        self.输出行: list[str] = []
        self._输出回调 = 输出
        self._直通输出 = 直通输出
        self.最后源码: str = ""
        self.最后退出码: int | None = None
        self.最后错误输出: str = ""

    def 执行(self, 程: 程序, 源: 源文件, 袋: 诊断袋) -> None:
        源码, _行映射 = 发射(程)
        self.最后源码 = 源码
        with tempfile.NamedTemporaryFile("w", suffix=".js",
                                         delete=False, encoding="utf-8") as f:
            f.write(源码)
            路径 = f.name
        try:
            捕获输出 = not self._直通输出
            r = subprocess.run(
                ["node", 路径],
                stdout=subprocess.PIPE if 捕获输出 else None,
                stderr=subprocess.PIPE,
                text=True, timeout=None if self._直通输出 else 30,
            )
        finally:
            Path(路径).unlink(missing_ok=True)
        self.最后退出码 = r.returncode
        self.最后错误输出 = r.stderr
        if r.returncode != 0:
            self._处理异常(r.stderr, 源, 袋)
            return
        for 行 in (r.stdout or "").splitlines():
            self.输出行.append(行)
            if self._输出回调:
                self._输出回调(行)
            else:
                print(行)

    def _处理异常(self, stderr: str, 源: 源文件, 袋: 诊断袋) -> None:
        """node 的 stderr 里找 CNplus错误（JSON 行），映射回 .cnp 位置。"""
        # 运行时最后抛错前会 console.error 一整行 JSON。不能用「遇到第一个 }」
        # 的正则截取：错误解释本身可以合法包含字典示例或其他花括号。
        for 行 in stderr.splitlines():
            _前, 标记, 负载 = 行.partition("__CNPLUS__")
            if not 标记:
                continue
            try:
                信息 = json.loads(负载)
            except json.JSONDecodeError:
                continue
            if not isinstance(信息, dict):
                continue
            码, 消息 = 信息.get("码"), 信息.get("消息")
            行号, 列号 = 信息.get("行"), 信息.get("列")
            提示, 解释 = 信息.get("提示"), 信息.get("解释")
            if not (isinstance(码, str) and len(码) == 6
                    and 码.startswith("CN") and 码[2:].isdigit()
                    and isinstance(消息, str)
                    and isinstance(行号, int) and not isinstance(行号, bool)
                    and isinstance(列号, int) and not isinstance(列号, bool)
                    and (提示 is None or isinstance(提示, str))
                    and (解释 is None or isinstance(解释, str))):
                continue
            跨 = 源.跨度于行列(行号, 列号)
            袋.报告(码, 消息, 跨, 提示=提示, 解释=解释)
            return
        袋.报告("CN9001", f"JS 运行时错误：{stderr.strip()[:200]}", 源.跨度于(0, 1),
              解释="这个错误来自 JS 运行环境，不是 CNplus 本身",
              提示="把生成代码保存下来（cnp 编译 --js）看看具体位置")


def 编译到文件(程: 程序, 目标: str | Path) -> Path:
    源码, _ = 发射(程)
    目标 = Path(目标)
    目标.write_text(源码, encoding="utf-8")
    return 目标
