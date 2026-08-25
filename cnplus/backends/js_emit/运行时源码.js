// CNplus 运行时 —— JS 转译后端的语义引擎（T2 核心）。
//
// 生成的 JS 代码每一步运算、每次作用域操作都调回这里，
// 保证 CNplus 语义不泄漏（严格真值、跨类型比较报错、
// / 恒为小数、块级作用域）。
//
// 这个模块是自包含的：不 import 任何东西，直接内联进生成的
// .js 文件，可在 node 与浏览器（ES5+）下独立运行。
//
// 数字语义防御（与 Python 后端的关键差异点）：
// - JS Number 是 64 位浮点，4/2 得整数 2 —— 显示层负责把
//   「值为整数的浮点数」渲染成 x.0（除法结果恒走浮点标记）
// - 整数超过 ±(2^53-1) 会失真 —— 校验整数 主动报 CN0303
// - -0 / NaN / Infinity 一律在入口拦截
//
// 抛出的 CNplus错误 带 (行, 列)，由生成代码映射回 .cnp 跨度。

"use strict";


class CNplus错误 extends Error {
    constructor(码, 消息, 行, 列, 提示, 解释) {
        super(消息);
        this.码 = 码;
        this.消息 = 消息;
        this.行 = 行;
        this.列 = 列;
        this.提示 = 提示;
        this.解释 = 解释;
    }
}


// ==================== 值 ====================

const 缺省 = { toString() { return "<缺省>"; } };

const 安全整数上限 = 9007199254740991;  // 2^53 - 1


class 小数值 {
    // JS 的 Number 层面 2 与 2.0 是同一个值，「这是小数」的信息
    // 在 JS 里原则上不存在。CNplus 语义要求 整数2 ≠ 小数2.0，
    // 发射器对小数字面量包 标记小数(2.0)，显示/类型名逐层识别。
    constructor(值) {
        this.值 = 值;
    }
}


function 标记小数(v) {
    return v instanceof 小数值 ? v : new 小数值(v);
}


function 拆小数(v) {
    return v instanceof 小数值 ? v.值 : v;
}


function 是布尔(v) { return typeof v === "boolean"; }
function 是数(v) {
    v = 拆小数(v);
    return typeof v === "number" && Number.isFinite(v);
}
function 是整数(v) {
    v = 拆小数(v);
    return typeof v === "number" && Number.isInteger(v);
}


function 校验整数(v, 行, 列) {
    if (!是整数(v) || Math.abs(v) > 安全整数上限) {
        if (是数(v) && Number.isInteger(v) && Math.abs(v) > 安全整数上限) {
            throw new CNplus错误("CN0303",
                "数字太大，超出了能精确表示的范围（约 9 千万亿）", 行, 列,
                "JS 环境里整数超过 2^53-1 会悄悄失真，CNplus 直接报错",
                "改用小数，或把数值控制在安全范围内");
        }
    }
    return v;
}


function 类型名(值) {
    if (值 === null) return "空";
    if (是布尔(值)) return "布尔";
    if (值 instanceof 小数值) return "小数";
    if (是整数(值)) return "整数";
    if (是数(值)) return "小数";
    if (typeof 值 === "string") return "字符串";
    if (Array.isArray(值)) return "列表";
    if (值 instanceof Map) return "字典";
    if (值 instanceof 函数值) return "函数";
    if (值 instanceof 类值) return "类";
    if (值 instanceof 实例值) return 值.类.名;
    if (值 instanceof 绑定方法) return "函数";
    return typeof 值;
}


function 显示小数(值) {
    // 3.5 → "3.5"；2 → "2.0"（除法结果恒为小数的显示规则）
    const 串 = String(值);
    return 串.includes(".") || 串.includes("e") ? 串 : 串 + ".0";
}


function 显示(值) {
    if (值 === null) return "空";
    if (值 === true) return "真";
    if (值 === false) return "假";
    if (值 instanceof 小数值) {
        const v = 值.值;
        return Object.is(v, -0) ? "0" : 显示小数(v);
    }
    if (typeof 值 === "number") {
        if (Object.is(值, -0)) return "0";
        if (Number.isInteger(值)) return String(值);
        return 显示小数(值);
    }
    if (typeof 值 === "string") return 值;
    if (Array.isArray(值))
        return "[" + 值.map(x => 显示(x)).join(", ") + "]";
    if (值 instanceof Map)
        return "{" + [...值.entries()].map(
            ([k, v]) => `${显示(k)}: ${显示(v)}`).join(", ") + "}";
    if (值 instanceof 函数值) return `<函数 ${值.名}>`;
    if (值 instanceof 实例值) return `<${值.类.名}>`;
    if (值 instanceof 类值) return `<类 ${值.名}>`;
    if (值 instanceof 绑定方法) return String(值);
    return String(值);
}


