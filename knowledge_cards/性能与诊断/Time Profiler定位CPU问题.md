---
topic: Time Profiler定位CPU问题
group: 性能与诊断
generated_at: 2026-07-29T20:03:07
provider: deepseek
---

# Time Profiler定位CPU问题

## 一句话总结

Time Profiler 通过周期性采样（默认 1 ms）所有线程调用栈，生成调用树和火焰图，帮助定位 CPU 热点函数，常用于分析 CPU 导致的卡顿、启动慢等问题 [1][6][10]；但其基于定时器的采样存在 aliasing 偏差，对于短突发热点可能漏检，新一代 CPU Profiler 更准确 [3][6]。

## 核心原理

- **采样机制**：Instruments 使用硬件定时器，默认每隔 1 ms 在所有 CPU 核心上记录当前线程的完整调用栈 [10]。采样是统计学意义上的热点发现，不保证覆盖每一次调用 [6]。
- **权重计算**：每次采样时，调用栈中每个函数获得一个权重（Weight），栈底正在执行的函数额外获得一个自权重（Self Weight），代表该方法自身消耗的 CPU 时间（不计子调用）[10]。
- **可视化输出**：采样数据可展示为**调用树（Call Tree）**或**火焰图（Flame Graph）**，帮助分析工作随时间分布的情况以及哪些线程同时活跃 [3][6]。

## 关键细节与易错点

1. **Aliasing 问题**：当系统中有周期性的工作与采样定时器频率一致时，某些函数会被不公平地过度代表（over-represented），导致热点误判。WWDC 2025 明确指出应优先选择 **CPU Profiler**，它能基于每个 CPU 的时钟频率独立采样，避免该偏差 [3]。
2. **采样局限性**：对于短于 1 ms 的突发 CPU 热点，Time Profiler 容易遗漏，需配合 Processor Trace 或 CPU Counters 等工具 [5][6]。
3. **隐藏系统库的取舍**：
   - 一般分析自家代码性能时，建议勾选 **Hide System Libraries**，过滤系统框架噪声，快速定位自己的热点方法 [1][2][11]。
   - 但在分析**启动性能**等场景时，Michael Jurewitz 建议**不勾选**，否则可能忽略系统库中不当的同步网络调用等耗时点 [8]。
4. **Self 列的重要性**：Self Weight 高的方法通常表示自身有长循环或低效实现，应优先优化 [7]。启动时若自家代码占比超过 20%–30%，可能就有问题 [7]。
5. **辅助标记**：使用 `os_signpost` 在代码中埋点，可在 Time Profiler 的 Points of Interest 通道中标记区间，降低“找时间范围”的工作量 [6]。
6. **组合使用**：Time Profiler 常与 Hangs、System Trace、Network 等工具配合使用，例如主线程卡顿先通过 Hangs 找到挂起区间，再用 Time Profiler 分析 CPU 热点 [11][4]。

## 高频追问

### Q1：Time Profiler 的采样频率是多少？能否调整？
- 默认采样间隔为 1 ms（硬件定时器）[10]。具体调整方式材料未提及，但不推荐降低频率以免丢失更多细节。

### Q2：如何避免 aliasing 导致的采样偏差？
- 官方建议直接使用 **CPU Profiler**，它按 CPU 时钟频率独立采样，自动避免 aliasing [3]。如果仍用 Time Profiler，可以尝试改变采样间隔或增加录制时长（材料未明确方法），但准确度不如 CPU Profiler。

### Q3：为什么有时候 Time Profiler 显示的热点函数在源代码中并没找到循环？
- 可能原因：① 该函数是系统库调用，若勾选了“Hide System Libraries”则不显示；② 热点实际来自子调用，但 Self Weight 低，Total Weight 高；③ aliasing 偏差导致非真实热点；④ 短突发热点未被采样到 [3][6][7]。建议关闭隐藏系统库并查看 Total Weight 确认。

### Q4：Time Profiler 能否检测主线程卡顿？如何操作？
- 可以。先用 Hangs 工具定位挂起区间，再展开进程轨道查看主线程 CPU 使用率（若接近 100% 则表明是 CPU 繁忙导致卡顿），然后使用 Time Profiler 分析该区间内的调用树，勾选“Hide System Libraries”聚焦自家代码 [10][11]。

### Q5：Time Profiler 和 CPU Profiler 的主要区别是什么？
- **Time Profiler** 基于固定定时器采样，存在 aliasing 缺陷，且对频率较高的 CPU 核心采样次数更少（有偏向）[3]。
- **CPU Profiler** 基于每个 CPU 的周期计数器独立采样，频率越高的核心采样越密集，更公平地反映真实 CPU 消耗，因此推荐用于 CPU 优化 [3]。材料未提及其他在 macOS/iOS 中的具体使用方式。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/影响动画性能的因素及如何使用 Instruments 检测.md › 3. Instruments 介绍 › 3.1 Time Profiler 模版（第127-140行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-检测.md › 卡顿-检测 › 9. 卡顿检测方案总结 › 4. Instruments系统工具（第1507-1514行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2025/308-optimize-cpu-performance-with-instruments.md › Optimize CPU performance with Instruments › Transcript（第129-139行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-检测.md › 耗电-检测 › 二、Instruments Energy Log › 推荐组合：Time Profiler + Network + Points of Interest（第77-87行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 十四、能力速查表（第543-555行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 三、CPU 与线程工具 › 3.1 Time Profiler（最常用）（第83-115行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/ios-5-tech-talk-michael-jurewitz-on-performance-measurement.md › 1. Launch Quickly › Instruments: Time Profiler（第81-90行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/ios-5-tech-talk-michael-jurewitz-on-performance-measurement.md › 1. Launch Quickly › Instruments: Time Profiler（第67-79行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2026/268-profile-fix-and-verify-improve-app-responsiveness-with-instruments.md › Profile, fix, and verify: Improve app responsiveness with Instruments › Transcript（第96-102行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2023/10248-analyze-hangs-with-instruments.md › Analyze hangs with Instruments › Transcript（第158-166行）
