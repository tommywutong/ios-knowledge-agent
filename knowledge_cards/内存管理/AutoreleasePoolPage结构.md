---
topic: AutoreleasePoolPage结构
group: 内存管理
generated_at: 2026-07-29T19:31:03
provider: deepseek
---

# AutoreleasePoolPage结构

## 一句话总结

`AutoreleasePoolPage` 是 Objective-C 自动释放池的底层实现单元，它是一个大小为 4096 字节的虚拟内存页，多个 page 通过 `parent` / `child` 指针构成双向链表，用来管理当前线程中标记为 `autorelease` 的对象。[1][6]

## 核心原理

### 数据结构定义

`AutoreleasePoolPage` 的核心成员变量如下：[1][6]

```cpp
class AutoreleasePoolPage {
    magic_t const magic;               // 校验值，用于验证 page 完整性
    id *next;                          // 栈顶指针，指向下一个可存放对象的位置
    pthread_t const thread;            // 所属线程（每个线程有独立的 autoreleasepool）
    AutoreleasePoolPage * const parent; // 父节点（双向链表）
    AutoreleasePoolPage *child;        // 子节点（双向链表）
    uint32_t const depth;              // 链表深度，从 0 开始递增
    uint32_t hiwat;                    // high water mark，记录最大入栈数量
};
```

- `magic`：用来校验 `AutoreleasePoolPage` 的结构是否完整。[6]
- `next`：指向最新添加的 autoreleased 对象的下一个位置，初始化时指向 `begin()`。[6] 当 `next == begin()` 时 page 为空；当 `next == end()` 时 page 已满。[6]
- `thread`：指向当前线程，每个线程有独立的 autoreleasepool。[1]
- `parent` / `child`：构成双向链表。第一个结点的 `parent` 值为 `nil`，最后一个结点的 `child` 值为 `nil`。[6]
- `depth`：代表深度，从 0 开始，往后递增 1。[6]
- `hiwat`：代表 high water mark。[6]

### 页容量计算

每个 page 大小为 4096 字节（一个虚拟内存页），成员变量占约 56 字节，剩余空间用于存储 autorelease 对象指针。每个指针大小为 8 字节，因此每个 page 大约可以存储 `(4096 - 56) / 8 ≈ 505` 个对象指针。[1][2][9]

这里有个关键细节：`PROTECT_AUTORELEASEPOOL` 宏在发布的 objc4 中根本没有定义，它是给运行时开发者自己重编 libobjc 时用的开关，不会随 Xcode 的 Debug 构建自动打开。所以实践中 4096 这个数值是对的，错的只是把它当成源码里的硬编码常量。[8]

### 哨兵对象（POOL_BOUNDARY）

哨兵对象就是 `nil`（`#define POOL_BOUNDARY nil`）。[8] 每次 `objc_autoreleasePoolPush` 往栈里压一个 `nil` 当边界，并把这个位置的地址返回（即 pool token）；`objc_autoreleasePoolPop` 拿着地址把栈弹回去，沿途每个对象发一次 `release`。[8]

一个 @autoreleasepool 展开来说就是 `objc_autoreleasePoolPush` 和 `objc_autoreleasePoolPop`，这两个函数实际对应的是 `AutoreleasePoolPage::push` 和 `AutoreleasePoolPage::pop`。[5]

### Push 操作流程

`autoreleaseFast` 方法分三种情况选择不同的代码执行：[3]

```c
static inline id *autoreleaseFast(id obj) {
    AutoreleasePoolPage *page = hotPage();
    if (page && !page->full()) {
        return page->add(obj);                 // 热页空间足够，直接添加
    } else if (page) {
        return autoreleaseFullPage(obj, page);  // 热页满了，找或建下一页
    } else {
        return autoreleaseNoPage(obj);          // 一页都还没有，创建热页
    }
}
```

- `hotPage` 可以理解为当前正在使用的 `AutoreleasePoolPage`。[3]

### Pop 操作流程

pop 函数的入参就是 push 函数的返回值，也就是 POOL_SENTINEL 的内存地址（pool token）。当执行 pop 操作时，内存地址在 pool token 之后的所有 autoreleased 对象都会被 release，直到 pool token 所在 page 的 `next` 指向 pool token 为止。[10]

具体步骤：[7][10]
1. 根据传入的哨兵对象地址找到哨兵对象所处的 page。
2. 在当前 page 中，将晚于哨兵对象插入的所有 autorelease 对象都发送一次 `- release` 消息，并向回移动 `next` 指针到正确位置。
3. 从最新加入的对象一直向前清理，可以向前跨越若干个 page，直到哨兵所在的 page。

pop 时会把释放过的槽位涂成 `SCRIBBLE = 0xA3`，在 lldb 里读一块刚排空的池内存，能看到成片的 `0xA3A3A3A3`。[8]

