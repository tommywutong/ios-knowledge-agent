---
topic: Mach-O Segment与Section
group: 编译链接与启动
generated_at: 2026-07-29T19:46:21
provider: deepseek
---

# Mach-O Segment与Section

## 一句话总结

Mach-O 使用 Segment（段）和 Section（节）两级结构组织数据和代码：Segment 是内存映射与权限管理的基本单位，控制可读/可写/可执行属性；Section 是数据组织的逻辑单位，存放特定类型的数据，同一 Segment 内的 Section 共享该 Segment 的内存保护属性。[4][8]

## 核心原理

- **两级结构**：Segment 是 Section 的容器，一个 Segment 可包含多个 Section。[4][8] 例如 `__TEXT` Segment 包含 `__text`（机器码）、`__stubs`（动态库调用桩）、`__cstring`（C 字符串常量）、`__const`（常量数据）等多个 Section。[4][8]
- **内存映射基本单位**：Segment 是操作系统进行内存映射的单位，必须对齐到页面边界（PAGE boundary）。[4][6][9] 页的大小与硬件相关：arm64 架构下为 16KB，其余架构（如 x86_64）为 4KB。[7]
- **权限控制**：每个 Segment 定义独立的内存保护属性（可读 r/可写 w/可执行 x）。[4][5][6][8] 例如 `__TEXT` 为 `r-x`（只读、可执行），`__DATA` 为 `rw-`（可读、可写），`__PAGEZERO` 为不可访问。[1][7][8]
- **Section 继承权限**：Section 从属于 Segment，不单独定义权限，其权限继承自所属的 Segment。[4][6][8]
- **命名规范**：Segment 约定使用双下划线加大写字母（如 `__TEXT`、`__DATA`），Section 约定使用双下划线加小写字母（如 `__text`、`__data`）。[6][10]
- **结构体定义**：Section 的元数据由 `struct section_64` 结构体描述（80 字节），该结构体冗余编码了所属 Segment 名称（`segname`）和 Section 自身名称（`sectname`），二者均可长达 16 字节。这种设计允许在不依赖字符串表的情况下直接读取 Section 名称。[9] Section 的语义由其名称（和 flags）决定。[9]

## 关键细节与易错点

- **Segment 页对齐，Section 不一定**：Segment 的大小总是页面大小的整数倍（最小为 4KB 或 16KB），其大小由包含的所有 Section 大小决定并向上取整至页边界。Section 没有整数倍页大小的限制，且 Section 之间不会重叠。[6][7]
- **“五大分区”及容易忽略的区域**：
    - `__PAGEZERO`：在 64 位 Mach-O 中保留低地址范围（起始地址 0x0），不映射为可访问内存。任何对 NULL 指针的解引用都会访问至此区域，立即触发 EXC_BAD_ACCESS 崩溃。[1][5][8]
    - `__LINKEDIT`：保存符号表、字符串表、重定位信息、代码签名等链接信息，服务于装载、符号解析和调试。只读（`r--`）。它不属于业务数据“五大分区”。[1][7][8]
- **`__DATA_CONST` 和 `__DATA_DIRTY`**：是 iOS 13+ 对 `__DATA` 段的细分优化。初始状态下 `__DATA_CONST` 的某些数据（如 `__got` 填充前）可能可写，启动完成后变为只读（`r--`），可被多进程共享。`__DATA_DIRTY` 存放运行时一定会修改的数据，单独分页可优化写时复制（COW）性能。[5][8]
- **编译时明确 Section**：编译器在汇编阶段（从 `.s` 文件可看出）已明确将不同类型的代码和数据放入特定的 Section 中，例如：
    - `__TEXT,__objc_classname`, `__TEXT,__objc_methname`, `__DATA,__objc_const`, `__DATA,__objc_data` 等。运行时并不“创建”类，而是登记编译时已铺好的静态数据。[11]
- **Load Commands 描述布局**：Mach-O 的 Load Commands 中最常见的是 `LC_SEGMENT_64`，它描述了一个段（如 `__TEXT`、`__DATA`）在文件和内存中的布局。[2][3][5]

**常见 Segment 及其权限列表**（基于材料[1][5][8]）：

