---
topic: OOM与Jetsam诊断
group: 性能与诊断
generated_at: 2026-07-29T20:05:13
provider: deepseek
---

# OOM与Jetsam诊断

## 一句话总结

OOM（Out of Memory）是 iOS 系统的 Jetsam 机制因进程 `phys_footprint` 超限或整机内存压力过大而直接杀死进程的事件，不产生标准线程堆栈；诊断需依赖 JetsamEvent 日志、事前内存水位记录、事中 Memory Dump 以及事后排除法（Watchdog、低电量等）才能归因。[4][6]

## 核心原理

### 1. Jetsam 机制与强杀类型

- iOS 通过 XNU 内核的 `memorystatus` 子系统（俗称 Jetsam）管理物理内存：进程按 Jetsam 优先级排序，当系统可用物理页或单个进程 footprint 触发阈值时按优先级杀进程。[9]
- 被杀时内核在 `/var/mobile/Library/Logs/CrashReporter/` 生成 `JetsamEvent-yyyy-MM-dd-HHmmss.ips` 文件（JSON 格式），并通过 `DiagnosticsReporting` 暴露给设置 → 隐私与安全性 → 分析与改进 → 分析数据。[2][9]
- 强杀类型及含义：[2]
  - `per-process-limit`：单进程 footprint 超过限额。**本文 OOM 主要类型**。
  - `vm-pageshortage`：系统可用物理页不足，按优先级清理进程。
  - `vnode-limit`：进程打开 vnode 过多（iOS 15+ 约 10000）。
  - `disk-space-shortage`：磁盘可用空间不足。
  - `highwater`：常驻进程超过 highwater 预期。
  - `fc-thrashing`：文件缓存颠簸。

### 2. OOM 与普通崩溃的核心区别

- 普通崩溃：有异常类型、信号、触发线程和堆栈，App 有机会在崩溃处理器记录现场。[4]
- OOM：被系统直接终止，App 被杀瞬间通常没有执行代码的机会，不会产生标准线程堆栈。[4]
- 因此 OOM 归因必须依赖事前和事后的证据链，不能像普通崩溃那样靠抓堆栈定位。[4]

### 3. JetsamEvent 日志的特性

- **不是单个进程的崩溃日志，而是整机一次 Jetsam 事件的快照**：一个文件包含几十个进程条目，只有其中一个（或少数）被真正杀掉；其余进程是作为内存画像被附带记录。[9]
- **不含线程堆栈**：它的价值在于告诉你“谁占用了多少内存”和“为什么被杀”，堆栈需由 App 自己的 Memory Dump 或 MetricKit 补齐。[9][2]
- OOM 通常产生两份日志：[10]
  1. `bug_type = 109`，`exception.type = EXC_RESOURCE`，`subtype = "MEMORY (Fatal) Footprint: ..."` → **有堆栈**。
  2. `bug_type = 298`，JetsamEvent → **无堆栈**，但有整机内存画像。
  - 实战中可把两者按 `incident_id` / `timestamp` 串起来：堆栈从 109 拿，整机归因从 298 拿。

### 4. 内存水位实时监控（事前）

- iOS 13+ 推荐 API：`os_proc_available_memory()` 返回距离 dirty memory limit 还剩的字节，是最准的实时阈值。[1]
- 通过 `task_info` 获取 `phys_footprint`（dirty memory + compressed memory），Jetsam 统计的就是它。[1]
- 关键字段语义：[1]

| 字段 | 含义 | 是否可作 OOM 依据 |
|------|------|------------------|
| `phys_footprint` | 进程 dirty memory + compressed memory | ✅ |
| `resident_size` | 物理驻留内存（不含 compressed） | ❌ 与 Xcode/Jetsam 计算口径不同 |
| `os_proc_available_memory()` | 距离 dirty memory limit 还剩的字节（iOS 13+） | ✅ 最准 |
| `footprint + available` | 实时 OOM 阈值 | ✅ 覆盖前后台、iOS 15+ entitlement 差异 |