### 内存布局

每个 page 的内存布局如下：[2]

```
AutoreleasePoolPage (4096 bytes):
┌─────────────────────────────────┐  ← page 起始地址
│  magic, next, thread, parent,   │
│  child, depth, hiwat            │     成员变量区域（约 56 字节）
├─────────────────────────────────┤
│  POOL_BOUNDARY (nil)            │  ← 外层 @autoreleasepool 的哨兵
│  obj1 指针                      │
│  obj2 指针                      │     外层池管理的对象
│  obj3 指针                      │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│  POOL_BOUNDARY (nil)            │  ← 内层嵌套 @autoreleasepool 的哨兵
│  obj4 指针                      │     内层池管理的对象
│  ...                            │
│  (空闲空间)                     │  ← next 指针指向此处
└─────────────────────────────────┘
```

### 线程关联

- 每个线程的 autoreleasepool 是一个指针的堆栈，每一个指针代表一个需要 release 的对象或 POOL_SENTINEL。[6]
- Thread-local storage（线程局部存储）指向 hot page，即最新添加的 autoreleased 对象所在的那个 page。[6]
- GCD 每跑一个 block 就 push/pop 一次，绝大多数 block 里一个对象都不入池。[12]

## 关键细节与易错点

### 1. 页大小不是硬编码常量 4096

源码里写的不是字面常量 4096，而是 `PROTECT_AUTORELEASEPOOL ? PAGE_MAX_SIZE : PAGE_MIN_SIZE`。但 `PROTECT_AUTORELEASEPOOL` 在发布的 objc4 里根本没有定义，它是给运行时开发者自己重编 libobjc 时用的开关，不会随 Xcode 的 Debug 构建自动打开。实践中 4096 这个数值是对的，错的只是把它当成源码里的硬编码常量。[8]

### 2. "栈顶指针"确切含义

虽然 `next` 常被称作"栈顶指针"，但它的确切含义是"指向下一个可存放对象的位置"，初始化时指向 `begin()`。[6] `next` 是真正可使用的栈指针，指向的是 page 内部的 `begin()` 到 `end()` 之间的内存区域。

### 3. 双向链表是实打实的

`parent` 和 `child` 串成双向链表，不是单链表。向后遍历（通过 `child`）用来查找有空间的 page 来存储新的 autorelease 对象；向前遍历（通过 `parent`）在 pop 操作时回溯释放对象，释放空 page 时返回到前一个 page。[1]

### 4. 一页 505 个，但不是所有平台都成立

页容量由四件事决定：`AutoreleasePoolPage::SIZE`、页头结构体的大小、指针宽度，以及哨兵占不占槽。四个都得单独确认。[4]
- `(4096−56)/8 = 505` 槽，首槽给哨兵剩 504，算术成立。[9]
- `objc_debug_autoreleasepoolpage_begin_offset` = 56，`objc_debug_autoreleasepoolpage_ptr_mask` = `0x0f00ffffffffffff`，出货 libobjc 确实和公开 objc4 的 `0xffffffffffff` 不一样。[9]

### 5. 池的释放不是所有对象马上释放

Autorelease Pool（自动释放池）是 iOS 内存管理中的一种延迟释放机制。当对象被标记为 autorelease 时，它不会立即释放，而是被注册到当前的 autoreleasepool 中，等到池销毁时统一调用 `release`。[11]

| 释放方式 | 创建方式 | 释放时机 | 是否依赖 RunLoop |
|---------|---------|---------|----------------|
| 立即释放 | `alloc/init`、`new`、`copy` | 引用计数归零时立即 dealloc | 否 |
| 延迟释放 | 便利构造方法如 `stringWithFormat:` | autoreleasepool 销毁时 | 主线程依赖 |

### 6. RunLoop 中的池管理

App 启动的时候会在主 Runloop 里面注册两个观察者和一个回调函数：[5]
- 第一个 Observe 观察到 entry 即将进入 loop 的时候，会调用 `_objc_autoreleasePoolPush()` 创建自动释放池，优先级最高，保证在所有回调方法之前。
- 第二个 Observe 观察到即将进入休眠或者退出的时候，当监听到 Beforewaiting 的时候，调用 `_objc_autoreleasePoolPop()` 和 `_objc_autoreleasePoolPush()` 释放旧的创建新的，当监听到 Exit 的时候调用 `_objc_autoreleasePoolPop` 释放 pool，优先级最低，发生在所有回调函数之后。

### 7. 自动释放优化

在现代 ARC 代码中，编译器会进行 "autorelease elision" 优化，进一步减少 autorelease 对象的数量，因此大部分对象都是立即释放的。[11]

## 高频追问

**Q1: 一页到底能存多少个对象？**

