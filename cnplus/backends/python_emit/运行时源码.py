"""CNplus 运行时 —— 转译后端的语义引擎。

生成的 Python 代码每一步运算、每次作用域操作都调回这里，**保证 CNplus
语义不泄漏**（严格真值、跨类型比较报错、/ 恒为小数、块级作用域）。

这个模块是**自包含**的：不 import cnplus，可以直接内联进生成的文件，
让生成的 .py 在任意 python3 下独立运行。

抛出的 `CNplus错误` 带 (行,列)，由后端映射回原始 .cnp 的跨度。
"""


class CNplus错误(Exception):
    def __init__(self, 码, 消息, 行, 列, 提示=None, 解释=None):
        super().__init__(消息)
        self.码 = 码
        self.消息 = 消息
        self.行 = 行
        self.列 = 列
        self.提示 = 提示
        self.解释 = 解释


# ==================== 值 ====================

class _缺省类:
    """默认值占位：表示这个参数没有默认值，调用时必须给。"""
    _单例 = None
    def __repr__(self):
        return "<缺省>"

缺省 = _缺省类()


class 函数值:
    __slots__ = ("实现", "闭包", "形参们", "名", "默认们")

    def __init__(self, 实现, 闭包, 形参们, 名="", 默认们=None):
        self.实现 = 实现
        self.闭包 = 闭包
        self.形参们 = 形参们
        self.名 = 名
        self.默认们 = 默认们 if 默认们 is not None else [缺省] * len(形参们)


def 类型名(值):
    if 值 is None:
        return "空"
    if isinstance(值, bool):
        return "布尔"
    if isinstance(值, int):
        return "整数"
    if isinstance(值, float):
        return "小数"
    if isinstance(值, str):
        return "字符串"
    if isinstance(值, list):
        return "列表"
    if isinstance(值, dict):
        return "字典"
    if isinstance(值, 函数值):
        return "函数"
    return type(值).__name__


def 显示(值):
    if 值 is None:
        return "空"
    if 值 is True:
        return "真"
    if 值 is False:
        return "假"
    if isinstance(值, float):
        return repr(值)
    if isinstance(值, list):
        return "[" + ", ".join(显示(x) for x in 值) + "]"
    if isinstance(值, dict):
        return "{" + ", ".join(f"{显示(k)}: {显示(v)}" for k, v in 值.items()) + "}"
    if isinstance(值, 函数值):
        return f"<函数 {值.名}>"
    return str(值)


def _是数(值):
    return isinstance(值, (int, float)) and not isinstance(值, bool)


def _可比较(左, 右):
    if 左 is None or 右 is None:
        return True
    if isinstance(左, bool) or isinstance(右, bool):
        return isinstance(左, bool) and isinstance(右, bool)
    if _是数(左) and _是数(右):
        return True
    return type(左) is type(右)


# ==================== 环境（块级作用域）====================

class 环境:
    __slots__ = ("表", "父")

    def __init__(self, 父=None):
        self.表 = {}
        self.父 = 父

    def 声明(self, 名, 值, 行=0, 列=0):
        # 与树遍历后端一致：直接覆盖，不在运行期查重复。
        # 重复声明由静态检查器（checker）在运行前报 CN0307，
        # 这样两后端行为一致，且函数可以覆盖内置名（如自定义「查找」）。
        self.表[名] = 值

    def 取(self, 名, 行=0, 列=0):
        环 = self
        while 环 is not None:
            if 名 in 环.表:
                return 环.表[名]
            环 = 环.父
        raise CNplus错误("CN0302", f"变量 {名} 还没有声明过", 行, 列,
                      解释=f"CNplus 不认识 {名}，因为你还没告诉它这个名字代表什么",
                      提示=f"先用「设」建立它，例如：设 {名} = 0")

    def 赋值(self, 名, 值, 行=0, 列=0):
        环 = self
        while 环 is not None:
            if 名 in 环.表:
                环.表[名] = 值
                return
            环 = 环.父
        raise CNplus错误("CN0302", f"变量 {名} 还没有声明过", 行, 列,
                      解释=f"CNplus 不认识 {名}，因为你还没告诉它这个名字代表什么",
                      提示=f"先用「设」建立它，例如：设 {名} = 0")

    def 赋外层(self, 名, 值, 行=0, 列=0):
        环 = self.父
        while 环 is not None:
            if 名 in 环.表:
                环.表[名] = 值
                return
            环 = 环.父
        raise CNplus错误("CN0302", f"变量 {名} 还没有声明过", 行, 列,
                      解释=f"外层也没有 {名} 这个变量，没法用「外部」改它",
                      提示=f"先用「设」建立它，例如：设 {名} = 0")


