---
topic: dyld镜像加载
group: 编译链接与启动
generated_at: 2026-07-29T19:47:24
provider: deepseek
---

# dyld镜像加载

## 一句话总结

dyld (the dynamic link editor) 是苹果操作系统的动态链接器，负责在运行时将主可执行文件和所有依赖的动态库镜像加载到进程地址空间，完成 rebase、bind 以及各类初始化后，最终将控制权交给程序的 `main()` 函数。 [3][6]

## 核心原理

### 1. dyld 的启动入口与流程

- 进程由内核通过 `fork()` 创建，调用 `execve` 加载 Mach‑O，将 Mach‑O 映射到内存，解析 mach_header 和 load commands，并从 `LC_LOAD_DYLINKER` 将 dyld 本身加载进来。 [2]
- dyld 的启动函数链为：`__dyld_start()` → `dyldbootstrap::start()` → `dyld4::prepare()`。 [2][3]
- **prepare 阶段**是 dyld4 的核心入口，依次完成：初始化全局 `gProcessInfo` → 判断模拟器路径分叉 → 为每个镜像选择加载器。 [1]

### 2. 镜像加载器的选择（PrebuiltLoader vs JustInTimeLoader）[1][11]

- dyld4 取消了 dyld3 的“全有或全无”模式，改为**按镜像粒度**选择加载器：
  - **PrebuiltLoader**：使用上次启动序列化的快照，直接复用解析结果，启动快（适用于未变化的镜像，如系统库）。
  - **JustInTimeLoader**：实时解析 Mach‑O，构建加载器（适用于首次启动或内容变更的镜像，如用户 App 主二进制）。
- **约束**：PrebuiltLoader 的依赖链中只能包含 PrebuiltLoader，因此用户主二进制（JustInTimeLoader）依赖的系统库可以整片使用 PrebuiltLoader。 [11]

### 3. 动态库的递归加载与依赖顺序 [8]

- dyld 从主可执行文件的 `LC_LOAD_DYLIB` 读取依赖动态库路径，优先从 **dyld shared cache** 查找，使用 `mmap()` 映射，验证代码签名。 [8]
- 采用**深度优先搜索**递归加载每个动态库的依赖，每个库只加载一次。最终按被依赖的库先于依赖方的顺序构建初始化顺序。 [8]
- 对于系统动态库（位于共享缓存），其加载和符号绑定在系统构建时已预先完成，不影响 App 启动时间；App 自定义动态库则每次启动都要完成完整流程。 [9]

### 4. Rebase 与 Bind（修正确认与符号绑定）[6][8][12]

- 由于 ASLR（地址空间布局随机化），每次启动的基地址不同，需要修正指针：
  - **Rebase（重定位）**：修正指向“当前镜像**内部**”的指针，将编译时预置地址加上 ASLR 偏移量（slide）。 [8]
  - **Bind（绑定）**：修正指向“当前镜像**外部**”的指针，通过查找符号表，将符号引用绑定到目标函数或变量的实际地址（如 `_objc_msgSend`）。 [8]
- 在 prepare 源码中，rebase 和 bind 由 `ldr->applyFixups()` 一并完成。 [12]

### 5. Initializers（初始化器）的运行 [3][6][8][10]

- dyld 完成 rebase 和 bind 后，运行所有镜像的初始化器（initializers），按依赖顺序自底向上执行（被依赖的库先初始化）。 [8]
- 初始化器包括：
  - **ObjC Runtime 注册**：读取 `__objc_nlclslist`（非懒加载类列表）和 `__objc_nlcatlist`（非懒加载分类列表），**在 `+load` 方法调用之前**注册类与分类。 [10]
  - **调用 `+load` 方法**：先调用类的 `+load`，再调用分类的 `+load`。 [10]
  - **执行 C++ 静态构造函数**（全局对象的构造函数）和 `__attribute__((constructor))` 函数。 [6]
- 初始化调用链：`runAllInitializersForMain` → `Loader::runInitializersBottomUp` → `notifyObjCInit` → `load_images` → `[ViewController load]`。 [3]

### 6. 连接 libdyld.dylib 与将控制权交给 main() [2][12]

- prepare 阶段的末尾，通过 libdyld.dylib 的 `__DATA,__dyld4` 段，将 dyld 内部运行时状态（全局 APIs 对象、镜像信息、进程变量等）暴露给用户空间，使 `dlopen` / `dlsym` 等 API 可用。 [12]
- 最终通过 `LC_MAIN` 查找程序入口地址，dyld 返回胶水地址，控制权交回给 `main()` 函数。 [2]

## 关键细节与易错点

1. **dyld 的“链接”与编译期静态链接的本质区别**
   dyld 是**运行时**的动态链接器，静态链接器（`ld`）在构建阶段完成库合并和加载命令生成。dyld 加载动态库时，因无法预知 ASLR 后的地址，需要实时执行 rebase/bind，而静态链接器在编译时已确定地址并完成重定位。两者分工不同，切勿混淆。 [2]