// ==================== 环境（块级作用域）====================

class 环境 {
    constructor(父) {
        this.表 = new Map();
        this.父 = 父 || null;
    }
    声明(名, 值, 行 = 0, 列 = 0) {
        this.表.set(名, 值);
    }
    取(名, 行 = 0, 列 = 0) {
        let 环 = this;
        while (环 !== null) {
            if (环.表.has(名)) return 环.表.get(名);
            环 = 环.父;
        }
        throw new CNplus错误("CN0302", `变量 ${名} 还没有声明过`, 行, 列,
            `CNplus 不认识 ${名}，因为你还没告诉它这个名字代表什么`,
            `两种可能：一是想把「${名}」当一段文字，给它加上双引号 （例如 设 名字 = "${名}"）；二是想用变量，但还没建立它 （先写 设 ${名} = …）`);
    }
    赋值(名, 值, 行 = 0, 列 = 0) {
        let 环 = this;
        while (环 !== null) {
            if (环.表.has(名)) { 环.表.set(名, 值); return; }
            环 = 环.父;
        }
        throw new CNplus错误("CN0302", `变量 ${名} 还没有声明过`, 行, 列,
            `CNplus 不认识 ${名}，因为你还没告诉它这个名字代表什么`,
            `两种可能：一是想把「${名}」当一段文字，给它加上双引号 （例如 设 名字 = "${名}"）；二是想用变量，但还没建立它 （先写 设 ${名} = …）`);
    }
    赋外层(名, 值, 行 = 0, 列 = 0) {
        let 环 = this.父;
        while (环 !== null) {
            if (环.表.has(名)) { 环.表.set(名, 值); return; }
            环 = 环.父;
        }
        throw new CNplus错误("CN0302", `变量 ${名} 还没有声明过`, 行, 列,
            `外层也没有 ${名} 这个变量，没法用「外部」改它`,
            `先用「设」建立它，例如：设 ${名} = 0`);
    }
}


// ==================== 运算（强制 CNplus 语义）====================

function 条件(值, 行, 列) {
    if (!是布尔(值)) {
        throw new CNplus错误("CN0301",
            `条件必须是布尔值（真 或 假），这里是${类型名(值)}`, 行, 列,
            "判断的位置只能放「成立/不成立」的问题，不能直接放一个数或一段文字",
            '写成一句能回答真/假的话，例如 x > 0、x != 0、名字 == "小明"');
    }
    return 值;
}


function 负(值, 行, 列) {
    值 = 拆小数(值);
    if (是布尔(值) || !是数(值)) {
        throw new CNplus错误("CN0303",
            `负号只能用于数字，这里是${类型名(值)}`, 行, 列,
            `${类型名(值)}没法取负数`);
    }
    return -值;
}


function 非(值, 行, 列) {
    if (!是布尔(值)) {
        throw new CNplus错误("CN0303",
            `「非」只能用于布尔值（真 或 假），这里是${类型名(值)}`, 行, 列,
            "「非」是把「成立」翻成「不成立」，所以它后面得跟一个真/假",
            "例如：非 (x > 0)");
    }
    return !值;
}


function 加(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    if (typeof 左 === "string" && typeof 右 === "string") return 左 + 右;
    if (!(是数(左) && 是数(右))) {
        throw new CNplus错误("CN0303",
            `「+」不能用于${类型名(左)}和${类型名(右)}`, 行, 列,
            "「+」要么把两个数字相加，要么把两段文字接起来，不能一边数字一边文字",
            `把数字转成文字再接起来：… + 文本(${显示(是数(左) ? 右 : 左)})`);
    }
    return 左 + 右;
}


function _两数(运, 左, 右, 行, 列) {
    if (!(是数(左) && 是数(右))) {
        throw new CNplus错误("CN0303",
            `「${运}」不能用于${类型名(左)}和${类型名(右)}`, 行, 列,
            `「${运}」两边都得是数字`,
            "检查两边的类型");
    }
    return [左, 右];
}


