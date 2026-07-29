---
topic: RunLoop Mode
group: RunLoop
generated_at: 2026-07-29T19:36:02
provider: deepseek
---

# RunLoop Mode

## 一句话总结

RunLoop Mode 是一种事件分组机制，每个 Mode 包含独立的 Source0、Source1、Timer 和 Observer 集合；RunLoop 同一时刻只能运行在一个 Mode 下，只处理当前 Mode 注册的事件源，以此实现事件隔离与优先级管理。[2][4]

## 核心原理

1. **Mode 的组成与切换**
   - 一个 RunLoop 可包含多个 Mode，每次调用 RunLoop 主函数时必须指定一个 Mode（即 `_currentMode`）。切换 Mode 需先退出当前循环，再以新 Mode 重新进入。[2][4][8]
   - 每个 Mode 内部持有独立的 `sources0`、`sources1`、`observers`、`timers` 集合。[7][8]
   - 公开提供的 Mode 名称有 `kCFRunLoopDefaultMode`（`NSDefaultRunLoopMode`）和 `UITrackingRunLoopMode`。[1][10] 内部使用的 Mode 包括 `UIInitializationRunLoopMode`（App 启动后不再使用）和 `GSEventReceiveRunLoopMode`（系统内部模式，可能随版本变化）。[2][5][8] 注意：这些内部 mode 在真机环境可能不出现，[6] 但多数文档仍将其列入。

2. **CommonModes 机制**
   - `kCFRunLoopCommonModes` 不是真正的 Mode，而是一个标记集合，本质上是存储在 RunLoop 的 `_commonModes` 中的字符串集合。[1][4][7][8]
   - 当我们将一个 Source/Observer/Timer 添加到 CommonModes 时，RunLoop 自动将其同步到所有被标记为 Common 的 Mode 中（如 `kCFRunLoopDefaultMode` 和 `UITrackingRunLoopMode 默认都已被标记为 Common）。[1][7][8]
   - Mode 一旦被标记为 Common，无法移除。[1]

3. **Mode 的隔离效果**
   - 事件源只能在其注册的 Mode 下触发；RunLoop 运行时仅处理当前 Mode 关联的事件源，其他 Mode 的事件处于“持有”状态。[1][3] 例如：将 Timer 添加到 DefaultMode，滑动 UIScrollView 时 RunLoop 切换到 TrackingMode，该 Timer 不会触发。[1][3][7]

## 关键细节与易错点

- **Mode 不能删除，只能通过 mode name 操作**：传入新的 mode name 时 RunLoop 会自动创建对应的 `CFRunLoopModeRef`；已创建的 mode 无法删除。[10]
- **同一时刻只能运行一个 Mode**：RunLoop 不会“运行在 CommonModes”上，CommonModes 只是一个集合，真正的运行模式是集合中的某一个具体 Mode。[1]
- **添加 Timer 到 CommonModes 解决滑动卡顿**：将 Timer 加入 `RunLoop.current.add(timer, forMode: .common)` 等价于同时加入 Default 和 Tracking 两个 Mode，因此滑动时 Timer 仍能回调。[1][3][11]
- **子线程 RunLoop 不会自动启动**：子线程创建的 NSTimer 必须手动添加到当前线程 RunLoop 的某个 Mode 并启动 RunLoop 才会触发。`[NSRunLoop currentRunLoop] run` 几乎无法停止，推荐使用 `runMode:beforeDate:` 实现可控退出。[11]
- **CAAnimation 等系统内部使用 commonModeItems**：CoreAnimation 的 timer 会注册到 commonModeItems（如 QuartzCore 中的 timer），确保动画在滑动时不中断。[12]

## 高频追问

**Q1: RunLoop 的 Mode 切换机制具体是怎样的？**
切换 Mode 时，RunLoop 会先退出当前 Mode 的循环，再以新 Mode 重新进入。典型场景是 ScrollView 滑动：用户开始滑动时 RunLoop 从 DefaultMode 切换到 TrackingMode，停止滑动后切换回 DefaultMode。[2][4][8]

**Q2: 为什么滑动 UIScrollView 时 NSTimer 会暂停？**
因为滑动时 RunLoop 自动切换到 `UITrackingRunLoopMode`，而 NSTimer 如果只注册在 `kCFRunLoopDefaultMode`，则在该 Mode 下不会触发。RunLoop 只处理当前 Mode 注册的事件源。[1][3][7][8]

**Q3: 如何让 NSTimer 在滑动时继续运行？**
将 Timer 添加到 `NSRunLoopCommonModes`（或使用 `kCFRunLoopCommonModes` 字符串），这样 Timer 会同时出现在 DefaultMode 和 TrackingMode 中。[1][3][11] 另一种方案是改用基于 GCD 的 Timer，它不依赖 RunLoop，因此不受 Mode 切换影响。[11]

**Q4: CommonModes 的本质是什么？**
CommonModes 是一个标记集合，不是真正的 Mode。RunLoop 内部维护一个 `_commonModes` 集合（存储被标记为 Common 的 Mode 名称）和一个 `_commonModeItems` 集合（存储同步的 Source/Observer/Timer）。当 RunLoop 内容变化时，自动将 `_commonModeItems` 同步到所有标记为 Common 的 Mode 中。[7][8]

**Q5: Apple 公开提供了几个 Mode？其他 Mode 有哪些，是否稳定？**
Apple 公开的 Mode 只有两个：`kCFRunLoopDefaultMode` 和 `UITrackingRunLoopMode`。[1][10] 内部还有 `UIInitializationRunLoopMode`（App 启动时使用，启动后不再使用）和 `GSEventReceiveRunLoopMode`（接收系统事件，未公开，可能随系统版本变化）。[2][5][8] 但某些真机环境（如 iOS 13+）可能不会出现这些内部 mode，[6] 故不建议依赖其存在。

**Q6: 能否向一个 Mode 添加事件源后，再将该 Mode 标记为 Common？**
可以。通过 `CFRunLoopAddCommonMode(runloop, modeName)` 可将某个 Mode 加入 CommonModes 集合。但一旦加入，无法移除。[1][7][10]

**Q7: RunLoop 中的 Mode 数量是动态的吗？**
是的。RunLoop 的 `_modes` 集合是动态的，可通过 `CFRunLoopAddCommonMode` 或直接添加事件源时传入新 mode name 来增加 Mode。[6][7] 但内部 mode（如 `UIInitializationRunLoopMode`）的数量可能随系统版本变化。[6]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/RunLoop从入门到进阶.md › 3. Run Loop 的组成 › 3.1 Run Loop Mode（第74-84行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › RunLoop 的核心组成 › 2. 运行模式（CFRunLoopModeRef）（第43-55行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Timer的使用.md › 4. Run Loop 与 Timer 关系 › 4.2 使用 Run Loop Mode（第175-205行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runloop.md › RunLoop › 常见面试题 › Q2: RunLoop 的 Mode 有什么作用？（第1068-1084行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第3033-3084行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md › RunLoop：mode、source 与那张流程图今天还对不对 › 一、先把主线程的 RunLoop 打出来 › UIKit 起来之后（第102-104行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › RunLoop 的 Mode（第150-186行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/一份走心的runloop源码分析.md › CFRunLoopMode（第231-247行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › RunLoop 的 Mode（第188-201行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › RunLoop（第606-633行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/ibireme/深入理解runloop.md › 苹果用 RunLoop 实现的功能（第433-467行）
