"""JS 转译后端（阶段 4，路线 C）。

发射器（Python 写）生成 JavaScript 源码，语义引擎是内联的
运行时源码.js —— 与 python_emit 同构：每语句一行、每步运算
调用运行时函数，保证 CNplus 语义不泄漏。
"""
from cnplus.backends.js_emit.后端 import JS转译后端, 编译到文件
from cnplus.backends.js_emit.发射器 import 发射

__all__ = ["JS转译后端", "编译到文件", "发射"]