function 减(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    [左, 右] = _两数("-", 左, 右, 行, 列);
    return 左 - 右;
}


function 乘(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    if (typeof 左 === "string" && 是数(右)) return 左.repeat(Math.trunc(右));
    if (typeof 右 === "string" && 是数(左)) return 右.repeat(Math.trunc(左));
    [左, 右] = _两数("*", 左, 右, 行, 列);
    return 左 * 右;
}


function 除(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    [左, 右] = _两数("/", 左, 右, 行, 列);
    if (右 === 0) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列,
            "东西没法平均分给 0 个人，这在数学上没有答案",
            "把除数改成非零的数");
    }
    // 语义约定：/ 恒为小数。结果包 小数值 标记，显示层渲染 x.0。
    return 标记小数(左 / 右);
}


function 整除(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    [左, 右] = _两数("//", 左, 右, 行, 列);
    if (右 === 0) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    return Math.floor(左 / 右);
}


function 取余(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    [左, 右] = _两数("%", 左, 右, 行, 列);
    if (右 === 0) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    // JS 的 % 是向零截断后的余数；CNplus 的 // 是向下取整，
    // 所以余数也必须由 左 = 右 * (左 // 右) + 余 推导。
    return 左 - Math.floor(左 / 右) * 右;
}


function 幂(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    if (!(是数(左) && 是数(右))) {
        throw new CNplus错误("CN0303",
            `「**」不能用于${类型名(左)}和${类型名(右)}`, 行, 列,
            "幂运算两边都得是数字", "检查两边的类型");
    }
    const 结 = 左 ** 右;
    if (!Number.isFinite(结)) {
        throw new CNplus错误("CN0303", "幂运算出错：结果太大", 行, 列,
            "结果太大或没有意义");
    }
    return 结;
}


function _可比较(左, 右) {
    if (左 === null || 右 === null) return true;
    if (是布尔(左) || 是布尔(右)) return 是布尔(左) && 是布尔(右);
    if (是数(左) && 是数(右)) return true;
    if (typeof 左 === "string" && typeof 右 === "string") return true;
    if (Array.isArray(左) && Array.isArray(右)) return true;
    if (左 instanceof Map && 右 instanceof Map) return true;
    return false;
}


function 等于(左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    if (!_可比较(左, 右)) {
        throw new CNplus错误("CN0303",
            `不能比较${类型名(左)}和${类型名(右)}`, 行, 列,
            `${类型名(左)}和${类型名(右)}是两类不同的东西，比它们相不相等没有意义`,
            "先用「文本(…)」或「整数(…)」把它们转成同一类再比");
    }
    return _值相等(左, 右);
}


function _值相等(左, 右) {
    if (Array.isArray(左) && Array.isArray(右)) {
        if (左.length !== 右.length) return false;
        return 左.every((v, i) => _值相等(v, 右[i]));
    }
    if (左 instanceof Map && 右 instanceof Map) {
        if (左.size !== 右.size) return false;
        for (const [k, v] of 左) {
            if (!右.has(k) || !_值相等(v, 右.get(k))) return false;
        }
        return true;
    }
    return 左 === 右;
}


function 不等于(左, 右, 行, 列) {
    return !等于(左, 右, 行, 列);
}


function _比大小(运, 左, 右, 行, 列) {
    左 = 拆小数(左); 右 = 拆小数(右);
    if (typeof 左 === "string" && typeof 右 === "string") {
        // pass
    } else if (是数(左) && 是数(右)) {
        // pass
    } else {
        throw new CNplus错误("CN0303",
            `不能比较${类型名(左)}和${类型名(右)}的大小`, 行, 列,
            `${类型名(左)}和${类型名(右)}没法排先后`,
            "数字跟数字比，文字跟文字比");
    }
    return [左, 右];
}


function 小于(左, 右, 行, 列) {
    [左, 右] = _比大小("<", 左, 右, 行, 列);
    return 左 < 右;
}
function 小于等于(左, 右, 行, 列) {
    [左, 右] = _比大小("<=", 左, 右, 行, 列);
    return 左 <= 右;
}
function 大于(左, 右, 行, 列) {
    [左, 右] = _比大小(">", 左, 右, 行, 列);
    return 左 > 右;
}
function 大于等于(左, 右, 行, 列) {
    [左, 右] = _比大小(">=", 左, 右, 行, 列);
    return 左 >= 右;
}