| Segment | 典型权限 | 包含的常见 Section |
|---------|---------|------------------|
| `__PAGEZERO` | 不可访问 | 无 |
| `__TEXT` | `r-x` | `__text`, `__stubs`, `__cstring`, `__objc_methname`, `__const` |
| `__DATA_CONST` | `r--`（启动后） | `__got`, `__const` (运行时), `__objc_classlist` |
| `__DATA` | `rw-` | `__data`, `__bss`, `__la_symbol_ptr` |
| `__DATA_DIRTY` | `rw-` | 运行时一定修改的数据 |
| `__LINKEDIT` | `r--` | 符号表、字符串表、代码签名等 |

## 高频追问

**Q1: Segment 和 Section 的关系是什么？为什么需要这种两级结构？**

**A:** Segment 是 Section 的容器，也是内存映射和管理权限的基本单位；Section 是逻辑组织单位。[4][8] 这种设计提供了：
- **安全性**：操作系统可按 Segment 设置内存保护（W^X 原则），防止代码被修改。[4]
- **灵活性**：链接器可按 Section 精细操作，如合并多个目标文件的同名 Section。[4]
- **效率**：运行时只需按 Segment 映射，无需处理每个 Section 的权限。[4]

**Q2: 常见的 `__TEXT`、`__DATA`、`__LINKEDIT` 段各自的主要作用是什么？**

**A:** `__TEXT` 包含代码和只读常量，以只读、可执行方式映射（`r-x`），不可修改。[6][7] `__DATA` 包含可写数据（如全局变量），以可读写方式映射（`rw-`）。[6][7] `__LINKEDIT` 保存链接信息，只读。[7][8]

**Q3: `__PAGEZERO` 段有什么作用？**

**A:** `__PAGEZERO` 位于地址 0x0 起始的保护区域，不映射为可访问内存。其作用是使得任何对 NULL 指针的解引用都会立即访问到不可访问的区域并触发 EXC_BAD_ACCESS 崩溃，帮助尽早发现空指针错误。[1][5][8]

**Q4: iOS 13+ 中对 `__DATA` 段做了哪些细分优化？**

**A:** iOS 13+ 新增了 `__DATA_CONST` 和 `__DATA_DIRTY` 来细分 `__DATA` 段。[5][8] `__DATA_CONST` 在启动完成后变为只读，可被多进程共享。[5][8] `__DATA_DIRTY` 存放运行时一定会修改的数据，将其单独分页以优化写时复制（COW）性能。[5][8]

**Q5: 如果代码尝试写入一个位于 `__TEXT` 段中的 Section（例如 `__cstring`），会发生什么？**

**A:** 会触发崩溃。因为 `__TEXT` 整段被映射为只读和可执行（`r-x`），[1][6][7] 任何写入操作都会违反权限，由操作系统上报 `EXC_BAD_ACCESS`。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：从虚拟地址空间到堆与栈.md › iOS 内存地图：从虚拟地址空间到 VM Region › Mach-O › Segment 与 Section（第286-306行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/Mach-O.md › 2026-05-14 23:26 Mach-O 文件结构与加载机制 › 整理后内容（第11-21行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/Mach-O.md › 2026-05-14 23:26 Mach-O 文件结构与加载机制（第3-9行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Mach-O的链接、装载与库.md › Mach-O的链接、装载与库 › 二、Mach-O 文件格式 › 2.3 Segment 详解 › Segment 与 Section 的关系（第163-208行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Mach-O的链接、装载与库.md › Mach-O的链接、装载与库 › 七、常见面试问题 › Q1: Mach-O文件由哪几部分组成？（第1424-1463行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Mach-O可执行文件.md › 4. Section（第211-250行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/优化-app-的启动时间.md › [优化 App 的启动时间](http://yulingtianxia.com/blog/2016/10/30/Optimizing-App-Startup-Time/) › App 运行理论 › 理论速成 › Mach-O 镜像文件（第80-92行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第948-992行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/maskray/exploring-object-file-formats.md › Exploring object file formats › Sections › Sections (Mach-O)（第427-451行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/包瘦身/包瘦身-可执行文件优化.md › 包瘦身-可执行文件优化 › 段迁移优化（__TEXT段瘦身） › 注意事项（第897-903行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/iOS 从源码到可执行文件：四个阶段与符号.md › 从源码到可执行文件：四个阶段与符号 › 一、四个阶段，两个进程 › 每一步在做什么（第108-139行）
