# CNplus

> 使用中文撸代码。一门中文编程语言 —— 玩具起步，架构上留有升级成正式语言的出口。

[![状态](https://img.shields.io/badge/状态-阶段0开发中-yellow)](.hermes/plans/)
[![许可](https://img.shields.io/badge/许可-Apache--2.0-blue)](LICENSE)

## 这是什么

```
函数 阶乘(n)
    如果 n <= 1
        返回 1
    否则
        返回 n * 阶乘(n - 1)

令 i = 1
循环 i <= 5
    打印(阶乘(i))
    i = i + 1
```

CNplus 有**自己的** lexer、parser 和 AST，后端可插拔。首发后端把 AST 转译成 Python 源码，
将来可以换成字节码 VM 或别的目标语言，而**前端一行不用改**。

这一点是本项目的全部要害：玩具和正式语言的分界不在功能（GC、类型系统、VM），
而在「源码 → AST」和「AST → 执行」之间有没有一条干净的接缝。

## 历史

CNplus 始于 2021 年 12 月，最初是一层中文函数名封装（`archive/CNplus-python`），
2022 年 6 月尝试用 C++ 重做成 IDLE（`archive/CNplus-mixed`），
停在 `main.cpp:28` 一个没写完的 `cout` 上。

2026 年重启。这次先建接缝，再建楼。老仓库原样保存在 `archive/` 下作只读参考。

## 与 Python 的差异（故意的）

| 主题 | CNplus | Python |
|---|---|---|
| 真值 | 只有 `真`/`假` 能出现在条件位置，`如果 0` 是编译错误 | 隐式真值 |
| 跨类型比较 | 数 vs 串比较报错 | 返回 `False` |
| 未声明变量 | 编译期错误 | 运行时 NameError |

详见 [语义约定](docs/spec/00-语义约定.md)。

## 开发路线

| 阶段 | 产出 | 状态 |
|---|---|---|
| 0 | lexer + parser + 树遍历求值 | 🚧 进行中 |
| 0.5 | VSCode 扩展（高亮 + 波浪线 + 运行） | ⬜ |
| 1 | Python 转译后端 + source map | ⬜ |
| 2 | 中文诊断系统 | ⬜ |
| 3 | REPL + LSP | ⬜ |
| 4 | 字节码 VM ／ JS 后端 | ⬜ |

完整计划见 [`.hermes/plans/`](.hermes/plans/)。

## 参与

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [AGENTS.md](AGENTS.md)。

## 许可

Apache-2.0，延续 2021 年原项目的选择。