function 与(左, 右, 行, 列) {
    if (!是布尔(左)) {
        throw new CNplus错误("CN0303",
            `「与」两侧必须是布尔值（真 或 假），这里是${类型名(左)}`, 行, 列,
            "「与」用来连接两个「成立/不成立」的判断",
            "例如：x > 0 与 y > 0");
    }
    if (!左) return false;  // 短路
    if (!是布尔(右)) {
        throw new CNplus错误("CN0303",
            `「与」两侧必须是布尔值（真 或 假），这里是${类型名(右)}`, 行, 列,
            "「与」用来连接两个「成立/不成立」的判断",
            "例如：x > 0 与 y > 0");
    }
    return 右;
}


function 或(左, 右, 行, 列) {
    if (!是布尔(左)) {
        throw new CNplus错误("CN0303",
            `「或」两侧必须是布尔值（真 或 假），这里是${类型名(左)}`, 行, 列,
            "「或」用来连接两个「成立/不成立」的判断",
            "例如：x > 0 或 y > 0");
    }
    if (左) return true;  // 短路
    if (!是布尔(右)) {
        throw new CNplus错误("CN0303",
            `「或」两侧必须是布尔值（真 或 假），这里是${类型名(右)}`, 行, 列,
            "「或」用来连接两个「成立/不成立」的判断",
            "例如：x > 0 或 y > 0");
    }
    return 右;
}


// ==================== 占位：函数值/类/调用（T5/T7 点亮）====================

class 函数值 {
    constructor(实现, 闭包, 形参们, 名 = "", 默认们 = null) {
        this.实现 = 实现;
        this.闭包 = 闭包;
        this.形参们 = 形参们;
        this.名 = 名;
        this.默认们 = 默认们 !== null ? 默认们
            : 形参们.map(() => 缺省);
    }
}


class 类值 {
    constructor(名, 方法表, 初始化形参 = []) {
        this.名 = 名;
        this.方法表 = 方法表;
        this.初始化形参 = 初始化形参;
    }
}


class 实例值 {
    constructor(类, 字段) {
        this.类 = 类;
        this.字段 = 字段;
    }
}


class 绑定方法 {
    constructor(函, 实例) {
        this.函 = 函;
        this.实例 = 实例;
    }
}


// ==================== 自增 / 解包 / 遍历 ====================

function 自增值(旧, 增量, 行, 列) {
    if (是布尔(旧) || !是数(旧)) {
        throw new CNplus错误("CN0303", `${类型名(旧)}不能自增/自减`, 行, 列,
            "++ 和 -- 只能用于数字", "确认这个变量是数字");
    }
    return 拆小数(旧) + 增量;
}


function 解包声明(环, 名们, 值, 行, 列) {
    if (!Array.isArray(值)) {
        throw new CNplus错误("CN0303",
            `右边是${类型名(值)}，没法拆给 ${名们.length} 个变量`, 行, 列,
            "要拆开赋值，右边得是一个列表（或多返回值）",
            "例如：设 甲, 乙 = [1, 2]");
    }
    if (值.length !== 名们.length) {
        throw new CNplus错误("CN0306",
            `左边有 ${名们.length} 个变量，右边有 ${值.length} 个值`, 行, 列,
            "拆开赋值时两边数量必须一样多",
            `左边写 ${值.length} 个变量，或让右边给 ${名们.length} 个值`);
    }
    名们.forEach((名, i) => 环.声明(名, 值[i], 行, 列));
}


function 遍历项(可迭代, 行, 列) {
    if (Array.isArray(可迭代)) return [...可迭代];
    if (typeof 可迭代 === "string") return [...可迭代];
    if (可迭代 instanceof Map) return [...可迭代.keys()];
    throw new CNplus错误("CN0309", `${类型名(可迭代)}不能遍历`, 行, 列,
        "「遍历…每个…」需要一串东西，比如列表、字典或文字",
        "用列表：遍历 [1, 2, 3] 每个 x");
}


// ==================== 集合：索引 / 切片 / 字典 ====================

