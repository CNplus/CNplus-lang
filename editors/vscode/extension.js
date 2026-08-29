// CNplus VSCode 扩展 —— 只是个壳。
//
// 真正的智能全在 Python 那边的 LSP server 里（cnplus/lsp/server.py），
// 这里只负责：找到能用的解释器、拉起 server、注册运行命令。
// 这就是「不自研 IDE，做 LSP」的意思 —— 换成 Neovim / Zed，换的只是这个壳。

const vscode = require("vscode");
const { execFile } = require("child_process");
const fs = require("fs");
const path = require("path");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let 客户端;
let 已探测到的解释器 = null; // 探测结果缓存，避免每次都试一遍

/**
 * 候选解释器清单，按可靠性排序。
 *
 * 为什么要探测：很多机器上同时装了多个 Python（macOS 自带 3.9、
 * Homebrew 的、uv 管的、conda 的……），而 PATH 里的 `python3` 常常
 * 是最旧那个。让用户手填路径既麻烦又容易填错，所以扩展自己找。
 */
function 候选解释器们() {
  const 候选 = [];

  // 1) 用户显式配置的最优先 —— 填了就听他的
  const 配置路径 = vscode.workspace.getConfiguration("cnplus").get("python路径");
  if (配置路径 && 配置路径.trim()) 候选.push(配置路径.trim());

  // 2) 工作区里的虚拟环境（开发 CNplus 本身时最常见）
  const 工作区们 = vscode.workspace.workspaceFolders || [];
  for (const 区 of 工作区们) {
    for (const 相对 of [".venv/bin/python", ".venv/Scripts/python.exe", "venv/bin/python"]) {
      候选.push(path.join(区.uri.fsPath, 相对));
    }
  }

  // 3) 常见的系统级安装位置（Homebrew / 官方 pkg / Linux）
  候选.push(
    "/opt/homebrew/bin/python3.11",   // Apple Silicon Homebrew
    "/opt/homebrew/bin/python3.12",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3.11",      // Intel Homebrew
    "/usr/local/bin/python3.12",
    "/usr/local/bin/python3",
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
    "/usr/bin/python3.11",
    "/usr/bin/python3.12"
  );

  // 4) 兜底：PATH 里的（可能是旧版，所以放最后）
  候选.push("python3", "python");

  return 候选;
}

/** 试一个解释器：能 import 到 cnplus 才算可用。 */
function 试解释器(可执行) {
  return new Promise((完成) => {
    execFile(
      可执行,
      ["-c", "import cnplus,cnplus.lsp.server,sys; print(cnplus.__version__); print(sys.version_info[:2])"],
      { timeout: 8000 },
      (错, 标准输出) => 完成(错 ? null : 标准输出.trim())
    );
  });
}

/**
 * 找出一个既有 cnplus、版本又够新的解释器。
 * 找到就缓存，之后直接复用。
 */
async function 找解释器({ 强制重找 = false } = {}) {
  if (已探测到的解释器 && !强制重找) return 已探测到的解释器;

  for (const 候选 of 候选解释器们()) {
    // 绝对路径先看文件在不在，省掉一次进程启动
    if (候选.includes(path.sep) && !fs.existsSync(候选)) continue;
    const 结果 = await 试解释器(候选);
    if (结果) {
      已探测到的解释器 = 候选;
      return 候选;
    }
  }
  已探测到的解释器 = null;
  return null;
}

/** 没找到解释器时，给一条能直接照做的提示。 */
async function 提示装不上(场景) {
  const 选择 = await vscode.window.showErrorMessage(
    `CNplus ${场景}：没有找到装了 cnplus 的 Python 解释器。`,
    "怎么安装",
    "手动指定路径"
  );
  if (选择 === "怎么安装") {
    vscode.env.openExternal(vscode.Uri.parse("https://wiki.cnplus.org"));
  } else if (选择 === "手动指定路径") {
    vscode.commands.executeCommand("workbench.action.openSettings", "cnplus.python路径");
  }
}

