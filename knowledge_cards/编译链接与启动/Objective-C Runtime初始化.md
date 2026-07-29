---
topic: Objective-C Runtime初始化
group: 编译链接与启动
generated_at: 2026-07-29T19:47:58
provider: deepseek
---

# Objective-C Runtime初始化

## 一句话总结

Objective-C Runtime 初始化由 dyld 在镜像加载过程中通过 `_dyld_objc_notify_register` 回调驱动，核心入口是 `_objc_init`（在 libSystem 初始化时被调用），向 dyld 注册 `map_images`、`load_images`、`unmap_image` 三个回调，依次完成类注册、元数据解析、类 realize、Category 合并和 `+load` 方法的调用 [1][2][9]。

## 核心原理

1. **`_objc_init` 注册回调**
   `_objc_init` 是 ObjC Runtime 的引导初始化函数，由 libSystem 在其内部初始化流程中调用（在 library initialization time 之前）[2][9]。`_objc_init` 内部依次执行 `environ_init()`、`tls_init()`、`static_init()`、`runtime_init()`、`exception_init()` 等基础环境初始化，最后调用 `_dyld_objc_notify_register(&map_images, load_images, unmap_image)`，将三个回调注册到 dyld 的 `RuntimeState` 中 [1][2]。

2. **`map_images` —— 元数据解析与类注册**
   dyld 每加载一个镜像后，会回调 `map_images`（内部调用 `map_images_nolock` → `_read_images`）[2][3][10]。该阶段完成：
   - 从 Mach-O 的 `__DATA`、`__DATA_CONST`、`__DATA_DIRTY` 段中读取 `__objc_classlist`（类列表）、`__objc_catlist`（Category 列表）、协议列表等元数据 [3][6]。
   - 遍历 `__objc_classlist`，将所有类**注册**到全局类表 `gdb_objc_realized_classes` [3][6]。
   - **类的 realize**：对**非懒加载类**（实现了 `+load` 方法的类）**立即 realize** —— 调用 `realizeClassWithoutSwift` 创建可读写的 `class_rw_t` 结构（编译期的 `class_ro_t` 是只读的），建立继承链（`cls->superclass`）和元类关系（`cls->isa`），初始化方法缓存 `cache_t`。**懒加载类**（未实现 `+load`）则**延迟到首次收到消息时**才 realize（`objc_msgSend` → `lookUpImpOrForward` 触发）[3][6]。
   - **处理 Category**：遍历 `__objc_catlist`，若对应类已 realize，立即将 Category 的方法、属性、协议附加到其 `class_rw_t` 上（方法插入到列表**前面**，实现“覆盖”效果）；若对应类尚未 realize，则暂存到 `unattachedCategories` 表，待类 realize 时再附加 [3][4][8]。
   - 此阶段中 Category 的处理实现经历了性能优化：旧版使用 `addUnattachedCategoryForClass` + `remethodizeClass` + `attachCategories` 三步，新版对已 realized 的类直接调用 `attachCategories` 立即合并，只有未 realized 的类才暂存。**核心思路不变**：延迟合并 [4][8]。

3. **`load_images` —— 调用 `+load` 方法**
   dyld 通过 `notifyObjCInit` 回调 `load_images`（内部调用 `call_load_methods`）[1][5]。`notifyObjCInit` 有双重条件门控：libobjc 已注册回调（`_notifyObjCInit != nullptr`）且该镜像可能含有 `+load` 方法（`mayHavePlusLoad == true`）时才触发 [5]。
   所有 `+load` 方法**通过函数指针直接调用**，不经过 `objc_msgSend`，因此 Category 的 `+load` 不会覆盖主类的 `+load`，两者都会执行 [3][6]。调用顺序：父类优先于子类 → 类优先于 Category → 同一镜像内按编译顺序（Build Phases → Compile Sources）→ 不同镜像按依赖顺序（被依赖的库先执行）。所有 `+load` 在主线程串行调用，直接阻塞启动 [3][6]。

4. **预热启动（Pre-warming）时已完成的工作**
   在 App 预热阶段，ObjC Runtime 已完成：`_objc_init` 基础初始化、读取 ObjC 元数据、注册所有类、类的 realize（非懒加载类）、处理 Category。**尚未执行** `+load` 方法，留到用户实际启动时调用 [11]。

## 关键细节与易错点