function 取索引(对象, 下标, 行, 列) {
    下标 = 拆小数(下标);
    if (Array.isArray(对象) || typeof 对象 === "string") {
        if (!Number.isInteger(下标)) {
            throw new CNplus错误("CN0303",
                `下标必须是整数，这里是${类型名(下标)}`, 行, 列,
                "方括号里要写「第几个」，用整数（负数表示从尾数）");
        }
        const 项们 = typeof 对象 === "string" ? [...对象] : 对象;
        let i = 下标;
        if (i < 0) i += 项们.length;
        if (i < 0 || i >= 项们.length) {
            throw new CNplus错误("CN0308",
                `下标 ${显示(下标)} 超出范围（一共 ${项们.length} 个）`, 行, 列,
                "列表下标从 0 开始，最大是「长度 - 1」",
                "用「长度(…)」看有多少个");
        }
        return 项们[i];
    }
    if (对象 instanceof Map) {
        if (!对象.has(下标)) {
            throw new CNplus错误("CN0308", `字典里没有标签 ${显示(下标)}`, 行, 列,
                "这个标签不在字典里", "检查标签是不是写错了");
        }
        return 对象.get(下标);
    }
    throw new CNplus错误("CN0303", `${类型名(对象)}不能用下标取值`, 行, 列,
        "只有列表、字典和文字能用 […] 取里面的东西",
        "检查这个东西的类型");
}


function 设索引(对象, 下标, 值, 行, 列) {
    下标 = 拆小数(下标);
    if (Array.isArray(对象)) {
        if (!Number.isInteger(下标)) {
            throw new CNplus错误("CN0303",
                `下标必须是整数，这里是${类型名(下标)}`, 行, 列);
        }
        let i = 下标;
        if (i < 0) i += 对象.length;
        if (i < 0 || i >= 对象.length) {
            throw new CNplus错误("CN0308",
                `下标 ${显示(下标)} 超出范围`, 行, 列,
                "这个位置不存在，没法往那里放东西",
                "列表下标从 0 开始");
        }
        对象[i] = 值;
        return;
    }
    if (对象 instanceof Map) {
        对象.set(下标, 值);
        return;
    }
    throw new CNplus错误("CN0303", `${类型名(对象)}不能用下标赋值`, 行, 列,
        "只有列表和字典能这样改内容",
        "检查一下这个东西是不是列表或字典");
}


function 造字典(键值对, 行, 列) {
    const 出 = new Map();
    for (const [键, 值] of 键值对) {
        const k = 拆小数(键);
        if (!(typeof k === "string" || Number.isInteger(k)
              || typeof k === "boolean" || k === null)) {
            throw new CNplus错误("CN0303",
                `${类型名(键)}不能作字典的标签`, 行, 列,
                "字典的标签得是文字或数字这类固定不变的东西",
                '例如 {"名字": "小明"}');
        }
        出.set(k, 值);
    }
    return 出;
}


function 取切片(对象, 起, 止, 行, 列) {
    // 与树遍历/Python 后端逐字同语义（D-037）：夹紧/负数/空段
    if (!Array.isArray(对象) && typeof 对象 !== "string") {
        throw new CNplus错误("CN0303", `${类型名(对象)}不能用切片取值`, 行, 列,
            "只有列表和文字能用 [起:止] 截一段",
            "检查这个东西的类型");
    }
    const 项们 = typeof 对象 === "string" ? [...对象] : 对象;
    const 长 = 项们.length;
    const 端点 = (值, 缺省) => {
        if (值 === null || 值 === undefined) return 缺省;
        值 = 拆小数(值);
        if (typeof 值 !== "number" || !Number.isInteger(值)) {
            throw new CNplus错误("CN0303",
                `切片的起止必须是整数，这里是${类型名(值)}`, 行, 列,
                "[起:止] 两端要写「第几个」，用整数（负数表示从尾数）",
                "例如 名单[1:3] 或 名单[-2:]");
        }
        if (值 < 0) 值 += 长;
        if (值 < 0) 值 = 0;
        return 值;
    };
    let s = 端点(起, 0);
    let e = 端点(止, 长);
    if (s > 长) s = 长;
    if (e > 长) e = 长;
    if (s > e) s = e;
    const 片段 = 项们.slice(s, e);
    return typeof 对象 === "string" ? 片段.join("") : 片段;
}


// ==================== 成员 / 类实例（D-036）====================

