---
topic: Source0与Source1
group: RunLoop
generated_at: 2026-07-29T19:36:26
provider: deepseek
---

# Source0与Source1

## 一句话总结
Source0 是手动触发的事件源，需通过 `CFRunLoopSourceSignal` + `CFRunLoopWakeUp` 主动唤醒 RunLoop 才能处理；Source1 基于 mach port，由内核或消息自动唤醒 RunLoop，处理事件是唤醒流程的一部分。[1][3][5][7]

## 核心原理
- **分类**：事件源（`CFRunLoopSourceRef`）分为 version0 和 version1，对应 Source0 和 Source1。结构体中包含 `_order`（优先级）和 `_runLoops`（CFMutableBagRef，一个 source 可对应多个 runloop）以及联合体 `_context`。[9]
- **Source0（非基于 Port）**：
  - 手动标记待处理：调用 `CFRunLoopSourceSignal` 标记，但**不能主动唤醒 RunLoop**，必须配合 `CFRunLoopWakeUp` 使用。[1][7]
  - 常见来源：`performSelector:onThread:withObject:waitUntilDone:` 跨线程调用、触摸事件的应用内分发（由 Source1 接收后封装成 Source0）、手动创建的 Source0、UI 刷新相关回调（如 `_UIApplicationHandleEventQueue`）。[1][11]
- **Source1（基于 Port）**：
  - 基于 mach port，**能够主动唤醒 RunLoop**。[1][3]
  - 内核自动标记：当 mach port 有消息到达时，内核自动将 source 标记为待处理并唤醒所在的 RunLoop 线程。[12][7]
  - 常见来源：触摸/硬件事件的系统级接收（如 `__IOHIDEventSystemClientQueueCallback`）、基于 port 的进程间通信（如 `PurpleEventCallback`、`notify_port_callback`）。[1][11]
- **事件处理顺序**（基于实验日志）：
  - RunLoop 被唤醒后首先检查唤醒原因，若是 Source1 唤醒，则在 `AfterWaiting` 观察者回调之后、`BeforeTimers` 之前立即执行 Source1 回调；Source0 回调则在后续的 `BeforeSources` 观察者回调之后执行。[5][6]
  - Source0 执行后，当前迭代 `poll` 标志为真，会跳过休眠（`BeforeWaiting` / 真正的 `mach_msg` 等待），用零超时再探一次端口，导致多出一轮空转。[5]

## 关键细节与易错点
1. **Source0 必须同时执行 Signal 和 WakeUp**
   只调用 `CFRunLoopSourceSignal` 而不调用 `CFRunLoopWakeUp`，RunLoop 不会立即处理该 source，事件根本不会到达，直到 RunLoop 因其他原因被唤醒或超时。[5]
2. **Source1 回调的执行时机早于 Source0**
   实验表明：Source1 回调在 `AfterWaiting` 之后、`BeforeTimers` 之前执行；Source0 回调在 `BeforeSources` 之后执行。两者的位置差别是结构性的：Source1 是唤醒 RunLoop 的消息本身，Source0 只是标记位，需等循环重新检查。[5][6]
3. **Source0 处理后会额外空转一轮**
   处理过 Source0 的那一轮 `poll` 标志为真，RunLoop 跳过休眠，用零超时再次探测端口，因此在日志中会看到连续两轮无休眠的迭代（`BeforeWaiting` / `AfterWaiting` 成对消失）。[5]
4. **触摸事件经历 Source1 → Source0 的转换**
   触摸事件的系统级接收由 Source1 完成（如 `__IOHIDEventSystemClientQueueCallback`），之后封装成 Source0 事件（如 `_UIApplicationHandleEventQueue`）在应用内分发。[1][3][11]
5. **一个 source 可以对应多个 runloop**
   结构体 `__CFRunLoopSource` 中以 `CFMutableBagRef` 保存 `_runLoops`，bag 允许重复，说明一个 source 可被添加到多个 runloop 中。[9]
6. **RunLoop 模式影响事件的接收**
   CFRunLoopMode 决定当前接收哪些 source，主线程默认在 `kCFRunLoopDefaultMode` 和 `UITrackingRunLoopMode` 之间切换。若 source 未添加到当前 mode，即使被触发也不会处理。[2][4]

## 高频追问
**Q1：source0 和 source1 的本质区别是什么？**
- 激活方式：source0 需要手动 signal + wakeUp；source1 由内核通过 mach port 消息自动激活。[1][7]
- 唤醒能力：source0 不能主动唤醒 RunLoop；source1 能主动唤醒。[1]
- 事件来源：source0 多为 App 内部事件（如 UI 刷新、performSelector）；source1 来自内核或进程间通信（如触摸事件系统级接收、port 消息）。[1][3]

**Q2：为什么需要区分两者？**
- 系统设计层面，source1 用于处理需要即时响应的外部事件（如触摸、端口消息），由内核驱动保证低延迟；source0 用于内部任务，由应用触发，可通过 RunLoop 的常规迭代处理。[1][5]
- 两者执行时机不同，source1 处理在唤醒后立即执行，source0 需等到 `BeforeSources` 阶段，这种分层允许 Observer 在 `BeforeTimers`/`BeforeSources` 中做预处理。[5][6]

**Q3：触摸事件属于哪个 source？**
- 系统级接收属于 Source1（如 `__IOHIDEventSystemClientQueueCallback`），应用内分发处理属于 Source0（如 `_UIApplicationHandleEventQueue`）。[1][11][3]
- 即硬件触摸事件先通过 mach port（Source1）唤醒 RunLoop，然后内核将事件分发给应用，应用再封装为 Source0 事件等待处理。[1]

**Q4：source1 的回调为什么能在 `AfterWaiting` 后立即执行？**
- 因为 source1 本身就是唤醒 RunLoop 的那条 mach port 消息的处理者。RunLoop 从 `mach_msg` 中返回后，在 `AfterWaiting` 阶段之后立即处理该 port 关联的回调，这是唤醒流程的组成部分。[5][6]

**Q5：source0 和 source1 能相互转换吗？**
- 常见的例子是触摸事件：Source1 接收系统事件后，将其封装成 Source0 事件放入队列等待处理。但这种转换是应用层的行为，底层 source 的类型并不会改变。[1]

**Q6：如何创建一个自定义 source0 或 source1？**
- Source0：调用 `CFRunLoopSourceCreate`，传入 version0 上下文（`CFRunLoopSourceContext`），然后通过 `CFRunLoopAddSource` 添加到 RunLoop 的某个 mode。[1]
- Source1：调用 `CFMachPortCreate` 创建 mach port，并将其包装成 source1（version1 上下文），同样添加到 RunLoop。[5]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的核心组成 › 3. 事件源（CFRunLoopSourceRef）（第99-118行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › 2026-05-14 23:29 RunLoop事件处理与模式切换机制 › 整理后内容（第143-153行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第3167-3221行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › 2026-05-14 23:29 RunLoop事件处理与模式切换机制（第135-141行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 三、source0 和 source1，用实验分清（第178-219行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 三、source0 和 source1，用实验分清（第221-231行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › CFRunLoopSource › Source0和Source1区别（第350-354行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › CFRunLoopSource（第327-348行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › 苹果用 RunLoop 实现的功能（第394-432行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/suelan.github.io/dive-into-cfrunloop.md › Inputs › Input Source - CFRunLoopSource › Two categories of Input Source（第111-115行）