# ==================== 运算（强制 CNplus 语义）====================

def 条件(值, 行, 列):
    if not isinstance(值, bool):
        raise CNplus错误("CN0301", f"条件必须是布尔值（真 或 假），这里是{类型名(值)}", 行, 列,
                      解释="判断的位置只能放「成立/不成立」的问题，不能直接放一个数或一段文字",
                      提示="写成一句能回答真/假的话，例如 x > 0、x != 0、名字 == \"小明\"")
    return 值


def 负(值, 行, 列):
    if isinstance(值, bool) or not _是数(值):
        raise CNplus错误("CN0303", f"负号只能用于数字，这里是{类型名(值)}", 行, 列,
                      解释=f"{类型名(值)}没法取负数")
    return -值


def 非(值, 行, 列):
    if not isinstance(值, bool):
        raise CNplus错误("CN0303", f"「非」只能用于布尔值（真 或 假），这里是{类型名(值)}", 行, 列,
                      解释="「非」是把「成立」翻成「不成立」，所以它后面得跟一个真/假",
                      提示="例如：非 (x > 0)")
    return not 值


def 加(左, 右, 行, 列):
    if isinstance(左, str) and isinstance(右, str):
        return 左 + 右
    if not (_是数(左) and _是数(右)):
        raise CNplus错误("CN0303", f"「+」不能用于{类型名(左)}和{类型名(右)}", 行, 列,
                      解释="「+」要么把两个数字相加，要么把两段文字接起来，不能一边数字一边文字",
                      提示=f"把数字转成文字再接起来：… + 文本({显示(右 if isinstance(左, str) else 左)})")
    return 左 + 右


def _两数(运, 左, 右, 行, 列):
    if not (_是数(左) and _是数(右)):
        raise CNplus错误("CN0303", f"「{运}」不能用于{类型名(左)}和{类型名(右)}", 行, 列,
                      解释=f"「{运}」两边都得是数字",
                      提示="检查两边的类型")
    return 左, 右


def 减(左, 右, 行, 列):
    左, 右 = _两数("-", 左, 右, 行, 列)
    return 左 - 右


def 乘(左, 右, 行, 列):
    if isinstance(左, str) and _是数(右):
        return 左 * int(右)
    if isinstance(右, str) and _是数(左):
        return 右 * int(左)
    左, 右 = _两数("*", 左, 右, 行, 列)
    return 左 * 右


def 除(左, 右, 行, 列):
    左, 右 = _两数("/", 左, 右, 行, 列)
    if 右 == 0:
        raise CNplus错误("CN0304", "除数不能是零", 行, 列,
                      解释="东西没法平均分给 0 个人，这在数学上没有答案",
                      提示="把除数改成非零的数")
    return 左 / 右  # 语义约定：/ 恒为小数


def 整除(左, 右, 行, 列):
    左, 右 = _两数("//", 左, 右, 行, 列)
    if 右 == 0:
        raise CNplus错误("CN0304", "除数不能是零", 行, 列)
    return 左 // 右


