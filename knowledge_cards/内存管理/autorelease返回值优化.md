---
topic: autorelease返回值优化
group: 内存管理
generated_at: 2026-07-29T19:31:36
provider: deepseek
---

# autorelease返回值优化

## 一句话总结

ARC 下被调用方通过 `objc_autoreleaseReturnValue` 与调用方的 `objc_retainAutoreleasedReturnValue` 协作，利用线程本地存储（TLS）和返回地址检测，跳过实际的 `autorelease` 与 `retain` 配对，将对象所有权直接传递给调用方，从而消除不必要的自动释放池操作。[2][1][4]

## 核心原理

- **优化流程（autorelease elision）**：编译器将工厂方法等返回值标记为 `objc_autoreleaseReturnValue`，调用方则将接收到的返回值通过 `objc_retainAutoreleasedReturnValue` 处理。如果运行时检测到二者连续且匹配，则直接传递所有权，避免 `autorelease + retain` 的耗时配对。[2][4]
- **底层机制**：
  1. `objc_autoreleaseReturnValue` 调用 `prepareOptimizedReturn`，该函数通过 `__builtin_return_address(0)` 获取当前返回地址，并检查调用方是否即将调用 `objc_retainAutoreleasedReturnValue` 或 `objc_unsafeClaimAutoreleasedReturnValue`。若检查通过，则将 `ReturnAtPlus1` 标志存入 TLS，并直接返回对象（跳过 `objc_autorelease`）；否则退化为普通 `autorelease`。[1][6]
  2. `objc_retainAutoreleasedReturnValue` 调用 `acceptOptimizedReturn`，从 TLS 读取标志并重置为 `ReturnAtPlus0`。若标志为 `ReturnAtPlus1`，则直接返回对象（跳过 `retain`）；否则调用 `objc_retain`。[6]
- **线程安全性**：TLS 是每个线程专有的键值存储，函数调用栈上相邻两个函数对 TLS 存取时中间无其他线程干扰，因此存取无需考虑多线程竞争。[6]
- **架构差异**：`callerAcceptsOptimizedReturn` 在不同 CPU 架构实现不同。arm64 上指令对齐较好，只需判断返回地址指向的值是否为特定指令码（如 `0xaa1d03fd`）；x86_64 上则需用复杂代码动态分析指令序列。[1][6] ARM 架构下，编译器还可在 `objc_retainAutoreleasedReturnValue` 前插入一条 `mov r7, r7` 的指令作为标记，供运行时检测。[9]
- **普通 `autorelease` 也经过 TLS**：现在版本的 `objc_autorelease` 实现中，第一步也会尝试调用 `prepareOptimizedReturn`（传入 `cameFromRootAutorelease = true`），将对象暂存于 TLS，直到下一次入池或 push/pop 操作时才移入自动释放池页。这不是返回值优化的副产品，而是 `autorelease` 自身的新行为。[8]

## 关键细节与易错点

- **所有权传递的时机**：优化成功后，被调用方在 `objc_autoreleaseReturnValue` 中直接返回对象（retain count 不变），调用方在 `objc_retainAutoreleasedReturnValue` 中不调用 retain，直接获得对象，从而 retain count 从被调用方创建时的 1 直接转为调用方持有（引用计数不变）。[4][1]
- **兼容性**：若调用方未参与优化（例如代码未用 ARC 或调用方不直接调用 `objc_retainAutoreleasedReturnValue`），运行时会自动回退，被调用方仍会进行正常 `autorelease`，调用方后续仍可正常 retain。[1][12]
- **`objc_autoreleaseReturnValue` 的调用方检查**：该检查只针对 `cameFromRootAutorelease` 为 false 的情况（即来自返回值优化路径）；普通 `autorelease` 传入 true，会跳过部分检查，直接存入 TLS。[8]
- **延迟入池现象**：由于普通 `autorelease` 也先缓存到 TLS，通过计数自动释放池中对象数量时，会发现每次 `autorelease` 后第一次无法立即入池，差一个对象。[8]
- **尾调用优化**：在某些汇编代码中，`objc_autoreleaseReturnValue` 可能以 `jmp` 指令（尾调用）实现，例如 `jmp _objc_autoreleaseReturnValue`。[5]

## 高频追问

### 1. 这个优化是如何实现的？能否结合 TLS 和返回地址检测详细说明？

**回答要点**：
- 被调用方：`objc_autoreleaseReturnValue` → `prepareOptimizedReturn` → 通过 `__builtin_return_address(0)` 获取返回地址 → 调用 `callerAcceptsOptimizedReturn` 检查调用方是否即将调用 `objc_retainAutoreleasedReturnValue`。若是，则将 `ReturnAtPlus1` 写入 TLS，并直接返回对象（不调用 `autorelease`）；否则调用 `objc_autorelease`。[1][6]
- 调用方：`objc_retainAutoreleasedReturnValue` → `acceptOptimizedReturn` → 从 TLS 读取标志，若为 `ReturnAtPlus1` 则重置标志并直接返回对象（不调用 `retain`）；否则调用 `objc_retain`。[6]
- 整个流程依赖 TLS 的线程局部性，确保同一线程内连续调用之间数据正确。[6]

