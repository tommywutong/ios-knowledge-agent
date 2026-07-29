---
topic: RunLoop常见应用
group: RunLoop
generated_at: 2026-07-29T19:37:56
provider: deepseek
---

# RunLoop常见应用

## 一句话总结
RunLoop 是一个事件循环机制，保证线程在有事件时处理任务、无事件时休眠节省资源，其常见应用包括**定时器管理、子线程保活、卡顿监控、图片延迟加载以及延迟方法调用**等 [5][1][4]。

## 核心原理
- **事件循环模型**：RunLoop 使线程可以进入 “接收消息 → 处理事件 → 等待” 的循环，不会立即退出 [10]。当有事件（如触摸、定时器、UI 刷新）时唤醒线程，无事件时让线程休眠，节省 CPU 资源 [5]。
- **与线程的对应关系**：每个线程都有一个唯一的 RunLoop 对象，主线程的 RunLoop 在应用启动时自动创建并启动，子线程的 RunLoop 是懒加载的，需要手动获取并启动 [2]。
- **存储结构**：全局字典存储，key 是线程，value 是 RunLoop [2]。
- **关键模式**：`NSDefaultRunLoopMode`（默认状态）、`UITrackingRunLoopMode`（滑动追踪）、`NSRunLoopCommonModes`（可被多个模式共同使用的标记集合）[1][4]。

## 关键细节与易错点

### 1. NSTimer 在滑动时失效
- **原因**：ScrollView 滑动时，主线程 RunLoop 从 `NSDefaultRunLoopMode` 切换到 `UITrackingRunLoopMode`，添加在 DefaultMode 下的 Timer 不会被触发 [4][9]。
- **解决方案**：
  - 将 Timer 添加到 `NSRunLoopCommonModes`，使其同时在 DefaultMode 和 TrackingMode 下生效 [4]。
  - 使用 GCD Timer（`dispatch_source_t`），它不依赖 RunLoop Mode，不受模式切换影响，精度最高 [2][4]。

### 2. 子线程保活（线程常驻）
- **关键步骤**：
  - 必须向子线程的 RunLoop 添加事件源（如 `NSPort`），否则 `CFRunLoopRunSpecific` 入口的 `__CFRunLoopModeIsEmpty` 检查会直接返回，RunLoop 根本不会启动 [4][7]。
  - **不要使用** `[NSRunLoop run]`，其外层 while(1) 无条件循环，无法被 `CFRunLoopStop()` 停止 [4][7]。
  - **推荐做法**：使用 `while + runMode:beforeDate:` 的可控循环，配合标志位（如 `_stopped`）控制退出 [1][4][7]。

```objc
// 正确示例
__weak typeof(self) weakSelf = self;
_thread = [[NSThread alloc] initWithBlock:^{
    [[NSRunLoop currentRunLoop] addPort:[[NSPort alloc] init] forMode:NSDefaultRunLoopMode];
    while (weakSelf && !weakSelf->_stopped) {
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode beforeDate:[NSDate distantFuture]];
    }
}];
[_thread start];
```

- **线程常驻 vs 线程保活**：常驻线程会持续占用系统资源；保活线程在空闲时资源占用较低，只在有任务时占用资源 [1]。

### 3. performSelector:afterDelay: 静默失效
- **原因**：该方法的实现是向当前线程的 RunLoop 添加一个定时器；如果当前子线程没有启动 RunLoop，定时器永远不会到期，selector 不会被调用 [11][12]。
- **注意**：子线程默认没有 RunLoop，需手动启动才能生效 [1][11]。

### 4. 图片延迟加载
- 将图片加载方法限定在 `NSDefaultRunLoopMode` 下，用户滑动时（`UITrackingRunLoopMode`）不加载，停止滑动后再加载，减少 CPU 消耗 [1]。

