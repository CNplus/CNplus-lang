// CNplus VSCode 扩展 —— 只是个壳。
//
// 真正的智能全在 Python 那边的 LSP server 里（cnplus/lsp/server.py），
// 这里只负责：拉起 server、注册运行命令。这就是「不自研 IDE，做 LSP」
// 的意思 —— 换成 Neovim / Zed，换的只是这个壳。

const vscode = require("vscode");
const path = require("path");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let 客户端;

function 取Python() {
  const 配置 = vscode.workspace.getConfiguration("cnplus");
  return 配置.get("python路径") || "python3";
}

function activate(上下文) {
  const 配置 = vscode.workspace.getConfiguration("cnplus");

  // ---- 运行当前文件 ----
  上下文.subscriptions.push(
    vscode.commands.registerCommand("cnplus.运行当前文件", () => {
      const 编辑器 = vscode.window.activeTextEditor;
      if (!编辑器 || 编辑器.document.languageId !== "cnplus") {
        vscode.window.showWarningMessage("请先打开一个 .cnp 文件");
        return;
      }
      编辑器.document.save().then(() => {
        const 终端 =
          vscode.window.terminals.find((t) => t.name === "CNplus") ||
          vscode.window.createTerminal("CNplus");
        终端.show(true);
        终端.sendText(`${取Python()} -m cnplus 运行 "${编辑器.document.fileName}"`);
      });
    })
  );

  // ---- LSP：实时诊断 ----
  if (!配置.get("启用LSP")) return;

  const 服务端选项 = {
    run: { command: 取Python(), args: ["-m", "cnplus.lsp.server"], transport: TransportKind.stdio },
    debug: { command: 取Python(), args: ["-m", "cnplus.lsp.server"], transport: TransportKind.stdio },
  };
  const 客户端选项 = {
    documentSelector: [{ scheme: "file", language: "cnplus" }],
    outputChannelName: "CNplus 语言服务",
  };

  客户端 = new LanguageClient("cnplus", "CNplus 语言服务", 服务端选项, 客户端选项);
  客户端.start().catch((错) => {
    vscode.window.showWarningMessage(
      `CNplus 语言服务启动失败（语法高亮仍可用）：${错.message}\n` +
        `请确认已安装：uv pip install -e ".[lsp]"`
    );
  });
}

function deactivate() {
  return 客户端 ? 客户端.stop() : undefined;
}

module.exports = { activate, deactivate };
