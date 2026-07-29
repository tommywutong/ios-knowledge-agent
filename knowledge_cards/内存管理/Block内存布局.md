---
topic: Block内存布局
group: 内存管理
generated_at: 2026-07-29T19:33:04
provider: deepseek
---

# Block内存布局

## 一句话总结

Block 本质上是一个 C 结构体，其内存布局由固定长度的头部（`isa`、`flags`、`reserved`、`invoke` 指针、`descriptor` 指针，共 32 字节）和紧随其后的捕获变量组成，捕获的变量按声明顺序追加在尾部。[1][2][3][4]

## 核心原理

1.  **Block 结构体组成**：Block 在内存中是一个结构体，包含必须的头部字段和可选的捕获变量部分。[1][2][4]
    - **固定头部**（32 字节）：
        - `isa`：指针，指向 Block 所属的类（如 `_NSConcreteStackBlock`、`_NSConcreteMallocBlock`、`_NSConcreteGlobalBlock`），用于区分 Block 类型（栈/堆/全局）。[1][4][7]
        - `flags`：整型，包含 Block 的各种属性标志（如是否包含 copy/dispose 辅助函数、是否有类型签名等）。[1][2][4]
        - `reserved`：保留字段。[1][2][4]
        - `invoke`：函数指针，指向 Block 实际执行的函数。调用 Block 本质上是调用 `invoke` 函数指针，并将 Block 自身作为第一个参数传入。[1][2][4][7]
        - `descriptor`：指向 Block 描述符结构体（`Block_descriptor`）的指针，其中包含 Block 的 size 等信息。[1][2][4]
    - **捕获变量**：如果 Block 捕获了外部变量，这些变量会按声明顺序作为结构体的字段追加在 `descriptor` 指针之后。[2][3][4]

2.  **Descriptor 结构体的实际布局**：在 libclosure 的真实实现中，`Block_descriptor` 并非一个形状固定的结构体，而是由最多三个独立的结构体（`Block_descriptor_1`、`Block_descriptor_2`、`Block_descriptor_3`）在内存中顺序拼接而成，每个部分的存在与否由 `flags` 字段决定。[2]
    - `Block_descriptor_1`：始终存在，包含 `reserved` 和 `size`（Block 结构体总大小）。[2]
    - `Block_descriptor_2`：仅当 `flags` 设置 `BLOCK_HAS_COPY_DISPOSE` 位时存在，包含 `copy` 和 `dispose` 函数指针，用于管理捕获的 `__block` 变量或对象的生命周期。[2][4]
    - `Block_descriptor_3`：仅当 `flags` 设置 `BLOCK_HAS_SIGNATURE` 位时存在，包含 `signature`（方法类型编码字符串）和 `layout`（Block 内部对象引用布局）。[2]

3.  **Block 的三种类型**：根据其在内存中的存储位置分为三类，通过 `isa` 指针区分。[1][11][12]
    - **Global Block（`__NSGlobalBlock__`）**：不捕获任何外部局部变量（包括自动变量），或仅捕获全局变量、静态局部变量的 Block。编译器在编译期确定其内容，存放在全局静态数据区。[12] 对其执行 `copy`、`retain`、`release` 均为空操作。[12]
    - **Stack Block（`_NSConcreteStackBlock`）**：捕获了外部局部变量（自动变量）的 Block，在定义时创建于栈上。[4][7] 调用 Block 实质是访问栈上的这个结构体指针。[7]
    - **Malloc Block（`__NSMallocBlock__`）**：对栈 Block 执行 `copy` 操作后，Block 被拷贝到堆上成为 Malloc Block，其生命周期由引用计数管理。[11] 在 ARC 下，编译器会自动对传入方法的 Block 参数等场景进行 `copy`。[11]

## 关键细节与易错点

1.  **文档与实际实现不符**：Clang 的 Block ABI 文档将 descriptor 描述为一个包含所有可能字段的固定结构体。而 libclosure 的实际实现将 descriptor 拆分为独立的子结构体并顺序拼接。这意味着如果你想在运行时通过内存偏移读取 Block 的签名，不能依赖文档的固定布局，必须根据 `flags` 手动计算偏移。[2]

2.  **`clang -rewrite-objc` 已被移除**：许多旧教程依赖 `clang -rewrite-objc` 将 Block 代码转换为 C++ 结构体来展示其布局。但在当前 Xcode 中，该重写动作已不再被编译。[5] 验证 Block 结构体布局的推荐方法是使用 LLVM IR 或直接读取 libclosure 头文件中的定义。[5]

