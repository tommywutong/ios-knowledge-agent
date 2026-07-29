---
topic: objc_msgSend快速路径
group: Objective-C Runtime
generated_at: 2026-07-29T19:25:32
provider: deepseek
---

# objc_msgSend快速路径

## 一句话总结

`[obj foo]` 编译为 `objc_msgSend(obj, sel)`，快速路径指在 ARM64 汇编层面通过 `CacheLookup` 在 `cache_t` 哈希表中命中目标 IMP，直接尾调用跳转，不进入 C 语言的慢速查找函数 `lookUpImpOrForward`。[1][2][3][12]

## 核心原理

### 1. 方法调用的本质

`[obj foo]` 被编译器翻译为 `objc_msgSend(obj, sel)`。[1] 这个函数用汇编实现的原因：性能关键、调用参数种类未知、尾调用优化。[1][9]

### 2. 快速路径的入口与判空

入口 `_objc_msgSend`（`objc-msg-arm64.s:587`）首先执行 `cmp p0, #0` 对 receiver 判空。[2][3] 若 receiver 为 0（nil），跳转到 `LReturnZero`，将 $x0$ 和 SIMD 浮点返回值寄存器全部清零后返回。[2][3] 若为 tagged pointer（最高位 MSB 为 1，看起来像负数），跳转 `LNilOrTagged`，从专表取 class 后再进入主流程。[2][3]

### 3. 从 isa 获取 class

判空通过后，`ldr p14, [x0]` 取出对象首 8 字节（原始 isa，含标志位）。[2][3][5] 接着通过 `GetClassFromIsa_p16 p14, 1, x0` 抹掉标志位并完成 ptrauth 解签，得到真正的 `Class` 存在 `p16`。[2][3] 这一汇编指令在真机上的反汇编等效操作为 `and x16, x14, #0x7ffffffffffff8`（& ISA_MASK），即通过掩码提取 isa 中的类指针。[5]

### 4. CacheLookup：缓存哈希查找

获取 class 后立即调用 `CacheLookup NORMAL, _objc_msgSend, __objc_msgSend_uncached`。[2][3] 查找基于 `cache_t` 数据结构：`_bucketsAndMaybeMask` 是指针与 mask 的融合字；`bucket_t` 包含 `{SEL, IMP}`，每个 bucket 的 IMP 被 ptrauth（指针认证）签名。[1] 查找过程按 SEL 哈希定位 bucket，若该位置 SEL 不匹配则通过 `cache_hash` / `cache_next` 进行开放寻址探测。[1][2][3]

### 5. 命中与未命中的分支

- **命中**：找到匹配 SEL 的 bucket 后，使用 `br IMP` 直接尾调用跳转至 IMP。[1]
- **未命中**：`CacheLookup` 跳转到 `__objc_msgSend_uncached`。[2][3] 该静态入口是未缓存消息的通用处理入口（不可由 C 直接调用）。[4] 它调用 `MethodTableLookup` 宏：保存关键寄存器（`SAVE_REGS`）、以 x0(receiver)、x1(sel)、x2(cls)、x3(3) 为参数调用 C 函数 `_lookUpImpOrForward`。[4] 返回值（IMP 地址）存入 x17，恢复寄存器后通过 `TailCallFunctionPointer x17` 尾调用 IMP。[4]

因此，快速路径的边界条件是 **CacheLookup 是否在 `cache_t` 中找到匹配 SEL**：[1] 找到则直接 `br IMP`（快速路径）；未找到则落地到慢速查找 `lookUpImpOrForward`（慢速路径）。

### 6. 缓存的写入与扩容

后续当方法在慢速查找中找到后，会被写入缓存。写入过程涉及哈希落位（`insert`）、翻倍扩容（`reallocate`）、丢弃旧表不迁移，以及装填因子与留空策略。[1]

## 关键细节与易错点

### 处理 nil receiver

易错点在于认为给 nil 发消息会 crash。实际上快速路径入口就判断了 `p0 == 0`，直接给所有返回值寄存器清零并返回，不会触发后续任何查找。[2][3][12]

### 为什么必须用汇编实现

