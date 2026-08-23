# 发布扩展到 VSCode 市场

> 这份文档记录发布流程。**注册账号和生成令牌只能由维护者本人完成**
> （涉及个人凭据），其余步骤已脚本化。

## 一次性准备

### 1. 注册 Azure DevOps 账号

VSCode 市场的账号体系挂在 Azure DevOps 上（微软的东西，绕不开）。

1. 打开 <https://dev.azure.com/>
2. 用微软账号登录（没有就注册一个，可用任意邮箱）
3. 登录后会让你创建一个 organization，名字随意（例如 `cnplus`），
   这个名字**不影响**扩展的显示名

### 2. 生成 Personal Access Token（PAT）

1. 在 Azure DevOps 右上角点头像旁的 **User settings** →
   **Personal access tokens**
2. 点 **New Token**，按下面填：

| 字段 | 填什么 |
|---|---|
| Name | `vsce-publish`（随意） |
| Organization | **必须选 `All accessible organizations`** |
| Expiration | 建议 1 年 |
| Scopes | 点 **Show all scopes**，勾选 **Marketplace → Manage** |

3. 点 Create，**立刻复制那串 token**（关掉就再也看不到了）

> ⚠️ Organization 一定要选 `All accessible organizations`，只选单个
> organization 会导致发布时报 401。这是最常见的坑。

### 3. 创建 Publisher

Publisher 是扩展的署名主体，必须和 `package.json` 里的 `publisher` 字段一致。
本项目用的是 **`cnplus`**。

1. 打开 <https://marketplace.visualstudio.com/manage>
2. 用同一个微软账号登录
3. 点 **Create publisher**：
   - **ID** 填 `cnplus`（这个就是 `package.json` 里的 publisher，不可改）
   - **Display name** 填 `CNplus`
   - 其余可留空

如果 `cnplus` 这个 ID 已被占用，改一个（例如 `cnplus-lang`），
**并同步修改 `editors/vscode/package.json` 的 `publisher` 字段**，否则发布会失败。

## 发布

准备好上面三样之后：

```bash
cd editors/vscode

# 登录（只需一次，token 存进本机 keychain）
vsce login cnplus
# 提示 Personal Access Token 时粘贴那串 token

# 发布
vsce publish
```

发布后几分钟内会出现在市场，之后用户就能直接搜「CNplus」安装。

### 后续更新版本

```bash
vsce publish minor   # 0.8.0 -> 0.9.0
vsce publish patch   # 0.8.0 -> 0.8.1
vsce publish 1.0.0   # 指定版本号
```

它会自动改 `package.json` 的 version、打包、上传。

## 本地测试（不发布）

改完扩展想先自己试：

```bash
cd editors/vscode
vsce package --allow-missing-repository --no-yarn
"/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
  --install-extension cnplus-0.8.0.vsix --force
```

然后**完全退出 VSCode 再打开**（⌘Q，不是关窗口），扩展才会重新加载。

## 发布前检查清单

- [ ] `vsce package` 无报错
- [ ] `python tools/生成语法文件.py` 已重跑（关键字有变动时）
- [ ] `pytest tests/test_语法文件生成.py` 通过（确认无关键字漏项）
- [ ] 本地装过 `.vsix` 并确认高亮、F5 运行都正常
- [ ] `package.json` 的 `version` 已递增
- [ ] README 里的安装说明与实际情况一致
      （例如 CNplus 若已上 PyPI，要把源码安装改成 `pip install cnplus`）

## 已知的坑

| 现象 | 原因 |
|---|---|
| 发布报 401 | PAT 的 Organization 没选 `All accessible organizations` |
| 发布报 publisher 不存在 | 没在 marketplace/manage 创建 publisher，或 ID 不一致 |
| 装了扩展但仍显示「纯文本」 | 没重启 VSCode；或用了 `ln -s` 软链方式（**已失效**，新版 VSCode 只认 `extensions.json` 登记过的扩展，必须装 `.vsix`） |
| `vsce` 找不到 | `npm install -g @vscode/vsce` |