### 5. 卡顿监控
- **原理**：在 RunLoop 上注册 `CFRunLoopObserver`，监听关键状态切换（如 `kCFRunLoopBeforeWaiting`、`kCFRunLoopAfterWaiting`）。同时开启子线程，以高精度监控定时器（如每 50ms 检查一次）判断主线程 RunLoop 是否在某个状态停留超过阈值（如 >200ms），若卡顿则收集当前主线程堆栈 [2][4][10]。
- **微信 Matrix 方案**：
  - 在 RunLoop 的起始和结束位置添加 Observer，获取主线程开始和结束状态 [10]。
  - 子线程检查周期 1 秒，RunLoop 超时阈值 2 秒；如果主线程运行超过 2 秒则认为卡顿，获取线程快照 [10]。
  - 如果单核 CPU 占用超过 80%，也会捕获当前线程快照 [10]。
- **简单方案的盲区**：单个 Observer（order=0）在 `kCFRunLoopBeforeWaiting` 阶段存在监测盲区—UI 布局、绘制、手势回调等系统 Observer 的耗时无法被捕获。微信 Matrix 通过注册两个 Observer（order 分别为 `LONG_MIN` 和 `LONG_MAX`）来包裹所有系统 Observer 的执行，从而完整覆盖 [4][7][3]。

### 6. 自动释放池的管理
- RunLoop 与自动释放池的管理密切相关 [1]（材料未展开，仅提及关联）。

## 高频追问

**Q1: NSTimer 滑动失效有哪些解决办法？分别的优缺点？**
- **答**：两种方案：① 将 Timer 添加到 `NSRunLoopCommonModes`，简单但仍在 RunLoop 上运行，若主线程有其他耗时任务仍可能延迟；② 使用 GCD Timer（`dispatch_source_t`），不依赖 RunLoop，精度最高，适合高精度需求 [4][2]。

**Q2: 子线程保活时，为什么不能直接调用 `[NSRunLoop run]`？**
- **答**：`[NSRunLoop run]` 内部是无限循环，且无法通过 `CFRunLoopStop()` 停止，导致线程无法被外部控制退出。应使用 `while + runMode:beforeDate:` 配合标志位实现可控退出 [4][7]。

**Q3: RunLoop 卡顿监控的原理是什么？如何避免误报？**
- **答**：通过注册 Observer 监听主线程 RunLoop 状态，子线程检测是否长时间未切换状态。误报来源包括：主线程 CPU 过高但未真正卡顿（如大量计算），以及 `kCFRunLoopBeforeWaiting` 阶段系统 Observer 耗时被忽略。微信的方案同时检测 CPU 占用（单核 >80%）作为卡顿辅助判断，并使用双 Observer 包裹系统 Observer 执行以覆盖盲区 [10][4]。

**Q4: performSelector:withObject:afterDelay: 在子线程中调用为何不执行？**
- **答**：该方法内部向当前线程的 RunLoop 添加定时器，子线程默认没有 RunLoop，因此定时器永不触发。需手动启动子线程的 RunLoop [11][12][1]。

**Q5: 如何保证 Timer 在滑动和非滑动模式下都工作？**
- **答**：将 Timer 添加到 `NSRunLoopCommonModes`，或改用 GCD Timer [4][2]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第3228-3269行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第3087-3164行）
[3] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第五周：RunLoop、AutoreleasePool、响应者链与生命周期 › 本周精读路线 › Day 2｜先会 RunLoop，再理解常驻线程与卡顿监测（对应 W4-03）（第498-510行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › 常见面试题 › Q4: RunLoop 在实际开发中有哪些应用？（第1177-1210行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/RunLoop 与 AutoReleasePool.md › RunLoop（第1-4行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第550-575行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Timer的注意事项.md › iOS 定时器的注意事项 › 注意事项二：RunLoop Mode 问题 › 问题描述（第192-203行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/cloud.tencent.cn/matrix-ios-卡顿监控.md › **原理**（第47-63行）
[11] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 3. Run Loop 的组成 › 3.2 Input Source › 3.2.3 Perform Selector Source（第171-204行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 八、常驻线程：把常见的那个错误犯一遍 › performSelector:afterDelay: 为什么会静默失效（第505-524行）
