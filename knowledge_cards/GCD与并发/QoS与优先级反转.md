---
topic: QoS与优先级反转
group: GCD与并发
generated_at: 2026-07-29T19:40:23
provider: deepseek
---

# QoS与优先级反转

## 一句话总结

优先级反转（Priority Inversion）是指高优先级任务被低优先级任务阻塞，两者相对优先级倒置的现象 [2][7]；当高QoS任务等待低QoS任务持有的锁时，系统会临时提升低优先级任务的优先级来缓解，但最佳实践是让共享同一资源的任务使用相同的QoS等级，以避免此问题 [1]。

## 核心原理

### 1. QoS（Quality of Service）等级定义
GCD提供以下QoS等级，任务继承其所在队列的优先级，系统为高QoS任务分配更多CPU时间片 [3]：
- **QOS_CLASS_USER_INTERACTIVE**（用户交互级）：最高优先级，影响UI响应（滑动、动画），要求毫秒级完成 [3][5][6]
- **QOS_CLASS_USER_INITIATED**（用户发起级）：用户主动触发（点击后网络请求），需秒级内完成 [3][5][6]
- **QOS_CLASS_DEFAULT**（默认级）：未指定时的默认值，建议显式指定其他等级 [3][5][6][11]
- **QOS_CLASS_UTILITY**（工具级）：耗时任务（下载、数据解析），系统可能限制CPU占用 [3][5][6]
- **QOS_CLASS_BACKGROUND**（后台级）：影响用户体验最小的任务（备份、日志上传），系统空闲时执行 [3][5][6]

### 2. 优先级反转发生的条件
当高优先级和低优先级的任务之间共享资源时可能发生优先级反转。典型场景：低优先级任务获得共享资源的锁，高优先级任务等待该锁而被阻塞。此时若有一个不需要该资源的中优先级任务可运行，它会抢占低优先级任务，导致低优先级任务无法释放锁，高优先级任务持续等待 [2][7]。

### 3. 系统缓解机制
当高QoS任务等待低QoS任务的锁时，系统会临时提升低QoS任务的优先级（Priority Inversion），以帮助尽快释放锁 [1]。dispatch queue 和 pthread mutex 通过自动提高持有锁线程的优先级解决优先级反转问题 [8]。

## 关键细节与易错点

### 1. 不能把QoS当成执行顺序保证
QoS是系统调度优先级的指导，不代表任务会按QoS等级顺序执行 [4]。任务、队列、工作线程、CPU核心是四层关系，优先级反转发生时，高优先级任务可能因等待锁而延迟执行。

### 2. 避免轻易更改优先级
在大多数情况下，改变优先级不会使事情按预期运行 [9]。使用不同优先级的多个队列会让并行编程更加复杂和不可预见 [7]。最好：
- 始终使用默认优先级队列（直接使用或作为目标队列）[7]
- 让共享同一资源的所有任务使用相同QoS [1]

### 3. 自旋锁中的优先级反转更严重
在自旋锁（如`OSSpinLock`）中，等待锁的高优先级线程持续自旋占用CPU，低优先级线程分配到的资源更少，可能导致锁长时间无法释放 [8][10]。自旋锁的等待是一个死循环，高优先级线程一直处于就绪状态，系统倾向于优先调度高优先级线程，低优先级线程因而得不到执行机会去解锁，形成僵局 [10]。

iOS8引入QoS后，这一问题被放大：高QoS线程不会衰减为低QoS，调度器永远优先为高QoS线程分配资源。处于自旋的高QoS线程会持续忙等，持有锁的低QoS线程得不到资源，自旋锁不再安全 [8][10]。iOS10以`os_unfair_lock`取代了`OSSpinLock` [8]。

### 4. 实验数据对比
在测试中（低优先级线程持锁 → 干几十微秒 → 解锁，16条高优先级线程同时抢锁），`OSSpinLock`的吞吐在658次到1798万次之间跳跃（相差四个数量级），最坏单次等待1049毫秒；`os_unfair_lock`四轮数据均在764万到837万之间，抖动不到10% [10]。

