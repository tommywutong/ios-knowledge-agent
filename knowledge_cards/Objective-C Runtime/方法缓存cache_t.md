---
topic: 方法缓存cache_t
group: Objective-C Runtime
generated_at: 2026-07-29T19:26:07
provider: deepseek
---

# 方法缓存cache_t

## 一句话总结

`cache_t` 是 `objc_class` 内嵌的一个高速哈希表，用于缓存最近被调用的方法，`bucket_t` 中存储 SEL 与 IMP 的键值对 [5] [4]。通过优先在缓存中查找，运行时系统显著提升了消息发送的效率 [5]。

## 核心原理

1.  **数据结构与存储方案**
    - `cache_t` 的核心字段是 `_bucketsAndMaybeMask`，在 arm64（64 位真机）等平台上，该字段将桶指针和容量掩码 (mask) 融合在同一个 64 位字中：高 16 位存储 mask，低 48 位存储 buckets 指针。这种设计减少了内存读取次数，允许一条 `ldr` 指令同时取出 mask 和 buckets [2] [3] [9]。
    - `_bucketsAndMaybeMask` 的解读方式依 `CACHE_MASK_STORAGE` 宏而异：
        - **OUTLINED**：该字段纯作指针使用，mask 作为一个独立的 `_mask` 字段存在 `union` 中 [10]。
        - **HIGH_16 / LOW_4**：mask 被内联编码（inline）到 `_bucketsAndMaybeMask` 的指定位中（如高 16 位或低 4 位）[9]。
    - `cache_t` 还含有一个 `union`，其成员之一 `_originalPreoptCache` 用于 dyld 共享缓存（shared cache）的预优化方法缓存（preoptimized cache），主要服务于系统类 [1] [2] [3]。
    - `bucket_t` 结构体中的 `sel`（方法选择器）作为哈希表的键（Key），`imp`（方法实现指针）作为值（Value）[4] [5] [8]。

2.  **查找过程（快速路径）**
    - 消息发送时，运行时系统首先在对象的 `isa` 指针指向的类的 `cache_t` 中查找。
    - 查找过程使用哈希算法：`cache_hash = (mask_t)((uintptr_t)sel & cache->_mask)`，通过按位与（bitwise AND）运算（比取模更快）得到数组索引 [4] [7]。
    - 在该索引位置的 `bucket_t` 中，比较 `sel` 是否匹配：
        - **匹配（命中）**：直接返回对应的 `IMP` [4]。
        - **不匹配**：使用开放寻址法（open addressing）向前（下）线性探测下一个 `bucket` 位置，直到找到匹配的 `sel` 或找到空的桶（`sel` 为 0）[4]。

3.  **写入与扩容**
    - 当消息查找在方法列表中寻找到 `IMP` 后，会调用 `cache_t::insert(SEL sel, IMP imp, id receiver)` 将方法写入缓存 [11] [12]。
    - 缓存的初始容量为 4（`INIT_CACHE_SIZE`）[11]。
    - 当缓存容量达到一定装填率（`cache_fill_ratio`，例如 3/4 或 7/8）时，`cache_t` 会进行扩容，并触发 `reallocate` 操作 [11]。
    - 在 `+initialize` 方法执行完成前，不允许缓存方法，以避免缓存动态修改后可能过期的 IMP [11]。

## 关键细节与易错点

1.  **`_bucketsAndMaybeMask` 的融合机制**：不要误以为 `cache_t` 始终有独立的 `_mask` 字段。在 arm64 真机上，`_mask` 被内联编码在 `_bucketsAndMaybeMask` 指针的高 16 位中，这是为了性能优化而设计的 [2] [3]。
2.  **不同平台布局差异**：`cache_t` 的成员布局在不同平台和架构下不同（如 32 位 vs 64 位，OUTLINED vs INLINE）。阅读源码时必须明确当前代码路径对应的 `CACHE_MASK_STORAGE` 宏 [1] [9]。
3.  **预优化缓存（Preoptimized Cache）**：系统类可能使用共享缓存中预优化的 `preopt_cache_t`，这是一个只读优化，运行时不应再尝试向其中写入新的缓存 [1] [6] [11]。
4.  **哈希冲突处理**：`cache_t` 采用开放寻址法解决哈希冲突，而不是链式哈希。当索引位置的 `sel` 不匹配且不为空时，会线性向前探测空位或匹配项 [4]。
5.  **`occupied` 的更新**：`_occupied` 表示当前已缓存的 `bucket` 数量。每次成功插入一个方法后会调用 `incrementOccupied()` 递增它，用于决定何时触发扩容 [1] [6] [11]。
6.  **易错点：`slowpath` 宏**：`slowpath()` 是一个编译器提示，告知分支预测器该分支极少发生（如被跳过的 `+initialize` 检查），有助于优化 CPU 分支预测。它不影响程序的逻辑正确性 [11]。

## 高频追问

（面试中围绕该主题的典型追问及基于材料的回答要点）

