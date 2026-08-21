"""源码位置与跨度 —— 铁律 2「万物带 Span」的地基。

每个 token、每个 AST 节点都必须带 Span。错误信息、source map、
调试器、LSP 全部建在这上面。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True, slots=True)
class 位置:
    """源码中的一个点。行列从 1 起（面向人类），偏移从 0 起（面向切片）。"""

    行: int
    列: int
    偏移: int

    def __str__(self) -> str:
        return f"{self.行}:{self.列}"


@dataclass(frozen=True, slots=True)
class 跨度:
    """源码中的一段区间，左闭右开 [起, 止)。"""

    起: 位置
    止: 位置

    def __post_init__(self) -> None:
        if self.止.偏移 < self.起.偏移:
            raise ValueError(f"跨度的止({self.止.偏移})不能早于起({self.起.偏移})")

    @property
    def 单行(self) -> bool:
        return self.起.行 == self.止.行

    @property
    def 长度(self) -> int:
        return self.止.偏移 - self.起.偏移

    def 合并(self, 其他: 跨度) -> 跨度:
        """取两个跨度的最小外包区间。用于「由子节点算出父节点的跨度」。"""
        起 = self.起 if self.起.偏移 <= 其他.起.偏移 else 其他.起
        止 = self.止 if self.止.偏移 >= 其他.止.偏移 else 其他.止
        return 跨度(起, 止)

    def __str__(self) -> str:
        if self.单行:
            return f"{self.起.行}:{self.起.列}-{self.止.列}"
        return f"{self.起}-{self.止}"


def 合并跨度(*跨度们: 跨度) -> 跨度:
    """合并任意多个跨度。至少要有一个。"""
    if not 跨度们:
        raise ValueError("合并跨度需要至少一个跨度")
    结果 = 跨度们[0]
    for s in 跨度们[1:]:
        结果 = 结果.合并(s)
    return 结果


class 源文件:
    """一份源码 + 行索引。负责偏移与行列之间的换算，以及取原文。"""

    def __init__(self, 文本: str, 文件名: str = "<内存>") -> None:
        self.文本 = 文本
        self.文件名 = 文件名

    @cached_property
    def _行起始偏移(self) -> list[int]:
        起始 = [0]
        for i, 字 in enumerate(self.文本):
            if 字 == "\n":
                起始.append(i + 1)
        return 起始

    @property
    def 行数(self) -> int:
        return len(self._行起始偏移)

    def 取行(self, 行号: int) -> str:
        """取第 行号 行（1 起），不含末尾换行。越界返回空串。"""
        if 行号 < 1 or 行号 > self.行数:
            return ""
        起 = self._行起始偏移[行号 - 1]
        止 = self._行起始偏移[行号] - 1 if 行号 < self.行数 else len(self.文本)
        return self.文本[起:止]

    def 位置于(self, 偏移: int) -> 位置:
        """由偏移算出行列。"""
        偏移 = max(0, min(偏移, len(self.文本)))
        # 二分找所在行
        低, 高 = 0, len(self._行起始偏移) - 1
        while 低 < 高:
            中 = (低 + 高 + 1) // 2
            if self._行起始偏移[中] <= 偏移:
                低 = 中
            else:
                高 = 中 - 1
        return 位置(行=低 + 1, 列=偏移 - self._行起始偏移[低] + 1, 偏移=偏移)

    def 原文(self, 跨: 跨度) -> str:
        """取跨度对应的原始文本。"""
        return self.文本[跨.起.偏移 : 跨.止.偏移]

    def 跨度于(self, 起偏移: int, 止偏移: int) -> 跨度:
        """由两个偏移直接造跨度。"""
        return 跨度(self.位置于(起偏移), self.位置于(止偏移))
