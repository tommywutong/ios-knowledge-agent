---
topic: Dispatch Barrier
group: GCD与并发
generated_at: 2026-07-29T19:39:10
provider: deepseek
---

# Dispatch Barrier

## 一句话总结

`dispatch_barrier_async` / `dispatch_barrier_sync` 在**自定义并发队列**上提供读写隔离：等待之前任务完成 → 独占队列执行栅栏块 → 完成后恢复并发；在全局并发队列或串行队列上失效，退化为普通异步/同步提交（但两种来源对退化后的具体行为有冲突）[1][2][4][8][9]。

## 核心原理

- **工作机制**：barrier block 提交后不立即执行，而是等待队列中所有已在执行的 block 全部完成；然后 barrier block 单独执行，此时队列不再调度其他 block；barrier block 执行完毕后，队列恢复并发调度后续提交的 block。[1][2][3][4][6]
- **适用范围**：只对**使用 `dispatch_queue_create` 并传入 `DISPATCH_QUEUE_CONCURRENT` 创建的私有并发队列**有效。在全局并发队列和串行队列上不会起屏障作用。[1][4][5][8][9]
- **典型应用 —— 多读单写**：使用自定义并发队列，读操作通过 `dispatch_sync` 或 `dispatch_async` 提交，写操作通过 `dispatch_barrier_async` 提交，实现多线程同时读、写时独占。[1][3][11]

## 关键细节与易错点

1. **barrier 在非自定义队列上的退化行为（存在冲突）**
   - Apple 官方文档指出：在全局并发队列或串行队列上，`dispatch_barrier_async` 退化为 `dispatch_async`，`dispatch_barrier_sync` 退化为 `dispatch_sync`。[8][9]
   - 而 ming1016 的文章称“效果和 `dispatch_sync` 一样”，[10] 这与 Apple 官方说法矛盾。应以官方文档为准。[8]
   - 串行队列一次只执行一个任务，本身就无需 barrier。[4][5]

2. **`dispatch_barrier_sync` 在并发队列内自调用会导致死锁**
   - 实验证明：在并发队列的 block 中调用 `dispatch_barrier_sync(同一队列)` 会永久挂起，因为 barrier 要求队列上没有正在执行的任务，而当前 block 自身就在队列中运行，条件永不能满足。[7]
   - 因此**写操作应使用 `dispatch_barrier_async`**，避免同步栅栏导致死锁。[11]

3. **读操作使用 `dispatch_sync` 到自定义并发队列是安全的**，不会像串行队列那样产生死锁。因为并发队列上 `dispatch_sync` 只需在调用线程上直接执行，不要求独占队列。[3][7]

4. **自定义并发队列支持 `dispatch_suspend` / `dispatch_resume`**，可用于临时暂停队列调度。[1][12]

5. **Swift 侧文档差异**：`DispatchWorkItemFlags.barrier` 的 Swift 文档只描述在并发队列上的行为，未明确提及全局队列的退化规则。[9]

## 高频追问

**Q1: 多读单写如何用 GCD Barrier 实现？**
A: 创建自定义并发队列；读操作（同步或异步）提交到该队列；写操作使用 `dispatch_barrier_async` 提交。这样读可以多线程并发，写时 barrier 确保隔离。[1][3][11]

**Q2: 为什么不能在全局队列上使用 barrier？**
A: Apple 文档明确说明，全局并发队列不是由自己创建的，barrier 函数在全局队列上行为等同于 `dispatch_async` / `dispatch_sync`，不会起到屏障作用。[8][9]

**Q3: barrier 在串行队列上会怎样？**
A: 串行队列本身一次只执行一个任务，barrier 函数退化为普通异步/同步提交，没有隔离效果。[1][4][5]

**Q4: `dispatch_barrier_sync` 和 `dispatch_barrier_async` 怎么选？**
A: 区别在于是否阻塞当前线程 [1]。但注意：如果在同一自定义并发队列的 block 内调用 `dispatch_barrier_sync`，会导致死锁。[7] 因此写操作推荐用 `dispatch_barrier_async`，读操作用 `dispatch_sync` 安全。[3][11]

**Q5: 除了 GCD barrier，还有哪些多读单写方案？**
A: 材料提到 `pthread_rwlock` 读写锁、`NSLock` + 条件控制、`NSCondition` 条件锁。[1] 但本卡片材料不足，无法提供详细对比。

**Q6: `dispatch_sync` 到自定义并发队列为何不会死锁？**
A: 因为 `dispatch_sync` 在并发队列上不需要独占队列所有权，可以直接在调用线程上执行当前 block，不要求等待队列空闲。[7]

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第1748-1756行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-15 11:07 GCD 中 dispatch_barrier_async 的读写隔离应用（第217-223行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Grand Central Dispatch的使用.md › 8. 单例读写线程安全（第408-448行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/线程同步之读写锁.md › 2. Dispatch Barrier › 2.2 写锁（第117-130行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/线程同步之读写锁.md › 2. Dispatch Barrier › 2.1 并发队列（第107-115行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-15 11:07 GCD 中 dispatch_barrier_async 的读写隔离应用 › 整理后内容（第225-235行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS GCD：队列不是线程，以及死锁的准确边界.md › GCD：队列不是线程，以及死锁的准确边界 › 三、死锁的准确边界 › 并发队列 sync 自己是安全的，barrier_sync 不是（第302-321行）
[8] /Users/tommywu/Obsidian/iOS/10 学习计划/claude工程文件/_研究简报-GCD.md › GCD 研究简报 › 一、必须写进文章的官方原文（逐字，可直接引用） › 1. barrier 在非自建并发队列上的行为 —— 中文圈流传的一处硬错误（第13-23行）
[9] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS GCD：队列不是线程，以及死锁的准确边界.md › GCD：队列不是线程，以及死锁的准确边界 › 四、barrier：一处流传极广的错误（第386-404行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › dispatch_barrier_async使用Barrier Task方法Dispatch Barrier解决多线程并发读写同一个资源发生死锁（第303-348行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/low-level-concurrency-apis.md › Isolation › One Resource, Multiple Readers, and a Single Writer（第170-196行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-10-14-what-s-new-in-gcd.md › (全文)（第36-43行）
