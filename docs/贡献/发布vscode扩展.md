# 分发 VSCode 扩展

> CNplus 扩展通过 **GitHub Release 的 `.vsix` 文件**分发，用户从官网或
> GitHub 下载后一条命令安装。不依赖 VSCode 市场（市场发布流程见文末附录）。

## 为什么用 .vsix 而不是市场

- 无需注册 Azure DevOps 账号、创建 publisher、管理 PAT，少一层微软账号体系
- 开源项目把安装包挂在自己的 Release 上，下载链接稳定、可追溯
- 用户侧安装只需一条命令，不联网搜索也能装

代价：用户不会在 VSCode 扩展面板里搜到，需要点进官网下载。

## 分发流程

### 1. 打包

```bash
cd editors/vscode
vsce package --allow-missing-repository --no-yarn
```

生成 `cnplus-<版本>.vsix`。

### 2. 上传到 GitHub Release

```bash
# 先确保对应版本号的 release 已存在（gh release create v0.8.0），然后：
gh release upload v0.8.0 cnplus-0.8.0.vsix --repo CNplus/CNplus-lang --clobber
```

上传后的稳定下载链接是：

```
https://github.com/CNplus/CNplus-lang/releases/download/v0.8.0/cnplus-0.8.0.vsix
```

把版本号换成当前版本即可。这个链接可直链（302 重定向到实际文件）。

### 3. 更新官网下载页

`CNplus-web/src/pages/download.astro` 里放这个链接和安装说明（见下）。
同时检查 `src/config/site.ts` 的 `version` 是否已同步。

## 用户侧安装（写进官网/README 的文案）

**方式一：命令行**

```bash
code --install-extension cnplus-0.8.0.vsix
```

**方式二：图形界面**

VSCode 里按 `⌘⇧X`（Windows/Linux 是 `Ctrl+Shift+X`）打开扩展面板，
点右上角 `…` → **从 VSIX 安装…**，选中下载的 `.vsix` 文件。

装完**完全退出 VSCode 再打开**（⌘Q，不是关窗口），扩展才会加载。

## 本地测试（不发布）

```bash
cd editors/vscode
vsce package --allow-missing-repository --no-yarn
"/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
  --install-extension cnplus-0.8.0.vsix --force
```

然后**完全退出 VSCode 再打开**，确认高亮和 F5 运行都正常。

## 发布前检查清单

- [ ] `vsce package` 无报错
- [ ] `python tools/生成语法文件.py` 已重跑（关键字有变动时）
- [ ] `pytest tests/test_语法文件生成.py` 通过（确认无关键字漏项）
- [ ] 本地装过 `.vsix` 并确认高亮、F5 运行都正常
- [ ] `package.json` 的 `version` 已递增，且与语言版本号一致
- [ ] `package.json` 的 `license` 与主仓库一致（Apache-2.0）
- [ ] 扩展 README 与官网下载页的安装说明一致
- [ ] 上传后验证下载链接可访问（`curl -sIL <链接>` 应返回 200）

## 已知的坑

| 现象 | 原因 |
|---|---|
| 装了扩展但仍显示「纯文本」 | 没重启 VSCode；或用了 `ln -s` 软链方式（**已失效**，新版 VSCode 只认 `extensions.json` 登记过的扩展，必须装 `.vsix`） |
| 下载链接 404 | release 不存在、或资产名/版本号不一致 |
| `vsce` 找不到 | `npm install -g @vscode/vsce` |
| `.vsix` 里的许可不对 | `package.json` 的 `license` 与主仓库 `LICENSE`/`pyproject.toml` 不一致，打包前核对 |

---

## 附录：上架 VSCode 市场（可选，暂未采用）

> 2026-08-23 尝试过市场发布，卡在 Azure DevOps 登录。以下流程供日后
> 若想恢复市场发布时参考。

### 一次性准备

1. **注册 Azure DevOps 账号**：<https://dev.azure.com/>，微软账号登录，
   创建一个 organization（名字随意，不影响扩展显示名）。
2. **生成 PAT**：右上角头像 → User settings → Personal access tokens →
   New Token。**Organization 必须选 `All accessible organizations`**（否则
   发布 401），Scopes 勾选 `Marketplace → Manage`。创建后立刻复制 token。
3. **创建 Publisher**：<https://marketplace.visualstudio.com/manage> 登录，
   Create publisher，ID 填 `cnplus`（须与 `package.json` 的 `publisher`
   一致）。若被占用，改 ID 并同步 `package.json`。

### 发布命令

```bash
cd editors/vscode
vsce login cnplus      # 粘贴 PAT
vsce publish           # 或 vsce publish minor / patch / 1.0.0
```
