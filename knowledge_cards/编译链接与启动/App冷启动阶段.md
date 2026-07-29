---
topic: App冷启动阶段
group: 编译链接与启动
generated_at: 2026-07-29T19:48:46
provider: deepseek
---

# App冷启动阶段

## 一句话总结

iOS App 冷启动是用户点击图标后，进程从零创建到首帧渲染完成的完整过程，分为 **Pre-main 阶段**（由 dyld 动态链接器负责，从进程创建到 `main()` 执行前）和 **main 阶段**（从 `main()` 到首帧渲染及首次可交互）。[1][3][5][6]

## 核心原理

### 1. Pre-main 阶段

Pre-main 阶段由 dyld（动态链接器）负责，主线程在内核 `fork()` 创建进程时同时创建，后续所有 Pre-main 工作都在主线程上执行。[4]

主要子步骤按顺序：[3][4][5]

1. **加载可执行文件**：内核创建进程，使用 `mmap()` 将主程序 Mach-O 文件映射到虚拟内存（惰性加载，只有实际访问的页才调入物理内存）。解析 Mach-O Header（验证 Magic Number、CPU 架构、文件类型）和 Load Commands（`LC_SEGMENT_64` 设置内存权限、`LC_LOAD_DYLIB` 记录动态库依赖、`LC_MAIN` 计算入口地址），最后验证代码签名。[4]

2. **加载动态库**：dyld 从主程序 Mach-O 的 `LC_LOAD_DYLIB` 读取依赖的动态库列表，按搜索规则查找（优先从共享缓存查找），使用 `mmap()` 映射到进程地址空间并验证代码签名。采用**深度优先搜索**递归加载每个动态库的依赖（每个库只加载一次），按依赖关系构建初始化顺序——被依赖的库先于依赖方（如 Foundation 在 UIKit 之前）。如果 App 使用 Swift，iOS 12.2 以后 Swift 标准库在系统共享缓存中，无需嵌入 App。[4]

3. **Rebase & Bind**：由于 ASLR（地址空间布局随机化），App 每次启动的加载地址不同，需要修正指针。**Rebase（重定位）**修正指向 Mach-O **内部**的指针，将编译时地址加上 ASLR 偏移量（slide）；**Bind（绑定）**修正指向 Mach-O **外部**的指针，查找符号表绑定到正确的外部符号地址（如 `_objc_msgSend`）。[4]

4. **ObjC Runtime 初始化**：类注册、Category 附加。[3][5]

5. **Swift Runtime 元数据注册**：类型元数据、协议遵循表。[3][5]

6. **调用 +load 方法**：每个类和 Category 的 `+load` 按照编译顺序、父类先于子类的顺序执行。[3][4][5]

7. **执行 Initializers**：C++ 静态构造函数、`__attribute__((constructor))` 修饰的函数。[3][4][5]

**时间分布**：一个 ObjC hello world 项目，从内核 `exec` 到主程序第一个 `+load` 约 3276 μs，到最后一个 constructor 约 3299 μs，到 `main()` 第一行约 3701 μs。约 89% 的 pre-main 时间花在业务代码执行之前。[2]

### 2. main 阶段

从 `main()` 开始到首帧渲染完成。[1][5][6]

子步骤：[3][5][6]
- `main()` 函数执行
- `UIApplicationMain`：创建 UIApplication、AppDelegate、启动 RunLoop
- AppDelegate 回调：`willFinishLaunching`、`didFinishLaunching`
- 首帧渲染：创建 Window、RootViewController、首屏 UI

**完整冷启动阶段划分**（常用指标定义）：[6]

| 阶段 | 起点 | 终点 |
|-----|------|------|
| T1 Pre-main | 进程创建 | `main()` 入口 |
| T2 Main | `main()` | `applicationDidFinishLaunching` 返回 |
| T3 首屏构建 | didFinishLaunching | 首屏第一帧 |
| T4 可交互 (TTI) | 首屏第一帧 | 关键按钮可点击 |