### 2. 为什么能避免 autorelease 和 retain 的配对开销？

**回答要点**：
- 传统方式：被调用方 `autorelease` 将对象加入自动释放池（增加线程池管理开销），调用方接收后必须 `retain` 以持有一份引用，最后自动释放池 drain 时再 `release`。这一对 **autorelease + retain** 以及后续的 drain 释放是冗余的，因为调用方立刻就要 retain，对象在池中只有短暂时间。[4][2]
- 优化后：通过 TLS 传递所有权标记，被调用方不调用 `autorelease`，调用方不调用 `retain`，对象引用计数直接传递，省略了三次消息发送（`autorelease`、`retain`、自动释放池的 `release`）及相关工作。[12]

### 3. 什么情况下这个优化会失效（即仍然走完整的 autorelease + retain）？

**回答要点**：
- 当调用方不是直接对返回值调用 `objc_retainAutoreleasedReturnValue` 时（例如调用方代码未用 ARC 编译、返回值被用于其他复杂表达式、或者有中间函数调用截断），`callerAcceptsOptimizedReturn` 返回 false，被调用方就会走普通 `autorelease`，调用方后续再通过 `objc_retain` 进行 retain。[1][6][12]
- 如果被调用方是通过 `__builtin_return_address` 检测到返回地址不匹配，或者返回地址指向的指令不是预期的模式，优化也会跳过。[1]

### 4. 普通 autorelease 和返回值优化中的 `objc_autoreleaseReturnValue` 有什么区别？它们是否共享同一底层路径？

**回答要点**：
- 两者都调用底层函数 `prepareOptimizedReturn`，但普通 `autorelease` 传入 `cameFromRootAutorelease = true`，而返回值优化传入 `false`。[8][1]
- 当 `cameFromRootAutorelease = false` 时，`prepareOptimizedReturn` 会先检查调用方是否接受优化（通过 `callerAcceptsOptimizedReturn`），若未通过则返回 false，`objc_autoreleaseReturnValue` 回退为 `objc_autorelease`。[1]
- 当 `cameFromRootAutorelease = true` 时，跳过该检查，直接存入 TLS，导致对象延迟入池。因此普通 `autorelease` 也会利用 TLS 做一次缓存，但目的并非返回值优化，而是 `autorelease` 自身的第一步处理。[8]

### 5. 能否从汇编层面观察这个优化？例如 arm64 或 x86_64 上如何检测？

**回答要点**：
- 汇编中，被调用方尾部会生成 `call objc_autoreleaseReturnValue` 或 `jmp objc_autoreleaseReturnValue`；调用方在接收返回值后（例如 `mov rdi, rax`）立即调用 `objc_retainAutoreleasedReturnValue`。[5][10]
- arm64 上，运行时通过检查返回地址处的指令是否为特定编码（如 `0xaa1d03fd`）来判断调用方即将调用 `objc_retainAutoreleasedReturnValue`。[1][6]
- ARM（非 64）上，编译器会在 `objc_retainAutoreleasedReturnValue` 前插入一条 `mov r7, r7` 作为标记，运行时检测该指令即可识别。[9]
- x86_64 上运行时需要更复杂的反汇编分析指令序列来确认。[1]

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/what-s-new-in-llvm.md › [What's New in LLVM](http://yulingtianxia.com/blog/2017/07/17/What-s-New-in-LLVM-2017/) › New Warnings › ARC 中的 Block 捕获参数 › 探索方法返回值内存管理的奥秘 › 优化过程及原理（第295-336行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/sunnyxx/黑幕背后的autorelease-sunnyxx的技术博客.md › Autorelease返回值的快速释放机制（第121-147行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 四、自动释放池（Autorelease Pool） › ARC下对象的两种释放机制 › 编译器优化（第478-522行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/tales-from-the-crash-mines-issue-1.md › (全文)（第392-408行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/what-s-new-in-llvm.md › [What's New in LLVM](http://yulingtianxia.com/blog/2017/07/17/What-s-New-in-LLVM-2017/) › New Warnings › ARC 中的 Block 捕获参数 › 探索方法返回值内存管理的奥秘 › 优化过程及原理（第338-361行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS AutoreleasePool：哨兵、页链表与 RunLoop 的关系.md › AutoreleasePool：哨兵、页链表与 RunLoop 的关系 › 三、少掉的那一个（第224-267行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-12-30-disassembling-the-assembly-part-3-arm-edition.md › (全文)（第245-258行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-12-23-disassembling-the-assembly-part-2.md › (全文)（第139-153行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2014-05-09-when-an-autorelease-isn-t.md › (全文)（第166-184行）