/** 不受信任窗口的提示（issue #1：静默不激活让人以为扩展坏了） */
function 提示不受信() {
  vscode.window
    .showWarningMessage(
      "CNplus：当前窗口不受信任，实时诊断与运行功能未启用（语法高亮仍可用）。",
      "信任此工作区"
    )
    .then((选择) => {
      if (选择 === "信任此工作区") {
        vscode.commands.executeCommand("workbench.trust.manage");
      }
    });
}

function activate(上下文) {
  // ---- 不受信任窗口：提示引导信任，别让用户以为扩展坏了（issue #1）----
  if (!vscode.workspace.isTrusted) {
    提示不受信();
    上下文.subscriptions.push(
      vscode.workspace.onDidGrantWorkspaceTrust(() => {
        // 用户点了信任后，本函数不会自动重跑，提示去重新加载窗口
        vscode.window
          .showInformationMessage("CNplus：工作区已受信任，正在启用完整功能…", "重新加载窗口")
          .then((选择) => {
            if (选择 === "重新加载窗口") {
              vscode.commands.executeCommand("workbench.action.reloadWindow");
            }
          });
      })
    );
  }

  // ---- 运行当前文件 ----
  上下文.subscriptions.push(
    vscode.commands.registerCommand("cnplus.运行当前文件", async () => {
      const 编辑器 = vscode.window.activeTextEditor;
      if (!编辑器 || 编辑器.document.languageId !== "cnplus") {
        vscode.window.showWarningMessage("请先打开一个 .cnp 文件");
        return;
      }
      const 解释器 = await 找解释器();
      if (!解释器) return 提示装不上("无法运行");

      await 编辑器.document.save();
      const 终端 =
        vscode.window.terminals.find((t) => t.name === "CNplus") ||
        vscode.window.createTerminal("CNplus");
      终端.show(true);
      // 文件可以在任何目录，用绝对路径，不依赖终端当前位置
      终端.sendText(`"${解释器}" -m cnplus 运行 "${编辑器.document.fileName}"`);
    })
  );

  // ---- 显示当前用的解释器（排查双版本问题时有用）----
  上下文.subscriptions.push(
    vscode.commands.registerCommand("cnplus.显示解释器", async () => {
      const 解释器 = await 找解释器({ 强制重找: true });
      if (!解释器) return 提示装不上("环境检查");
      const 详情 = await 试解释器(解释器);
      vscode.window.showInformationMessage(
        `CNplus 正在使用：${解释器}（CNplus ${详情.split("\n")[0]}）`
      );
    })
  );

  // ---- LSP：实时诊断 ----
  if (!vscode.workspace.getConfiguration("cnplus").get("启用LSP")) return;

  找解释器().then((解释器) => {
    if (!解释器) {
      // 语法高亮不依赖 LSP，所以这里只提示、不报错阻断
      vscode.window.showWarningMessage(
        "CNplus：未找到可启动语言服务的 Python（需安装 cnplus[lsp]），实时诊断已停用（语法高亮仍可用）。" +
          "运行命令「CNplus: 显示当前使用的解释器」可查看探测详情。"
      );
      return;
    }

    const 服务端选项 = {
      run: { command: 解释器, args: ["-m", "cnplus.lsp.server"], transport: TransportKind.stdio },
      debug: { command: 解释器, args: ["-m", "cnplus.lsp.server"], transport: TransportKind.stdio },
    };
    const 客户端选项 = {
      documentSelector: [{ scheme: "file", language: "cnplus" }],
      outputChannelName: "CNplus 语言服务",
    };

    客户端 = new LanguageClient("cnplus", "CNplus 语言服务", 服务端选项, 客户端选项);
    客户端.start().catch((错) => {
      vscode.window.showWarningMessage(
        `CNplus 语言服务启动失败（语法高亮仍可用）：${错.message}`
      );
    });
  });
}

function deactivate() {
  return 客户端 ? 客户端.stop() : undefined;
}

module.exports = { activate, deactivate };
