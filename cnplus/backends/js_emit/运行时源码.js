// CNplus 运行时 —— JS 转译后端的语义引擎（T2 核心）。
//
// 生成的 JS 代码每一步运算、每次作用域操作都调回这里，
// 保证 CNplus 语义不泄漏（严格真值、跨类型比较报错、
// / 恒为小数、块级作用域）。
//
// 这个模块是自包含的：不 import 任何东西，直接内联进生成的
// .js 文件，可在支持 BigInt 的 node 与现代浏览器中独立运行。
//
// 数字语义防御（与 Python 后端的关键差异点）：
// - CNplus 整数统一使用 BigInt，保持任意精度
// - CNplus 小数使用 Number + 小数值标记，保留 2.0 的类型信息
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

class 小数值 {
    // JS 的 Number 层面 2 与 2.0 是同一个值，「这是小数」的信息
    // 在 JS 里原则上不存在。CNplus 语义要求 整数2 ≠ 小数2.0，
    // 发射器对小数字面量包 标记小数(2.0)，显示/类型名逐层识别。
    constructor(值) {
        this.值 = 值;
    }
}


function 标记小数(v) {
    if (v instanceof 小数值) return v;
    if (typeof v === "bigint") v = Number(v);
    if (typeof v !== "number" || !Number.isFinite(v)) {
        throw new CNplus错误("CN0303", "小数超出了能表示的范围", 0, 0,
            "小数采用 IEEE 754 双精度，过大的整数不能转换成有限小数");
    }
    return new 小数值(v);
}


function 拆小数(v) {
    return v instanceof 小数值 ? v.值 : v;
}


function 是布尔(v) { return typeof v === "boolean"; }
function 是数(v) {
    v = 拆小数(v);
    return typeof v === "bigint" || typeof v === "number" && Number.isFinite(v);
}
function 是整数(v) {
    return typeof v === "bigint";
}


