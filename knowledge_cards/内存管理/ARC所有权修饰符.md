---
topic: ARC所有权修饰符
group: 内存管理
generated_at: 2026-07-29T19:29:22
provider: deepseek
---

# ARC所有权修饰符

## 一句话总结
ARC 用 `__strong`（默认）、`__weak`（自动置 nil）、`__unsafe_unretained`（不置 nil）和 `__autoreleasing`（用于 out‑parameter 和返回值）标明引用所有权；其中 `__weak` 有运行时登记和自动清空机制，`__unsafe_unretained` 只是裸赋值等价于 MRC 的 `assign`，在对象销毁后留下悬垂指针。[3][5][6][8]

## 核心原理

1. **引用计数的底层指令**：ARC 在 SIL 层将所有权操作翻译为 `strong_retain`/`strong_release`、`unowned_retain`/`unowned_release`，而弱引用读写通过 `load_weak`/`store_weak` 实现。[4]

2. **`__weak` 的 registion 机制**：当使用 `__weak` 修饰变量时，编译器会在赋值/销毁时调用 `objc_storeWeak` 把变量地址登记到 SideTable 中，对象出栈时通过查表自动将指针置为 nil。`__unsafe_unretained` 只是一次裸赋值，运行时对它一无所知，因此不会被清零。[8]

3. **`__unsafe_unretained` 的危险性**：指向的对象销毁后，指针仍指向已释放的内存，访问是未定义行为——可能因为内存未复用而“没事”，也可能拿到垃圾对象或直接崩溃。这种“有时候好使”的特性使它在开发阶段难以稳定复现。[2][3][10]

4. **`__autoreleasing` 的隐式转换**：ARC 会将方法参数中的 `NSError **` 等 “out‑parameter” 隐式修饰为 `__autoreleasing`，导致赋值时自动插入 `retain` 和 `autorelease`。如果该参数被 block 捕获，而 block 在 `@autoreleasepool` 内执行，则 `*error` 可能在 block 外被提前释放。[9]

5. **属性修饰符对应关系**：`strong` → `__strong`，`weak` → `__weak`，`unsafe_unretained` → `__unsafe_unretained`，`assign` 在 ARC 下等同于 `unsafe_unretained` 即非 zeroing 弱引用。[3][5]

## 关键细节与易错点

### 1. `__block` 与所有权修饰符的互动
- 在 ARC 下，`__block` 变量默认使用 `__strong` 所有权（layout = `STRONG`），因此 `__block id` 会 strong 持有对象，无法直接切断循环引用。[1]
- 显式加上 `__unsafe_unretained` 后，layout 变为 `UNRETAINED`，且 `HAS_COPY_DISPOSE` 为 0，不生成 helper，从而恢复断环能力。[1]
- 使用 `__block __weak` 也能断环，且比 `__unsafe_unretained` 安全（对象销毁后自动置 nil），但通常直接用 `weakSelf` 更直白。[1]
- MRC 下 `__block` 默认为 `UNRETAINED`，因此能直接断环；ARC 只是改变了默认所有权修饰符，libclosure 本身并未改变。[1]

### 2. `__weak` 与 `__unsafe_unretained` 的实测差异
| 场景 | `__weak` | `__unsafe_unretained` |
|------|----------|------------------------|
| 对象存活时 | 指向对象地址 | 指向对象地址 |
| 对象销毁后 | 指针被置为 `0x0` | 指针仍指向已释放内存（悬垂指针） |
| 底层行为 | 调用 `objc_storeWeak` 登记 | 裸赋值，运行时无记录 |

数据来源：[2][8]

### 3. 性能差异
一千万次属性读取实测：
- `strong`: 11.3–16.8 ns
- `unsafe_unretained`: 11.5–18.1 ns
- `weak`: 46.1–46.3 ns（约为 strong 的 3–4 倍）

绝对值不大（约 46 ns/次），只有在逐帧执行几千次的热路径且能自证生命周期安全时，才值得用 `unsafe_unretained` 代替 `weak`。[2]

### 4. 旧系统兼容性
- `__weak`（zeroing weak reference）在 iOS 4 及之前、Mac OS X 10.6 及之前不可用，必须用 `__unsafe_unretained`。[3][10]
- 社区方案如 `PLWeakCompatibility` 通过欺骗编译器在旧系统上提供 zeroing weak 支持。[10]

