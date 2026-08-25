"""可参与共享语料对拍的后端登记。

新增后端时，在这里登记其名称、后端类与运行方式；对拍测试不再各自维护
后端名单。后端若尚未支持某类语料，应通过能力清单显式声明，而不是静默跳过。
"""
from __future__ import annotations

from dataclasses import dataclass

from cnplus.backends.base import 后端


@dataclass(frozen=True)
class 对拍后端登记:
    """测试执行一个后端所需的稳定元数据。"""

    名称: str
    后端类: type[后端]
    是子进程: bool = False


def 对拍后端们() -> tuple[对拍后端登记, ...]:
    """返回当前可运行共享语料的后端。

    延迟导入避免后端实现加载运行时模块时形成循环依赖。
    """
    from cnplus.backends.js_emit import JS转译后端
    from cnplus.backends.python_emit import Python转译后端
    from cnplus.backends.treewalk import 树遍历后端

    return (
        对拍后端登记("树遍历", 树遍历后端),
        对拍后端登记("Python 转译", Python转译后端),
        对拍后端登记("JS 转译", JS转译后端, 是子进程=True),
    )