def 取余(左, 右, 行, 列):
    左, 右 = _两数("%", 左, 右, 行, 列)
    if 右 == 0:
        raise CNplus错误("CN0304", "除数不能是零", 行, 列)
    return 左 % 右


def 等于(左, 右, 行, 列):
    if not _可比较(左, 右):
        raise CNplus错误("CN0303", f"不能比较{类型名(左)}和{类型名(右)}", 行, 列,
                      解释=f"{类型名(左)}和{类型名(右)}是两类不同的东西，比它们相不相等没有意义",
                      提示="先用「文本(…)」或「整数(…)」把它们转成同一类再比")
    return 左 == 右


def 不等于(左, 右, 行, 列):
    return not 等于(左, 右, 行, 列)


def _比大小(运, 左, 右, 行, 列):
    if isinstance(左, str) and isinstance(右, str):
        pass
    elif _是数(左) and _是数(右):
        pass
    else:
        raise CNplus错误("CN0303", f"不能比较{类型名(左)}和{类型名(右)}的大小", 行, 列,
                      解释=f"{类型名(左)}和{类型名(右)}没法排先后",
                      提示="数字跟数字比，文字跟文字比")
    return 左, 右


def 小于(左, 右, 行, 列):
    左, 右 = _比大小("<", 左, 右, 行, 列)
    return 左 < 右


def 小于等于(左, 右, 行, 列):
    左, 右 = _比大小("<=", 左, 右, 行, 列)
    return 左 <= 右


def 大于(左, 右, 行, 列):
    左, 右 = _比大小(">", 左, 右, 行, 列)
    return 左 > 右


def 大于等于(左, 右, 行, 列):
    左, 右 = _比大小(">=", 左, 右, 行, 列)
    return 左 >= 右


def 与(左, 右, 行, 列):
    if not isinstance(左, bool):
        raise CNplus错误("CN0303", f"「与」两侧必须是布尔值（真 或 假），这里是{类型名(左)}", 行, 列,
                      解释="「与」用来连接两个「成立/不成立」的判断",
                      提示="例如：x > 0 与 y > 0")
    if not 左:
        return False  # 短路
    if not isinstance(右, bool):
        raise CNplus错误("CN0303", f"「与」两侧必须是布尔值（真 或 假），这里是{类型名(右)}", 行, 列,
                      解释="「与」用来连接两个「成立/不成立」的判断",
                      提示="例如：x > 0 与 y > 0")
    return 右


def 或(左, 右, 行, 列):
    if not isinstance(左, bool):
        raise CNplus错误("CN0303", f"「或」两侧必须是布尔值（真 或 假），这里是{类型名(左)}", 行, 列,
                      解释="「或」用来连接两个「成立/不成立」的判断",
                      提示="例如：x > 0 或 y > 0")
    if 左:
        return True  # 短路
    if not isinstance(右, bool):
        raise CNplus错误("CN0303", f"「或」两侧必须是布尔值（真 或 假），这里是{类型名(右)}", 行, 列,
                      解释="「或」用来连接两个「成立/不成立」的判断",
                      提示="例如：x > 0 或 y > 0")
    return 右


# ==================== 调用 / 导入 / 成员 ====================

def 自增值(旧, 增量, 行, 列):
    if isinstance(旧, bool) or not isinstance(旧, (int, float)):
        raise CNplus错误("CN0303", f"{类型名(旧)}不能自增/自减", 行, 列,
                      解释="++ 和 -- 只能用于数字", 提示="确认这个变量是数字")
    return 旧 + 增量


def 解包声明(环, 名们, 值, 行, 列):
    if not isinstance(值, (list, tuple)):
        raise CNplus错误("CN0303", f"右边是{类型名(值)}，没法拆给 {len(名们)} 个变量", 行, 列,
                      解释="要拆开赋值，右边得是一个列表（或多返回值）",
                      提示="例如：设 甲, 乙 = [1, 2]")
    if len(值) != len(名们):
        raise CNplus错误("CN0306", f"左边有 {len(名们)} 个变量，右边有 {len(值)} 个值", 行, 列,
                      解释="拆开赋值时两边数量必须一样多",
                      提示=f"左边写 {len(值)} 个变量，或让右边给 {len(名们)} 个值")
    for 名, v in zip(名们, 值):
        环.声明(名, v, 行, 列)