C 语言无法保持未知类型参数栈帧一致性。`objc_msgSend` 作为汇编 trampoline，查缓存找到 IMP 后原样跳过去，全程不碰 x2 及以后的参数寄存器。[8] 因此调用方必须按目标方法的签名把寄存器摆好，而让 C 编译器摆对的唯一办法就是用目标方法的精确签名去声明这次调用（强制转型函数指针）。[8] 在 arm64 上，SDK 已经把变参原型关死：`OBJC_OLD_DISPATCH_PROTOTYPES` 为 0 时，声明是 `void objc_msgSend(void)`，不强制转型连参数都传不对。[8]

### 真机反汇编与源码差异

真机反汇编 `objc_msgSend` 的取 class 步骤只显示两条指令：`ldr x14, [x0]` 和 `and x16, x14, #0x7ffffffffffff8`。[5] 源码中的 `GetClassFromIsa_p16` 宏是这两条指令的内联封装，由编译时宏展开生成，在反汇编层面不可区分。[5]

### 缓存命中与慢速查找的关系

第 1 次发送相同消息时（cache 未命中）会执行 `lookUpImpOrForward`；第 2 次相同消息 cache 命中，**不会再进 `lookUpImpOrForward`**。[11]

## 高频追问

**Q：快速路径中 `bucket_t` 的 ptrauth 具体是怎么处理的？（材料未提及）

本卡片材料不足。材料提到 bucket 的 SEL 和 IMP 被 ptrauth 签名 [1][2][3]，但未提供签名/解签的具体汇编代码段。

**Q：快速路径中的 read barrier（内存屏障）在哪里？

本卡片材料不足。快速路径的汇编流程 [2][3][4] 中没有出现任何显式的内存屏障指令，也没有材料解释 cache 写入是否包含 barrier。

**Q：如果类没有实现某个方法，但父类有，第几次调用才能进入快速路径？

材料没有直接给出数字，但可以通过流程推导：第 1 次调用父类方法时，若子类 cache 未命中，会通过慢速查找沿 superclass 链找到父类的 IMP，结果写入子类的 cache [1][12]。第 2 次调用时子类 cache 命中，进入快速路径。严格来说，"第 2 次对子类实例发送该消息"即可进入快速路径。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Part 2 - 消息发送与转发.before-renumber.md › 【iOS】Runtime - Part 2 && 消息发送：缓存、查找与转发 › 目录 › 第一部分 · 快速路径（缓存命中）（第7-21行）
[2] /Users/tommywu/Obsidian/iOS/Runtime/Part 2 - 消息发送与转发.md › 第一部分 · 快速路径（缓存命中） › 2. 快速路径汇编逐段（`objc-msg-arm64.s`）（第828-875行）
[3] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Part 2 - 消息发送与转发.before-renumber.md › 【iOS】Runtime - Part 2 && 消息发送：缓存、查找与转发 › 第一部分 · 快速路径（缓存命中） › 4. 快速路径汇编逐段（`objc-msg-arm64.s`）（第815-862行）
[4] /Users/tommywu/Obsidian/iOS/Runtime/Part 2 - 消息发送与转发.md › 第二部分 · 慢速查找（lookUpImpOrForward）（第1614-1666行）
[5] /Users/tommywu/Desktop/26暑期内容/iOS底层源码探索/msgSend-demo/实战素材.md › 消息发送实战素材（真机 macOS 26 / 系统 libobjc 实测） › 二、objc_msgSend 入口反汇编（对照 objc-msg-arm64.s 的 _objc_msgSend）（第27-33行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS YYModel 源码：为什么比 JSONModel 快.md › YYModel 源码：为什么比 JSONModel 快 › 三、`objc_msgSend` 强转函数指针，到底为什么必须精确 › 它为什么合法（第233-252行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/zhongwuzw.github.io/ios知识小集之为什么objc-msgsend-是用汇编实现的.md › iOS知识小集之为什么objc_msgSend()是用汇编实现的 › 参考（第50-56行）
[11] /Users/tommywu/Desktop/26暑期内容/iOS底层源码探索/msgSend-demo/README.md › msgSend-demo —— 用 LLDB 观察系统 libobjc 的消息发送 › 三、观察正常消息发送（[d bark]）（第22-40行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runtime.md › Runtime › 常见面试题 › Q1: objc_msgSend 的执行流程？（第798-807行）
