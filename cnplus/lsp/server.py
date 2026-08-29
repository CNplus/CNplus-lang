"""LSP 服务端 —— 实时诊断、补全、悬停与定义跳转。

**复用同一套 lexer/parser，零重复实现。** 这是不自研 IDE（D-006）的兑现：
写一个 server，VSCode / Neovim / Zed / JetBrains 全都能用。

依赖 pygls 2.x：pip install -e ".[lsp]"
注意 pygls 2.x 与 1.x 的 API 不同（模块路径、推送方法名都变了）。
"""
from __future__ import annotations

try:
    from lsprotocol import types as lsp
    from pygls.lsp.server import LanguageServer
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        '缺少 pygls 2.x。请先运行：pip install -e ".[lsp]"'
    ) from e

from cnplus import __version__
from cnplus.checker import 检查
from cnplus.diagnostics import 级别
from cnplus.parser.parser import 解析
from cnplus.source import 源文件, 跨度

服务器 = LanguageServer("cnplus-lsp", __version__)


def _内部列转LSP列(源: 源文件, 行: int, 列: int) -> int:
    """把 1 起 Unicode 码点列转成 0 起 UTF-16 单元列。"""
    前缀 = 源.取行(行)[:max(列 - 1, 0)]
    return len(前缀.encode("utf-16-le")) // 2


def _LSP列转内部列(行文本: str, LSP列: int) -> int:
    """把 0 起 UTF-16 单元列转成 1 起 Unicode 码点列。"""
    已走 = 0
    for 下标, 字 in enumerate(行文本):
        下一处 = 已走 + len(字.encode("utf-16-le")) // 2
        if 下一处 > LSP列:
            return 下标 + 1
        已走 = 下一处
        if 已走 == LSP列:
            return 下标 + 2
    return len(行文本) + 1


def _跨度转LSP范围(源: 源文件, 跨: 跨度) -> lsp.Range:
    return lsp.Range(
        start=lsp.Position(
            line=跨.起.行 - 1,
            character=_内部列转LSP列(源, 跨.起.行, 跨.起.列),
        ),
        end=lsp.Position(
            line=跨.止.行 - 1,
            character=_内部列转LSP列(源, 跨.止.行, 跨.止.列),
        ),
    )


def _文档与位置(ls: LanguageServer, uri: str, pos) -> tuple[str, int, int]:
    """取文档文本和 1 起行列。"""
    文档 = ls.workspace.get_text_document(uri)
    行0 = pos.line
    行们 = 文档.source.split("\n")
    行文本 = 行们[行0] if 0 <= 行0 < len(行们) else ""
    return 文档.source, 行0 + 1, _LSP列转内部列(行文本, pos.character)


def 转诊断(诊, 源: 源文件) -> lsp.Diagnostic:
    """CNplus 诊断 -> LSP 诊断。行列从 1 起转成从 0 起。"""
    范围 = _跨度转LSP范围(源, 诊.跨)
    # 有可标记字符时扩成一个完整码点；行尾保持合法零宽范围，不能越界。
    if 范围.start == 范围.end:
        行文本 = 源.取行(诊.跨.起.行)
        下标 = 诊.跨.起.列 - 1
        if 0 <= 下标 < len(行文本):
            范围.end.character += len(行文本[下标].encode("utf-16-le")) // 2
    消息 = 诊.消息
    if 诊.提示:
        消息 += f"\n提示：{诊.提示}"
    return lsp.Diagnostic(
        range=范围,
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
    跨 = 跳转模块.定义跨度于(码, 行, 列)
    if 跨 is None:
        return None
    return lsp.Location(
        uri=uri,
        range=_跨度转LSP范围(源文件(码, uri), 跨),
    )


def main() -> None:
    服务器.start_io()


if __name__ == "__main__":
    main()