启动总时长有三种定义：[6]
- **狭义**：T1 + T2（点击图标到 `didFinishLaunching` 返回）
- **广义**：T1 + T2 + T3（用户看到首屏）
- **用户视角**：T1 + T2 + T3 + T4（用户能开始操作）

### 3. Pre-main 耗时测量方法

使用 `sysctl(KERN_PROC)` 获取本进程的 `p_starttime`（内核在 `exec` 时记的时刻），与当前 `gettimeofday` 相减得到耗时。[2]

```c
static inline double premain_us(void){
    struct kinfo_proc kp; size_t len = sizeof(kp);
    int mib[4] = { CTL_KERN, KERN_PROC, KERN_PROC_PID, (int)getpid() };
    struct timeval now; gettimeofday(&now, NULL);
    if (sysctl(mib, 4, &kp, &len, NULL, 0) != 0) return -1;
    struct timeval st = kp.kp_proc.p_un.__p_starttime;
    return (double)(now.tv_sec - st.tv_sec)*1e6 + (double)(now.tv_usec - st.tv_usec);
}
```

**注意**：该口径在 iOS 上不能直接对应 iOS 冷启动终点，因为 iOS 冷启动还包含 `UIApplicationMain`、scene 连接、首帧渲染，`main()` 只是中间点。本文档中的毫秒数只用于回答“有没有差异”，不能当作 iOS 上的收益。[2] 建议使用 Instruments 的 App Launch 模板，它把 pre-main 拆成 dyld 各子阶段，并给出到首帧的完整时间轴；同一设备、相同构建配置、重启后第一次启动、至少 10 次取中位数。[2][7][11]

### 4. 埋点方案

| 埋点时机 | 实现方式 | 统计内容 |
|---------|---------|---------|
| 进程创建时间 | `sysctl` 获取 `p_starttime` | 启动起点 |
| +load 方法 | ObjC `+load` 方法 | dylib 加载 + Rebase/Bind + Runtime 初始化完成 |
| 高优先级 constructor | `__attribute__((constructor(101)))` | +load 执行完成 |
| 低优先级 constructor | `__attribute__((constructor(65535)))` | 大部分 Initializers 执行完成 |
| main 函数 | main.swift 顶部 | Pre-main 结束，main 开始 |
| willFinishLaunching | AppDelegate 回调 | main 到 willFinish 的耗时 |
| didFinishLaunching 开始 | AppDelegate 回调 | willFinish 执行耗时 |
| didFinishLaunching 结束 | return 前标记 | didFinish 执行耗时 |
| 首帧渲染 | viewDidAppear + DispatchQueue.main.async | didFinish 到首帧的耗时 |

[9]

### 5. main 阶段优化策略

**启动任务分级管理**：[10]

| 级别 | 执行时机 | 包含任务示例 |
|-----|---------|------------|
| P0 - 关键 | didFinishLaunching 同步执行 | 崩溃监控、日志系统、网络库配置、首屏数据请求 |
| P1 - 重要 | didFinishLaunching 异步执行 | 推送注册、数据库初始化、非首屏 SDK |
| P2 - 可延迟 | 首帧后或 RunLoop 空闲时 | 统计 SDK、分享 SDK、广告 SDK、预加载缓存 |

**并行初始化**：利用 GCD 并发队列将无依赖关系的初始化任务并行执行，涉及 UI 操作的初始化必须在主线程。[10]

**利用 RunLoop 空闲时机**：在 `kCFRunLoopBeforeWaiting` 时注册 Observer，将低优先级任务拆分为多个小任务，在 RunLoop 每次空闲时执行一批。[10]

**延迟加载**：[10]
- 首屏无关的 SDK 延迟初始化（分享、支付、地图等 SDK 在用户首次使用相关功能时再初始化）
- 非必要视图懒加载（TabBar 中非首页的 ViewController 延迟到切换时再创建）
- 首屏数据预加载（在后台提前加载首屏数据，避免白屏等待）

**Pre-main 阶段优化**：[7]
- 动态库裁剪
- `+load` 迁移到 `+initialize`
- 二进制重排（减少 Page Fault）

