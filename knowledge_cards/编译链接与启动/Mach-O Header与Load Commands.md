---
topic: Mach-O Header与Load Commands
group: 编译链接与启动
generated_at: 2026-07-29T19:45:55
provider: deepseek
---

# Mach-O Header与Load Commands

## 一句话总结

Mach‑O 文件由 **Header**（标识 CPU 架构、文件类型与命令总数）、**Load Commands**（指导 dyld 如何加载，包括段映射、依赖库、入口点等）和 **Data**（按 Segment/Section 组织的实际代码和数据）三部分组成 [1][3][4][6]。

## 核心原理

1. **三段式结构**
   Mach‑O 文件宏观上由三块组成：
   - **Header（头部）**：描述文件的基本信息，相当于文件的“身份证” [3][6]。
   - **Load Commands（加载命令）**：相当于文件的“目录”，告诉 dyld 如何加载 [1][3][6]。
   - **Data（数据区）**：实际存储代码和数据，按 Segment（段）和 Section（节）两级结构组织 [3][6]。

2. **Header 的具体内容**
   `struct mach_header_64` 包含以下字段 [3][10]：
   - `magic`：魔数，64 位 Mach‑O 为 `0xfeedfacf`，也用于判断字节序和位宽 [10]。
   - `cputype` / `cpusubtype`：目标 CPU 架构（如 ARM64、X86_64） [3][7][10]。
   - `filetype`：文件类型（如 `MH_EXECUTE` 可执行文件、`MH_DYLIB` 动态库） [3][6][10]。
   - `ncmds`：Load Commands 的数量 [3][10][11][12]。
   - `sizeofcmds`：所有 Load Commands 的总字节数 [10]。
   - `flags`：标记（如 `MH_NOUNDEFS`、`MH_DYLDLINK`、`MH_TWOLEVEL`、`MH_PIE`） [7][10]。
   - `reserved`：保留字段，仅 64 位格式有 [10]。

3. **Load Commands 的通用结构**
   每个 Load Command 以 `struct load_command` 开头 [8][11]：
   ```c
   struct load_command {
       uint32_t cmd;     /* 命令类型，如 LC_SEGMENT_64 */
       uint32_t cmdsize; /* 命令总字节数 */
   };
   ```
   实际命令大于此基本结构；`cmd` 字段决定后续数据的解释方式 [8]。Load Commands 在文件中必须 **8 字节对齐**（64 位 Mach‑O） [8]。

4. **常见 Load Commands 及其作用**
   - `LC_SEGMENT_64`：定义段（如 `__TEXT`、`__DATA`）在文件和虚拟内存中的布局，指定地址、大小、保护属性 [1][2][3][6]。
     - 内核处理时调用 `mmap()` 将段映射到虚拟地址空间并设置内存保护 [9]。
   - `LC_LOAD_DYLIB`：声明依赖的动态库（如 Foundation、UIKit） [3][6]。
     - 内核提取路径加入待加载队列，记录版本要求 [9]。
   - `LC_MAIN`：记录程序入口点（main 函数偏移），结合 ASLR 偏移计算虚拟地址 [6][9]。
   - `LC_CODE_SIGNATURE`：记录代码签名的位置和大小，供后续验证 [6][9]。
   - `LC_SYMTAB` / `LC_DYSYMTAB`：符号表与动态符号表的位置 [3][6]。
   - `LC_DYLD_INFO_ONLY`：记录 Rebase、Bind、Export 信息，传递给 dyld [9]。
   - `LC_ENCRYPTION_INFO_64`：记录加密段范围（如 App Store 加密） [9]。

5. **遍历 Load Commands 的方法**
   通过 Header 中的 `ncmds` 和 `sizeofcmds` 定位命令区，依次跳过每个命令的 `cmdsize` 即可遍历 [11][12]。
   ```c
   // 伪代码示意（来自 [12]）
   uintptr_t lc_cursor = (uintptr_t)mh + sizeof(struct mach_header_64);
   for (uint32_t idx = 0; idx < mh->ncmds; idx++) {
       struct load_command *lc = (struct load_command *)lc_cursor;
       // 处理 lc...
       lc_cursor += lc->cmdsize;
   }
   ```

6. **内核加载时的处理流程**
   - 内核用 `mmap()` 将 Mach‑O 映射到虚拟内存（惰性加载） [9]。
   - 读取 Header 验证魔数、架构匹配、文件类型，并根据 `ncmds` / `sizeofcmds` 确定 Load Commands 区域 [9]。
   - 遍历所有 Load Command，对每种类型执行对应操作（如映射段、记录依赖、保存入口点偏移） [9]。

## 关键细节与易错点

- **Header 与 Load Commands 是固定长度吗？**
  Header 本身大小固定（`mach_header_64` 为 32 字节 [10]），但 Load Commands 数量不固定，由 `ncmds` 和 `sizeofcmds` 说明 [3][10]。不同的 Load Command 拥有不同的 `cmdsize` [8][11]，所以只能用迭代方式解析，不能假设固定大小。