function 校验整数(v, 行, 列) {
    if (typeof v === "bigint") return v;
    if (typeof v === "number" && Number.isSafeInteger(v)) return BigInt(v);
    throw new CNplus错误("CN0303", "这里需要一个整数", 行, 列,
        "整数不能带小数部分，也不能来自已经失真的 JS Number",
        "使用整数写法，或先用「整数(…)」转换");
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
    if (typeof 值 === "function") return "函数";
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
    if (typeof 值 === "bigint") return String(值);
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
    if (是布尔(值) || !是数(值)) {
        throw new CNplus错误("CN0303",
            `负号只能用于数字，这里是${类型名(值)}`, 行, 列,
            `${类型名(值)}没法取负数`);
    }
    if (值 instanceof 小数值 || typeof 值 === "number") {
        return 标记小数(-Number(拆小数(值)));
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
    if (typeof 左 === "string" && typeof 右 === "string") return 左 + 右;
    [左, 右] = _两数("+", 左, 右, 行, 列);
    if (_有小数(左, 右)) return 标记小数(_到Number(左) + _到Number(右));
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


function _有小数(...值们) {
    return 值们.some(v => v instanceof 小数值 || typeof v === "number");
}


function _到Number(v) {
    return Number(拆小数(v));
}


function _整数向下商(左, 右) {
    let 商 = 左 / 右;
    const 余 = 左 % 右;
    if (余 !== 0n && (左 < 0n) !== (右 < 0n)) 商 -= 1n;
    return 商;
}


function _向偶数舍入商(分子, 分母) {
    let 商 = 分子 / 分母;
    const 余数 = 分子 % 分母;
    const 两倍余数 = 余数 * 2n;
    if (两倍余数 > 分母 || (两倍余数 === 分母 && 商 % 2n !== 0n)) 商 += 1n;
    return 商;
}


function _BigInt真除(左, 右) {
    const 负数 = (左 < 0n) !== (右 < 0n);
    let 分子 = 左 < 0n ? -左 : 左;
    const 分母 = 右 < 0n ? -右 : 右;
    if (分子 === 0n) return 0;

    const 分子位数 = 分子.toString(2).length;
    const 分母位数 = 分母.toString(2).length;
    const 位差 = 分子位数 - 分母位数;
    let 指数 = 位差;
    if (位差 >= 0) {
        if (分子 < (分母 << BigInt(位差))) 指数 -= 1;
    } else if ((分子 << BigInt(-位差)) < 分母) {
        指数 -= 1;
    }

    let 尾数;
    let 二次方;
    if (指数 < -1022) {
        尾数 = _向偶数舍入商(分子 << 1074n, 分母);
        二次方 = -1074;
    } else {
        const 位移 = 52 - 指数;
        尾数 = 位移 >= 0
            ? _向偶数舍入商(分子 << BigInt(位移), 分母)
            : _向偶数舍入商(分子, 分母 << BigInt(-位移));
        if (尾数 === 2n ** 53n) {
            尾数 >>= 1n;
            指数 += 1;
        }
        if (指数 > 1023) return 负数 ? -Infinity : Infinity;
        二次方 = 指数 - 52;
    }
    const 结果 = Number(尾数) * 2 ** 二次方;
    return 负数 ? -结果 : 结果;
}


function 减(左, 右, 行, 列) {
    [左, 右] = _两数("-", 左, 右, 行, 列);
    if (_有小数(左, 右)) return 标记小数(_到Number(左) - _到Number(右));
    return 左 - 右;
}


function 乘(左, 右, 行, 列) {
    if (typeof 左 === "string" && 是数(右)) return 左.repeat(Math.trunc(_到Number(右)));
    if (typeof 右 === "string" && 是数(左)) return 右.repeat(Math.trunc(_到Number(左)));
    [左, 右] = _两数("*", 左, 右, 行, 列);
    if (_有小数(左, 右)) return 标记小数(_到Number(左) * _到Number(右));
    return 左 * 右;
}


function 除(左, 右, 行, 列) {
    [左, 右] = _两数("/", 左, 右, 行, 列);
    if (拆小数(右) === 0 || 拆小数(右) === 0n) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列,
            "东西没法平均分给 0 个人，这在数学上没有答案",
            "把除数改成非零的数");
    }
    // 语义约定：/ 恒为小数。结果包 小数值 标记，显示层渲染 x.0。
    const 商 = typeof 左 === "bigint" && typeof 右 === "bigint"
        ? _BigInt真除(左, 右)
        : _到Number(左) / _到Number(右);
    return 标记小数(商);
}


function 整除(左, 右, 行, 列) {
    [左, 右] = _两数("//", 左, 右, 行, 列);
    if (拆小数(右) === 0 || 拆小数(右) === 0n) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    if (_有小数(左, 右)) {
        return 标记小数(Math.floor(_到Number(左) / _到Number(右)));
    }
    return _整数向下商(左, 右);
}


function 取余(左, 右, 行, 列) {
    [左, 右] = _两数("%", 左, 右, 行, 列);
    if (拆小数(右) === 0 || 拆小数(右) === 0n) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    // JS 的 BigInt % 是向零截断后的余数；CNplus 的 // 是向下取整，
    // 所以余数也必须由 左 = 右 * (左 // 右) + 余 推导。
    if (_有小数(左, 右)) {
        const 左数 = _到Number(左); const 右数 = _到Number(右);
        return 标记小数(左数 - Math.floor(左数 / 右数) * 右数);
    }
    return 左 - _整数向下商(左, 右) * 右;
}


function 幂(左, 右, 行, 列) {
    if (!(是数(左) && 是数(右))) {
        throw new CNplus错误("CN0303",
            `「**」不能用于${类型名(左)}和${类型名(右)}`, 行, 列,
            "幂运算两边都得是数字", "检查两边的类型");
    }
    if (!_有小数(左, 右) && 右 >= 0n) return 左 ** 右;
    const 结 = _到Number(左) ** _到Number(右);
    if (!Number.isFinite(结)) {
        throw new CNplus错误("CN0303", "幂运算出错：结果太大", 行, 列,
            "结果太大或没有意义");
    }
    return 标记小数(结);
}


