---
topic: 引用计数与SideTable
group: 内存管理
generated_at: 2026-07-29T19:29:52
provider: deepseek
---

# 引用计数与SideTable

## 一句话总结

Objective-C 对象的引用计数优先存储在 isa 的 `extra_rc` 字段（8 位）中，溢出时启用 `SideTable` 中的 `refcnts` 哈希表存储大值；`SideTable` 同时管理弱引用表，通过 `StripedMap` 分片和独立锁实现线程安全 [1][3][4]。

## 核心原理

1. **两级存储策略**
   - **内联存储**：当对象引用计数 ≤ 255 时，存储在 isa 的 `extra_rc`（8 位无符号整数），此时 `has_sidetable_rc = 0` [8][11]。
   - **侧表存储**：`extra_rc` 达到 255 后，下一次 retain 触发溢出，`has_sidetable_rc` 置为 1，系统将一半计数（`RC_HALF`，即 128）迁移到 `SideTable` 的 `refcnts` 哈希表中，另一半仍留在 `extra_rc` [11]。
   - 释放时优先减少 `extra_rc`，减到 0 后再从 `SideTable` 取回一半，避免频繁加锁 [11]。

2. **SideTable 结构**
   ```c
   struct SideTable {
       os_unfair_lock slock;           // 锁，保证线程安全
       RefcountMap refcnts;            // 引用计数哈希表（对象指针 → 引用计数）
       weak_table_t weak_table;        // 弱引用表
   };
   ```
   - `RefcountMap` 是一个 `DenseMap`，键为对象地址，值为引用计数（需右移 `SIDE_TABLE_RC_SHIFT` 位后 +1 才是真实计数）[1][6]。
   - `weak_table` 存储弱引用信息，与 `refcnts` 无关，仅共用锁和分片 [9]。

3. **StripedMap 分片机制**
   - 系统维护一个固定大小的 `SideTable` 数组 `StripedMap`，通过对象地址哈希取模定位对应的 `SideTable`：
     ```c
     static SideTable& table = SideTables()[obj];
     ```
   - 分片数量：iOS/watchOS/tvOS 真机为 **8**，Mac 和所有模拟器为 **64** [9]。
   - 设计目的：分散锁竞争，不同 `SideTable` 上的操作可以并行执行 [3][9]。
   - 多个对象可能映射到同一个 `SideTable`，但由于锁粒度减小，整体并发性能优于单一全局表 [3]。

4. **纯 Swift 类的引用计数存储**
   - Swift 对象通过 `InlineRefCountBits`（8 字节）存储引用计数，使用 bit 63 标识模式：
     - **内联模式**（bit 63 = 0）：直接存储 strong 计数、unowned 计数和 `isDeiniting` 标志。
     - **SideTable 模式**（bit 63 = 1）：8 字节变为指向 `HeapObjectSideTableEntry` 的指针，该 entry 中包含完整的引用计数和对象指针 [7]。
   - 触发切换的条件：
     - 对象首次被 weak 引用。
     - strong 或 unowned 计数溢出（32 位系统更易发生）。
   - 切换不可逆，即使后续所有 weak 引用消失也不会切回内联模式 [7]。
   - 读取 weak 变量时：通过 `HeapObjectSideTableEntry` 获取对象指针，检查 strong 计数是否 > 0，若对象已释放则返回 nil [7]。

5. **引用计数获取与修改入口**
   - `retain`/`release` 最终调用 `objc_object::rootRetain()` / `rootRelease()`，对 TaggedPointer 直接返回，否则操作 `SideTable` 的 `refcnts` [5][12]。
   - `retainCount` 的 `rootRetainCount()` 方法优先读取 `isa.extra_rc`（加 1），若 `has_sidetable_rc` 为 1，则调用 `sidetable_getExtraRC_nolock()` 加上 SideTable 中的溢出计数 [6]。
   - 对于 32 位指针 isa（非优化），引用计数完全存储在 `SideTable` 的哈希表中 [1]。

## 关键细节与易错点

1. **`has_sidetable_rc` 标志**
   - 该标志位（isa 的 bit 55）仅表示引用计数已使用 `SideTable` 的 `refcnts`，并不代表对象有弱引用 [11]。
   - 注意：溢出时 `has_sidetable_rc` 置 1，但 `extra_rc` 仍然保留一半计数（`RC_HALF`），之后所有引用计数操作均需读写 SideTable [11]。

2. **RC_HALF 的作用**
   - `RC_HALF` 值为 128，溢出时将一半计数迁移到 SideTable，后续 release 时优先消耗 `extra_rc`，减到 0 后再从 SideTable 取回一半，从而减少加锁次数 [11]。

