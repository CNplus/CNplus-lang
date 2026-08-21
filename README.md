# CNplus

> 使用中文撸代码。一门中文编程语言 —— 玩具起步，架构上留有升级成正式语言的出口。

[![状态](https://img.shields.io/badge/状态-阶段0.5完成-brightgreen)](.hermes/plans/)
[![测试](https://img.shields.io/badge/测试-162%20通过-brightgreen)](tests/)
[![许可](https://img.shields.io/badge/许可-Apache--2.0-blue)](LICENSE)

## 这是什么

```
设 单价 = 15
设 数量 = 4

打印("总价：" + 文本(单价 * 数量) + " 元")

如果 单价 * 数量 > 50
    打印("满 50 包邮！")
否则
    打印("再买点就包邮了")
```

**没写过程序？** 从[十分钟上手](docs/十分钟上手.md)开始，不需要任何基础。

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
| 0 | lexer + parser + 树遍历求值 | ✅ v0.0.5 |
| 0.5 | VSCode 扩展（高亮 + 波浪线 + 运行） | ✅ v0.1.0 |
| 1 | Python 转译后端 + 借用 pip 库 | ✅ v0.3.0 |
| — | 列表/字典/遍历/30 内置函数 | ✅ v0.4.0 |
| 2 | 诊断升级（拼写建议等） | ⬜ |
| 3 | REPL + LSP 补全/跳转 | ⬜ |
| 4 | 字节码 VM ／ JS 后端 | ⬜ |

完整计划见 [`.hermes/plans/`](.hermes/plans/)。

## 快速开始

```bash
git clone https://github.com/CNplus/CNplus-lang.git
cd CNplus-lang
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev,lsp]"

python -m cnplus 运行 示例/01-你好.cnp    # 你好，世界！
python -m cnplus 检查 示例/05-算总价.cnp  # 只查错不执行
python -m cnplus 语法树 示例/01-你好.cnp  # 看语法树（调试用）
```

### VSCode 支持

```bash
ln -s "$(pwd)/editors/vscode" ~/.vscode/extensions/cnplus
cd editors/vscode && npm install
```

重启 VSCode，打开 `.cnp` 文件即有高亮、实时中文报错、F5 运行。
详见 [`editors/vscode/README.md`](editors/vscode/README.md)。

## 文档

| 文档 | 给谁看 |
|---|---|
| [十分钟上手](docs/十分钟上手.md) | **零基础从这里开始** |
| [示例程序](示例/) | 9 个可直接运行的例子，由易到难 |
| [列表和字典](docs/列表和字典.md) | 想一次记住一堆东西 |
| [借用 Python 库](docs/借用python库.md) | 想读写文件、上网、用 pip 库 |
| [语义约定](docs/spec/00-语义约定.md) | 想知道精确规则的人 |
| [诊断码表](docs/spec/03-诊断码.md) | 查错误编号 |

## 错误信息长这样

三层结构：**术语**给有基础的人看，**大白话**给没基础的人看，**改法**经常能直接照抄。

```
错误[CN0302]: 变量 年龄x 还没有声明过
 --> 我的程序.cnp:2:4
  |
2 | 打印(年龄x)
  |      ^^^^^
  = 也就是说: CNplus 不认识 年龄x，因为你还没告诉它这个名字代表什么
  = 这样改: 是不是想写「年龄」？
```

## 一个意思，多种写法

用你顺口的那个，效果完全一样：

| 意思 | 可以写成 |
|---|---|
| 建立名字 | `设` `令` `让` |
| 判断 | `如果` `若` `假如` |
| 否则 | `否则` `不然` `要不然` |
| 重复 | `循环` `当` `重复` |
| 造工具 | `函数` `定义` `过程` |
| 给出结果 | `返回` `返` `给出` |

## 参与

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [AGENTS.md](AGENTS.md)。

## 许可

Apache-2.0，延续 2021 年原项目的选择。