### 5. 关联对象中的“weak”陷阱
- `OBJC_ASSOCIATION_ASSIGN` 的注释虽写“Specifies a weak reference”，但此处的“weak”对应 ARC 的 `unsafe_unretained`（非 zeroing），实现中未使用任何 `objc_storeWeak` 调用。[7]

### 6. delegate 为何不用 `unsafe_unretained`
- 流行说法“防止循环引用”因果倒置。真正的理由是所有权的方向：`UITableView` 不应拥有其 delegate，因为 delegate 通常是更上层、生命周期更长的对象。如果 delegate 用 strong，即使没有循环引用，也可能导致被代理对象无法正常释放。按所有权推导，答案唯一。[2]

## 高频追问

**Q1: `__unsafe_unretained` 和 `__weak` 的根本区别只是“是否自动置 nil”吗？**
不。差别更靠前：`__weak` 会调用 `objc_storeWeak` 将变量地址登记进表，运行时知道需要清空；`__unsafe_unretained` 只是一次裸赋值，运行时对它一无所知。[8]

**Q2: 为什么在 ARC 下用 `__block` 修饰对象却无法打破循环引用？**
因为 ARC 下 `__block` 的默认所有权修饰符是 `__strong`，导致 block 强引用外部变量。只有显式使用 `__unsafe_unretained` 或 `__weak` 才能改为非强引用，从而断开循环。[1]

**Q3: `OBJC_ASSOCIATION_ASSIGN` 是 zeroing weak 吗？**
不是。它对应 ARC 的 `__unsafe_unretained`（non-zeroing weak），注释中的“weak”是 MRC 时代的旧术语，实现中没有使用 zeroing weak 的 runtime 函数。[7]

**Q4: 什么时候应该故意选 `__unsafe_unretained` 而非 `__weak`？**
在以下两个条件同时满足时：① 代码运行在旧系统（iOS 4 及以下），`__weak` 不可用；② 能通过手动清零或生命周期保证避免悬垂指针。否则，为性能放弃安全性通常不值得（一千万次读取差距约 30 ns，绝对值很小）。[2][3]

**Q5: 为什么用 `__autoreleasing` 修饰的 out‑parameter 在被 block 捕获时可能导致 use‑after‑free？**
因为 ARC 会隐式给 `*error` 赋值时插入 `retain`/`autorelease`，而 block 所在的方法（如 `enumerateKeysAndObjectsUsingBlock:`）会在 `@autoreleasepool` 内执行 block，导致 `*error` 在 pool  drained 时被释放，之后访问即为野指针。[9] 解决方案：将参数声明为 `__strong` 或捕获一个 `__block __strong` 变量。[9]

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 循环引用与 weak-strong dance.md › Block 循环引用与 weak-strong dance › 一、六种写法 › 第 ③ 和第 ⑥ 行放在一起才有意思（第58-74行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 属性关键字：从所有权推导，而不是从类型名猜.md › 属性关键字：从所有权推导，而不是从类型名猜 › 一、所有权那一栏 › weak 与 unsafe_unretained 的实测差异（第182-212行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-09-30-automatic-reference-counting.md › (全文)（第200-211行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/SIL.md › SIL（Swift Intermediate Language） › 关键 SIL 指令详解 › 引用计数指令（ARC 相关）（第353-367行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 三、ARC（自动引用计数） › 所有权修饰符（第223-232行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Block的本质.md › 8. Block 的循环引用 › 8.2 使用`__unsafe_unretained`修饰变量（第892-899行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/alwaysprocessing/objective-c-internals-associated-references-a-comparison-of-apple-s-associated-references-.md › Objective-C Internals: Associated References › The Apple Way › A Closer Look At assign Storage（第202-210行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS weak 的实现：SideTable 与置 nil 的时机.md › weak 的实现：SideTable、weak_table_t 与置 nil 的时机 › 六、几个说法需要辨析 › "weak 和 unsafe_unretained 只差会不会自动置 nil"（第444-446行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/what-s-new-in-llvm.md › [What's New in LLVM](http://yulingtianxia.com/blog/2017/07/17/What-s-New-in-LLVM-2017/) › New Warnings › ARC 中的 Block 捕获参数（第195-218行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/last-time-768338.md › (全文)（第26-31行）