def _绑定(被调, 实参们, 关键字们, 行, 列):
    形参 = 被调.形参们
    默认 = 被调.默认们
    if len(实参们) > len(形参):
        raise CNplus错误("CN0306", f"{被调.名} 最多 {len(形参)} 个参数，给了 {len(实参们)} 个", 行, 列,
                      解释=f"你定义 {被调.名} 时写了 {len(形参)} 个位置",
                      提示=f"参数有：{'、'.join(形参) or '无'}")
    已填 = {}
    for i, 值 in enumerate(实参们):
        已填[形参[i]] = 值
    for 名, 值 in 关键字们:
        if 名 not in 形参:
            raise CNplus错误("CN0306", f"{被调.名} 没有叫「{名}」的参数", 行, 列,
                          解释=f"{被调.名} 的参数是：{'、'.join(形参) or '无'}",
                          提示="检查参数名是不是写错了")
        if 名 in 已填:
            raise CNplus错误("CN0306", f"参数「{名}」给了两次", 行, 列,
                          解释="一个参数只能赋值一次", 提示="删掉重复的那个")
        已填[名] = 值
    局部 = 环境(被调.闭包)
    for i, 名 in enumerate(形参):
        if 名 in 已填:
            局部.表[名] = 已填[名]
        elif 默认[i] is not 缺省:
            局部.表[名] = 默认[i]
        else:
            raise CNplus错误("CN0306", f"{被调.名} 缺少参数「{名}」", 行, 列,
                          解释=f"「{名}」没有默认值，调用时必须给它",
                          提示=f"补上：{被调.名}(…)")
    return 局部


def 调用(被调, 实参们, 关键字们, 行, 列):
    if isinstance(被调, 函数值):
        局部 = _绑定(被调, 实参们, 关键字们, 行, 列)
        return 被调.实现(局部)
    if callable(被调):
        kw = {名: 值 for 名, 值 in 关键字们}
        try:
            return 被调(*实参们, **kw)
        except CNplus错误:
            raise
        except EOFError:
            raise
        except Exception as ex:
            # 库/内置抛的错也包成 CNplus错误，这样「捕获」能接住 ——
            # 报错文本直接用异常消息，与树遍历后端一致
            raise CNplus错误("CN0303", str(ex), 行, 列) from None
    raise CNplus错误("CN0305", f"{类型名(被调)}不能被调用", 行, 列,
                  解释="名字后面加括号表示「执行它」，但只有函数能被执行",
                  提示="检查是不是名字写错了，或者本来不该加括号")


def 抛出(说明, 行, 列):
    """主动制造一个错误（对应 CNplus 的「抛出」）。"""
    raise CNplus错误("CN0311", 显示(说明), 行, 列,
                  解释="这是程序自己用「抛出」制造的错误",
                  提示="用「尝试 … 捕获」可以接住它")


_可点方法 = {
    "追加", "插入", "移除", "弹出", "排序", "倒序", "包含", "连接", "长度",
    "所有标签", "所有值", "有标签", "删标签",
    "分割", "替换", "查找", "去空白", "大写", "小写", "开头是", "结尾是",
}