- **`_objc_init` 的调用者**：`_objc_init` 由 libSystem 在其初始化过程中调用（通过 `libSystem_initializer` 逐步调用），而非 dyld 直接调用 [2][9]。
- **realize（实现）的定义**：指的是 Runtime 把编译产物中的 `class_ro_t` 展开成运行期可用的 `class_rw_t` / `class_rw_ext_t` 结构，修正 ivar 偏移，连接父类和元类关系，初始化方法缓存 `cache_t`，并将基础方法、属性、协议以及等待附加的 Category 合并进去 [4]。
- **Category 附加时机**：如果类在加载 Category 时已经 realize，则立即附加；如果尚未 realize，则暂存到 `unattachedCategories` 表，待类 realize 时再统一附加 [3][4][8]。
- **`+load` 的调用方式**：通过函数指针直接调用，不经过 `objc_msgSend`，因此 Category 的 `+load` 不会被主类的 `+load` 覆盖 [3][6]。
- **`+load` 阻塞启动**：所有 `+load` 在主线程串行执行，直接阻塞进程启动 [3][6]。
- **预热阶段与冷启动的区别**：预热阶段已完成 `_objc_init`、类注册、realize、Category 处理，但 `+load` 延迟到用户实际启动时再执行 [11]。
- **`notifyObjCInit` 的守护条件**：只有 libobjc 已初始化（`_notifyObjCInit` 非 null）且该镜像可能含有 `+load`（`mayHavePlusLoad == true`）时才会回调 `load_images`，避免无谓的函数调用 [1][5]。

## 高频追问

### Q：Category 的加载细节？新旧版本 objc4 的实现差异是什么？
**回答要点**（基于 [4][8]）：
- 旧版源码：使用 `addUnattachedCategoryForClass` + `remethodizeClass` + `attachCategories` 三个函数，清晰划分“登记 → 取出 → 合并”三个步骤。
- 新版源码：做了路径优化，对已经 realized 的类直接调用 `attachCategories` 立即合并，只有未 realized 的类才先放入 unattached category 表，等到类 realization 时再统一附加。**核心思路不变**：都是“延迟合并”——Category 加载时如果目标类还没准备好，就先存起来，等准备好了再合。

### Q：`+load` 和 `+initialize` 的区别？
**本卡片材料不足**（材料中未涉及 `+initialize` 的机制或对比，无法给出基于材料的回答）。

### Q：如果一个类没有实现 `+load`，它何时被 realize？
**回答要点**（基于 [3][6]）：
- 懒加载类（未实现 `+load`）**延迟到首次收到消息时**才 realize，由 `objc_msgSend` → `lookUpImpOrForward` 触发，执行与立即 realize 相同的初始化流程（创建 `class_rw_t`、建立继承链、初始化缓存等）。

### Q：预热启动（Pre-warming）对 Runtime 初始化有何影响？
**回答要点**（基于 [11]）：
- 预热阶段已完成 `_objc_init` 基础初始化、读取 ObjC 元数据、注册所有类、类的 realize（非懒加载类）、处理 Category。**但 `+load` 方法的调用被延迟**，等到用户实际启动时再执行，以避免占用预热的冷启动时间。

### Q：`+load` 的调用顺序能否被分类（Category）影响？
**回答要点**（基于 [3][6]）：
- 不能。`+load` 通过**函数指针直接调用**，不经过 `objc_msgSend`，因此 Category 的 `+load` 不会覆盖主类的 `+load`，两者都会执行。顺序为：父类优先于子类 → 类优先于 Category → 同一镜像内按编译顺序 → 不同镜像按依赖顺序。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › dyld源码 › _dyld_objc_notify_register（第542-580行）
[2] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 1. 分类 category › 1.5 分类信息合并到类源码（第168-207行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 六、常见面试问题 › Q1: APP启动的详细流程 › Pre-main 阶段（第1128-1148行）
[4] /Users/tommywu/Obsidian/iOS/Runtime/Part 3 - Category：加载、覆盖与关联对象.md › Runtime 什么时候加载 Category（第360-391行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › dyld源码 › notifyObjCInit（第506-540行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › App 启动与优化（第26-30行）
[8] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Category_OC2_0.md › category如何加载（第340-367行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/sunnyxx/ios-程序-main-函数之前发生了什么-sunnyxx的技术博客.md › runtime 与 +load（第105-129行）
[10] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 1. 分类 category › 1.5 分类信息合并到类源码（第209-250行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 三、预热启动（Pre-warm Launch） › 什么是预热启动 › ObjC Runtime 初始化状态详解（第992-1008行）
