---
topic: RunLoop与线程
group: RunLoop
generated_at: 2026-07-29T19:35:41
provider: deepseek
---

# RunLoop与线程

## 一句话总结

每个线程有唯一对应的 RunLoop 对象，通过全局字典 `__CFRunLoops` 以线程（`pthread_t`）为 Key 存储；采用懒加载创建，主线程由 `UIApplicationMain` 自动获取并启动，子线程需在内部首次调用 `CFRunLoopGetCurrent()` 时创建；RunLoop 的销毁发生在线程结束时 [1][2][3][7]。

## 核心原理

1. **一对一映射**：线程和 RunLoop 的关系保存在全局 `CFMutableDictionaryRef` 中，key 是 `pthread_t`，value 是 `CFRunLoopRef` [2][4][7]。
2. **懒加载**：线程刚创建时没有 RunLoop，只有第一次主动获取（`CFRunLoopGetCurrent` / `CFRunLoopGetMain`）时才通过 `_CFRunLoopGet0()` 创建；如果不获取，则一直没有 [1][2][3][7]。
3. **获取方式**：
   - 主线程：`CFRunLoopGetMain()` 内部调 `_CFRunLoopGet0(pthread_main_thread_np())` [2][4][7]。
   - 当前线程：`CFRunLoopGetCurrent()` 内部调 `_CFRunLoopGet0(pthread_self())`，**必须在当前线程内部调用**才能获取当前线程的 RunLoop（主线程没有此限制，但一般无必要在子线程获取主线程 RunLoop）[2][6][7]。
4. **主线程自动启动**：主线程的 RunLoop 由 `UIApplicationMain` → `GSEventRunModal` → `CFRunLoopRunSpecific` 调用链自动获取并启动 [1][3]。
5. **RunLoop 的结构**：处理四类事物——Sources（source0 需手动触发，source1 基于 mach port）、Timers（toll-free bridged 的 NSTimer）、Observers（观察 RunLoop 状态）、Blocks（`CFRunLoopPerformBlock` 添加）[10]；它们都必须关联特定的模式（mode），模式起到筛选作用 [10]。
6. **Common Modes**：`kCFRunLoopCommonModes` 并非独立模式，而是一个模式的集合；可以通过 `CFRunLoopAddCommonMode` 将模式加入该集合；若添加 source/timer/observer/block 时指定 `kCFRunLoopCommonModes`，则会被分别添加到集合中的每一个模式；`kCFRunLoopDefaultMode` 默认在 common modes 中 [10]。

## 关键细节与易错点

- **启动与运行**：仅仅创建 RunLoop 对象并不会使其运行，还需要调用运行函数（如 `CFRunLoopRun`）才能启动事件循环；主线程在 `UIApplicationMain` 内部已经运行起来 [1][3][10]。
- **子线程获取限制**：`CFRunLoopGetCurrent()` 在内部通过 `_CFGetTSD` 检查当前线程的 RunLoop，不存在则调用 `_CFRunLoopGet0(pthread_self())`，因此必须在子线程内部调用；不能在其他线程直接获取子线程的 RunLoop [6][11]。
- **运行期限**：RunLoop 在第一次获取时创建，在线程结束时销毁 [2][3][7]。系统通过 `_CFSetTSD` 注册销毁回调 `__CFFinalizeRunLoop`，在线程退出时自动释放 RunLoop [7]。
- **NSRunLoop 与 CFRunLoop**：`NSRunLoop` 是 Cocoa 框架的 Objective-C 封装，**非线程安全**，必须在其所属线程的上下文中调用；`CFRunLoop` 是 Core Foundation 的 C API，线程安全，使用 `CFRunLoopRef` 引用 [5]。
- **GCD 与 RunLoop**：GCD（libDispatch）管理的线程默认没有 RunLoop；只有向主线程分发 block 时，libDispatch 会向主线程 RunLoop 发送消息，在 `__CFRUNLOOP_IS_SERVICING_THE_MAIN_DISPATCH_QUEUE__` 回调中执行 block；dispatch 到其他线程时仍然由 libDispatch 自行处理，不涉及 RunLoop [9]。
- **主线程 RunLoop 的首次创建**：在 `_CFRunLoopGet0` 中，若全局字典 `__CFRunLoops` 还不存在，会先创建该字典，并立即为主线程创建一个 RunLoop 并存入字典（调用 `__CFRunLoopCreate(pthread_main_thread_np())`），之后才返回给调用方 [2][4][7]。这意味着即使子线程从未获取，主线程的 RunLoop 也已在第一次调用 `CFRunLoopGetMain` 或 `CFRunLoopGetCurrent` 时（若当前线程是主线程）被创建。
- **Common Modes 的误解**：不要把 `kCFRunLoopCommonModes` 当作一个实际存在的 mode，它是一个 “标记集合”，内部逻辑会将事件添加到集合中的各个 mode [10]。

## 高频追问

### Q1：如何让子线程保活？
**回答依据**：RunLoop 可以使线程在没有事件时休眠，有事件时唤醒处理，从而让线程的入口函数不会立即 return，实现线程保活 [5]。具体做法是在子线程内部获取其 RunLoop 并添加一个 Input Source（如 NSTimer 或 mach port source）后运行 RunLoop，否则 RunLoop 会因为无事件源而直接退出（材料未给出完整代码实现，仅说明原理）[5][7]。

### Q2：子线程的 RunLoop 可以手动销毁吗？
**回答依据**：RunLoop 的销毁发生在线程结束时，由系统自动调用 `__CFFinalizeRunLoop` 回调 [2][3][7]。材料中没有提供手动提前销毁 RunLoop 的方法或接口。

### Q3：主线程 RunLoop 是什么时候创建的？
**回答依据**：主线程 RunLoop 在全局字典首次初始化时（`_CFRunLoopGet0` 第一次被调用时）就被主动创建并存入字典，然后由 `UIApplicationMain` 内部的调用链自动获取并启动 [1][3][4][7]。

### Q4：`_CFRunLoopGet0` 的线程安全如何保证？
**回答依据**：`_CFRunLoopGet0` 内部使用 `__CFLock(&loopsLock)` 和 `__CFUnlock(&loopsLock)` 加锁访问全局字典 `__CFRunLoops`，确保多线程环境下字典的读写安全 [2][4]。

### Q5：为什么主线程不需要手动调用 `CFRunLoopRun`？
**回答依据**：`UIApplicationMain` 内部调用 `GSEventRunModal` → `CFRunLoopRunSpecific` 启动了主线程的 RunLoop [1][3]。但材料未说明子线程是否必须手动运行，只提到 RunLoop 需要运行起来才能处理事件 [10]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 与线程的关系（第18-33行）
[2] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 4. Run Loop 的使用 › 4.1 获取 Run Loop（第419-462行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › 常见面试题 › Q1: RunLoop 和线程的关系？（第1060-1066行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop与线程关系 › _CFRunLoopGet0()函数源码（第173-212行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/threading-programming-guide-1.md › [Threading Programming Guide(1)](http://yulingtianxia.com/blog/2017/08/28/Threading-Programming-Guide-1/) › 线程相关概念 › 苹果系统的支持 › Run Loops（第112-123行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop与线程关系（第141-145行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › RunLoop 与线程的关系（第71-112行）
[9] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 7. 使用 demo 演示如何使用（第734-753行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/desgard.com/run-loop-记录与源码注释-作者kylin.md › Run Loop 记录与源码注释 › CFRunLoop（第49-83行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop与线程关系 › 获取子线程的runloop（第159-169行）