-   **Q1：方法缓存查找的具体流程是怎样的？**
    -   **要点**：`cache_t` 使用哈希表结构，通过 `sel & mask` 计算下标，再在 `bucket_t` 数组中比较 `sel` 是否匹配；若不匹配则线性探测。目的是在避免遍历整个方法列表的情况下快速命中 [4] [7]。

-   **Q2：`cache_t` 什么时候扩容？怎么扩容？**
    -   **要点**：初始容量为 4 [11]。当已缓存的方法数量 (`occupied`) 加上一个结束标记（`CACHE_END_MARKER`）超过容量的一定比例（如 3/4 或 7/8，由 `cache_fill_ratio` 控制）时，会触发扩容 [11]。扩容通过 `reallocate` 方法分配更大的哈希表并重新填充 [6] [11]。

-   **Q3：为什么用 `sel & mask` 而不用取模操作？**
    -   **要点**：位运算（按位与）相比取模（%）在底层 CPU 指令上更高效，能以更快速度完成哈希索引计算，是常见的性能优化手段 [4] [7]。

-   **Q4：`cache_t` 在 arm64 和模拟器上的布局有什么不同？**
    -   **要点**：在 arm64 真机上，`_mask` 被内联在 `_bucketsAndMaybeMask` 的高 16 位中，不占独立字段；在 Mac 模拟器（x86_64）上，`_mask` 往往是独立存在的 `explicit_atomic<mask_t>` 字段 [2] [3] [9] [10]。模拟器布局更直观，常作为分析参考。

-   **Q5：什么是预优化缓存（preoptimized cache）？它有什么影响？**
    -   **要点**：预优化缓存是 dyld 在共享缓存中为系统类预先建立好的方法缓存，是一个只读优化。如果当前类的缓存是预优化的（`isConstantOptimizedCache` 返回真），则不能在运行时向其插入新缓存，否则会触发 `_objc_fatal` 断言 [11]。

-   **Q6：为什么 `+initialize` 没执行完时不允许缓存方法？**
    -   **要点**：在 `+initialize` 执行过程中，可能通过 `method_setImplementation` 或 `class_addMethod` 动态修改方法列表。如果在这之前缓存了某个 IMP，`+initialize` 完成后该 IMP 可能已经改变，缓存中的数据就会失效。因此，运行时系统会确保在 `+initialize` 完成前不将任何方法写入缓存 [11]。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/Runtime/Part 1 - 对象与类的本质.md › 类的本质：objc_class › 类的四大件：isa / superclass / cache / bits › cache：方法缓存（第773-806行）
[2] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Part 2 - 消息发送与转发.before-renumber.md › 【iOS】Runtime - Part 2 && 消息发送：缓存、查找与转发 › 第一部分 · 快速路径（缓存命中） › 3. cache_t 数据结构（`objc-runtime-new.h:337`） › 3.1 `_bucketsAndMaybeMask`：指针与 mask 的融合（第575-597行）
[3] /Users/tommywu/Obsidian/iOS/Runtime/Part 2 - 消息发送与转发.md › 第一部分 · 快速路径（缓存命中） › 1. cache_t 数据结构（`objc-runtime-new.h:337`） › 1.1 `_bucketsAndMaybeMask`：指针与 mask 的融合（第588-610行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runtime.md › Runtime › 消息发送机制 › 方法缓存（第45-81行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c-runtime.md › [Objective-C Runtime](http://yulingtianxia.com/blog/2014/11/05/objective-c-runtime/) › Runtime 基础数据结构 › Class › cache_t（第211-244行）
[6] /Users/tommywu/Obsidian/iOS/Runtime/Part 1 - 对象与类的本质.md › 类的本质：objc_class › 类的四大件：isa / superclass / cache / bits › cache：方法缓存（第807-844行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/objective-c-runtime-运行时之一-类与对象.md › 类与对象基础数据结构 › objc_cache（第100-118行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/kingcos.me/浅尝-objc-msgsend.md › Steps › 消息发送 › 方法缓存（第241-241行）
[9] /Users/tommywu/Obsidian/iOS/Runtime/Part 2 - 消息发送与转发.md › 第一部分 · 快速路径（缓存命中） › 1. cache_t 数据结构（`objc-runtime-new.h:337`） › 1.1 `_bucketsAndMaybeMask`：指针与 mask 的融合（第474-504行）
[10] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Part 2 - 消息发送与转发.before-renumber.md › 【iOS】Runtime - Part 2 && 消息发送：缓存、查找与转发 › 第一部分 · 快速路径（缓存命中） › 3. cache_t 数据结构（`objc-runtime-new.h:337`） › 3.1 `_bucketsAndMaybeMask`：指针与 mask 的融合（第492-513行）
[11] /Users/tommywu/Obsidian/iOS/Runtime/Part 2 - 消息发送与转发.md › 第一部分 · 快速路径（缓存命中） › 3. 缓存的写入与扩容（`objc-cache.mm`） › 3.1 `insert`：哈希落位（:873）（第1456-1499行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/kingcos.me/浅尝-objc-msgsend.md › Steps › 消息发送 › 当未命中缓存时（第251-285行）