### 6. 二进制重排原理

冷启动时，如果调用的函数分散在不同的代码页，可能产生较多 Page Fault。二进制重排将启动阶段调用的函数集中排列到相邻的代码页中，减少需要按需调入物理内存的离散代码页数量。[10]

实现步骤：[10]
1. **插桩收集**：使用 Clang SanitizerCoverage（`-fsanitize-coverage=func,trace-pc-guard`）在每个函数入口插入回调
2. **生成 Order File**：运行 App 收集启动阶段的函数调用顺序，生成函数排列文件
3. **链接器重排**：通过 Xcode 的 `Order File` 配置项指定文件路径，链接器按照指定顺序排列函数
4. **验证效果**：通过 Instruments 的 System Trace 观察 Page Fault 数量的变化

### 7. 测量工具

- **Instruments App Launch 模板**：整合 Time Profiler、Virtual Memory、System Trace，覆盖 `main()` 之前（dyld、runtime）到首屏绘制的全过程。与 `DYLD_PRINT_STATISTICS`、`os_signpost PointsOfInterest "FirstMeaningfulPaint"` 协同使用，量化启动优化效果。[11]
- **Instruments 排查启动慢的一般步骤**：[7] 选 App Launch 模板冷启动录制 → 关注 Pre-main（dyld、objc、+initialize、静态构造）vs Post-main → Pre-main 时间过长检查动态库、+load、二进制重排 → Post-main 时间过长用 Time Profiler 看 `application(_:didFinishLaunching...)` 热点，用 File Activity 看是否主线程读大文件 → 配合 `os_signpost` 对 `FirstMeaningfulPaint` 打点。

## 关键细节与易错点

1. **主线程创建时机**：主线程并非在 `main()` 中创建，而是在内核 `fork()` 创建进程时同时创建，后续所有 Pre-main 工作都在主线程上执行。[4]

2. **Pre-main 阶段不包括 UIApplicationMain**：冷启动通常将 Pre-main 定义为进程创建到 `main()` 入口，但 iOS 冷启动的完整流程还包含 `UIApplicationMain`、scene 连接、首帧渲染，`main()` 只是中间的一个点。如果仅用 `sysctl` 测量到 `main()` 之前的耗时，不能代表 iOS 冷启动总时长。[2]

3. **+load 与 +initialize 的区别**：`+load` 方法在 Pre-main 阶段由 dyld 直接调用，执行时机非常早；而 `+initialize` 是懒加载的，在类第一次收到消息时才由运行时调用（属于 main 阶段或更晚）。优化时应将 `+load` 中的工作迁移到 `+initialize` 中。[7][8]

4. **动态库加载顺序**：使用深度优先搜索递归加载每个动态库的依赖，每个库只加载一次。最终按依赖关系构建初始化顺序——被依赖的库先于依赖方（如 Foundation 在 UIKit 之前）。[4]

5. **iOS 12.2+ Swift 标准库位置**：iOS 12.2 以后 Swift 标准库位于系统共享缓存中，无需嵌入 App，减少了 App 包体积和启动时动态库加载量。[4]

6. **Rebase 和 Bind 的区别**：Rebase 修正指向 Mach-O **内部**的指针，Bind 修正指向 Mach-O **外部**的指针。[4]

7. **二进制重排只影响 Page Fault 次数**：二进制重排优化的是冷启动时因函数散落在不同代码页导致的 Page Fault 次数，而非所有 Pre-main 耗时。效果通过 Instruments System Trace 观察 Page Fault 数量变化来验证。[10]

8. **启动总时长的定义差异**：不同的业务场景关注不同的终点。优化目标应明确是“用户看到首屏（T1+T2+T3）”还是“用户可交互（T1+T2+T3+T4）”。[6]

## 高频追问

**Q1: Pre-main 阶段具体包含哪些步骤？**
A: Pre-main 阶段由 dyld 负责，包括：加载可执行文件 → 加载动态库（深度优先递归加载） → Rebase & Bind → ObjC Runtime 初始化（类注册、Category 附加） → Swift Runtime 元数据注册 → 调用 +load 方法 → 执行 Initializers（C++ 静态构造函数、__attribute__）。[3][4][5]

