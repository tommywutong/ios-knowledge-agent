---
topic: Timer与Observer
group: RunLoop
generated_at: 2026-07-29T19:36:53
provider: deepseek
---

# Timer与Observer

## 一句话总结

Timer 依赖 RunLoop 驱动，添加到特定 Mode 下才能触发回调；Observer 监听 RunLoop 状态变化，在关键时机（如 BeforeWaiting）执行系统或开发者注册的任务（如 Core Animation 渲染提交、空闲任务分派）[2][4][5]。

## 核心原理

### 1. Timer 在 RunLoop 中的处理流程

RunLoop 每一轮迭代的处理顺序：
1. 通知 Observer `kCFRunLoopBeforeTimers` —— 此时 Timer 尚未处理 [1][11]
2. 通知 Observer `kCFRunLoopBeforeSources`
3. 处理 Blocks 和 Source0
4. 若有 GCD 主队列消息就绪，跳至步骤 9
5. 通知 Observer `kCFRunLoopBeforeWaiting`
6. 线程休眠（`mach_msg`）
7. 唤醒后通知 Observer `kCFRunLoopAfterWaiting`
8. 根据唤醒原因处理事件：Timer 到时则调用 `__CFRunLoopDoTimers()`，GCD 主队列则执行 block，Source1 则处理 [4][5]
9. 处理 Blocks（步骤 8 中可能新提交的 block）
10. 循环判断 [5]

**关键时序**：Timer 的回调实际发生在 `AfterWaiting` 之后、下一次 `BeforeTimers` 之前。`BeforeTimers` 的字面意思是“即将处理 Timer”，但触发时本轮 Timer 尚未处理，真正处理的是上一次睡醒后到期的 Timer [11]。

### 2. RunLoop Mode 对 Timer 的影响

- 主线程默认在 `kCFRunLoopDefaultMode`（NSDefaultRunLoopMode）和 `UITrackingRunLoopMode` 之间切换 [10]
- 当 ScrollView 滑动时，主线程 RunLoop 切换到 `UITrackingRunLoopMode`，添加在 DefaultMode 下的 Timer 不会触发 [1][9][10]
- 解决方案：将 Timer 添加到 `NSRunLoopCommonModes`（同时覆盖 Default 和 Tracking Mode），或使用不依赖 RunLoop 的 GCD Timer [1]

### 3. Observer 的类型与触发时机

CFRunLoopObserver 可监听六种活动 [2][6]：

| 状态位 | 名称 | 含义 |
|--------|------|------|
| `kCFRunLoopEntry` (1UL << 0) | 即将进入 RunLoop | 在 `CFRunLoopRunSpecific` 入口触发，仅一次 [11] |
| `kCFRunLoopBeforeTimers` (1UL << 1) | 即将处理 Timer | 每轮循环开始，但 Timer 尚未处理 [11] |
| `kCFRunLoopBeforeSources` (1UL << 2) | 即将处理 Source | 处理 Source0 之前 [5] |
| `kCFRunLoopBeforeWaiting` (1UL << 5) | 即将进入休眠 | 休眠前，系统在此做批量处理 [4][7] |
| `kCFRunLoopAfterWaiting` (1UL << 6) | 刚从休眠中唤醒 | 唤醒后，事件处理前 [5] |
| `kCFRunLoopExit` (1UL << 7) | 即将退出 RunLoop | 在 `CFRunLoopRunSpecific` 出口触发，仅一次 [11] |
| `kCFRunLoopAllActivities` (0x0FFFFFFFU) | 监听所有状态 | 常用调试 [2] |

### 4. Observer 的典型系统应用

- **Core Animation 渲染提交**：注册为 Observer，activities `0xa0` = `kCFRunLoopBeforeWaiting | kCFRunLoopExit`，order = 2000000（很高），回调为 `CA::Transaction::observer_callback`。在 RunLoop 即将休眠或退出时，将本循环中所有 UI 修改合并成一次 `CATransaction` 提交给 Render Server [3][7]。
- **手势识别批量处理**：`UIGestureRecognizer` 在 `kCFRunLoopBeforeWaiting` 时由系统 Observer 统一触发 `_UIGestureRecognizerUpdate` [4]。
- **AutoreleasePool 释放与重建**：在 `kCFRunLoopBeforeWaiting` 时释放旧池并创建新池 [4]。

### 5. 开发者利用 Observer 的常见场景

- **主线程空闲时执行任务**：在 `kCFRunLoopBeforeWaiting` 时从任务队列取出有限数量任务执行，避免影响主线程响应性 [1][8]。
- **卡顿监控**：通过比较相邻两次 `kCFRunLoopBeforeTimers` 回调的时间间隔，判断主线程是否长时间阻塞 [12]。

## 关键细节与易错点

1. **Timer 在子线程不工作**：子线程的 RunLoop 默认不启动，必须将 Timer 加入当前线程 RunLoop 并手动启动（如 `CFRunLoopRun()`），否则 Timer 不会触发 [1]。