3.  **Block 字面量在栈上**：Block 字面量（Literals）在栈上创建为一个结构体实例，Block 变量实际上是一个指向这个栈上结构的指针。`isa` 指针初始指向 `_NSConcreteStackBlock`。[4][7] 这一点对理解何时需要 `copy` Block 至关重要。[7]

4.  **ARC 下“看不到栈 Block”是测量问题**：在 ARC 环境下，认为“所有 Block 都自动被 `copy` 到堆上”的说法并不绝对，这取决于观察的时机和测量方式。在某些场景下，栈上的 Block 仍然存在，只是可能因为 ARC 的自动 `copy` 行为而被迅速忽略。[5]

## 高频追问

-   **描述一下 Block 的内部结构（内存布局）。**
    Block 在底层是一个结构体。它包含一个固定大小的头部：`isa` 指针（指向 Block 的类，用以区分类型）、`flags`（标志位）、`reserved`（保留字段）、`invoke`（函数指针，指向 Block 执行体）、`descriptor`（指向描述符的指针，包含 Block 大小等信息）。如果 Block 捕获了外部变量，这些变量会按声明顺序紧跟在头部之后。[1][2][4] 需要注意的是，`descriptor` 指向的内容并非一个固定结构体，而是根据 `flags` 的标志位，在内存中顺序拼接了三个子结构体（`Block_descriptor_1`、`Block_descriptor_2`、`Block_descriptor_3`），分别存储大小、copy/dispose 函数和类型签名。[2]

-   **Block 有哪几种类型？存储在什么位置？**
    Block 有三种类型：[1][12][11]
    1.  `__NSGlobalBlock__` (Global Block)：不捕获任何自动变量，存储在全局数据区。[12] 它的 `copy` 是空操作。[12]
    2.  `_NSConcreteStackBlock` (Stack Block)：捕获了自动变量，默认存储在栈上。[4][7]
    3.  `__NSMallocBlock__` (Malloc Block)：是 Stack Block 被 `copy` 到堆上的结果，由 ARC 引用计数管理生命周期。[11]

-   **ARC 下，Block 何时会自动从栈拷贝到堆？**
    本卡片材料不足，未提供 ARC 下自动 copy 的完整触发条件列表。但已知 ARC 下编译器会自动对传入方法的 Block 参数等场景进行 `copy`。[11] 并且有观点指出，“ARC 下看不到栈 Block”这一说法受测量姿势影响，并不绝对。[5]

-   **如何从 Block 中提取其类型签名？**
    需要根据 Block 的 `flags` 字段手动计算偏移，绕过其 `descriptor` 指针，找到 `Block_descriptor_3` 部分（包含 `signature` 字段）。[2][8] 具体步骤是：首先检查 `flags` 中是否设置了 `BLOCK_HAS_SIGNATURE` 标志位，以确认签名存在。[8] 然后，再检查是否设置了 `BLOCK_HAS_COPY_DISPOSE` 标志位，因为 `copy` 和 `dispose` 函数指针（`Block_descriptor_2`）存储在 `signature` 之前，如果存在，会占用额外的内存空间，偏移计算需将这部分大小计入。[8]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第二周：weak、属性关键字与 Block › 本周精读路线 › Day 3｜先看 Block 是什么，再谈捕获（对应 W2-12、W2-13、W2-15）（第185-198行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的结构：ABI、descriptor 与三种类型.md › Block 的结构：ABI、descriptor 与三种类型 › 二、Block_layout：文档和实现不是一回事（第52-100行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的变量捕获与 __block.md › Block 的变量捕获与 __block（第16-22行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/informit.com/big-nerd-ranch-advanced-mac-os-x-programming-blocks.md › [Big Nerd Ranch Advanced Mac OS X Programming: Blocks](https://www.informit.com/articles/article.aspx?p=1749597) › For the More Curious: Blocks Internals › Implementation › Block literals（第152-205行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的结构：ABI、descriptor 与三种类型.md › Block 的结构：ABI、descriptor 与三种类型（第16-33行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/informit.com/big-nerd-ranch-advanced-mac-os-x-programming-blocks.md › [Big Nerd Ranch Advanced Mac OS X 编程：Block](https://www.informit.com/articles/article.aspx?p=1749597) › 更进一步：Block 内部实现 › 实现 › Block 字面量（第167-208行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-05-06-a-tour-of-mablockclosure.md › (全文)（第93-125行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › Block 的类型与内存分布 › Malloc Block（第213-223行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › Block 的类型与内存分布 › Global Block（第163-182行）