function 取成员(对象, 属性, 行, 列) {
    if (对象 instanceof 实例值) {
        if (对象.字段.has(属性)) return 对象.字段.get(属性);
        const 函 = 对象.类.方法表.get(属性);
        if (函 !== undefined) return new 绑定方法(函, 对象);
        throw new CNplus错误("CN0302",
            `${对象.类.名} 里没有「${属性}」这个字段或方法`, 行, 列,
            `${对象.类.名} 的字段和方法里都找不到这个名字`,
            "检查名字是不是写错了，或去类定义里看看");
    }
    throw new CNplus错误("CN0302",
        `${属性} 在 ${类型名(对象)} 里不存在`, 行, 列,
        `这个东西没有叫「${属性}」的成员`,
        "检查成员名是不是写错了");
}


function 设成员(对象, 属性, 值, 行, 列) {
    if (对象 instanceof 实例值) {
        对象.字段.set(属性, 值);
        return;
    }
    throw new CNplus错误("CN0303",
        `${类型名(对象)} 没法用「.」设置成员`, 行, 列,
        "「对象.成员 = 值」目前只用于类实例的字段",
        "检查点号左边是不是一个实例");
}


function 实例化(类, 实参们, 关键字们, 行, 列) {
    const 实例 = new 实例值(类, new Map());
    const 初 = 类.方法表.get("__初始化__");
    if (初 === undefined) {
        if (实参们.length > 0 || 关键字们.length > 0) {
            throw new CNplus错误("CN0306",
                `${类.名} 没有写「初始化」，不需要参数，给了 ${实参们.length} 个`,
                行, 列,
                "类没定义初始化，造它的时候括号里不用填东西",
                `直接写 ${类.名}()`);
        }
        return 实例;
    }
    const 局部 = _绑定(初, 实参们, 关键字们, 行, 列);
    for (const p of 初.形参们) {
        实例.字段.set(p, 局部.表.has(p) ? 局部.表.get(p) : null);
    }
    局部.声明("自己", 实例);
    初.实现(局部);
    return 实例;
}


const _可点方法 = new Set([
    "追加", "插入", "移除", "弹出", "排序", "倒序", "包含", "连接", "长度",
    "所有标签", "所有值", "有标签", "删标签",
    "分割", "替换", "查找", "去空白", "大写", "小写", "开头是", "结尾是",
]);


function 点调用(全局, 对象, 方法名, 实参们, 关键字们, 行, 列) {
    if ((Array.isArray(对象) || 对象 instanceof Map || typeof 对象 === "string")
        && _可点方法.has(方法名)) {
        const 函数 = 内置们[方法名];
        if (函数 !== undefined) {
            return 函数(对象, ...实参们);
        }
    }
    const 成员 = 取成员(对象, 方法名, 行, 列);
    return 调用(成员, 实参们, 关键字们, 行, 列);
}


// ==================== 调用 ====================

function 调用(被调, 实参们, 关键字们, 行, 列) {
    if (被调 instanceof 类值) {
        return 实例化(被调, 实参们, 关键字们, 行, 列);
    }
    if (被调 instanceof 绑定方法) {
        const 局部 = _绑定(被调.函, 实参们, 关键字们, 行, 列);
        局部.声明("自己", 被调.实例);
        return 被调.函.实现(局部);
    }
    if (被调 instanceof 函数值) {
        const 局部 = _绑定(被调, 实参们, 关键字们, 行, 列);
        return 被调.实现(局部);
    }
    if (typeof 被调 === "function") {
        return 被调(...实参们);
    }
    throw new CNplus错误("CN0305", `${类型名(被调)}不能被调用`, 行, 列,
        "名字后面加括号表示「执行它」，但只有函数能被执行",
        "检查是不是名字写错了，或者本来不该加括号");
}


function _绑定(被调, 实参们, 关键字们, 行, 列) {
    const 形参 = 被调.形参们;
    const 默认 = 被调.默认们;
    if (实参们.length > 形参.length) {
        throw new CNplus错误("CN0306",
            `${被调.名} 最多 ${形参.length} 个参数，给了 ${实参们.length} 个`,
            行, 列,
            `你定义 ${被调.名} 时写了 ${形参.length} 个位置`,
            `参数有：${形参.join("、") || "无"}`);
    }
    const 已填 = new Map();
    形参.forEach((名, i) => { if (i < 实参们.length) 已填.set(名, 实参们[i]); });
    for (const [名, 值] of 关键字们) {
        if (!形参.includes(名)) {
            throw new CNplus错误("CN0306",
                `${被调.名} 没有叫「${名}」的参数`, 行, 列,
                `${被调.名} 的参数是：${形参.join("、") || "无"}`,
                "检查参数名是不是写错了");
        }
        if (已填.has(名)) {
            throw new CNplus错误("CN0306", `参数「${名}」给了两次`, 行, 列,
                "一个参数只能赋值一次", "删掉重复的那个");
        }
        已填.set(名, 值);
    }
    const 局部 = new 环境(被调.闭包);
    形参.forEach((名, i) => {
        if (已填.has(名)) {
            局部.表.set(名, 已填.get(名));
        } else if (默认[i] !== 缺省) {
            局部.表.set(名, 默认[i]);
        } else {
            throw new CNplus错误("CN0306", `${被调.名} 缺少参数「${名}」`,
                行, 列,
                `「${名}」没有默认值，调用时必须给它`,
                `补上：${被调.名}(…)`);
        }
    });
    return 局部;
}


