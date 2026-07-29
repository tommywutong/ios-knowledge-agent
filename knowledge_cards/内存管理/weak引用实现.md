---
topic: weak引用实现
group: 内存管理
generated_at: 2026-07-29T19:30:28
provider: deepseek
---

# weak引用实现

## 一句话总结

weak引用通过 Runtime 的 SideTable 机制维护一张从对象地址到所有指向它的 weak 指针地址的反向索引表，当对象析构时，在 `dealloc` 过程中同步遍历该表将所有 weak 指针置为 nil。 [1] [3] [4]

## 核心原理

1. **数据结构层级**：全局存在多个 `SideTable` 分片，每个 `SideTable` 包含一个自旋锁 `slock`、引用计数哈希表 `refcnts` 和弱引用表 `weak_table_t`。 [7] [9] `weak_table_t` 是一个哈希表，key 为被引用对象的地址，value 为 `weak_entry_t`，后者维护该对象的所有弱引用指针地址。 [1] [10]

2. **注册阶段**：当弱引用指针指向对象时，通过 `objc_storeWeak`（内部调用 `weak_register_no_lock`）将关系注册到对象所在 `SideTable` 的 `weak_table` 中，同时设置对象 isa 中的 `weakly_referenced` 标志位。 [11] [4]

3. **置 nil 调用链**：对象 `dealloc` 时进入 `rootDealloc()`，检查 isa 的 `weakly_referenced` 标志位：若为 false 且无其他特殊标志，走快速路径直接 `free`；否则进入慢速路径 `object_dispose -> objc_destructInstance -> clearDeallocating() -> clearDeallocating_slow()` 触发 `weak_clear_no_lock()`。 [4]

4. **清理过程**：`weak_clear_no_lock` 以对象地址为 key 在 `weak_table` 中哈希查找对应的 `weak_entry`；根据 entry 的 `out_of_line_ness` 标志判断使用内联数组还是动态数组；遍历所有弱引用指针地址，校验 `*referrer == referent` 后执行 `*referrer = nil`；最后从 `weak_table` 中移除该 entry。 [4] [5]

5. **线程安全**：`storeWeak` 采用基于地址排序的加锁顺序（先锁地址较小的 SideTable，再锁较大的）避免死锁，内部含重试循环（加锁后重新读取 `*location` 确认旧值未被其他线程修改）。 [11] [10] 整个 `weak_clear_no_lock` 在 SideTable 锁保护下执行，防止与并发的 `storeWeak`、`objc_loadWeakRetained` 产生竞争。 [4]

## 关键细节与易错点

- **快速路径优化**：若 isa 的 `weakly_referenced` 标志为 false，说明没有弱引用，可直接跳过快照清理，直接 `free`。 [4]
- **弱引用表的两种存储**：`weak_entry_t` 根据 `out_of_line_ness` 标志决定使用内联数组 `inline_referrers`（固定大小）还是动态数组 `referrers`（哈希表）。 [4] [5]
- **置 nil 时机**：是在 `dealloc` 过程中同步执行，而非等待 `dealloc` 方法执行完毕。 [4] （材料 [2] 指出“要等 dealloc 跑完”是流行但能被实验推翻的错误说法）
- **SideTable 不可析构**：其析构函数直接调用 `_objc_fatal("Do not delete SideTable.")`，表示设计上不允许独立删除 SideTable。 [9]
- **注册 / 清理的锁保护范围**：`storeWeak` 可能同时操作新旧两个对象所属的 SideTable，通过地址排序的 `lockTwo` / `unlockTwo` 模板实现安全加锁。 [11] [9]

## 高频追问

### Q1: weak 变量在对象释放后为什么能自动变成 nil？
A: 依赖于对象析构时 Runtime 的主动清理机制。完整调用链为 `dealloc → _objc_rootDealloc → rootDealloc()`（检查 `weakly_referenced` 标志）→ 慢速路径 `object_dispose → objc_destructInstance → clearDeallocating() → clearDeallocating_slow()` → `weak_clear_no_lock()`。该函数遍历所有指向该对象的 weak 指针，逐个校验后置为 nil，并从 `weak_table` 中移除 entry，整个流程在 SideTable 锁保护下完成。 [4] [5]

### Q2: weak 实现中如何保证线程安全？
A: 两方面保障：1）`storeWeak` 采用基于地址排序的加锁顺序（先锁地址较小的 SideTable，再锁较大的）避免死锁，且内部包含重试循环——加锁后重新读取 `*location` 确认旧值未被其他线程修改。 [11] [10] 2）`weak_clear_no_lock` 在 SideTable 锁的保护下执行，防止与并发的 `storeWeak`、`objc_loadWeakRetained` 产生数据竞争。 [4]

### Q3: weak 和 `__unsafe_unretained` 的区别是什么？
A: weak 在对象释放后由 Runtime 自动将指针置为 nil，依赖 SideTable 注册与清理机制，有额外开销；`__unsafe_unretained` 不进行任何跟踪，对象释放后指针变为悬垂指针，无运行时开销但使用不安全。 [1] [3] （材料 [12] 指出可用 `__unsafe_unretained` 对照悬垂指针风险）

### Q4: weak 的置 nil 时机是在 dealloc 之前还是之后？
A: 是在 `dealloc` 过程中同步进行的。`weak_clear_no_lock` 在 `rootDealloc()` 的慢速路径中、`objc_destructInstance` 之前被调用，因此不存在“等 dealloc 跑完才置 nil”的野指针窗口。 [4] 材料 [2] 指出那种流行说法是错误的。

### Q5: SideTable 的结构和作用是什么？
A: `SideTable` 包含三个成员：`spinlock_t slock`（自旋锁）、`RefcountMap refcnts`（引用计数哈希表，存储 isa 的 `extra_rc` 溢出部分的引用计数）、`weak_table_t weak_table`（弱引用哈希表）。每个 SideTable 不单独析构，其析构函数设计为 `_objc_fatal`。 [7] [9] [4]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 七、常见面试题 › Q6: weak是如何实现自动置nil的？（第993-1000行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS weak 的实现：SideTable 与置 nil 的时机.md › (全文)（第1-15行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS weak 的实现：SideTable 与置 nil 的时机.md › weak 的实现：SideTable、weak_table_t 与置 nil 的时机（第16-28行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/weak详解.md › weak详解 › 面试常见问题 › Q2: weak变量在对象释放后为什么能自动变成nil？（第623-645行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/weak详解.md › weak详解 › weak引用的核心函数 › weak_clear_no_lock（第293-331行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 二、引用计数机制 › 引用计数的存储 › 侧表存储（SideTable）（第162-176行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/blog.csdn.net/objective-c-runtime机制-7-sidetables-sidetable-weak-table-weak-entry-t.md › SideTable（第233-287行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/ios知识小集-第2期-2015-05-31.md › weak的生命周期（第275-334行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/weak详解.md › weak详解 › weak引用的核心函数 › objc_storeWeak（核心函数）（第168-208行）
[12] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第二周：weak、属性关键字与 Block › 本周精读路线 › Day 2｜weak 按“写入—读取—销毁”三段学（对应 W2-01～W2-06）（第177-183行）
