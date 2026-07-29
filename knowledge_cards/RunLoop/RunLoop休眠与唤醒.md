---
topic: RunLoop休眠与唤醒
group: RunLoop
generated_at: 2026-07-29T19:37:13
provider: deepseek
---

# RunLoop休眠与唤醒

## 一句话总结

RunLoop 的休眠不是用户态的 while 空转，而是通过调用 `mach_msg()` 陷入内核，让线程真正被内核挂起，不消耗 CPU；当有消息到达监听端口（Source1、Timer、GCD 主队列 port）或手动发送消息时，内核将线程唤醒，从 `mach_msg()` 返回继续执行。[2][3][5][12]

## 核心原理

1. **休眠实现**：RunLoop 在即将休眠时调用 `__CFRunLoopServiceMachPort()`，该函数内部调用 `mach_msg()` 并传入 `MACH_RCV_MSG` 选项，监听一个端口集（`waitSet`）。线程从用户态切换到内核态，进入 `mach_msg_trap` 状态被内核挂起，不占用 CPU。[2][5][12]

2. **唤醒机制**：内核通过向监听端口投递消息来唤醒线程。可能的唤醒源包括：
   - 一个基于 port 的 Source1 事件
   - 一个 Timer 到期
   - RunLoop 自身的超时时间到了
   - 被其他调用者手动唤醒（调用 `CFRunLoopWakeUp`，向 `_wakeUpPort` 发送一个空的 mach 消息）[1][5][7]

3. **内核态切换流程**：
   ```
   用户态: mach_msg(MACH_RCV_MSG) → 系统调用 →
   内核态: 线程挂起等待（mach_msg_trap）→
   收到消息 → 唤醒线程 → 返回用户态: mach_msg 返回
   ```[2][3]

4. **Observer 通知**：休眠前通知 Observer `kCFRunLoopBeforeWaiting`；唤醒后通知 `kCFRunLoopAfterWaiting`。[4][5][9][11]

5. **特殊情况**：如果在上一次循环中已经处理过 Source0 且处于 polling 模式，RunLoop 不会真的休眠（`poll ? 0 : TIMEOUT_INFINITY`）[6][12]；另外，在休眠前会快速检查 GCD 主队列的 mach port（`dispatchPort`）上是否有未处理的消息，如果有则跳过休眠直接处理[4][5]。

## 关键细节与易错点

- **不是空转**：`mach_msg()` 休眠与用户态 `while(!hasEvent)` 空转有本质区别——后者持续占用 CPU，而休眠时线程完全被内核挂起。[2]
- **手动唤醒**：`CFRunLoopWakeUp` 通过 `__CFSendTrivialMachMessage` 向 `_wakeUpPort` 发送一条空消息，`mach_msg()` 因此返回。[1][7]
- **休眠前处理的时机**：`kCFRunLoopBeforeWaiting` 由系统 Observer 做了三件重要的事：触发手势识别的回调、执行 UIView/CALayer 的界面更新（Core Animation 提交渲染事务）、对 AutoreleasePool 进行释放与重建。[4][8]
- **唤醒后的处理**：根据 `livePort` 区分唤醒源：如果是 Timer 到期则执行 `__CFRunLoopDoTimers`；如果是 GCD 主队列 port 则执行 `__CFRUNLOOP_IS_SERVICING_THE_MAIN_DISPATCH_QUEUE__`；如果是 Source1 则执行 `__CFRunLoopDoSource1`。[5][9][10]
- **超时机制**：`mach_msg` 的超时参数（`TIMEOUT_INFINITY` 或指定时长）由 RunLoop 的调用模式决定，当超时时间到达时也会唤醒。[5][6]
- **端口集**：`waitSet` 包含多个 port，RunLoop 通过 `livePort` 识别收到的消息来自哪个端口。[5][6]

## 高频追问

**Q1: RunLoop 休眠时到底消耗 CPU 吗？**
A: 不消耗。所有样本采集中，空闲的主线程栈都停在 `mach_msg2_trap`，线程被内核挂起。[12]

**Q2: 为什么说 `mach_msg()` 是 RunLoop 休眠的核心？**
A: `mach_msg` 是 Mach 内核提供的消息接收/发送函数。RunLoop 休眠时调用 `mach_msg(MACH_RCV_MSG)` 监听端口，线程进入内核态等待，直到收到消息才返回。这是 RunLoop 实现无 CPU 消耗等待的基础。[2][5]

**Q3: `kCFRunLoopBeforeWaiting` 和 `kCFRunLoopAfterWaiting` 两个 Observer 通知分别在什么时候触发？**
A: `kCFRunLoopBeforeWaiting` 在调用 `mach_msg` 休眠之前触发；`kCFRunLoopAfterWaiting` 在 `mach_msg` 返回、线程被唤醒后立即触发。[5][9][11]

**Q4: 如何手动唤醒一个休眠中的 RunLoop？**
A: 调用 `CFRunLoopWakeUp(rl)`，它向 RunLoop 的 `_wakeUpPort` 发送一个空的 mach 消息，使休眠在 `mach_msg()` 上的线程立即返回。[1][7]

**Q5: 如果 RunLoop 在休眠前检测到 GCD 主队列有待处理消息，还会休眠吗？**
A: 不会。在正式调用 `mach_msg` 前，RunLoop 会以超时为 0 的非阻塞方式检查 GCD 主队列的 port（`dispatchPort`），如果有待处理消息，则跳过休眠直接进入唤醒后的处理步骤。[4][5]

**Q6: Source0 处理完后会不会有时也不休眠？**
A: 材料中提及，如果 poll 模式为 true（例如 `runMode:beforeDate:` 调用），`__CFRunLoopServiceMachPort` 传入的 timeout 为 0，即非阻塞检查，不会真正进入休眠。[6][12] 此外，当上次 Source0 未处理完毕且 `sourceHandledThisLoop` 为 false 时，也可能进入休眠。具体逻辑需查看源码。[5]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的底层实现 › CFRunLoopWakeUp 的实现（第703-715行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的底层实现 › mach_msg 与休眠机制（第418-463行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › RunLoop相关类和构成（第62-133行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第504-547行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › RunLoop 的内部逻辑（第252-289行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop运行相关源码 › __CFRunLoopRun源码（第891-920行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop运行相关源码 › 手动唤醒runloop的代码（第1049-1069行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-原理.md › 卡顿-原理 › RunLoop如何驱动渲染 › RunLoop渲染调度流程（第370-390行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/cloud.tencent.com/ios-卡顿监测方案总结.md › **RunLoop**（第128-174行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第3167-3221行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的底层实现 › CFRunLoopRunSpecific 与 __CFRunLoopRun 核心逻辑（第469-511行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 四、睡着的时候在干什么（第266-306行）
