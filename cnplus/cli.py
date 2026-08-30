"""命令行入口。

    cnp 运行 x.cnp      执行程序
    cnp 交互            打开交互模式
    cnp 编译 --js x.cnp 生成 JavaScript
    cnp 词法 x.cnp      打印词元流（调试）
    cnp 语法树 x.cnp    打印 AST（调试）
    cnp 检查 x.cnp      只报诊断，不执行
"""
from __future__ import annotations

import sys
from pathlib import Path

from cnplus.backends.python_emit import Python转译后端, 编译到文件
from cnplus.backends.treewalk import 树遍历后端
from cnplus.checker import 检查 as 静态检查
from cnplus.diagnostics import 诊断袋
from cnplus.lexer.lexer import 扫描
from cnplus.parser.parser import 解析
from cnplus.source import 源文件

_用法 = """CNplus —— 使用中文撸代码

用法：
  cnp 运行 <文件.cnp>             执行程序（树遍历后端）
  cnp 运行 --python <文件.cnp>    转译成 Python 再执行（可导入 pip 库）
  cnp 运行 --js <文件.cnp>        转译成 JavaScript 后用 Node 执行
  cnp 编译 <文件.cnp>             编译成独立的 .py 文件，可到处运行
  cnp 编译 --js <文件.cnp>        编译成可在 Node 或现代浏览器运行的 .js 文件
  cnp 交互                       打开交互模式
  cnp 检查 <文件.cnp>             只检查错误，不执行
  cnp 词法 <文件.cnp>             打印词元流（调试）
  cnp 语法树 <文件.cnp>           打印语法树（调试）
  cnp 版本                       显示版本
"""


def _用法文本() -> str:
    from cnplus.backends.js_emit import JS转译后端

    能力 = JS转译后端.能力
    说明 = f"JS 生成物可运行于{'、'.join(能力.运行环境们)}。"
    if not 能力.支持导入:
        说明 += "JS 后端暂不支持「导入」。"
    return _用法 + "\n" + 说明


def _读源(路径: str) -> 源文件 | None:
    p = Path(路径)
    if not p.exists():
        print(f"错误：找不到文件 {路径}", file=sys.stderr)
        return None
    return 源文件(p.read_text(encoding="utf-8"), p.name)


def _报诊断(袋: 诊断袋, 源: 源文件) -> None:
    if len(袋):
        print(袋.渲染全部(源), file=sys.stderr)


def 运行(路径: str, 用转译: bool = False, 用JS: bool = False) -> int:
    源 = _读源(路径)
    if 源 is None:
        return 2
    程, 袋 = 解析(源)
    if not 袋.有错:
        静态检查(程, 袋)
    if 袋.有错:
        _报诊断(袋, 源)
        print(f"\n发现 {len(袋)} 个问题，未执行。", file=sys.stderr)
        return 1
    if 用JS:
        from cnplus.backends.js_emit import JS转译后端
        后 = JS转译后端(直通输出=True)
    else:
        后 = Python转译后端() if 用转译 else 树遍历后端()
    后.执行(程, 源, 袋)
    if 袋.有错:
        _报诊断(袋, 源)
        return 1
    return 0


def 编译(路径: str, 目标: str | None = None, js: bool = False) -> int:
    源 = _读源(路径)
    if 源 is None:
        return 2
    程, 袋 = 解析(源)
    if not 袋.有错:
        静态检查(程, 袋)
    if 袋.有错:
        _报诊断(袋, 源)
        print(f"\n发现 {len(袋)} 个问题，未编译。", file=sys.stderr)
        return 1
    if js:
        from cnplus.backends.js_emit import 编译到文件 as js编译
        目标路径 = Path(目标) if 目标 else Path(路径).with_suffix(".js")
        js编译(程, 目标路径)
        print(f"已编译 → {目标路径}")
        print(f"可独立运行：node {目标路径}")
    else:
        目标路径 = Path(目标) if 目标 else Path(路径).with_suffix(".py")
        编译到文件(程, 目标路径)
        print(f"已编译 → {目标路径}")
        print(f"可独立运行：python3 {目标路径}")
    return 0


def 检查(路径: str) -> int:
    源 = _读源(路径)
    if 源 is None:
        return 2
    程, 袋 = 解析(源)
    if not 袋.有错:
        静态检查(程, 袋)
    if len(袋):
        _报诊断(袋, 源)
        print(f"\n发现 {len(袋)} 个问题。", file=sys.stderr)
        return 1 if 袋.有错 else 0
    print("没有发现问题。")
    return 0


def 词法(路径: str) -> int:
    源 = _读源(路径)
    if 源 is None:
        return 2
    词元们, 袋 = 扫描(源)
    for t in 词元们:
        print(f"{str(t.跨):<16} {t.种!s:<8} {t.文本!r}"
              + (f" = {t.值!r}" if t.值 is not None else ""))
    _报诊断(袋, 源)
    return 1 if 袋.有错 else 0


def 语法树(路径: str) -> int:
    源 = _读源(路径)
    if 源 is None:
        return 2
    程, 袋 = 解析(源)
    print(_画树(程))
    _报诊断(袋, 源)
    return 1 if 袋.有错 else 0


