# CNplus for VSCode

用中文写程序。这个扩展为 [CNplus 语言](https://github.com/CNplus/CNplus-lang)
提供语法高亮、实时错误提示和一键运行。

```
设 名字 = 询问("你叫什么名字？")
打印(@"你好，{名字}！")

遍历 范围(1, 4) 每个 i
    如果 i == 2
        继续
    打印(@"第 {i} 次")
```

## 功能

| 功能 | 说明 |
|---|---|
| 语法高亮 | 关键字、字符串、数字、函数名 |
| 实时错误提示 | 边写边查，错误直接标在代码上 |
| 一键运行 | `F5` 或点右上角 ▶ |
| 自动找解释器 | 装了多个 Python 也不用手动配置 |

## 安装

分两步：先装 CNplus 本体，再装这个扩展。

### 第 1 步：装 CNplus 本体

扩展只是编辑器这一层，运行程序需要先装 CNplus 本体。

> CNplus 尚未发布到 PyPI，目前从源码安装：

```bash
git clone https://github.com/CNplus/CNplus-lang.git
cd CNplus-lang
pip3 install -e ".[lsp]"
```

需要 Python 3.11 或更新的版本。装好后可以先在终端验证：

```bash
cnp 版本
```

### 第 2 步：装扩展

从 [GitHub Release](https://github.com/CNplus/CNplus-lang/releases) 下载
`cnplus-<版本>.vsix`（或从 [官网](https://cnplus.org/download) 下载），然后：

**图形界面（推荐，不用装任何东西）**：VSCode 里按 `⌘⇧X`（Windows/Linux
是 `Ctrl+Shift+X`），点右上角 `…` → **从 VSIX 安装…**，选中下载的
`.vsix` 文件。

**命令行**（需先装好 `code` 命令）：

```bash
code --install-extension cnplus-0.8.1.vsix
```

若提示 `code` 命令找不到：在 VSCode 里按 `⌘⇧P` 输入 `install code`，
选「Shell Command: Install 'code' command in PATH」，重开终端再试；
或直接用上面的图形界面方式。

装完**完全退出 VSCode 再打开**（⌘Q，不是关窗口），扩展才会加载。

### 如果你电脑上有多个 Python

这很常见（macOS 自带一个旧的、Homebrew 装一个新的……）。扩展会**自动**
按这个顺序找一个装了 cnplus 的解释器：

1. 你在设置里指定的路径（如果填了）
2. 当前项目里的 `.venv`
3. Homebrew 装的 Python（`/opt/homebrew`、`/usr/local`）
4. 系统 Python

想知道当前用的是哪个，按 `⌘⇧P` 运行 **CNplus: 显示当前使用的解释器**。

自动探测选错了才需要手填，在设置里搜 `cnplus.python路径`。

## 命令

| 命令 | 快捷键 |
|---|---|
| CNplus: 运行当前文件 | `F5` |
| CNplus: 显示当前使用的解释器 | — |

## 设置

| 设置项 | 默认 | 说明 |
|---|---|---|
| `cnplus.python路径` | 空（自动探测） | 手动指定解释器 |
| `cnplus.启用LSP` | `true` | 实时错误提示 |

## 关于 CNplus

一门用中文写的编程语言，关键字、错误提示全是中文，面向没有编程基础的人。
它有自己的词法分析器、语法分析器和抽象语法树，不是在 Python 上套一层中文函数名。

错误提示分三层，术语和大白话都给：

```
错误[CN0302]: 变量 年龄x 还没有声明过
 --> 我的程序.cnp:2:4
  |
2 | 打印(年龄x)
  |      ^^^^^
  = 也就是说: CNplus 不认识 年龄x，因为你还没告诉它这个名字代表什么
  = 这样改: 是不是想写「年龄」？
```

- 教程：<https://wiki.cnplus.org>
- 源码：<https://github.com/CNplus/CNplus-lang>
- 反馈：<https://github.com/CNplus/CNplus-lang/issues>

## 许可

Apache-2.0