A: 每个 page 大小为 4096 字节，成员变量占约 56 字节，剩余空间用于存储 autorelease 对象指针。每个指针大小为 8 字节，因此每个 page 大约可以存储 `(4096 - 56) / 8 ≈ 505` 个对象指针。[1][2] 首槽如果给了哨兵，则剩 504 个可用槽位。[9] 注意这个数字在特定平台（如 iOS arm64）上成立，页容量由 `AutoreleasePoolPage::SIZE`、页头结构体的大小、指针宽度和哨兵占不占槽共同决定。[4]

**Q2: 哨兵地址被返回后是怎么用来释放的？**

A: 每次 `objc_autoreleasePoolPush` 返回的就是这个哨兵对象的地址，被 `objc_autoreleasePoolPop` 作为入参。pop 时根据传入的哨兵对象地址找到哨兵对象所处的 page，在当前 page 中将晚于哨兵对象插入的所有 autorelease 对象都发送一次 `- release` 消息，并向回移动 `next` 指针到正确位置。可以向前跨越若干个 page，直到哨兵所在的 page。[7][10]

**Q3: pop 是怎么遍历释放多个 page 内的对象的？**

A: 从最新加入的对象一直向前清理，可以向前跨越若干个 page，直到哨兵所在的 page。[7] 每删除一页就修正双向链表的指针，将当前 page 返回给系统，并修改上一层 page 的 `child` 指针为 `nil`。[5]

**Q4: 嵌套的 autoreleasepool 是如何实现的？**

A: 嵌套的 @autoreleasepool 在底层就是栈里多个哨兵，天然支持。[8] 每次进入 @autoreleasepool 时 push 一个 POOL_BOUNDARY，退出时从栈顶开始对每个对象调用 `release`，直到遇到对应的 POOL_BOUNDARY。[11]

**Q5: 自动释放池和线程是什么关系？**

A: 每一个线程都有自己独立的 autoreleasepool，通过 Thread-local storage（线程局部存储）指向本线程的 hot page。[1][6] 线程之间不共用自动释放池。

**Q6: page 满了之后如何处理？**

A: 当有 hotPage 且当前 page 已满时，调用 `autoreleaseFullPage` 初始化一个新的 page，然后调用 `page->add(obj)` 将对象添加至新的 page 中。[3]

**Q7: pop 操作后，已经清空的 page 会被销毁吗？**

A: 会。pop 操作会释放栈中的对象并修正双向链表的指针，每删除一页就修正双向链表的指针，将其返回给系统。[5][7]

**Q8: 什么情况下会触发 `autoreleaseNoPage`？**

A: 无 hotPage 时，调用 `autoreleaseNoPage` 创建一个 hotPage，然后调用 `page->add(obj)` 将对象添加至自动释放池中。[3] 这种情况发生在第一次使用 autoreleasepool 时。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 四、自动释放池（Autorelease Pool） › 底层实现 › AutoreleasePoolPage结构（第542-561行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 四、自动释放池（Autorelease Pool） › 底层实现 › 内存布局（第563-588行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/blog.csdn.net/objective-c之autorelease-pool底层实现原理记录-双向链表-以及在runloop中是如何参与进去的.md › objc_autoreleasePoolPush (Push操作)（第139-175行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS AutoreleasePool：哨兵、页链表与 RunLoop 的关系.md › AutoreleasePool：哨兵、页链表与 RunLoop 的关系 › 二、一页 505 个，这个数字在哪些平台上成立（第102-104行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/blog.csdn.net/objective-c之autorelease-pool底层实现原理记录-双向链表-以及在runloop中是如何参与进去的.md › 总结：（第235-255行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/leichunfeng/objective-c-autorelease-pool-的实现原理.md › Objective-C Autorelease Pool 的实现原理 › AutoreleasePoolPage（第162-186行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/sunnyxx/黑幕背后的autorelease-sunnyxx的技术博客.md › Autorelease原理 › 释放时刻（第97-111行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：MRC 的所有权规则.md › MRC 的所有权规则：retain、release 与 autorelease › 五、autorelease 池的实现（第323-348行）
[9] /Users/tommywu/Obsidian/iOS/10 学习计划/claude工程文件/_执行进度（Claude 代写）.md › 代写执行进度台账 › 三、文档清单（32 篇待写 + 2 篇已有 = 34） › 第五周：RunLoop、AutoreleasePool、响应者链与生命周期（第290-294行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/leichunfeng/objective-c-autorelease-pool-的实现原理.md › Objective-C Autorelease Pool 的实现原理 › AutoreleasePoolPage › pop 操作（第354-384行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 七、常见面试题 › Q7: 请详细介绍Autorelease Pool的工作机制和底层实现（第1002-1046行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS AutoreleasePool：哨兵、页链表与 RunLoop 的关系.md › AutoreleasePool：哨兵、页链表与 RunLoop 的关系 › 一、先把池打印出来（第90-100行）
