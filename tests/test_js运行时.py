"""JS 运行时语义单测（T2）——用 node 直接断言 运行时源码.js 的行为。

关键防御点每个一条测试：
- 除法恒为小数（JS 原生 4/2 是整数 2）
- 严格真值
- 环境链
- 显示的真/假/空
- 整数安全边界
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

运行时 = Path(__file__).parents[1] / "cnplus" / "backends" / "js_emit" / "运行时源码.js"


def node跑(代码: str) -> str:
    """运行时源码 + 代码 片段喂 node，返回 stdout。"""
    源 = 运行时.read_text(encoding="utf-8") + "\n" + 代码
    r = subprocess.run(["node", "-e", 源], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError(f"node 执行失败：\n{r.stderr[:500]}")
    return r.stdout


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="本机无 node")


# ==================== 值与显示 ====================

def test_显示_真():
    assert node跑("console.log(显示(true))") == "真\n"

def test_显示_假():
    assert node跑("console.log(显示(false))") == "假\n"

def test_显示_空():
    assert node跑("console.log(显示(null))") == "空\n"

def test_显示_整数():
    assert node跑("console.log(显示(3))") == "3\n"

def test_显示_小数():
    assert node跑("console.log(显示(3.5))") == "3.5\n"

def test_显示_除法恒小数():
    """JS 原生 4/2 === 2（整数）——运行时必须显示成 2.0。"""
    assert node跑("console.log(显示(除(4, 2, 0, 0)))") == "2.0\n"

def test_显示_负零():
    assert node跑("console.log(显示(-0))") == "0\n"

def test_显示_列表():
    assert node跑("console.log(显示([1, 2, 3]))") == "[1, 2, 3]\n"

def test_显示_列表含小数():
    assert node跑("console.log(显示([标记小数(2)]))") == "[2.0]\n"


def test_除法结果是小数标记():
    """除法结果即使整除也是小数——显示 2.0，类型名 小数。"""
    assert node跑("console.log(类型名(除(4, 2, 0, 0)))") == "小数\n"

def test_显示_字符串():
    assert node跑("console.log(显示('你好'))") == "你好\n"


# ==================== 类型名 ====================

def test_类型名():
    assert node跑("console.log(类型名(3))") == "整数\n"
    assert node跑("console.log(类型名(3.5))") == "小数\n"
    assert node跑("console.log(类型名(标记小数(2)))") == "小数\n"
    assert node跑("console.log(类型名(true))") == "布尔\n"
    assert node跑("console.log(类型名('a'))") == "字符串\n"
    assert node跑("console.log(类型名(null))") == "空\n"
    assert node跑("console.log(类型名([1]))") == "列表\n"
    assert node跑("console.log(类型名(new Map()))") == "字典\n"


# ==================== 运算语义 ====================

def test_除_恒小数():
    assert node跑("console.log(拆小数(除(4, 2, 0, 0)))") == "2\n"  # 数值是 2，类型/显示层负责 .0

def test_除_除零报错():
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\ntry { 除(1, 0, 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0304"

def test_条件_严格真值():
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\ntry { 条件(1, 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0301"

def test_加_跨类型报错():
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\ntry { 加(1, 'a', 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0303"

def test_加_字符串拼接():
    assert node跑("console.log(加('a', 'b', 0, 0))") == "ab\n"

def test_等于_跨类型报错():
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\ntry { 等于(1, 'a', 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0303"


# ==================== 整数安全边界 ====================

def test_整数_超出安全范围报错():
    """2^53 失真——运行时必须拒绝而不是悄悄给错值。"""
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\ntry { 校验整数(9007199254740993, 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0303"

def test_整数_安全范围内通过():
    assert node跑("console.log(校验整数(9007199254740991, 0, 0))") == "9007199254740991\n"


# ==================== 环境链 ====================

def test_环境_声明与取():
    assert node跑("""
const 环 = new 环境(null);
环.声明('x', 42, 0, 0);
console.log(环.取('x', 0, 0));
""") == "42\n"

def test_环境_父链查找():
    assert node跑("""
const 父 = new 环境(null);
父.声明('x', 1, 0, 0);
const 子 = new 环境(父);
console.log(子.取('x', 0, 0));
""") == "1\n"

def test_环境_未声明报CN0302():
    r = subprocess.run(["node", "-e", 运行时.read_text(encoding='utf-8')
                        + "\nconst 环 = new 环境(null); try { 环.取('小明', 0, 0) } catch (e) { console.log(e.码) }"],
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "CN0302"

def test_环境_赋值():
    assert node跑("""
const 环 = new 环境(null);
环.声明('x', 1, 0, 0);
环.赋值('x', 9, 0, 0);
console.log(环.取('x', 0, 0));
""") == "9\n"
