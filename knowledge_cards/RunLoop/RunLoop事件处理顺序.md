---
topic: RunLoop事件处理顺序
group: RunLoop
generated_at: 2026-07-29T19:37:33
provider: deepseek
---

# RunLoop事件处理顺序

## 一句话总结
RunLoop 是一个 do-while 循环，在 **外层启动入口**（如 `CFRunLoopRun`、`runMode:beforeDate:`）和 **内层 `CFRunLoopRunSpecific` 调用** 两层结构下，按固定顺序处理 Observer、Timer、Source0、Source1、Blocks 五类事件，Core Animation 渲染事务在休眠前（BeforeWaiting）统一提交。[4][7][11]

---

## 核心原理

### 1. 两层循环结构
- **外层循环**由启动 API 决定：
  - `runMode:beforeDate:` 只运行一次内层循环 [11]
  - `CFRunLoopRun()` 会反复调用 `CFRunLoopRunSpecific`，外层检查返回值后可被 `CFRunLoopStop()` 停止 [11]
  - `[NSRunLoop run]` 是 `while(1)` 无条件循环，`CFRunLoopStop()` 只能停止当前内层运行，外层会再次进入 [11]
- **内层循环**即一次 `CFRunLoopRunSpecific` 调用，负责事件分发 [4][12]

### 2. 一次 `CFRunLoopRunSpecific` 内的事件处理顺序

| 步骤 | 事件/动作 | 说明 |
|------|-----------|------|
| 1 | 通知 Observer：`kCFRunLoopEntry` | 进入 RunLoop，AutoreleasePool 在此创建 [7][10] |
| → 进入 `__CFRunLoopRun` do-while | | |
| 2 | 通知 Observer：`kCFRunLoopBeforeTimers` | 即将处理 Timer [4][7] |
| 3 | 通知 Observer：`kCFRunLoopBeforeSources` | 即将处理 Source0 [4][7] |
| 4a | 处理 Blocks（通过 `CFRunLoopPerformBlock` 提交到当前 Mode）[7][10] |
| 4b | 处理 Source0（如 `performSelector:onThread:`、手动触发的 Source0）[7][10] |
| 4c | 如果 4b 处理了 Source0，则再次处理 Blocks（因为 Source0 回调可能提交新 block）[7][10] |
| 5 | 检查 GCD 主队列消息：若有就绪，跳过休眠跳转到步骤 9 [4][7] |
| 6 | 通知 Observer：`kCFRunLoopBeforeWaiting` | 即将休眠。Core Animation 在此提交渲染事务（`CA::Transaction::commit`）[3][6] |
| 7 | 线程休眠（`mach_msg`），等待唤醒源：Source1、Timer 到时、超时、外部手动唤醒 [4] |
| 8 | 通知 Observer：`kCFRunLoopAfterWaiting` | 从休眠中唤醒 [4] |
| 9 | 处理唤醒时收到的消息：Timer → 处理 Timer；`dispatch_async` 到主队列 → 执行 block；Source1 → 处理 Source1 [4] |
| 10 | 处理 Blocks（步骤 9 的回调可能通过 `CFRunLoopPerformBlock` 提交了新 block）[4] |
| 11 | 判断：继续循环 → 回到步骤 2；退出循环 → 步骤 12 [4] |
| 12 | 通知 Observer：`kCFRunLoopExit` | 退出 RunLoop [4] |

### 3. Mode 与事件筛选
- `CFRunLoopMode` 决定当前接收哪些 source/timer/observer [1][2]
- 主线程默认在 **NSDefaultRunLoopMode** 和 **UITrackingRunLoopMode** 之间切换 [1]
- 滚动 ScrollView 时主线程进入 `UITrackingRunLoopMode`，`NSTimer` 默认添加在 `NSDefaultRunLoopMode`，因此 timer 停止触发 [1][5]

---

## 关键细节与易错点

### 1. Source0 与 Source1 的本质区别
- **Source0**：不依赖内核端口，需手动标记待处理（`CFRunLoopSourceSignal`）并唤醒 RunLoop [7]
- **Source1**：基于 mach port 的内核事件，唤醒时由内核自动触发 [9]

### 2. Blocks 的两次处理时机
- 第一次在步骤 4a（处理 Source0 之前）[7]
- 第二次在步骤 4c（如果处理了 Source0）和步骤 10（休眠唤醒后）[4][7]