- iOS 13 以下兜底：只能用 Jetsam 日志的 `rpages × pageSize` 或机型经验值。[1]

### 5. Memory Dump（事中）

- 目标：在运行期持续记录存活对象及其分配堆栈，内存触顶、收到 Memory Warning、进入后台或达到水位阈值时，将存活对象表、堆栈表等落盘，下次启动上报分析。[8]
- 典型实现：hook `malloc_logger` 和 `__syscall_logger` 捕获分配释放事件；回调里不能再次 malloc 或调用 Foundation，需用无锁 ring buffer、预分配结构和异步处理线程；堆栈只记录原始 PC 离线符号化；核心数据通过预映射文件或 WAL 持续落盘。[8]
- 分析时按类名、对象数、总字节、Top 分配堆栈等聚合，重点找大图、无界缓存、页面泄漏、循环引用和单堆栈大分配。[8]

### 6. Watchdog 与 OOM 的排除关系

- Watchdog 是 iOS 为保证应用响应性设置的看门狗，常见于启动、前后台切换、挂起、终止、后台任务等生命周期阶段超时。日志特征：`bug_type = 309`，`termination.code` 为 `0x8BADF00D`。[6]
- Watchdog 不是内存问题，必须从 OOM 排除法中单独剥离，否则可能把前台卡死误判成 FOOM。[6]

## 关键细节与易错点

1. **`phys_footprint` vs `resident_size`**：`phys_footprint` 包含 compressed memory，与 Jetsam 统计口径一致；`resident_size` 不含 compressed，不能用于 OOM 判断。[1]
2. **JetsamEvent 不是单个 App 的崩溃日志**：一个 JetsamEvent 文件描述整机事件，被杀进程的 `reason` 字段非空，`largestProcess` 不一定等于被杀对象。[8][11]
3. **`rpages × pageSize` 换算 footprint**：在 JetsamEvent 的 `processes` 条目中，`rpages` 是 resident pages，乘以 `pageSize`（通常 16384）得到 footprint（字节），再除以 1024/1024 得到 MB。[8][11]
4. **FOOM 与 BOOM 的判断**：在 `processes` 中看 `states`，若为 `frontmost` 则属于 FOOM（前台 OOM），若为 `background` 或 `suspended` 则属于 BOOM（后台 OOM）。[8][11]
5. **Coalition 共享账本**：主 App、WebKit 子进程和 Extension 可能共享 coalition 账本，同组兄弟进程也可能是真正内存大户。[8][11]
6. **OOM 日志的检索入口**：JetsamEvent 日志文件位于设置 → 隐私与安全性 → 分析与改进 → 分析数据，文件名以 `JetsamEvent-` 开头。[2]
7. **iOS 限制为参考值**：实际限制因设备、系统状态、前后台而异，且系统内存压力大时限制会降低。[3]
8. **Memory Dump 实现不能调用 malloc/Foundation**：由于 hook 点本身在分配释放的回调中，必须使用无锁 ring buffer 和预分配内存，避免递归。[8]

## 高频追问

### Q1: 如何判断一个 OOM 是前台（FOOM）还是后台（BOOM）？

**材料回答**：在 JetsamEvent 日志的 `processes` 中找到被杀进程（`reason` 非空），查看其 `states` 字段：若为 `frontmost` 则为 FOOM，若为 `background` 或 `suspended` 则为 BOOM。[8][11] 此外，事后判断可结合下次启动时的未正常退出标记、上次前后台状态和上次内存水位。[4]

### Q2: JetsamEvent 日志中 `reason` 字段有哪些常见值？如何针对性治理？