**Q2: 如何测量 Pre-main 阶段的耗时？**
A: 可以使用 `sysctl(KERN_PROC)` 获取进程创建时间戳（`p_starttime`），与当前时间差计算。但该方法在 iOS 上不能直接对应 iOS 冷启动终点，因为 iOS 冷启动还包含 UIApplicationMain、首帧渲染。更推荐在 macOS 上用该口径做差异对比，或使用 Instruments 的 App Launch 模板结合 `DYLD_PRINT_STATISTICS` 观察各子阶段耗时。[2][11]

**Q3: 如何埋点监控冷启动各阶段耗时？**
A: 需要在代码中插入打点。常见方案：通过 `sysctl` 获取进程创建时间作为起点；在 ObjC `+load` 方法中记录作为 Pre-main 关键节点；使用 `__attribute__((constructor(101)))` 记录 +load 完成；在 `main()` 函数第一行记录 Pre-main 结束；在 AppDelegate 回调 `willFinishLaunching`、`didFinishLaunching` 开始/结束记录；在首帧渲染后（如 `viewDidAppear + DispatchQueue.main.async`）记录首帧渲染完成。[9]

**Q4: 二进制重排的原理和步骤是什么？**
A: 二进制重排通过将冷启动期间调用的函数集中排列到相邻的代码页，减少缺页中断（Page Fault）次数。步骤：① 使用 Clang SanitizerCoverage（`-fsanitize-coverage=func,trace-pc-guard`）插桩收集函数调用顺序；② 运行 App 生成 Order File；③ 在 Xcode 的 Order File 配置项中指定该文件；④ 链接器按顺序排列函数；⑤ 用 Instruments System Trace 验证 Page Fault 数量变化。[10][8]

**Q5: main 阶段如何进行优化？**
A: 主要策略包括：① 启动任务分级管理（P0 同步、P1 异步、P2 延迟）；② 并行初始化（无依赖的任务用 GCD 并发队列）；③ 利用 RunLoop 空闲时机处理低优先级任务；④ 延迟加载非首屏 SDK、懒加载非首页 ViewController、预加载首屏数据。此外，Pre-main 阶段的优化也影响整体冷启动时间，如动态库裁剪、将 `+load` 迁移到 `+initialize`、二进制重排。[10][7]

**Q6: 冷启动和热启动、预热启动的区别是什么？**
A: 材料中提及三种类型，但未给出明确定义。通常：冷启动是进程从零创建；热启动是 App 已在内存中且进程存活，按下 Home 键后重新回到前台。本卡片材料未详细展开差异，建议参考苹果官方文档。[1]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 六、常见面试问题 › Q1: APP启动的详细流程（第1104-1106行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/iOS App 启动：三代 dyld、pre-main 与可测量的优化项.md › App 启动：三代 dyld、pre-main 与可测量的优化项 › 三、启动各阶段的真实顺序 › 那个 400 微秒的洞（第367-393行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 一、冷启动（Cold Launch） › 冷启动流程概览（第40-68行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › App 启动与优化（第9-24行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/启动优化/启动优化.md › 启动优化 › 启动流程概述（第11-46行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/APM/APM-指标体系.md › APM-指标体系 › 四、启动指标 › 4.1 启动阶段划分（第243-283行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 十二、典型排查实战 › 12.3 启动慢：App Launch + Time Profiler + File Activity（第506-512行）
[8] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第七周：编译、链接、Mach-O、dyld 与 App 启动 › 本周精读路线 › Day 5｜把 Runtime 初始化放进 App 冷启动（对应 W6-08）（第744-757行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/启动优化/启动优化-观测.md › 启动优化-观测 › 六、常见面试问题 › 6.2 如何埋点监测冷启动各阶段的耗时？（第695-716行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › App 启动与优化（第166-206行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 十、系统与辅助工具 › 10.2 App Launch（第443-446行）
