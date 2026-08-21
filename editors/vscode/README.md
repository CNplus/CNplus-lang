# CNplus VSCode 扩展

语法高亮 + 实时错误诊断 + 一键运行。

## 本地安装（不需要发布到市场）

```bash
# 1. 装 Python 侧的 LSP 依赖
cd /path/to/CNplus
uv pip install -e ".[lsp]"

# 2. 软链到 VSCode 扩展目录
ln -s "$(pwd)/editors/vscode" ~/.vscode/extensions/cnplus

# 3. 装扩展壳的 JS 依赖（只需一次）
cd editors/vscode && npm install

# 4. 重启 VSCode，打开任意 .cnp 文件
```

## 功能

| 功能 | 说明 |
|---|---|
| 语法高亮 | 由 `keywords.toml` 生成，含所有别名（`如果`/`若`） |
| 实时诊断 | 边打字边报错，中文消息 + 精确波浪线 |
| 运行 | `F5` 或标题栏播放按钮 |
| 括号/引号自动配对 | 半角与全角都支持 |
| 自动缩进 | `如果`/`循环`/`函数` 后自动缩进 |

## 语法文件是生成的，别手改

```bash
python tools/生成语法文件.py
```

改了 `cnplus/lexer/keywords.toml` 之后重跑这条命令。
手写 TextMate 语法必然与 lexer 漂移（见决策 D-007）。

## 架构

```
VSCode ──stdio──> python -m cnplus.lsp.server ──> 同一套 lexer/parser
```

扩展壳只有 ~60 行 JS，所有智能都在 Python 侧。换成 Neovim / Zed 只需换壳。