**材料回答**：常见 reason 及治理重点：[2][8][11]
- `per-process-limit`：单进程 footprint 超限额 → 治理核心：Memory Dump、降采样、缓存治理。
- `vm-pageshortage`：整机物理页不足 → 治理：后台及时释放、降低驻留。
- `vnode-limit`：vnode/fd 资源过多 → 审计 `open/mmap/dlopen` 生命周期。
- `disk-space-shortage`：磁盘空间不足 → 分级清理、容量上限。
- `fc-thrashing`：文件缓存颠簸 → 顺序化 I/O、合理使用 mmap。
- `idle-exit`：正常后台空闲退出，不应算 OOM。

### Q3: OOM 与 Watchdog 的核心区别是什么？如何在一份异常日志中区分？

**材料回答**：
- OOM：系统因内存压力杀进程，JetsamEvent 日志 `bug_type = 298`，无堆栈，有 `reason` 和内存指标。[8][11]
- Watchdog：系统因主线程长时间不响应而杀进程，日志 `bug_type = 309`，`termination.code = 0x8BADF00D`，`termination.namespace` 为 `FRONTBOARD`、`RUNNINGBOARD` 或 `SPRINGBOARD`。[6]
- 治理上 OOM 重点做内存治理，Watchdog 重点做生命周期关键路径耗时拆解（启动、后台任务超时等）。[6]

### Q4: 为什么 OOM 必须事前监控？事前需要采集哪些数据？

**材料回答**：因为 OOM 被杀瞬间 App 通常没有执行代码的机会，不会产生标准线程堆栈，所以归因必须依赖事前和事后的证据链。[4] 事前需要持续记录：[4]
- `phys_footprint`、`os_proc_available_memory()`、内存压力比例。
- 大内存分配、页面泄漏、图片解码尺寸、缓存规模、关键业务路径。
- 事中在水位达到阈值或收到内存警告时把 Memory Dump 持续落盘。
- 事后下次启动结合未正常退出标记、是否有普通崩溃日志、App/OS 是否升级、是否 Watchdog、是否低电量、上次前后台状态和上次内存水位判断 FOOM/BOOM。

### Q5: iOS 13 以下如何获取 OOM 阈值？

**材料回答**：iOS 13 以下没有 `os_proc_available_memory()` API，只能通过 JetsamEvent 日志中的 `rpages × pageSize` 换算具体机型当时的阈值，或使用机型经验值作为参考。[1]

### Q6: Memory Dump 在 OOM 治理中解决什么问题？实现时最需要注意什么？

**材料回答**：Memory Dump 解决的是“哪段代码分配的对象还活着”的问题——排除法、MetricKit、JetsamEvent 只能告诉你可能发生了 OOM 和当时占用了多少内存，但不能直接告诉你存活对象的分配堆栈。[8] 实现时最重要注意：hook 回调里不能再次 malloc 或调用 Foundation，必须用无锁 ring buffer、预分配结构和异步处理线程，否则会造成递归崩溃。[8]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 常见崩溃类型及修复 › 8. OOM（Out Of Memory）崩溃 › OOM 阈值与内存用量获取（第357-399行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 常见崩溃类型及修复 › 8. OOM（Out Of Memory）崩溃 › Jetsam 机制与强杀类型（第340-355行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-原理.md › 崩溃-原理 › 内存相关崩溃 › OOM（Out of Memory）（第360-384行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃.md › 崩溃 › 常见面试问题 › 14. OOM 和普通崩溃有什么不同？为什么说 OOM 需要事前监控？（第200-202行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 崩溃治理（第5317-5333行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 崩溃治理（第5335-5351行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/JetsamEvent日志解读.md › JetsamEvent 日志解读 › 1. Jetsam 与 JetsamEvent 是什么（第9-22行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃日志解读.md › 崩溃日志解读 › 9. 实战案例解读 › 案例 5：OOM（EXC_RESOURCE + JetsamEvent 并发）（第593-600行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃.md › 崩溃 › 常见面试问题 › 15. JetsamEvent 日志怎么看？如何根据它判断 OOM 根因？（第204-206行）