function _可比较(左, 右) {
    if (左 === null || 右 === null) return true;
    if (是布尔(左) || 是布尔(右)) return 是布尔(左) && 是布尔(右);
    if (是数(左) && 是数(右)) return true;
    if (typeof 左 === "string" && typeof 右 === "string") return true;
    if (Array.isArray(左) && Array.isArray(右)) return true;
    if (左 instanceof Map && 右 instanceof Map) return true;
    if (左 instanceof 实例值 && 右 instanceof 实例值) return true;
    return false;
}


function 等于(左, 右, 行, 列) {
    return _值相等(左, 右, 行, 列);
}


function _值相等(左, 右, 行, 列, 已见 = new WeakMap()) {
    if (!_可比较(左, 右)) {
        throw new CNplus错误("CN0303",
            `不能比较${类型名(左)}和${类型名(右)}`, 行, 列,
            `${类型名(左)}和${类型名(右)}是两类不同的东西，比它们相不相等没有意义`,
            "先用「文本(…)」或「整数(…)」把它们转成同一类再比");
    }
    if (左 === null || 右 === null) return 左 === 右;
    if (是数(左) && 是数(右)) {
        左 = 拆小数(左); 右 = 拆小数(右);
        if (typeof 左 === "bigint" && typeof 右 === "number") {
            return Number.isInteger(右) && 左 === BigInt(右);
        }
        if (typeof 左 === "number" && typeof 右 === "bigint") {
            return Number.isInteger(左) && BigInt(左) === 右;
        }
        return 左 === 右;
    }
    if (Array.isArray(左) && Array.isArray(右)) {
        if (左 === 右) return true;
        let 右们 = 已见.get(左);
        if (右们?.has(右)) return true;
        if (右们 === undefined) {
            右们 = new WeakSet();
            已见.set(左, 右们);
        }
        右们.add(右);
        let 相等 = 左.length === 右.length;
        for (let i = 0; i < Math.min(左.length, 右.length); i++) {
            if (!_值相等(左[i], 右[i], 行, 列, 已见)) 相等 = false;
        }
        return 相等;
    }
    if (左 instanceof Map && 右 instanceof Map) {
        if (左 === 右) return true;
        let 右们 = 已见.get(左);
        if (右们?.has(右)) return true;
        if (右们 === undefined) {
            右们 = new WeakSet();
            已见.set(左, 右们);
        }
        右们.add(右);
        let 相等 = 左.size === 右.size;
        for (const [k, v] of 左) {
            if (!右.has(k)) {
                相等 = false;
            } else if (!_值相等(v, 右.get(k), 行, 列, 已见)) {
                相等 = false;
            }
        }
        return 相等;
    }
    if (左 instanceof 实例值) return 左 === 右;
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
    if (旧 instanceof 小数值 || typeof 旧 === "number") {
        return 标记小数(_到Number(旧) + 增量);
    }
    return 旧 + BigInt(增量);
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

function _字典标签(标签, 行 = 0, 列 = 0) {
    const 值 = 拆小数(标签);
    if (typeof 值 === "number" && Number.isInteger(值)) return BigInt(值);
    if (typeof 值 === "string" || typeof 值 === "bigint"
        || typeof 值 === "boolean" || 值 === null) return 值;
    throw new CNplus错误("CN0303",
        `${类型名(标签)}不能作字典的标签`, 行, 列,
        "字典的标签得是文字、整数、布尔或空这类固定不变的东西",
        '例如 {"名字": "小明"}');
}


function _序列下标(下标, 长, 行, 列, 是赋值 = false) {
    if (下标 instanceof 小数值) {
        throw new CNplus错误("CN0303",
            `下标必须是整数，这里是${类型名(下标)}`, 行, 列,
            "方括号里要写「第几个」，用整数（负数表示从尾数）");
    }
    下标 = 拆小数(下标);
    let 位置;
    if (typeof 下标 === "bigint") {
        位置 = 下标;
    } else if (typeof 下标 === "number" && Number.isInteger(下标)) {
        位置 = BigInt(下标);
    } else {
        throw new CNplus错误("CN0303",
            `下标必须是整数，这里是${类型名(下标)}`, 行, 列,
            "方括号里要写「第几个」，用整数（负数表示从尾数）");
    }
    const 长整数 = BigInt(长);
    if (位置 < 0n) 位置 += 长整数;
    if (位置 < 0n || 位置 >= 长整数) {
        throw new CNplus错误("CN0308",
            是赋值 ? `下标 ${显示(下标)} 超出范围` :
                `下标 ${显示(下标)} 超出范围（一共 ${长} 个）`, 行, 列,
            是赋值 ? "这个位置不存在，没法往那里放东西" :
                "列表下标从 0 开始，最大是「长度 - 1」",
            是赋值 ? "列表下标从 0 开始" : "用「长度(…)」看有多少个");
    }
    return Number(位置);
}


function 取索引(对象, 下标, 行, 列) {
    if (Array.isArray(对象) || typeof 对象 === "string") {
        const 项们 = typeof 对象 === "string" ? [...对象] : 对象;
        const i = _序列下标(下标, 项们.length, 行, 列);
        return 项们[i];
    }
    if (对象 instanceof Map) {
        const 标签 = _字典标签(下标, 行, 列);
        if (!对象.has(标签)) {
            throw new CNplus错误("CN0308", `字典里没有标签 ${显示(下标)}`, 行, 列,
                "这个标签不在字典里", "检查标签是不是写错了");
        }
        return 对象.get(标签);
    }
    throw new CNplus错误("CN0303", `${类型名(对象)}不能用下标取值`, 行, 列,
        "只有列表、字典和文字能用 […] 取里面的东西",
        "检查这个东西的类型");
}


function 设索引(对象, 下标, 值, 行, 列) {
    if (Array.isArray(对象)) {
        const i = _序列下标(下标, 对象.length, 行, 列, true);
        对象[i] = 值;
        return;
    }
    if (对象 instanceof Map) {
        对象.set(_字典标签(下标, 行, 列), 值);
        return;
    }
    throw new CNplus错误("CN0303", `${类型名(对象)}不能用下标赋值`, 行, 列,
        "只有列表和字典能这样改内容",
        "检查一下这个东西是不是列表或字典");
}


function 复合设索引(对象, 下标, 求右侧, 运算, 行, 列) {
    // 对象、下标已按左到右求值；先读旧值，再执行右侧，最后写回。
    const 旧 = 取索引(对象, 下标, 行, 列);
    const 右 = 求右侧();
    设索引(对象, 下标, 运算(旧, 右, 行, 列), 行, 列);
}


function 造字典(键值对, 行, 列) {
    const 出 = new Map();
    for (const [键, 值] of 键值对) {
        const k = _字典标签(键, 行, 列);
        出.set(k, 值);
    }
    return 出;
}


function 取切片(对象, 起, 止, 步长, 行, 列, 起位置, 止位置, 步长位置) {
    // CNplus 三段式合同（D-037 / Issue #22）：正负步长、省略边界、夹紧、空段。
    if (!Array.isArray(对象) && typeof 对象 !== "string") {
        throw new CNplus错误("CN0303", `${类型名(对象)}不能用切片取值`, 行, 列,
            "只有列表和文字能用 [起:止:步长] 截一段",
            "检查这个东西的类型");
    }
    const 项们 = typeof 对象 === "string" ? [...对象] : 对象;
    const 长 = BigInt(项们.length);
    const 切片整数 = (值, 名称, 位置) => {
        if (值 === null || 值 === undefined) return null;
        const [错行, 错列] = 位置 ?? [行, 列];
        if (值 instanceof 小数值) {
            throw new CNplus错误("CN0303",
                `切片的${名称}必须是整数，这里是小数`, 错行, 错列,
                "[起:止:步长] 三段都要用整数；负步长表示从后向前取",
                "例如 名单[1:5:2] 或 名单[::-1]");
        }
        值 = 拆小数(值);
        if (typeof 值 === "bigint") return 值;
        if (typeof 值 === "number" && Number.isInteger(值)) return BigInt(值);
        throw new CNplus错误("CN0303",
            `切片的${名称}必须是整数，这里是${类型名(值)}`, 错行, 错列,
            "[起:止:步长] 三段都要用整数；负步长表示从后向前取",
            "例如 名单[1:5:2] 或 名单[::-1]");
    };
    const d = 切片整数(步长, "步长", 步长位置) ?? 1n;
    if (d === 0n) {
        const [错行, 错列] = 步长位置 ?? [行, 列];
        throw new CNplus错误("CN0303", "切片的步长不能是 0", 错行, 错列,
            "步长表示每次向前或向后移动几个位置，写 0 会一直停在原地",
            "改成 1、2 或 -1 这类非零整数");
    }
    const 正向 = d > 0n;
    const 归一端点 = (原值, 是起点) => {
        if (原值 === null) {
            if (正向) return 是起点 ? 0n : 长;
            return 是起点 ? 长 - 1n : -1n;
        }
        let 值 = 原值;
        if (值 < 0n) 值 += 长;
        if (正向) {
            if (值 < 0n) return 0n;
            if (值 > 长) return 长;
            return 值;
        }
        if (值 < 0n) return -1n;
        if (值 >= 长) return 长 - 1n;
        return 值;
    };
    const s = 归一端点(切片整数(起, "起点", 起位置), true);
    const e = 归一端点(切片整数(止, "终点", 止位置), false);
    const 片段 = [];
    for (let i = s; 正向 ? i < e : i > e; i += d) {
        片段.push(项们[Number(i)]);
    }
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


function 复合设成员(对象, 属性, 求右侧, 运算, 行, 列) {
    // 对象已求值一次；先读旧成员，再执行右侧，最后写回。
    const 旧 = 取成员(对象, 属性, 行, 列);
    const 右 = 求右侧();
    设成员(对象, 属性, 运算(旧, 右, 行, 列), 行, 列);
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
            if (typeof 函数._按位置调用 === "function") {
                return 函数._按位置调用([对象, ...实参们], 行, 列);
            }
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
        if (typeof 被调._按位置调用 === "function") {
            return 被调._按位置调用(实参们, 行, 列);
        }
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
    if (typeof a === "bigint") return a;
    if (typeof a === "number" && Number.isFinite(a)) return BigInt(Math.trunc(a));
    if (typeof a === "string" && /^[+-]?\d+$/.test(a.trim())) {
        return BigInt(a.trim());
    }
    throw new CNplus错误("CN0303", `没法把 ${显示(a)} 变成整数`, 0, 0);
}


function _转小数(a) {
    a = 拆小数(a);
    if (typeof a === "bigint" || typeof a === "number") return 标记小数(Number(a));
    if (typeof a === "string") {
        const n = Number(a.trim());
        if (!Number.isNaN(n)) return 标记小数(n);
    }
    throw new CNplus错误("CN0303", `没法把 ${显示(a)} 变成小数`, 0, 0);
}


function _范围(...参数) {
    const 们 = 参数.map(x => {
        const v = 拆小数(x);
        if (typeof v === "bigint") return v;
        throw new CNplus错误("CN0303", "范围的参数必须是整数", 0, 0);
    });
    if (们.length === 1) {
        const 出 = [];
        for (let i = 0n; i < 们[0]; i++) 出.push(i);
        return 出;
    }
    if (们.length === 2) {
        const 出 = [];
        for (let i = 们[0]; i < 们[1]; i++) 出.push(i);
        return 出;
    }
    const 出 = [];
    if (们[2] === 0n) {
        throw new CNplus错误("CN0303", "范围的步长不能是零", 0, 0);
    }
    if (们[2] > 0n) {
        for (let i = 们[0]; i < 们[1]; i += 们[2]) 出.push(i);
    } else {
        for (let i = 们[0]; i > 们[1]; i += 们[2]) 出.push(i);
    }
    return 出;
}


function _求和(序列) {
    if (!序列.every(x => 是数(x)))
        throw new CNplus错误("CN0303", "求和只能用于全是数字的列表", 0, 0);
    return 序列.reduce((a, b) => 加(a, b, 0, 0), 0n);
}


function _询问(提示) {
    const 提示文 = 提示 === null || typeof 提示 === "undefined" ? "" : 显示(提示);
    const 行 = _读一行(提示文);
    return 行 === null ? "" : 行;
}


function _读一行(提示文 = "") {
    const 是Node = typeof process !== "undefined" && process !== null
        && typeof process.stdout !== "undefined"
        && typeof Buffer !== "undefined" && typeof require === "function";
    if (!是Node) {
        return typeof globalThis.prompt === "function" ? globalThis.prompt(提示文) : null;
    }
    if (提示文 !== "") process.stdout.write(提示文);
    // 同步读 stdin 一行；EOF 返回 null（不能返回空串——询问数值会死循环）
    try {
        const 字节们 = [];
        const 缓冲 = Buffer.alloc(1);
        while (true) {
            const n = require("fs").readSync(0, 缓冲, 0, 1);
            if (n === 0 && 字节们.length === 0) return null;
            if (n === 0 || 缓冲[0] === 0x0A) {
                if (字节们[字节们.length - 1] === 0x0D) 字节们.pop();
                return Buffer.from(字节们).toString("utf8");
            }
            字节们.push(缓冲[0]);
        }
    } catch (e) {
        return null;
    }
}


function _询问数值(提示) {
    while (true) {
        const 提示文 = 提示 === null || typeof 提示 === "undefined" ? "" : 显示(提示);
        const 行 = _读一行(提示文);
        if (行 === null) {
            throw new CNplus错误("CN0310", "还需要一个数字，但输入已经结束了", 0, 0,
                "程序还想要输入，可是没有更多输入了",
                "交互运行时直接输入；用管道喂数据时检查是不是给少了");
        }
        const 试 = 行.trim();
        const n = Number(试);
        if (!Number.isNaN(n) && 试 !== "") {
            if (/[.eE]/.test(试)) return 标记小数(n);
            if (/^[+-]?\d+$/.test(试)) return BigInt(试);
        }
        console.log(`「${试}」不是数字，请重新输入。`);
    }
}


function _位置数(v) {
    const 位置 = Math.trunc(_到Number(v));
    if (!Number.isSafeInteger(位置)) {
        throw new CNplus错误("CN0303", "列表位置超出了能处理的范围", 0, 0);
    }
    return 位置;
}


function _绝对值(v) {
    if (!是数(v)) throw new CNplus错误("CN0303", "绝对值只能用于数字", 0, 0);
    if (v instanceof 小数值 || typeof v === "number") {
        return 标记小数(Math.abs(_到Number(v)));
    }
    return v < 0n ? -v : v;
}


function _四舍五入(值, 位数 = undefined) {
    if (!是数(值)) throw new CNplus错误("CN0303", "四舍五入只能用于数字", 0, 0);
    const 指定位数 = typeof 位数 !== "undefined";
    let 位 = 0n;
    if (指定位数) {
        const 原位 = 拆小数(位数);
        if (typeof 原位 !== "bigint")
            throw new CNplus错误("CN0303", "四舍五入的小数位数必须是整数", 0, 0);
        位 = 原位;
    }
    const 原值 = 拆小数(值);
    if (typeof 原值 === "bigint") {
        if (!指定位数 || 位 >= 0n) return 原值;
        const 位数值 = -位;
        const 绝对值 = 原值 < 0n ? -原值 : 原值;
        if (位数值 > BigInt(绝对值.toString().length)) return 0n;
        const 倍 = 10n ** 位数值;
        let 商 = 绝对值 / 倍;
        if ((绝对值 % 倍) * 2n >= 倍) 商 += 1n;
        return (原值 < 0n ? -商 : 商) * 倍;
    }
    const 负 = 原值 < 0;
    const 绝对值 = Math.abs(原值);
    let 舍后;
    if (位 > 308n) 舍后 = 绝对值;
    else if (位 < -324n) 舍后 = 0;
    else {
        const 位数字 = Number(位);
        const [系数, 指数文 = "0"] = 绝对值.toString().split("e");
        const 移位 = Number(`${系数}e${Number(指数文) + 位数字}`);
        舍后 = Number.isFinite(移位)
            ? Number(`${Math.floor(移位 + 0.5)}e${-位数字}`)
            : 绝对值;
    }
    const 结果 = 负 ? -舍后 : 舍后;
    return 指定位数 ? 标记小数(结果) : BigInt(Math.trunc(结果));
}


function _平方根(值) {
    if (!是数(值)) throw new CNplus错误("CN0303", "平方根只能用于数字", 0, 0);
    const 数 = _到Number(值);
    if (数 < 0) throw new CNplus错误("CN0303", "负数没有实数平方根", 0, 0);
    return 标记小数(Math.sqrt(数));
}


function _分割(文, 分隔符 = undefined) {
    if (typeof 分隔符 === "undefined" || 分隔符 === null) {
        const 去空 = 文.trim();
        return 去空 === "" ? [] : 去空.split(/\s+/u);
    }
    return 分隔符 === "" ? [...文] : 文.split(分隔符);
}


function _替换(文, 旧, 新) {
    if (旧 === "") return 文 === "" ? 新 : 新 + [...文].join(新) + 新;
    return 文.split(旧).join(新);
}


function _查找(文, 子) {
    const utf16位置 = 文.indexOf(子);
    if (utf16位置 < 0) return -1n;
    return BigInt([...文.slice(0, utf16位置)].length);
}


function _极值(取最大, ...参数) {
    const 单个 = 参数.length === 1 ? 参数[0] : null;
    const 值们 = Array.isArray(单个) ? 单个 :
        typeof 单个 === "string" ? [...单个] : 参数;
    if (值们.length === 0) throw new CNplus错误("CN0303", "至少要给一个值", 0, 0);
    return 值们.reduce((当前, 值) =>
        (取最大 ? 大于(值, 当前, 0, 0) : 小于(值, 当前, 0, 0)) ? 值 : 当前);
}


function _随机BigInt下于(上限) {
    if (上限 === 1n) return 0n;
    const 位数 = (上限 - 1n).toString(2).length;
    while (true) {
        let 值 = 0n;
        let 剩余 = 位数;
        while (剩余 > 0) {
            const 本次 = Math.min(32, 剩余);
            const 块 = BigInt(Math.floor(Math.random() * 2 ** 本次));
            值 = (值 << BigInt(本次)) | 块;
            剩余 -= 本次;
        }
        if (值 < 上限) return 值;
    }
}


function _随机端点(v) {
    const 值 = 拆小数(v);
    if (typeof 值 === "bigint") return 值;
    if (typeof 值 === "number" && Number.isFinite(值)) return BigInt(Math.trunc(值));
    throw new CNplus错误("CN0303", "随机数的端点必须是数值", 0, 0);
}


function _随机整数(a, b) {
    const 起 = _随机端点(a); const 止 = _随机端点(b);
    if (起 > 止) throw new CNplus错误("CN0303", "随机数的起点不能大于终点", 0, 0);
    return 起 + _随机BigInt下于(止 - 起 + 1n);
}


function _带位置内置(实现) {
    const 包装 = (...实参们) => 实现(...实参们, 0, 0);
    包装._按位置调用 = (实参们, 行, 列) => 实现(...实参们, 行, 列);
    return 包装;
}


function _带位置参数内置(实现) {
    const 包装 = (...实参们) => 实现(实参们, 0, 0);
    包装._按位置调用 = (实参们, 行, 列) => 实现(实参们, 行, 列);
    return 包装;
}


const 内置们 = {
    "打印": _内置_打印,
    "询问": _询问,
    "询问数值": _询问数值,
    "类型": 类型名,
    "文本": 显示,
    "整数": _转整数,
    "小数": _转小数,
    "长度": (x) => BigInt(x instanceof Map ? x.size :
        typeof x === "string" ? [...x].length : x.length),
    "范围": _范围,
    "随机数": _随机整数,
    "绝对值": _绝对值,
    "最大": (...a) => _极值(true, ...a),
    "最小": (...a) => _极值(false, ...a),
    "求和": _求和,
    "四舍五入": _四舍五入,
    "平方根": _平方根,
    "追加": (表, 项) => { 表.push(项); },
    "插入": _带位置内置((表, 位, 项, 行, 列) => {
        const 原位 = 拆小数(位);
        if (typeof 原位 !== "bigint") {
            throw new CNplus错误("CN0303", "插入的位置必须是整数", 行, 列);
        }
        let 实际位置;
        const 长 = BigInt(表.length);
        if (原位 < 0n) 实际位置 = 原位 < -长 ? 0 : Number(长 + 原位);
        else 实际位置 = 原位 > 长 ? 表.length : Number(原位);
        表.splice(实际位置, 0, 项);
    }),
    "移除": _带位置内置((表, 项, 行, 列) => {
        let i = -1;
        for (let j = 0; j < 表.length; j++) {
            if (_值相等(表[j], 项, 行, 列)) { i = j; break; }
        }
        if (i === -1) throw new CNplus错误("CN0303",
            `列表里没有 ${显示(项)}`, 行, 列, "检查要移除的东西在不在列表里");
        表.splice(i, 1);
    }),
    "弹出": _带位置参数内置((实参们, 行, 列) => {
        const [表, ...位置] = 实参们;
        if (位置.length === 0) {
            if (表.length === 0) throw new CNplus错误("CN0308",
                "空列表没有东西可以弹出", 行, 列,
                "要弹出的位置不在列表范围内", "先用「长度(列表)」检查列表是否为空");
            return 表.pop();
        }
        const i = _序列下标(位置[0], 表.length, 行, 列, false);
        return 表.splice(i, 1)[0];
    }),
    "排序": _带位置内置((表, 行, 列) =>
        [...表].sort((a, b) => _排序比较(a, b, 行, 列))),
    "倒序": (表) => [...表].reverse(),
    "包含": _带位置内置((容器, 项, 行, 列) => {
        if (容器 instanceof Map) return 容器.has(_字典标签(项, 行, 列));
        if (Array.isArray(容器)) {
            for (const 已有 of 容器) if (_值相等(已有, 项, 行, 列)) return true;
            return false;
        }
        return 容器.includes(项);
    }),
    "连接": (表, 隔) => 表.map(x => 显示(x)).join(隔),
    "所有标签": (字) => [...字.keys()],
    "所有值": (字) => [...字.values()],
    "有标签": _带位置内置((字, 标签, 行, 列) =>
        字.has(_字典标签(标签, 行, 列))),
    "删标签": _带位置内置((字, 标签, 行, 列) => {
        字.delete(_字典标签(标签, 行, 列));
        return null;
    }),
    "分割": _分割,
    "替换": _替换,
    "查找": _查找,
    "去空白": (文) => 文.trim(),
    "大写": (文) => 文.toUpperCase(),
    "小写": (文) => 文.toLowerCase(),
    "开头是": (文, 前) => 文.startsWith(前),
    "结尾是": (文, 后) => 文.endsWith(后),
};


function _排序比较(a, b, 行 = 0, 列 = 0) {
    a = 拆小数(a); b = 拆小数(b);
    if (是数(a) && 是数(b)) return a < b ? -1 : a > b ? 1 : 0;
    if (typeof a === "string" && typeof b === "string") {
        return a < b ? -1 : a > b ? 1 : 0;
    }
    throw new CNplus错误("CN0303", "排序的项目必须全是数值或全是文字", 行, 列);
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

if (typeof process !== "undefined" && process !== null && typeof process.on === "function") {
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
}