### 5. QoS与全局队列的对应关系
iOS8引入QoS，全局队列与QoS类的对应关系 [12]：

| 全局队列优先级 | 对应的QoS类 | 说明 |
|---|---|---|
| Main thread | UserInteractive | UI相关、交互 |
| DISPATCH_QUEUE_PRIORITY_HIGH | UserInitiated | 用户发起，需立即得到结果 |
| DISPATCH_QUEUE_PRIORITY_DEFAULT | Default | 默认值 |
| DISPATCH_QUEUE_PRIORITY_LOW | Utility | 耗时稍长（下载等） |
| DISPATCH_QUEUE_PRIORITY_BACKGROUND | Background | 后台不可见操作 |

## 高频追问

**Q1：什么是优先级反转（Priority Inversion）？**

优先级反转是一种不希望发生的任务调度状态，高优先级任务被低优先级任务抢占，形成相对优先级倒置 [2]。常见场景：高优先级任务等待低优先级任务正在使用的临界资源，同时低优先级任务被一个次高优先级任务抢占，无法及时释放资源 [2]。例如，音频输出线程（高优先级）被界面线程（低优先级）堵塞会导致扬声器故障 [2]。

**Q2：为什么 iOS 要弃用 OSSpinLock？**

因为自旋锁在等待时持续自旋占用CPU [10]。当高QoS线程等待低QoS线程持有的锁时，高优先级线程保持自旋，系统调度器会优先分配资源给高优先级线程，低优先级线程得不到执行机会释放锁，造成"高等待低释放、低等待高让出CPU"的死循环 [10]。该问题在高QoS和低QoS线程争用同一把自旋锁时尤为严重 [8]。iOS10改用`os_unfair_lock`解决此问题 [8]。

**Q3：QoS 的五个等级分别是什么？适用于哪些场景？**

| QoS等级 | 优先级 | 适用场景 |
|---|---|---|
| USER_INTERACTIVE | 最高 | UI刷新、动画、列表滑动，毫秒级完成 [3][5][6] |
| USER_INITIATED | 高 | 点击按钮后网络请求、用户等待结果，秒级内 [3][5][6] |
| DEFAULT | 默认 | 普通任务，建议显式指定其他等级 [3][5][6][11] |
| UTILITY | 低 | 下载文件、数据解析，可显示进度条 [3][5][6] |
| BACKGROUND | 最低 | 备份数据、同步日志、统计分析 [3][5][6] |

**Q4：串行队列是否支持 QoS 设置？如何通过 GCD 设置优先级？**

可以通过 `dispatch_set_target_queue` 给自定义队列绑定 QoS 等级 [3]。全局并发队列提供了不同QoS的队列，任务放入对应队列即继承该队列的优先级 [3][11]。

**Q5：当高优先级任务等待低优先级任务持有的锁，同时有多个中优先级任务并发时，优先级反转的情况会不会更复杂？**

本卡片材料不足。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-CPU与后台优化.md › 耗电-CPU与后台优化 › 四、GCD与QoS › QoS反转陷阱（第209-213行）
[2] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/并发控制之线程同步.md › 3. Synchronization 常见问题 › 3.4 优先级倒置 Priority Inversion（第111-115行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第2037-2072行）
[4] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第四周：线程、GCD、Operation 与锁 › 本周精读路线 › Day 5｜队列不是线程，QoS 不是绝对优先级（对应 W3-07、W3-08）（第431-442行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-26 12:15:55 GCD 服务质量等级详解 ^a6dd79（第473-486行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-26 12:15:55 GCD 服务质量等级详解 ^a6dd79 › 整理后内容（第488-504行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/并发编程-api-及挑战.md › 优先级反转（第374-388行）
[8] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/线程同步之自旋锁.md › 4. 优先级反转（第197-216行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/底层并发-api.md › 队列 › 优先级（第127-133行）
[10] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS 锁：从 OSSpinLock 的废弃说起.md › 锁：从 OSSpinLock 的废弃说起 › 一、优先级反转，准确地说是什么（第36-65行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › GCD（Grand Central Dispatch） › 队列类型（第97-129行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › iOS系统版本新特性 › iOS8（第1026-1036行）