def 点调用(全局, 对象, 方法名, 实参们, 关键字们, 行, 列):
    # 名单.追加(x)：对象是列表/字典/文字且方法名是内置集合方法时，
    # 当成 追加(名单, x)。否则退回普通成员访问 + 调用。
    if isinstance(对象, (list, dict, str)) and 方法名 in _可点方法:
        函数 = 内置们.get(方法名)
        if 函数 is not None:
            try:
                return 函数(对象, *实参们)
            except CNplus错误:
                raise
            except Exception as ex:
                raise CNplus错误("CN0303", f"调用 {方法名} 出错：{ex}", 行, 列)
    成员 = 取成员(对象, 方法名, 行, 列)
    return 调用(成员, 实参们, 关键字们, 行, 列)


def 取成员(对象, 属性, 行, 列):
    try:
        return getattr(对象, 属性)
    except AttributeError:
        raise CNplus错误("CN0302", f"{属性} 在 {类型名(对象)} 里不存在", 行, 列,
                      解释=f"这个东西没有叫「{属性}」的成员",
                      提示="检查成员名是不是写错了")


def 导入(模块名, 行, 列):
    import importlib
    try:
        return importlib.import_module(模块名)
    except Exception as ex:
        raise CNplus错误("CN0303", f"导入 {模块名!r} 失败：{ex}", 行, 列,
                      解释="找不到这个库，或者装的时候出了错",
                      提示=f"先确认它已安装：pip install {模块名}")


# ==================== 集合：索引 / 遍历 ====================

class 跳出信号(Exception):
    pass


class 继续信号(Exception):
    pass


def 取索引(对象, 下标, 行, 列):
    try:
        return 对象[下标]
    except TypeError:
        raise CNplus错误("CN0303", f"{类型名(对象)}不能用下标取值", 行, 列,
                      解释="只有列表、字典和文字能用 […] 取里面的东西",
                      提示="检查这个东西的类型")
    except IndexError:
        长 = len(对象) if hasattr(对象, "__len__") else "?"
        raise CNplus错误("CN0308", f"下标 {显示(下标)} 超出范围（一共 {长} 个）", 行, 列,
                      解释="列表下标从 0 开始，最大是「长度 - 1」",
                      提示="用「长度(…)」看有多少个")
    except KeyError:
        raise CNplus错误("CN0308", f"字典里没有标签 {显示(下标)}", 行, 列,
                      解释="这个标签不在字典里", 提示="检查标签是不是写错了")


def 设索引(对象, 下标, 值, 行, 列):
    try:
        对象[下标] = 值
    except TypeError:
        raise CNplus错误("CN0303", f"{类型名(对象)}不能用下标赋值", 行, 列,
                      解释="只有列表和字典能这样改内容",
                      提示="检查一下这个东西是不是列表或字典")
    except (IndexError, KeyError):
        raise CNplus错误("CN0308", f"下标 {显示(下标)} 超出范围", 行, 列,
                      解释="这个位置不存在，没法往那里放东西",
                      提示="列表下标从 0 开始")


def 造字典(键值对, 行, 列):
    出 = {}
    for 键, 值 in 键值对:
        try:
            出[键] = 值
        except TypeError:
            raise CNplus错误("CN0303", f"{类型名(键)}不能作字典的标签", 行, 列,
                          解释="字典的标签得是文字或数字这类固定不变的东西",
                          提示='例如 {"名字": "小明"}')
    return 出


def 遍历项(可迭代, 行, 列):
    try:
        return list(可迭代)
    except TypeError:
        raise CNplus错误("CN0309", f"{类型名(可迭代)}不能遍历", 行, 列,
                      解释="「遍历…每个…」需要一串东西，比如列表、字典或文字",
                      提示="用列表：遍历 [1, 2, 3] 每个 x")


def 幂(左, 右, 行, 列):
    if not (_是数(左) and _是数(右)):
        raise CNplus错误("CN0303", f"「**」不能用于{类型名(左)}和{类型名(右)}", 行, 列,
                      解释="幂运算两边都得是数字", 提示="检查两边的类型")
    try:
        return 左 ** 右
    except (OverflowError, ZeroDivisionError) as ex:
        raise CNplus错误("CN0303", f"幂运算出错：{ex}", 行, 列, 解释="结果太大或没有意义")


