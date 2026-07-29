---
topic: Memory Footprint与OOM
group: 内存管理
generated_at: 2026-07-29T19:35:18
provider: deepseek
---

# Memory Footprint与OOM

## 一句话总结

OOM（Out Of Memory）是iOS系统的Jetsam机制因进程`phys_footprint`超限或整机内存压力过大而直接杀进程的事件，被杀瞬间通常没有执行代码机会，也不产生标准线程堆栈，因此OOM治理的核心是**事前持续记录内存水位**与**事后结合JetsamEvent日志归因** [5]。

## 核心原理

1.  **Jetsam机制**：iOS通过XNU内核的`memorystatus`管理物理内存资源。当系统整体或单进程内存超限时，按Jetsam优先级杀死进程，终止原因写入Jetsam Event Report [6]。
2.  **phys_footprint 是判据**：Jetsam统计进程占用使用的是`phys_footprint`（dirty memory + compressed memory），而非`resident_size`（RSS，不包含压缩内存）。两者差异可达2~3倍，`resident_size`不能作为OOM依据 [1][2]。
3.  **OOM强杀类型**：常见类型及治理核心如下：

| 强杀类型 (reason) | 含义 | 治理核心 |
|------------------|------|---------|
| `per-process-limit` | 单进程footprint超过限额（主要类型） | Memory Dump、降采样、缓存治理 [6] |
| `vm-pageshortage` | 系统可用物理页不足，按优先级清理 | 后台及时释放、降低驻留 [6] |
| `vnode-limit` | 进程打开vnode过多（iOS 15+约10000） | 审计fd泄漏 [6] |
| `disk-space-shortage` | 磁盘可用空间不足 | 分级清理、容量上限 [6] |
| `highwater` | 常驻进程超过预期 | 系统扩展/后台任务场景 [6] |
| `fc-thrashing` | 文件缓存颠簸 | 顺序化I/O、合理使用mmap [6] |
| `idle-exit` | 后台空闲退出（正常） | 非异常，和OOM无关 [10] |

4.  **Watchdog vs OOM**：Watchdog是系统为保证应用响应性设置的看门狗机制，常见于生命周期阶段超时。日志特征是`bug_type = 309`，`termination.code = 0x8BADF00D`。治理思路是围绕生命周期关键路径做耗时拆解。Watchdog必须从OOM排除法中单独剥离，否则会把前台卡死误判成FOOM [8]。
5.  **事前监控的必要性**：普通崩溃有异常类型、信号和堆栈；OOM被杀瞬间没有执行代码机会，因此归因必须依赖事前（持续记录`phys_footprint`、`os_proc_available_memory()`、内存压力比例等）和事后（结合未正常退出标记、JetsamEvent日志等）的证据链 [5]。

## 关键细节与易错点

1.  **phys_footprint vs resident_size**：`resident_size` 是RSS，不包含被压缩的内存；`phys_footprint` 是Apple真正用于判定Jetsam的值。两者不能混用 [1][2]。
2.  **os_proc_available_memory()的正确使用**：iOS 13+可用，返回**当前进程还可申请的内存**字节数。OOM阈值（limit）= `phys_footprint` + `os_proc_available_memory()`。压力比例（pressure）= `footprint / limit` [1]。
3.  **JetsamEvent日志物理换算**：`processes`中记录的`rpages`是**物理页数**，必须乘以`pageSize`再换算成MB才是当时footprint [3]。
4.  **vnode-limit的典型值**：iOS 15+进程打开vnode上限约为10000个，超出后会触发Jetsam [6][10]。
5.  **SDWebImage内存优化选择**：`limitBytes`只保证不超过某个内存上限，输出尺寸取决于原图；`thumbnail`（通过`SDWebImageContextImageThumbnailPixelSize`）直接指定目标像素尺寸。做列表场景应使用后者 [7]。
6.  **EXC_RESOURCE与JetsamEvent并发日志**：一个进程OOM通常产生两份日志：`bug_type=109`的`EXC_RESOURCE`（有堆栈）和`bug_type=298`的JetsamEvent（无堆栈，有整机内存画像）。实战中应将两者按`incident_id`/`timestamp`串起来分析 [9]。
7.  **JetsamEvent日志中的`processes`字段**：`largestProcess`不一定等于被杀对象，需在`processes`里找`reason`非空的条目，那才是被杀进程 [3]。

## 高频追问

1.  **如何区分FOOM与BOOM？**
    *   **回答要点**：结合**上次退出前的前后台状态**和**JetsamEvent日志中的`states`字段**判断 [3][5]。FOOM（Foreground OOM）指App在前台时被杀，BOOM（Background OOM）指在后台或挂起时被杀。结合`states`（如`frontmost`）判断 [3]。

2.  **什么是sharecoalition？在OOM归因中有什么意义？**
    *   **回答要点**：查看JetsamEvent日志的`coalition`字段 [3]。主App、WebKit子进程和Extension可能共享coalition账本，同组兄弟进程也可能是真正内存大户，不能只看当前App进程 [3]。

3.  **为什么说OOM需要事前监控？**
    *   **回答要点**：OOM是Jetsam直接杀进程，被杀瞬间App通常没有执行代码的机会，也不会产生标准线程堆栈 [5]。因此归因必须依赖事前（持续记录`phys_footprint`、`os_proc_available_memory()`、内存压力比例、大内存分配等）和事后（下次启动结合未正常退出标记、JetsamEvent日志等）的证据链 [5]。

4.  **JetsamEvent日志怎么看？第一步看什么？**
    *   **回答要点**：JetsamEvent日志文件名以`JetsamEvent-`开头，JSON格式，不含线程堆栈 [6]。第一步看`reason`字段，确定Jetsam触发原因（如`per-process-limit`、`vm-pageshortage`等） [3][10]。

5.  **收到了`EXC_RESOURCE`和JetsamEvent两份日志，怎么配合使用？**
    *   **回答要点**：将两者按`incident_id`/`timestamp`串起来 [9]。堆栈从`bug_type=109`的`EXC_RESOURCE`日志获取，整机内存归因从`bug_type=298`的JetsamEvent日志获取 [9]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 常见崩溃类型及修复 › 8. OOM（Out Of Memory）崩溃 › OOM 阈值与内存用量获取（第357-399行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/APM/APM-数据采集.md › APM-数据采集 › 四、内存 / OOM 监控 › 4.1 内存水位采集（第281-306行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃.md › 崩溃 › 常见面试问题 › 15. JetsamEvent 日志怎么看？如何根据它判断 OOM 根因？（第204-206行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃.md › 崩溃 › 常见面试问题 › 14. OOM 和普通崩溃有什么不同？为什么说 OOM 需要事前监控？（第200-202行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 常见崩溃类型及修复 › 8. OOM（Out Of Memory）崩溃 › Jetsam 机制与强杀类型（第340-355行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/架构与网络/iOS SDWebImage：下载、解码与两级缓存的完整链路.md › SDWebImage：下载、解码与两级缓存的完整链路 › 三、downsample：这一节最实用（第260-278行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 崩溃治理（第5317-5333行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃日志解读.md › 崩溃日志解读 › 9. 实战案例解读 › 案例 5：OOM（EXC_RESOURCE + JetsamEvent 并发）（第593-600行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/JetsamEvent日志解读.md › JetsamEvent 日志解读 › 4. Body 顶层字段详解 › 4.2 `reason`（第113-126行）
