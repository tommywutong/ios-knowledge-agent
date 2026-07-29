---
topic: Allocations与内存泄漏
group: 性能与诊断
generated_at: 2026-07-29T20:03:27
provider: deepseek
---

# Allocations与内存泄漏

## 一句话总结
内存泄漏通常源于循环引用，`Allocations` 通过观察内存增长模式和 Heapshot 分析定位泄漏，而 `Leaks` 工具检测完全不可达的环；两者结合，配合 `Xcode Memory Graph Debugger`，是 iOS 内存泄漏的核心诊断手段。

## 核心原理

- **内存泄漏定义**：进程中分配了一个对象，丢失了对它的所有引用，且从未释放。这些对象依然是“脏”的（dirty），但进程无法访问或释放它们，直到进程退出。[9]
- **循环引用（Retain Cycle）**：两个或多个对象互相持有强引用（retain），形成闭环，导致所有对象都无法被释放。[10] 例如，对象 A 和 B 互相引用，且没有外部引用指向它们，就构成泄漏。[9]
- **ARC 与泄漏**：Swift 的自动引用计数（ARC）能防止许多泄漏，但即使是 ARC 管理的对象，也可能因循环引用而泄漏。[9] 避免强循环引用的方法是必要时使用弱引用（weak）。[9]

## 关键细节与易错点

- **Allocations 与 Leaks 的互补性**：
  - **Allocations 工具** 用于观察总体分配曲线：若图表持续增长，通常暗示严重泄漏；重复同一操作（如切换页面）后内存未回落到基线，是泄漏或“废弃内存”（abandoned memory）的信号，可能由循环引用导致。[2]
  - **Heapshot 分析（Mark Heap）**：在重复操作之间点击“Mark Heap”，`Allocations` 会显示哪些对象未被释放，帮助定位问题。[2]
  - **Leaks 工具** 默认每 10 秒扫描堆，检测不再可达的对象（真正意义上的泄漏）。适用于闭包循环引用、`malloc`/`free` 不匹配、delegate 被强引用等场景。[3]
  - **Leaks 的局限性**：只能识别“完全不可达的环”。若泄漏对象仍被单例或全局变量持有（逻辑泄漏），`Leaks` 无法捕获，这种情况需配合 `Allocations` 的 Generation 分析法。[3] 外部引用的存在也会使泄漏不被识别。[1]
- **泄漏树（Leak Tree）**：`leaks` 命令行工具或 `Memory Graph Debugger` 显示泄漏对象时，会同时展示它们所属的循环引用关系图（Root Cycle）。修复一个根节点的泄漏，可能连带释放其他被引用的对象。[7][8]
- **工具开销**：
  - `MallocStackLogging` 和 `Allocations` 是实时追踪，会消耗一定内存和 CPU 来记录分配信息。[6]
  - `Leaks`、`VM Tracker` 和 `内存图` 是快照式，分析时会挂起目标 app，可能导致短暂卡顿。[6]
- **保守扫描的误报**：工具扫描内存时，会按字节寻找可能是指针的值。但该值也可能是数字、标志或随机字节。因此，保守扫描可能产生“不确定、保守的引用”记录。[7]

## 高频追问

1. **如何用 Allocations 检测内存泄漏？**
   - **观察图表**：注意分配图是否持续增长。[2]
   - **Heapshot 分析**：重复同一操作（例如导航前后），操作前点击“Mark Heap”，操作后再次点击。对比两个 Heap 间的对象，只应看到瞬态增长（例如新 view 创建后又释放）。若部分内存未被回收，则存在泄漏或废弃内存。[2]

2. **Xcode Memory Graph Debugger 有什么作用？**
   - 在调试时点击 Debug Memory Graph 按钮，可视化对象间的引用关系。紫色感叹号标记的对象通常是泄漏，可直接通过图形界面查看循环引用。[11]

3. **`leaks` 命令行工具如何使用？**
   - 在进程或内存图（memgraph）上运行 `leaks`。它会输出泄漏对象列表，以及每个泄漏的“根循环”信息和分配调用栈（若启用了 malloc stack logging），以定位问题代码。[4][8][12]

4. **循环引用为什么必然导致内存泄漏？**
   - 循环引用形成后，无论 ARC 还是手动引用计数都无法打破环。只要没有外部引用指向环中的任何对象，进程就永远无法访问或释放它们，这些对象会占用“脏”内存直至进程结束。[10][9]

5. **如何避免循环引用？**
   - 避免创建强循环引用。如果无法避免，使用弱引用（`weak`）或无主引用（`unowned`）打破环。[9] 在 block/闭包中捕获 self 时，务必使用 `[weak self]` 或 `[unowned self]`，并注意通过 weak 后的变量间接访问实例变量（`blockSelf->_someIvar`），避免直接引用原始 self。[1]

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2010-04-30-dealing-with-retain-cycles.md › (全文)（第251-258行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/ios-5-tech-talk-michael-jurewitz-on-performance-measurement.md › 2. Minimize Memory Usage › Instruments: Allocations + Leaks + VM Tracker + Activity Monitor（第116-121行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 四、内存工具 › 4.2 Leaks（第200-207行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10180-detect-and-diagnose-memory-issues.md › Detect and diagnose memory issues › Transcript（第152-170行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2024/10173-analyze-heap-memory.md › Analyze heap memory › Transcript（第331-333行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2024/10173-analyze-heap-memory.md › Analyze heap memory › Transcript（第269-271行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2018/416-ios-memory-deep-dive.md › iOS Memory Deep Dive › Transcript（第193-201行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10180-detect-and-diagnose-memory-issues.md › Detect and diagnose memory issues › Transcript（第140-150行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/fbeng/automatic-memory-leak-detection-on-ios.md › Retain cycles（第38-48行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › 循环引用问题 › 循环引用的检测（第726-730行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2022/10106-profile-and-optimize-your-game-s-memory.md › Profile and optimize your game's memory › Transcript（第123-133行）
