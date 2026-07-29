---
topic: 虚拟内存与VM Region
group: 内存管理
generated_at: 2026-07-29T19:34:56
provider: deepseek
---

# 虚拟内存与VM Region
## 一句话总结
iOS 中虚拟地址空间由内核按 VM Region（虚拟内存区域）进行管理，每个 Region 是一段连续的虚拟地址范围，具有独立的保护权限和内容来源；整个进程的虚拟地址空间大小取决于设备物理内存量，且通过 VM Tracker 等工具可以按 Region 观察其 Dirty、Resident 状态，从而准确评估 App 的真实内存占用。

## 核心原理
1. **VM Region 是内核描述地址空间的真实方式** [6]
   对于进程中每一段连续的虚拟地址范围，内核使用 VM Region 结构来记录其起始地址、大小、保护权限（读/写/执行）、映射来源（如 Mach-O 文件、mmap、堆、栈等）。`vm_region_64()` 系统调用可以查询指定地址所属 Region 的信息，包括权限和大小 [10]。

2. **iOS 64 位虚拟地址空间大小取决于物理内存量** [3]
   iOS 内核（xnu）在 `pmap.c` 中根据 `max_mem`（物理内存大小）计算最大虚拟地址偏移：
   - 设备 RAM > 3 GiB 时，最大偏移 = `min_max_offset + 0x138000000`，总地址空间约 15.375 GiB
   - 设备 RAM > 1 GiB 且 ≤ 3 GiB 时，最大偏移 = `min_max_offset + 0x38000000`，总地址空间约 9.375 GiB
   - 设备 RAM ≤ 1 GiB 时，最大偏移 = `min_max_offset`（约 6.375 GiB）
   其中 `min_max_offset` 基于共享区域基址和大小计算。因此，不同物理内存的 iOS 设备拥有不同大小的虚拟地址空间（这与传统的固定 48 位地址空间不同）。

3. **VM Region 的 Dirty / Resident / Swapped 状态** [5][12]
   - **Resident Size**：当前在物理内存中的页面大小（包括可被换出的 clean 页面）。
   - **Dirty Size**：已被修改过的页面大小（无法被系统换出，必须保留在物理内存或压缩内存中）。
   - **Swapped / Compressed**：被系统压缩或交换出去的页面。
   VM Tracker 显示 Dirty + Resident 的组合被视为 App 真实内存使用的最准确视图 [12]。Dirty 内存的多少直接决定了 App 被 Jetsam 终止的概率。

4. **进程级内存指标与 VM Region 的差异** [9]
   `task_basic_info.virtual_size` 反映进程保留的虚拟地址范围总量（不直接对应物理 RAM 占用），`resident_size` 反映当前驻留物理内存的页面总量（不包含被压缩的部分）。而 Apple 用于判定 Jetsam 的指标是 `task_vm_info.phys_footprint`，它更接近进程责任内存（包括脏页和压缩内存）[11]。

5. **ASLR 与 VM Region 的关系** [8]
   地址空间布局随机化（ASLR）使得每个进程加载时，其代码段、数据段等 VM Region 的基地址增加一个随机偏移（ASLR Offset）。函数的内存地址计算为：`VM Address = File Offset + ASLR Offset + __PageZero Size`。

## 关键细节与易错点
- **虚拟地址空间大小是设备相关的**：不要假设所有 iOS 设备都有相同的虚拟地址空间上限。超过设备物理内存量对应的地址空间后，继续映射会失败（mmap 消耗虚拟地址空间）[3][7]。
- **`resident_size` ≠ `phys_footprint`**：`resident_size` 是 RSS，不包含被压缩的内存；`phys_footprint` 包含压缩内存，是 Jetsam 判定依据。两者差距可达 2~3 倍 [11]。
- **VM Region 观察比 Allocations 更准确**：Allocations 只追踪堆上的分配，而图像缓存、mmap 文件、Metal Heap 等非堆内存需要 VM Tracker 的 VM Region 视图才能看到 [5]。
- **`vm_region_64()` 可以检查指针是否属于可读 Region**：通过查询保护权限（`info.protection & VM_PROT_READ`）判断该地址是否在可读的 VM Region 内 [10]。
- **Large memory spikes 会触发系统驱逐只读页面**：即使只是短暂的内存高峰，系统也可能将应用的代码页（clean 只读页）从物理内存中换出，之后加载回来会导致卡顿 [12]。

## 高频追问
1. **iOS 虚拟地址空间大小为什么在不同设备上不同？**
   因为 iOS 内核根据设备物理内存量动态计算最大虚拟地址偏移 [3]。这是为了在有限的地址转换资源下平衡可用地址空间与性能，更大的物理内存可以支持更大的虚拟地址空间。

2. **如何获取一个地址所属的 VM Region 信息？**
   使用 `vm_region_64()` 系统调用。传入目标地址，返回该 Region 的起始地址、大小、保护权限等信息。注意地址会被调整为 Region 的起始地址 [10]。

3. **`phys_footprint` 与 `resident_size` 的区别是什么？为什么线上监控要用 `phys_footprint`？**
   `resident_size` 是驻留物理内存的总量，但不包括被压缩的页；`phys_footprint` 是 Apple 官方用于判定 Jetsam 的口径，包含脏页和压缩页。线上监控使用 `phys_footprint` 更准确反映 App 的内存压力 [9][11]。

4. **大量使用 mmap 会对虚拟地址空间造成什么影响？**
   mmap 会分配虚拟内存区域，消耗虚拟地址空间。在 32 位系统上地址空间有限（4GB），64 位系统空间较大但仍需合理使用，否则可能导致地址空间耗尽 [7]。

5. **如何判断 App 的真实内存使用？为什么 Allocations 显示的内存与 VM Tracker 不同？**
   VM Tracker 的 Dirty Size 和 Resident Size 是真实内存使用的最准确视图 [12]。Allocations 只跟踪堆上 malloc/new 的内存，而图片解码后的 IOSurface、mmap 文件、Metal Heap 等不在堆上，需要通过 VM Tracker 观察 VM Region 来发现 [5]。

## 原始资料索引

[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/alwaysprocessing/size-matters-an-exploration-of-virtual-memory-on-ios-an-out-of-memory-crash-while-debuggin.md › 大小问题：iOS 虚拟内存探究 › iOS 上的虚拟内存 › 64 位虚拟地址空间（第49-91行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/Instruments详解.md › Instruments详解 › 四、内存工具 › 4.3 VM Tracker（第209-215行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：Clean、Dirty、Compressed 与 Memory Footprint.md › iOS 内存：Clean、Dirty、Compressed 与 Memory Footprint › 前言（第17-21行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/mmap详解.md › mmap详解 › 注意事项与最佳实践 › 2. 内存管理（第630-638行）
[8] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/地址空间布局随机化ASLR及iOS内核如何实现随机化.md › 3. 函数地址（第131-142行）
[9] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：Clean、Dirty、Compressed 与 Memory Footprint.md › iOS 内存：Clean、Dirty、Compressed 与 Memory Footprint › 申请内存不等于立刻产生等量的 Memory Footprint › 先区分进程级汇总与逐个 VM Region（第49-98行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/blog.timac.org/testing-if-an-arbitrary-pointer-is-a-valid-objective-c-object.md › 有效且可读的内存（第240-293行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/APM/APM-数据采集.md › APM-数据采集 › 四、内存 / OOM 监控 › 4.1 内存水位采集（第281-306行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/ios-5-tech-talk-michael-jurewitz-on-performance-measurement.md › 2. Minimize Memory Usage › Instruments: Allocations + Leaks + VM Tracker + Activity Monitor（第123-128行）