### 3. Core Animation 事务提交节点
- 观察者回调为 `CA::Transaction::observer_callback`，activities = `kCFRunLoopBeforeWaiting | kCFRunLoopExit`，order = 2000000 [3]
- 意味着 **所有 UI 修改在休眠前统一提交**，若本轮事件处理耗时过长，渲染会被推迟导致掉帧 [3][6]

### 4. GCD 主队列的特殊处理
- 步骤 5 使用零超时 `mach_msg` 快速探测主队列 mach port，有消息则跳过休眠直接到步骤 9，避免不必要的休眠-唤醒开销 [7]

### 5. Timer 与 Mode 切换的陷阱
- `NSTimer` 默认加入当前 RunLoop 的 defaultMode，滚动时 timer 不触发 [1][5]
- 解决：将 Timer 添加到 `NSRunLoopCommonModes`（同时覆盖 default 和 tracking）或使用 GCD Timer [8]
- 子线程创建 `NSTimer` 需先启动子线程 RunLoop，否则 timer 不会触发 [8]

### 6. AutoreleasePool 的创建时机
- 在 `kCFRunLoopEntry` 通知后创建 [7][10]

---

## 高频追问

### Q1: 滚动 ScrollView 时为什么 NSTimer 会停？
因为主线程 RunLoop 从 `NSDefaultRunLoopMode` 切换到 `UITrackingRunLoopMode`，而 NSTimer 默认只注册在 default 对应的 mode 下，所以无法被触发。[1][5]

### Q2: 如果 RunLoop 的事件处理阶段耗时过长，会发生什么？
本轮 Source0/Timer 处理时间过长会使 RunLoop 无法及时进入休眠前的 `BeforeWaiting` 阶段，Core Animation 事务无法按时提交，导致下一帧无法合成，表现为掉帧。[3][6]

### Q3: 什么是 CommonModes？
CommonModes 是一个**标记集合**，并非独立 mode。将 Source/Observer/Timer 添加到 CommonModes 等效于添加到所有被标记为 common 的 mode（如 `kCFRunLoopDefaultMode` 和 `UITrackingRunLoopMode`）上。[9]

### Q4: 如何手动触发一次 RunLoop 立即处理 Source0？
调用 `CFRunLoopSourceSignal(source)` 标记 Source0 为待处理，再调用 `CFRunLoopWakeUp(runLoop)` 唤醒目标线程的 RunLoop。[7]

### Q5: 子线程保活应该用什么 API？为什么不用 `[NSRunLoop run]`？
推荐使用 `runMode:beforeDate:` 配合条件判断，或 `CFRunLoopRun()`（可用 `CFRunLoopStop()` 停止）。`[NSRunLoop run]` 是 `while(1)` 无条件循环，`CFRunLoopStop()` 只能停止当前一轮内层运行，外层还会再次进入，导致无法可靠停止。[11]

### Q6: RunLoop 的 Observer 可以注册哪些活动（activities）？
`kCFRunLoopEntry`、`kCFRunLoopBeforeTimers`、`kCFRunLoopBeforeSources`、`kCFRunLoopBeforeWaiting`、`kCFRunLoopAfterWaiting`、`kCFRunLoopExit`。[4][7]

### Q7: 如何验证一次 RunLoop 中的事件顺序？
在主线程注册一个 Observer，打印所有活动的回调。材料中未给出具体打印代码，但提到实验方法：注册 observer 打印 entry、before timers、before sources、before waiting、after waiting、exit。[9]

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › 2026-05-14 23:29 RunLoop事件处理与模式切换机制（第135-141行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › 2026-05-14 23:29 RunLoop事件处理与模式切换机制 › 整理后内容（第143-153行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/UIKit 与渲染/iOS UIView 与 CALayer：三棵树、绘制流水线与离屏渲染.md › UIView 与 CALayer：三棵树、绘制流水线与离屏渲染 › 六、攒到一次提交 › 是谁在跑一轮 RunLoop 的时候来收账（第465-478行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的运行流程（第269-299行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 3. Run Loop 的组成 › 3.5 Run Loop 内部逻辑（第290-306行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-原理.md › 卡顿-原理 › RunLoop如何驱动渲染 › RunLoop渲染调度流程（第370-390行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的运行流程 › 流程详解（第301-348行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第606-633行）
[9] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第五周：RunLoop、AutoreleasePool、响应者链与生命周期 › 本周精读路线 › Day 1｜RunLoop 先学“一轮发生什么”（对应 W4-02）（第485-496行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第464-502行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › 常见面试题 › Q3: RunLoop 的运作流程是怎样的？（第1086-1101行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的底层实现 › CFRunLoopRunSpecific 与 __CFRunLoopRun 核心逻辑（第465-467行）
