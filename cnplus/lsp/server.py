"""LSP 服务端 —— 阶段 0.5 只做实时诊断。

**复用同一套 lexer/parser，零重复实现。** 这是不自研 IDE（D-006）的兑现：
写一个 server，VSCode / Neovim / Zed / JetBrains 全都能用。

依赖 pygls 2.x：uv pip install -e ".[lsp]"
注意 pygls 2.x 与 1.x 的 API 不同（模块路径、推送方法名都变了）。
"""
from __future__ import annotations

try:
    from lsprotocol import types as lsp
    from pygls.lsp.server import LanguageServer
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        '缺少 pygls 2.x。请先运行：uv pip install -e ".[lsp]"'
    ) from e

from cnplus import __version__
from cnplus.checker import 检查
from cnplus.diagnostics import 级别
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

服务器 = LanguageServer("cnplus-lsp", __version__)


def _文档与位置(ls: LanguageServer, uri: str, pos) -> tuple[str, int, int]:
    """取文档文本和 1 起行列。"""
    文档 = ls.workspace.get_text_document(uri)
    行0, 列0 = pos.line, pos.character
    return 文档.source, 行0 + 1, 列0 + 1


def 转诊断(诊, 源: 源文件) -> lsp.Diagnostic:
    """CNplus 诊断 -> LSP 诊断。行列从 1 起转成从 0 起。"""
    起 = lsp.Position(line=诊.跨.起.行 - 1, character=max(诊.跨.起.列 - 1, 0))
    # 保证至少一格宽，否则 VSCode 不画波浪线
    止列 = 诊.跨.止.列 - 1 if 诊.跨.止.行 != 诊.跨.起.行 else max(诊.跨.止.列 - 1, 诊.跨.起.列)
    止 = lsp.Position(line=诊.跨.止.行 - 1, character=max(止列, 0))
    消息 = 诊.消息
    if 诊.提示:
        消息 += f"\n提示：{诊.提示}"
    return lsp.Diagnostic(
        range=lsp.Range(start=起, end=止),
        message=消息,
        severity=(lsp.DiagnosticSeverity.Error if 诊.级 is 级别.错误
                  else lsp.DiagnosticSeverity.Warning),
        code=诊.码,
        source="cnplus",
    )


def 诊断文本(文本: str, 文件名: str = "<编辑器>") -> list[lsp.Diagnostic]:
    """纯函数，方便测试：文本进，LSP 诊断出。"""
    源 = 源文件(文本, 文件名)
    # parser 永不抛异常（D-005），所以这里可以放心直接调
    程, 袋 = 解析(源)
    if not 袋.有错:
        # 语法没问题才做静态检查，否则会在残缺 AST 上产生噪音
        检查(程, 袋)
    return [转诊断(d, 源) for d in 袋]


def _检查并推送(ls: LanguageServer, uri: str) -> None:
    文档 = ls.workspace.get_text_document(uri)
    诊断们 = 诊断文本(文档.source, uri.rsplit("/", 1)[-1])
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=诊断们)
    )


@服务器.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def 打开(ls: LanguageServer, 参数: lsp.DidOpenTextDocumentParams) -> None:
    _检查并推送(ls, 参数.text_document.uri)


@服务器.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def 变更(ls: LanguageServer, 参数: lsp.DidChangeTextDocumentParams) -> None:
    _检查并推送(ls, 参数.text_document.uri)


@服务器.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def 保存(ls: LanguageServer, 参数: lsp.DidSaveTextDocumentParams) -> None:
    _检查并推送(ls, 参数.text_document.uri)


# ==================== 补全 / 悬停 / 跳转（阶段 3 收尾） ====================

@服务器.feature(lsp.TEXT_DOCUMENT_COMPLETION)
def 补全(ls: LanguageServer, 参数: lsp.CompletionParams) -> lsp.CompletionList:
    from cnplus.lsp import 补全 as 补全模块
    码, 行, 列 = _文档与位置(ls, 参数.text_document.uri, 参数.position)
    项们 = 补全模块.补全于(码, 行, 列)
    return lsp.CompletionList(is_incomplete=False, items=项们)


@服务器.feature(lsp.TEXT_DOCUMENT_HOVER)
def 悬停(ls: LanguageServer, 参数: lsp.HoverParams) -> lsp.Hover | None:
    from cnplus.lsp import 悬停 as 悬停模块
    码, 行, 列 = _文档与位置(ls, 参数.text_document.uri, 参数.position)
    文本 = 悬停模块.悬停于(码, 行, 列)
    if 文本 is None:
        return None
    return lsp.Hover(contents=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown,
                                                value=文本))


@服务器.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def 跳转定义(ls: LanguageServer,
             参数: lsp.DefinitionParams) -> lsp.Location | None:
    from cnplus.lsp import 跳转 as 跳转模块
    uri = 参数.text_document.uri
    码, 行, 列 = _文档与位置(ls, uri, 参数.position)
    位置 = 跳转模块.定义于(码, 行, 列)
    if 位置 is None:
        return None
    行, 列 = 位置
    return lsp.Location(
        uri=uri,
        range=lsp.Range(
            start=lsp.Position(line=行 - 1, character=列 - 1),
            end=lsp.Position(line=行 - 1, character=列 - 1 + 2),
        ),
    )


def main() -> None:
    服务器.start_io()


if __name__ == "__main__":
    main()