2. **系统 App 动态库 vs 自定义动态库的启动开销差异**
   系统动态库已缓存在 **dyld shared cache**，rebase/bind 信息预计算，启动时仅需内存映射；自定义动态库即使有 Launch Closure 缓存，rebase/bind 操作**依然必须执行**（因 ASLR slide 每次不同），因此动态库数量越多，启动耗时越长。Apple 建议自定义动态库不超过 6 个。 [9]

3. **`+load` 方法在初始化器中的准确时机**
   `+load` 是 ObjC Runtime 初始化的一部分，发生在 dyld 运行 initializers 阶段，**早于 `main()` 函数**。其调用顺序为：先加载所有类的 `+load`，再加载所有分类的 `+load`（分类在前，调用在后）。 [10]

4. **模拟器路径分叉**
   在 macOS 真机上，若当前程序为模拟器程序，dyld4 的 `prepare` 会直接转入 `prepareSim()` 完整独立的加载流程，不执行后续的真机流程。 [1]

5. **dyld3 与 dyld4 的架构差异**
   dyld3 采取“双模式”（优先使用 closure 回退到 dyld2），dyld4 取消模式分层，改为**按镜像粒度**选择 PrebuiltLoader 或 JustInTimeLoader，且 libdyld.dylib 变薄，运行时代码回归 dyld 本身。 [11]

## 高频追问

### Q: dyld 加载镜像时，rebase 和 bind 的顺序是怎样的？为什么必须先 rebase 再 bind？

- 材料中明确 rebase 和 bind 由 `ldr->applyFixups()` 一次性完成 [12]，未提及严格先后顺序。但其他来源描述流程时通常先列 rebase 再列 bind [6][8]，且 ASLR 原理要求先修正内部指针，再绑定外部符号（因为外部符号查找依赖内部指针的准确性）。**本卡片材料未提供必须顺序的直接证据**，建议参考其他权威资料。

### Q: dyld shared cache 对启动优化有什么影响？

- 系统动态库放在共享缓存中，其加载和符号绑定已预先完成，App 启动时只需 mmap，不消耗符号解析时间。 [9]
- App 自定义动态库的 Launch Closure 机制能缓存依赖关系和 rebase/bind 信息，但 rebase/bind 操作本身因 ASLR 仍然必须在每次启动时执行。 [9]
- 因此，减少自定义动态库数量仍然是优化启动的有效手段。

### Q: `+load` 方法为什么会在 `main()` 之前调用？dyld 如何找到需要执行 `+load` 的类和分类？

- `+load` 属于 dyld initializers 阶段的一部分，发生在 `main()` 之前。 [6][10]
- dyld（通过 ObjC Runtime）读取 Mach‑O 的 `__DATA` 段中的 `__objc_nlclslist`（非懒加载类列表）和 `__objc_nlcatlist`（非懒加载分类列表），先遍历类列表调用 `+load`，再遍历分类列表调用 `+load`。 [10]

### Q: dyld4 中的 PrebuiltLoader 和 JustInTimeLoader 是如何选择的？用户 App 主二进制通常走哪种？

- 选择依据是镜像是否在启动时发生了变化：首次启动或文件变更后的镜像使用 JustInTimeLoader 实时解析；未变化的镜像（如共享缓存中的系统库）使用 PrebuiltLoader 重用快照。 [1][11]
- 用户 App 主二进制是新编的，必然是 JustInTimeLoader；但其依赖的系统库在共享缓存中有 PrebuiltLoader，可以整片接入（遵守 PrebuiltLoader 依赖链约束）。 [11]

### Q: dyld4 相比 dyld3 做了哪些关键改进？

- 取消 dyld3 的“双模式”（优先 closure，失败回退 dyld2），减少代码冗余和混淆。 [11]
- 将粒度从进程级降到镜像级：每个镜像独立选择 PrebuiltLoader 或 JustInTimeLoader，而非整个进程统一模式。 [11]
- 将运行时代码从 libdyld.dylib 移回 dyld 中，libdyld.dylib 变薄。 [11]

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › dyld源码 › prepare（第133-168行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/segmentfault.com/ios-编译链接与-mach-o-深度解析-静态库-动态库原理剖析-到工程化实践.md › 十一、dyld 及其工作流程 › 6. dyld 加载过程（第4400-4457行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › (全文)（第1-8行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Mach-O的链接、装载与库.md › Mach-O的链接、装载与库 › 四、动态库与运行时加载 › 4.4 dyld 加载流程（第650-665行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 六、常见面试问题 › Q1: APP启动的详细流程 › Pre-main 阶段（第1108-1126行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/启动优化/启动优化-减少动态库.md › 启动优化-减少动态库 › 问题分析（第7-36行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/load与initialize的区别.md › +load与+initialize的区别 › 调用时机详解 › +load的调用时机（第53-71行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/iOS App 启动：三代 dyld、pre-main 与可测量的优化项.md › App 启动：三代 dyld、pre-main 与可测量的优化项 › 二、三代 dyld：分界线能查到，而且不是社区说的那个 › dyld4 是来推翻 dyld3 的（第227-258行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › dyld源码 › prepare（第274-302行）