def _画树(节, 深: int = 0) -> str:
    缩 = "  " * 深
    名 = type(节).__name__
    字段 = []
    子 = []
    for f in getattr(节, "__slots__", ()) or ():
        if f == "跨" or f.endswith("跨") or f.endswith("跨们"):
            continue
        v = getattr(节, f, None)
        if hasattr(v, "跨"):
            子.append((f, v))
        elif isinstance(v, tuple) and v and hasattr(v[0], "跨"):
            for i, x in enumerate(v):
                子.append((f"{f}[{i}]", x))
        elif isinstance(v, tuple) and not v:
            pass
        elif v is not None:
            字段.append(f"{f}={v!r}")
    头 = f"{缩}{名}"
    if 字段:
        头 += " " + " ".join(字段)
    头 += f"  @{节.跨}"
    行 = [头]
    for 标, c in 子:
        行.append(f"{缩}  ·{标}")
        行.append(_画树(c, 深 + 2))
    return "\n".join(行)


def main(参数: list[str] | None = None) -> int:
    参数 = list(sys.argv[1:] if 参数 is None else 参数)
    if not 参数 or 参数[0] in ("-h", "--help", "帮助"):
        print(_用法文本())
        return 0
    命令 = 参数[0]
    if 命令 in ("版本", "--version", "-V"):
        if len(参数) > 1:
            print(f"错误：{命令} 收到了多余的参数 {参数[1]!r}", file=sys.stderr)
            return 2
        from cnplus import __version__
        print(f"CNplus {__version__}")
        return 0
    允许选项 = {
        "运行": {"--js", "--python", "-p", "--转译"},
        "编译": {"--js"},
        "检查": set(), "词法": set(), "语法树": set(),
        "run": set(), "check": set(),
    }
    if 命令 in 允许选项:
        for 项 in 参数[1:]:
            if 项.startswith("-") and 项 not in 允许选项[命令]:
                print(f"错误：不认识的选项 {项!r}", file=sys.stderr)
                return 2
    if 命令 == "编译":
        if len(参数) < 2:
            print("错误：编译 需要一个文件名", file=sys.stderr)
            return 2
        js = "--js" in 参数
        位置参数 = [a for a in 参数[1:] if not a.startswith("--")]
        if not 位置参数:
            选项 = " --js" if js else ""
            print(f"错误：编译{选项} 需要一个文件名", file=sys.stderr)
            return 2
        if len(位置参数) > 2:
            print(f"错误：编译 收到了多余的参数 {位置参数[2]!r}", file=sys.stderr)
            return 2
        return 编译(位置参数[0], 位置参数[1] if len(位置参数) > 1 else None, js=js)
    if 命令 == "交互":
        if len(参数) > 1:
            print(f"错误：交互 收到了多余的参数 {参数[1]!r}", file=sys.stderr)
            return 2
        from cnplus.repl import 交互循环
        交互循环()
        return 0
    # 运行 支持 --python 转译后端
    if 命令 == "运行":
        后端选项 = {"--js", "--python", "-p", "--转译"}
        if len(参数) >= 3 and 参数[1] in 后端选项 and 参数[2] in 后端选项:
            print("错误：运行一次只能选择一个后端选项", file=sys.stderr)
            return 2
        if len(参数) >= 3 and 参数[1] not in 后端选项 \
                and any(项 in 后端选项 for 项 in 参数[2:]):
            print("错误：运行的后端选项要写在文件名前", file=sys.stderr)
            return 2
        允许个数 = 3 if len(参数) >= 2 and 参数[1] in 后端选项 else 2
        if len(参数) > 允许个数:
            print(f"错误：运行 收到了多余的参数 {参数[允许个数]!r}", file=sys.stderr)
            return 2
        if len(参数) >= 2 and 参数[1] == "--js":
            if len(参数) < 3:
                print("错误：运行 --js 需要一个文件名", file=sys.stderr)
                return 2
            return 运行(参数[2], 用JS=True)
        if len(参数) >= 2 and 参数[1] in ("--python", "-p", "--转译"):
            if len(参数) < 3:
                print("错误：运行 --python 需要一个文件名", file=sys.stderr)
                return 2
            return 运行(参数[2], 用转译=True)
        if len(参数) < 2:
            print("错误：运行 需要一个文件名", file=sys.stderr)
            return 2
        return 运行(参数[1])
    if 命令 not in ("检查", "词法", "语法树", "run", "check"):
        print(f"错误：不认识的命令 {命令!r}", file=sys.stderr)
        print(_用法文本(), file=sys.stderr)
        return 2
    if len(参数) < 2:
        print(f"错误：{命令} 需要一个文件名", file=sys.stderr)
        print(_用法文本(), file=sys.stderr)
        return 2
    if len(参数) > 2:
        print(f"错误：{命令} 收到了多余的参数 {参数[2]!r}", file=sys.stderr)
        return 2
    表 = {"检查": 检查, "词法": 词法, "语法树": 语法树,
         "run": 运行, "check": 检查}
    return 表[命令](参数[1])


if __name__ == "__main__":
    sys.exit(main())