// ==================== 内置函数 ====================

function _内置_打印(...值们) {
    console.log(值们.map(v => 显示(v)).join(" "));
}


function _转整数(a) {
    a = 拆小数(a);
    if (typeof a === "number" && Number.isInteger(a)) return a;
    if (typeof a === "string" || typeof a === "number") {
        const n = Number.parseInt(a, 10);
        if (!Number.isNaN(n) && String(n) === String(a).trim()) {
            校验整数(n, 0, 0);
            return n;
        }
    }
    throw new CNplus错误("CN0303", `没法把 ${显示(a)} 变成整数`, 0, 0);
}


function _转小数(a) {
    a = 拆小数(a);
    if (typeof a === "number") return 标记小数(a);
    if (typeof a === "string") {
        const n = Number(a.trim());
        if (!Number.isNaN(n)) return 标记小数(n);
    }
    throw new CNplus错误("CN0303", `没法把 ${显示(a)} 变成小数`, 0, 0);
}


function _范围(...参数) {
    const 们 = 参数.map(x => Math.trunc(拆小数(x)));
    if (们.length === 1) {
        const 出 = [];
        for (let i = 0; i < 们[0]; i++) 出.push(i);
        return 出;
    }
    if (们.length === 2) {
        const 出 = [];
        for (let i = 们[0]; i < 们[1]; i++) 出.push(i);
        return 出;
    }
    const 出 = [];
    for (let i = 们[0]; i < 们[1]; i += 们[2]) 出.push(i);
    return 出;
}


function _求和(序列) {
    if (!序列.every(x => 是数(x)))
        throw new CNplus错误("CN0303", "求和只能用于全是数字的列表", 0, 0);
    return 序列.reduce((a, b) => a + b, 0);
}


function _询问(提示) {
    // Node 有 stdin；浏览器侧由宿主替换此实现
    if (typeof 提示 !== "undefined" && 提示 !== null && 提示 !== undefined) {
        process.stdout.write(显示(提示));
    }
    const 行 = _读一行();
    return 行 === null ? "" : 行;
}


function _读一行() {
    // 同步读 stdin 一行；EOF 返回 null（不能返回空串——询问数值会死循环）
    try {
        let 块 = "";
        const 缓冲 = Buffer.alloc(1);
        while (true) {
            const n = require("fs").readSync(0, 缓冲, 0, 1);
            if (n === 0) return 块 === "" ? null : 块;
            const 字 = 缓冲.toString("utf8");
            if (字 === "\n") return 块;
            块 += 字;
        }
    } catch (e) {
        return null;
    }
}


function _询问数值(提示) {
    while (true) {
        if (提示 !== null && 提示 !== undefined) {
            process.stdout.write(显示(提示));
        }
        const 行 = _读一行();
        if (行 === null) {
            throw new CNplus错误("CN0310", "还需要一个数字，但输入已经结束了", 0, 0,
                "程序还想要输入，可是没有更多输入了",
                "交互运行时直接输入；用管道喂数据时检查是不是给少了");
        }
        const 试 = 行.trim();
        const n = Number(试);
        if (!Number.isNaN(n) && 试 !== "") {
            return 试.includes(".") ? 标记小数(n) : 校验整数(n, 0, 0);
        }
        console.log(`「${试}」不是数字，请重新输入。`);
    }
}