# ==================== 内置函数 ====================

def _内置_打印(*值们):
    print(" ".join(显示(v) for v in 值们))


import random as _随机库


def _范围(*参数):
    return list(range(*[int(x) for x in 参数]))


def _求和(序列):
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in 序列):
        raise TypeError("求和只能用于全是数字的列表")
    return sum(序列)


def _分割(文字, 分隔符=None):
    return 文字.split(分隔符) if 分隔符 is not None else 文字.split()


def _读一行():
    """返回 None 表示输入结束（EOF）。不能返回空串 —— 会让 询问数值 死循环。"""
    try:
        return input()
    except EOFError:
        return None


def _询问(提示=None):
    if 提示 is not None:
        print(显示(提示), end="", flush=True)
    return _读一行() or ""


def _询问数值(提示=None):
    while True:
        if 提示 is not None:
            print(显示(提示), end="", flush=True)
        行 = _读一行()
        if 行 is None:
            # 抛 EOFError，让后端用行映射定位到真正的调用处
            raise EOFError("还需要一个数字，但输入已经结束了")
        试 = 行.strip()
        try:
            if "." in 试:
                return float(试)
            return int(试)
        except ValueError:
            print(f"「{试}」不是数字，请重新输入。", flush=True)


def _转整数(a):
    try:
        return int(a)
    except (ValueError, TypeError):
        raise ValueError(f"没法把 {显示(a)} 变成整数") from None


def _转小数(a):
    try:
        return float(a)
    except (ValueError, TypeError):
        raise ValueError(f"没法把 {显示(a)} 变成小数") from None


内置们 = {
    "打印": _内置_打印,
    "询问": _询问,
    "询问数值": _询问数值,
    "类型": 类型名,
    "文本": 显示,
    "整数": _转整数,
    "小数": _转小数,
    "长度": len,
    "范围": _范围,
    "随机数": lambda a, b: _随机库.randint(int(a), int(b)),
    "绝对值": abs,
    "最大": lambda *a: max(a[0]) if len(a) == 1 else max(a),
    "最小": lambda *a: min(a[0]) if len(a) == 1 else min(a),
    "求和": _求和,
    "四舍五入": round,
    "平方根": lambda a: a ** 0.5,
    "追加": lambda 表, 项: 表.append(项),
    "插入": lambda 表, 位, 项: 表.insert(int(位), 项),
    "移除": lambda 表, 项: 表.remove(项),
    "弹出": lambda 表, *a: 表.pop(int(a[0])) if a else 表.pop(),
    "排序": lambda 表: sorted(表),
    "倒序": lambda 表: list(reversed(表)),
    "包含": lambda 容器, 项: 项 in 容器,
    "连接": lambda 表, 隔: 隔.join(显示(x) for x in 表),
    "所有标签": lambda 字: list(字.keys()),
    "所有值": lambda 字: list(字.values()),
    "有标签": lambda 字, 标签: 标签 in 字,
    "删标签": lambda 字, 标签: 字.pop(标签, None),
    "分割": _分割,
    "替换": lambda 文, 旧, 新: 文.replace(旧, 新),
    "查找": lambda 文, 子: 文.find(子),
    "去空白": lambda 文: 文.strip(),
    "大写": lambda 文: 文.upper(),
    "小写": lambda 文: 文.lower(),
    "开头是": lambda 文, 前: 文.startswith(前),
    "结尾是": lambda 文, 后: 文.endswith(后),
}


def 建全局环境():
    """内置放父环境，返回的是它的子环境（用户顶层）。

    这样用户能用 `设 查找 = 1` / `函数 查找(…)` 遮蔽内置名，
    与树遍历后端和静态检查器一致。
    """
    _内置环 = 环境()
    for 名, 值 in 内置们.items():
        _内置环.表[名] = 值
    return 环境(_内置环)