2. **Timer 循环引用**：NSTimer/CADisplayLink 使用 target-action 模式会强引用 target，若 target 又持有 timer 则形成循环引用。解决方案：使用 Block API（iOS 10+）配合 weak-strong dance；使用 NSProxy 弱引用 target；或改用 GCD Timer [1]。

3. **BeforeTimers 命名误导**：`kCFRunLoopBeforeTimers` 触发时，本轮 Timer 尚未处理，不能作为 Timer 即将执行的确定信号。Timer 回调在 `AfterWaiting` 之后、下一次 `BeforeTimers` 之前 [11]。

4. **Entry 和 Exit 不属于循环迭代**：它们只在 `CFRunLoopRunSpecific` 的一次完整调用中触发，不在 do-while 循环内部。因此卡顿监控不应以 `Entry` 作为一轮开始，而应以 `BeforeTimers` [11]。

5. **Observer 的 order 影响执行顺序**：Core Animation 的 Observer 使用 order = 2000000，确保它在同一时机的其他 Observer 之后执行，从而收集完整状态 [3]。

6. **GCD Timer 不依赖 RunLoop**：不需要添加到 RunLoop，也不会受 Mode 切换影响 [1]。

## 高频追问

**Q1:NSTimer 在滑动 ScrollView 时为什么停止？如何解决？**

- 原因：NSTimer 默认添加在 `NSDefaultRunLoopMode`，滑动时主线程 RunLoop 切换到 `UITrackingRunLoopMode`，DefaultMode 下的 Timer 无法触发 [1][9][10]。
- 解决方案：使用 `NSRunLoopCommonModes`（覆盖 Default 和 Tracking），或改用 GCD Timer [1]。

**Q2:如何利用 RunLoopObserver 实现卡顿监控？**

- 在 `kCFRunLoopBeforeTimers` 或 `kCFRunLoopBeforeWaiting` 注册 Observer，记录时间戳。若两次回调间隔超过阈值（如 50ms），说明主线程卡顿 [12]。
- 注意：不应以 `kCFRunLoopEntry` 作为轮次开始，因为 Entry 不参与循环迭代 [11]。

**Q3:Core Animation 的渲染事务在 RunLoop 的哪个时机提交？**

- 在 `kCFRunLoopBeforeWaiting`（即将休眠）时，由注册的 Observer `CA::Transaction::observer_callback` 统一提交（order=2000000 确保最后执行）。若主线程被阻塞，无法进入该阶段，渲染会延迟甚至掉帧 [3][7]。

**Q4:NSTimer 在子线程中正确使用方式？**

- 子线程 RunLoop 默认不运行，需先创建 Timer 并加入当前 RunLoop（如 `[[NSRunLoop currentRunLoop] addTimer:forMode:]`），再调用 `CFRunLoopRun()` 或 `runMode:beforeDate:` 启动 [1]。
- 不建议直接使用 `[[NSRunLoop currentRunLoop] run]` 做可停止的保活，因其外层循环难以退出 [1]。

**Q5:Timer 回调在 RunLoop 流程中具体在哪一刻执行？**

- Timer 到期后，RunLoop 从休眠唤醒（`AfterWaiting`），然后根据唤醒原因调用 `__CFRunLoopDoTimers()` 执行回调。此时尚未进入下一次 `BeforeTimers` [11]。

---

*本卡片材料不足：关于 NSTimer 的精度与 RunLoop 循环时间的关系、CADisplayLink 与 RunLoop 的详细绑定方式、Observer 的 order 优先级冲突等未见材料明确说明。*

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第606-633行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的核心组成 › 6. 观察者（CFRunLoopObserverRef）（第217-267行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/UIKit 与渲染/iOS UIView 与 CALayer：三棵树、绘制流水线与离屏渲染.md › UIView 与 CALayer：三棵树、绘制流水线与离屏渲染 › 六、攒到一次提交 › 是谁在跑一轮 RunLoop 的时候来收账（第465-478行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第504-547行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的运行流程（第269-299行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › RunLoop observer（第573-589行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-原理.md › 卡顿-原理 › RunLoop如何驱动渲染 › RunLoop渲染调度流程（第370-390行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/sunnyxx/优化uitableviewcell高度计算的那些事-sunnyxx的技术博客.md › 利用RunLoop空闲时间执行预缓存任务 › 用RunLoopObserver找准时机（第202-230行）
[9] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 3. Run Loop 的组成 › 3.5 Run Loop 内部逻辑（第290-306行）
[10] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop › 2026-05-14 23:29 RunLoop事件处理与模式切换机制 › 整理后内容（第143-153行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 二、一轮循环的真实顺序（第127-172行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/suelan.github.io/dive-into-cfrunloop.md › 使用案例 › 检测主线程中的卡顿（hitch）阻塞（第275-292行）
