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
    [左, 右] = _两数("-", 左, 右, 行, 列);
    return 左 - 右;
}


function 乘(左, 右, 行, 列) {
    if (typeof 左 === "string" && 是数(右)) return 左.repeat(Math.trunc(右));
    if (typeof 右 === "string" && 是数(左)) return 右.repeat(Math.trunc(左));
    [左, 右] = _两数("*", 左, 右, 行, 列);
    return 左 * 右;
}


function 除(左, 右, 行, 列) {
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
    [左, 右] = _两数("//", 左, 右, 行, 列);
    if (右 === 0) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    return Math.floor(左 / 右);
}


function 取余(左, 右, 行, 列) {
    [左, 右] = _两数("%", 左, 右, 行, 列);
    if (右 === 0) {
        throw new CNplus错误("CN0304", "除数不能是零", 行, 列);
    }
    return 左 % 右;
}


function 幂(左, 右, 行, 列) {
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
    return typeof 左 === typeof 右
        && (typeof 左 === "string" || Array.isArray(左) && Array.isArray(右));
}


function 等于(左, 右, 行, 列) {
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
    return 左 === right_eq(右, 左);
}
function right_eq(a, b) { return a === b; }


function 不等于(左, 右, 行, 列) {
    return !等于(左, 右, 行, 列);
}


function _比大小(运, 左, 右, 行, 列) {
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


// ==================== 调用（T3 最小：内置函数）====================

function 调用(被调, 实参们, 关键字们, 行, 列) {
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


// ==================== 内置函数（T3 最小集）====================

function _内置_打印(...值们) {
    console.log(值们.map(v => 显示(v)).join(" "));
}


const 内置们 = {
    "打印": _内置_打印,
    "类型": 类型名,
    "文本": 显示,
};


function 建全局环境() {
    // 内置放父环境，用户顶层是子环境 —— 遮蔽内置名与
    // Python 后端/checker 一致（D-033）
    const 内置环 = new 环境(null);
    for (const [名, 值] of Object.entries(内置们)) {
        内置环.表.set(名, 值);
    }
    return new 环境(内置环);
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