const 内置们 = {
    "打印": _内置_打印,
    "询问": _询问,
    "询问数值": _询问数值,
    "类型": 类型名,
    "文本": 显示,
    "整数": _转整数,
    "小数": _转小数,
    "长度": (x) => x instanceof Map ? x.size :
        typeof x === "string" ? [...x].length : x.length,
    "范围": _范围,
    "随机数": (a, b) => 校验整数(Math.floor(
        Math.random() * (Math.trunc(拆小数(b)) - Math.trunc(拆小数(a)) + 1))
        + Math.trunc(拆小数(a)), 0, 0),
    "绝对值": (a) => Math.abs(拆小数(a)),
    "最大": (...a) => a.length === 1 ? Math.max(...a[0]) : Math.max(...a),
    "最小": (...a) => a.length === 1 ? Math.min(...a[0]) : Math.min(...a),
    "求和": _求和,
    "四舍五入": (a) => Math.round(拆小数(a)),
    "平方根": (a) => 标记小数(Math.sqrt(拆小数(a))),
    "追加": (表, 项) => { 表.push(项); },
    "插入": (表, 位, 项) => 表.splice(Math.trunc(拆小数(位)), 0, 项),
    "移除": (表, 项) => {
        const i = 表.indexOf(项);
        if (i === -1) throw new CNplus错误("CN0303",
            `列表里没有 ${显示(项)}`, 0, 0, "检查要移除的东西在不在列表里");
        表.splice(i, 1);
    },
    "弹出": (表, ...a) => a.length ? 表.splice(Math.trunc(拆小数(a[0])), 1)[0] : 表.pop(),
    "排序": (表) => [...表].sort((a, b) => _排序比较(a, b)),
    "倒序": (表) => [...表].reverse(),
    "包含": (容器, 项) => 容器 instanceof Map ? [...容器.keys()].includes(项) : 容器.includes(项),
    "连接": (表, 隔) => 表.map(x => 显示(x)).join(隔),
    "所有标签": (字) => [...字.keys()],
    "所有值": (字) => [...字.values()],
    "有标签": (字, 标签) => 字.has(标签),
    "删标签": (字, 标签) => 字.delete(标签),
    "分割": (文, 分隔符) => 分隔符 !== undefined && 分隔符 !== null
        ? 文.split(分隔符) : 文.trim().split(/\s+/),
    "替换": (文, 旧, 新) => 文.split(旧).join(新),
    "查找": (文, 子) => 文.indexOf(子),
    "去空白": (文) => 文.trim(),
    "大写": (文) => 文.toUpperCase(),
    "小写": (文) => 文.toLowerCase(),
    "开头是": (文, 前) => 文.startsWith(前),
    "结尾是": (文, 后) => 文.endsWith(后),
};


function _排序比较(a, b) {
    a = 拆小数(a); b = 拆小数(b);
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0;
}


function 建全局环境() {
    // 内置放父环境，用户顶层是子环境 —— 遮蔽内置名与
    // Python 后端/checker 一致（D-033）
    const 内置环 = new 环境(null);
    for (const [名, 值] of Object.entries(内置们)) {
        内置环.表.set(名, 值);
    }
    return new 环境(内置环);
}


function 加连接(片段们) {
    // 格式串 @“…{表达式}…” 的拼接：全部先 显示() 成文字再接
    return 片段们.join("");
}


function 抛出(说明, 行, 列) {
    throw new CNplus错误("CN0311", 显示(说明), 行, 列,
        "这是程序自己用「抛出」制造的错误",
        "用「尝试 … 捕获」可以接住它");
}


function 不支持导入(模块名, 行, 列) {
    throw new CNplus错误("CN0303",
        `JS 运行环境暂不支持「导入」（${模块名}）`, 行, 列,
        "JS 后端 v1 只覆盖纯 CNplus 程序，导入 Python 库请用默认后端",
        "把 导入 的部分拆出去，或用 cnp 运行（树遍历）/--python 跑");
}


// ==================== 错误出口 ====================
// 顶层未捕获的 CNplus错误：输出标记行（后端.py 靠它映射回 .cnp）
// 再以非零码退出。放在最后，覆盖全局。

process.on("uncaughtException", (e) => {
    if (e instanceof CNplus错误) {
        console.error("__CNPLUS__" + JSON.stringify({
            码: e.码, 消息: e.消息, 行: e.行, 列: e.列,
            提示: e.提示, 解释: e.解释,
        }));
        process.exit(1);
    }
    console.error("__CNPLUS__" + JSON.stringify({
        码: "CN9001", 消息: String(e), 行: 0, 列: 0,
    }));
    process.exit(1);
});