3. **SideTable 不等于 weak 表**
   - `SideTable` 包含三个独立成员：锁、`refcnts`、`weak_table`。`weak_table` 只是其中一个，两者互不相干，仅共用锁和分片 [9]。
   - 给对象加 weak 引用会导致 `weak_table` 被操作，但引用计数仍可能只存在 `extra_rc`（除非溢出），不会强制走 `refcnts` [9]。

4. **分片数与真机差异**
   - 真机 8 片，Mac 和模拟器 64 片。原因推测：真机内存更紧凑、核心少，减少脏内存开销；Mac 核心多、并发压力大，需要更多分片避免锁竞争 [9]。
   - 每片按缓存行对齐（`alignas(CacheLineSize)`）避免伪共享 [9]。

5. **Swift 类 SideTable 切换的不可逆性**
   - 一旦切换为 SideTable 模式，即使后续所有 weak 引用消失，也不会归还 SideTable 内存，因为重新同步的代价过高 [7]。
   - 这正是 weak 比 unowned “更重”的原因：首次 weak 引用会触发 SideTable 分配和模式切换，而 unowned 仅需内联计数 [7]。

6. **TaggedPointer 的特殊处理**
   - TaggedPointer 对象（如小整数、短 NSString）的值存储在栈指针本身，不参与引用计数管理，`retain`/`release` 直接返回自身，不操作 SideTable [5]。

## 高频追问

**Q: 引用计数溢出后为什么只迁移一半到 SideTable？**
- 为了优化频繁 retain/release 场景下的性能。留一半在 `extra_rc`，后续快速增减计数无需加锁；只有 `extra_rc` 减到 0 时才需要从 SideTable 取回一半，同时避免每次操作都访问哈希表 [11]。

**Q: SideTable 中的 weak 表和引用计数表有什么关系？**
- 两者无直接关联。`refcnts` 存储引用计数溢出部分，`weak_table` 存储弱引用结构。它们只是共用同一个 `SideTable` 分片和其锁 `slock`，操作时需加锁保证线程安全 [1][9]。

**Q: 多个对象如何共享同一个 SideTable？**
- 通过地址哈希取模定位：`SideTables()[obj]` 将对象地址哈希后对 `StripeCount`（8 或 64）取余，余数相同的对象共享同一个 `SideTable`。这类似于哈希冲突，但避免了为每个对象分配独立表，同时分散锁竞争 [3]。

**Q: 为什么 Swift 的 weak 比 unowned “重”？**
- 因为首次 weak 引用会触发 `InlineRefCountBits` 从内联模式切换到 SideTable 模式，需要分配 `HeapObjectSideTableEntry` 并进行计数迁移，且切换不可逆。而 unowned 只需要保证对象生命周期内引用有效，无需 SideTable 支持，直接使用内联计数即可 [7]。

**Q: 对象 dealloc 时弱引用置 nil 是如何做到的？**
- 在对象释放的最后阶段，Runtime 会通过 `SideTable` 中的 `weak_table` 查找所有指向该对象的弱引用条目，并将它们置为 nil [4]。具体流程（如 `clearDeallocating`）依赖 `SideTable` 的锁和 `weak_table_t` 的结构，但材料未展开细节，可参考 weak 详解章节。

**Q: 如何在代码中观察 `extra_rc` 溢出和 `has_sidetable_rc` 的变化？**
- 通过读取 raw isa 位域（例如 `uintptr_t isa = *(uintptr_t *)(__bridge void *)obj;`），解析 bit 55（`has_sidetable_rc`）和 bit 56~63（`extra_rc`），配合 `CFGetRetainCount` 对比即可看到溢出行为 [11]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › 引用计数机制 › 引用计数的存储策略 › 大引用计数：侧表存储（第327-342行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/weak详解.md › weak详解 › weak的底层数据结构 › SideTable（第27-49行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 二、引用计数机制 › 引用计数的存储 › 侧表存储（SideTable）（第162-176行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c-引用计数原理.md › 修改引用计数 › retain 和 release（第319-343行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c-引用计数原理.md › 获取引用计数（第230-284行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Swift底层原理-结构体、类和协议.md › Swift底层原理-结构体、类和协议 › Swift类的底层实现 › 纯Swift类（未继承NSObject） › InlineRefCountBits 与 SideTable 的切换（第190-212行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › 引用计数机制 › 引用计数的存储策略（第304-306行）
[9] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS weak 的实现：SideTable 与置 nil 的时机.md › weak 的实现：SideTable、weak_table_t 与置 nil 的时机 › 一、四层结构，每层的 key 都不一样 › SideTable 不等于 weak 表（第103-129行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：MRC 的所有权规则.md › MRC 的所有权规则：retain、release 与 autorelease › 四、引用计数存在哪：一个能测出来的问题 › 实测（第228-261行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/alwaysprocessing/objective-c-internals-release-although-release-is-just-the-logical-inverse-of-retain-its-i.md › Objective-C Internals: Release › Entry Points › NSObject（第29-64行）