- **`__PAGEZERO` 段**
  位于地址 0x0 起始的不可访问段，用于捕获对 NULL 指针的解引用 [6]。该段不包含任何 Section。

- **`LC_MAIN` 与 `LC_UNIXTHREAD` 的区别**
  材料未直接对比，但 `LC_MAIN` 是现代 iOS/macOS 可执行文件使用的入口命令 [6][9]，旧格式可能用 `LC_UNIXTHREAD`。

- **`LC_SEGMENT_64` 与 Segment、Section 的关系**
  Segment 是虚拟内存映射的基本单位，同一 Segment 内的 Section 共享内存保护属性 [6]。所有 Segment 的布局由 Load Command 定义，内核据此决定如何映射 [1][2][9]。

- **加载时不“解析”整个文件**
  内核仅基于 Load Commands 映射段，并不解析 Section 内的具体符号；符号绑定等工作后续由 dyld 完成 [9]。

## 高频追问

**Q1: Mach‑O 文件由哪几部分组成？**
由 Header、Load Commands、Data（Segment/Section）三部分组成 [1][3][4][6]。

**Q2: Header 中的哪些字段对加载最关键？**
- `magic`：验证文件格式 [3][9][10]。
- `cputype` / `cpusubtype`：验证架构兼容性 [3][7][9]。
- `filetype`：区分可执行文件、动态库等 [3][6]。
- `ncmds` / `sizeofcmds`：确定 Load Commands 区域的范围 [3][10][11]。

**Q3: 如何遍历 Load Commands？**
获取 Header 后，计算头部偏移（对 64 位为 `sizeof(mach_header_64)`），然后根据 `ncmds` 循环，每次跳过当前 Load Command 的 `cmdsize` 字节，直至处理完所有命令 [11][12]。

**Q4: `LC_SEGMENT_64` 命令包含哪些关键信息？**
包含段名（如 `__TEXT`）、在文件中的偏移与大小、在虚拟内存中的地址与大小、以及内存保护属性（可读/可写/可执行） [1][2][6][9]。内核根据这些信息调用 `mmap()` 并设置权限 [9]。

**Q5: 为什么说 Load Commands 是 Mach‑O 的“目录”？**
因为 Load Commands 描述了文件中所有 Segment 的位置、依赖库、入口点、符号表等关键元数据，加载器（内核和 dyld）完全依赖这些命令来完成内存映射和动态链接 [3][6][9]。

**Q6: `__LINKEDIT` 段的作用是什么？**
存放符号表、字符串表、代码签名等链接时需用到的只读数据 [6]。

**Q7: 内核处理 Load Commands 时会做代码签名验证吗？**
内核记录 `LC_CODE_SIGNATURE` 中的签名位置和大小，为后续验证准备数据，但实际验证可能在稍后阶段进行 [9]。详细时机本卡片材料不足。

**Q8: 动态库依赖（`LC_LOAD_DYLIB`）是在内核态还是用户态处理的？**
内核负责提取路径并加入队列，版本兼容性检查和实际加载由 dyld（用户态）完成 [9]。

**Q9: Header 本身属于哪个 Segment？**
本卡片材料不足。有资料提到 header 位于 `__TEXT` 段中 [10]，但该观点未在提供的材料正文中明确说明，因此不在此处确认。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/Mach-O.md › 2026-05-14 23:26 Mach-O 文件结构与加载机制（第3-9行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/Mach-O.md › 2026-05-14 23:26 Mach-O 文件结构与加载机制 › 整理后内容（第11-21行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Mach-O的链接、装载与库.md › Mach-O的链接、装载与库 › 二、Mach-O 文件格式 › 2.2 Mach-O 的结构（第122-159行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Mach-O可执行文件.md › 5 Mach-O › 5.2 Mach-O的基本结构（第339-347行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Mach-O的链接、装载与库.md › Mach-O的链接、装载与库 › 七、常见面试问题 › Q1: Mach-O文件由哪几部分组成？（第1424-1463行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/mach-o-executables.md › Sections › Mach-O（第399-438行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2012-11-30-let-s-build-a-mach-o-executable.md › (全文)（第117-149行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 一、冷启动（Cold Launch） › Pre-main 阶段 › 1. 加载可执行文件（Load Executable） › 1.2 加载Mach-O到内存（第99-147行）
[10] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/iOS Mach-O：结构、符号绑定与 chained fixups.md › Mach-O：结构、符号绑定与 chained fixups › 一、三段式，以及 header 自己也在 `__TEXT` 里（第44-105行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/lowlevelbits/parsing-mach-o-files-low-level-bits.md › Parsing Mach-O files › Parse Mach-O file › Parsing › Mach-O Header（第232-271行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ddeville.me/dynamic-linking-on-ios.md › Dynamic libraries on iOS › Logging loaded dynamic libraries（第149-179行）
