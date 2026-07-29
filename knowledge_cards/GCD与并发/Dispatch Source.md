---
topic: Dispatch Source
group: GCD与并发
generated_at: 2026-07-29T19:39:56
provider: deepseek
---

# Dispatch Source

## 一句话总结

Dispatch Source 是 GCD 中用于监听底层系统对象（如文件描述符、Mach 端口、信号量、进程事件等）的机制，通过事件处理 handler 异步响应变化 [12]。

## 核心原理

- **事件类型**：Dispatch Source 支持多种系统事件，包括 `DISPATCH_SOURCE_TYPE_DATA_ADD`（数据增加）、`DISPATCH_SOURCE_TYPE_DATA_OR`（数据 OR）、`DISPATCH_SOURCE_TYPE_MACH_SEND`/`MACH_RECV`（Mach 端口发送/接收）、`DISPATCH_SOURCE_TYPE_MEMORYPRESSURE`（内存压力）、`DISPATCH_SOURCE_TYPE_PROC`（进程事件）、`DISPATCH_SOURCE_TYPE_READ`（读数据）、`DISPATCH_SOURCE_TYPE_SIGNAL`（信号）、`DISPATCH_SOURCE_TYPE_TIMER`（定时器）、`DISPATCH_SOURCE_TYPE_VNODE`（文件系统变化）、`DISPATCH_SOURCE_TYPE_WRITE`（文件写入）[12]。
- **创建流程**：使用 `dispatch_source_create` 创建，创建后处于挂起（suspended）状态，需调用 `dispatch_resume` 启动事件监听 [12]。通过 ``dispatch_source_set_event_handler` 设置事件处理 handler，通过 `dispatch_source_set_cancel_handler` 设置取消时清理的 handler [12]。
- **文件系统相关 Source**：官方提供 `makeReadSource`、`makeWriteSource`、`makeFileSystemObjectSource` 方法，分别用于读取、写入文件描述符以及监控文件系统事件，对应类型 `DispatchSourceRead`、`DispatchSourceWrite`、`DispatchSourceFileSystemObject` [5][6][8][10]。
- **定时器 Source 的常见封装**：可以通过 `DispatchSource.makeTimerSource(queue:)` 创建定时器，并调用 `scheduleOneshot` 或 `schedule` 设定超时或间隔，最后调用 `resume` 启动 [1][2][4]。示例中封装了 `singleTimer` 便捷方法，传入间隔、leeway（宽容度）和队列 [1][2]。

## 关键细节与易错点

1. **定时器必须 resume 才能触发**：创建 `DispatchSourceTimer` 后，必须调用 `resume()`，否则事件 handler 不会执行 [1][2][4]。
2. **取消的注意事项**：
   - 使用 `dispatch_source_cancel` 取消定时器，并置为 nil [11]。
   - **不能直接 cancel 一个尚未 resume（处于 suspended 状态）的 source**，否则会导致崩溃。如果需要销毁一个可能处于 suspended 状态的 timer，**必须先 resume 再 cancel**：
     ```objc
     dispatch_resume(self.gcdTimer);
     dispatch_source_cancel(self.gcdTimer);
     self.gcdTimer = nil;
     ```
     [11]
3. **避免 retain cycle**：在事件处理 handler 中若需持有 timer 自身，应使用 `[weak res]` 来避免循环引用 [1]。
4. **利用 leeway 降低功耗**：苹果 WWDC 推荐非精确任务**给足 tolerance（leeway）**，系统才能将唤醒合并到其他任务上，从而减少耗电。例如间隔 10 秒的任务允许 5 秒 leeway [3]。
5. **指定队列同步数据**：将定时器调度到与数据访问相同的队列（即作为 mutex 的队列），可以避免无效结果，并简化代码 [2]。
6. **单队列下的同步处理**：在 `TimeoutService` 示例中，所有操作（包括连接和超时 timer）都在同一个串行队列 `self.queue` 上执行，保证了线程安全，消除了竞态条件 [7][9]。

## 高频追问

**Q1: `DispatchSourceTimer` 和 `NSTimer` 相比有什么优势？**
- 材料支持：`DispatchSourceTimer` 可以指定调度队列（如 `DispatchQueue.global()` 或自定义队列），不会受 RunLoop 模式影响 [1][2][4]；支持设置 leeway 合并唤醒以优化能耗 [3]；创建后必须手动 resume，适合子线程使用 [4]。

**Q2: 如何正确销毁一个 GCD 定时器？**
- 参考关键细节第2点：若 timer 已 resume，直接 `dispatch_source_cancel` 并置 nil；若可能处于 suspended 状态，必须先 `dispatch_resume` 再 cancel，否则崩溃 [11]。

**Q3: 为什么有时 `DispatchSourceTimer` 不触发？**
- 可能原因：未调用 `resume()`（创建后默认 suspended）[1][2][4]；或者已经 cancel 但未正确处理 [11]。

**Q4: 如何实现一个子线程中的重复定时器？**
- 使用 `dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, queue)` 创建，设定间隔和 leeway，设置 event handler，然后 `dispatch_resume` [4]。

**Q5: 怎么用 Dispatch Source 监听进程退出？**
- 使用 `DISPATCH_SOURCE_TYPE_PROC`，指定进程 PID 和事件掩码（如 `DISPATCH_PROC_EXIT`），设置 event handler 并在 handler 中处理退出事件，最后 `dispatch_resume` 启动 [12]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/design-patterns-for-safe-timer-usage-cocoa-with-love.md › Ignoring cancelled timers（第158-179行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/design-patterns-for-safe-timer-usage-cocoa-with-love.md › A single queue, synchronized timer（第302-326行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-CPU与后台优化.md › 耗电-CPU与后台优化 › 三、Timer与高频任务优化 › 优化策略 › 2. 合理使用DispatchSourceTimer的tolerance（第104-112行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Timer的注意事项.md › iOS 定时器的注意事项 › 注意事项三：子线程使用定时器 › 解决方案（第287-295行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/dispatch/dispatchsourceread.md › DispatchSourceRead › See Also › Creating a File System Source（第44-51行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/dispatch/dispatchsourcewrite.md › DispatchSourceWrite › See Also › Creating a File System Source（第44-51行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/what-is-reactive-programming-and-why-should-i-use-it-cocoa-with-love.md › An asynchronous task with a timeout（第245-288行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/dispatch/dispatchsource.md › DispatchSource › Topics › Creating a File System Source（第54-62行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/testing-actions-over-time-cocoa-with-love.md › Let’s fill in the TimeoutService implementation（第74-117行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/dispatch/dispatchsourcefilesystemobject.md › DispatchSourceFileSystemObject › See Also › Creating a File System Source（第55-62行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Timer的注意事项.md › iOS 定时器的注意事项 › 注意事项五：正确销毁定时器 › GCD Timer（第362-382行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › Dispatch Source 用GCD监视进程（第815-854行）
