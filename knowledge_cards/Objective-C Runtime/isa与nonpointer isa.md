---
topic: isa与nonpointer isa
group: Objective-C Runtime
generated_at: 2026-07-29T19:25:04
provider: deepseek
---

# isa与nonpointer isa

## 一句话总结

isa 是 Objective-C 对象的第一个成员（8字节），既可以是单纯的类指针（Class），也可以是联合体 `isa_t`，在 64 位系统上利用空闲位域存储类指针、引用计数、标志位等元信息，这就是 **nonpointer isa**（非指针 isa）。[1][2]

## 核心原理

- **`isa_t` 联合体**：共享 8 字节内存，两种解读方式——`cls`（普通 Class 指针）和 `bits`（位域结构体）。当 `nonpointer = 1` 时按位域解读，当 `nonpointer = 0` 时按普通指针解读。[1]
- **位域字段（arm64，非 e）**：`nonpointer:1`、`has_assoc:1`、`has_cxx_dtor:1`、`shiftcls:33`（类指针）、`magic:6`、`weakly_referenced:1`、`deallocating:1`、`has_sidetable_rc:1`、`extra_rc:19`，共 64 位。[1][7]
- **位域字段（arm64e，A12+）**：`nonpointer:1`、`has_assoc:1`、`weakly_referenced:1`、`shiftcls_and_sig:52`（类指针+PAC签名合并）、`has_sidetable_rc:1`、`extra_rc:8`；去掉了 `magic`、`deallocating`、`has_cxx_dtor`。[3][7]
- **ISA_MASK**：arm64 为 `0x0000000ffffffff8`，arm64e 为 `0x007ffffffffffff8`；`isa & ISA_MASK` 得到类对象地址。[1][3][5]
- **`extra_rc` 语义**：最新实现中 `extra_rc` 直接存储引用计数值（不是减一），对象刚创建时 `extra_rc = 1`。[12] 旧版材料仍描述为“引用计数减一”，已与新版冲突。[1][8][10] 冲突点明确：[12] 实测和源码均证明 `extra_rc` 直接是引用计数，而 [1][8][10] 仍写“减一”。依据 [12] 的实测和源码引用，`extra_rc` 直接等于引用计数值。
- **引用计数溢出**：`extra_rc` 最大可存 255（8 位，arm64e）或 524287（19 位，arm64），超出时 `has_sidetable_rc` 置为 1，引用计数溢出到 SideTable。[4][11] 溢出时并非全部搬走，而是留一半 `RC_HALF` 在 `extra_rc` 中。[11]
- **演进时间线**：objc4-680 首位字段 `indexed`，750 改名 `nonpointer`，818 arm64e 大改并合并签名、去掉 `magic`/`deallocating`/`has_cxx_dtor`、`extra_rc` 从 19 位减到 8 位。[3][6]
- **支持条件**：`SUPPORT_NONPOINTER_ISA` 仅 arm64 架构支持（`__LP64__`且非 `TARGET_OS_WIN32` 等）。[10]

## 关键细节与易错点

- **isa 不是单纯的类指针**：`0x01000001000080e9` 这样的值不能直接当作类地址，必须通过 `& ISA_MASK` 才能得到类地址。[5]
- **三种 mask 用途不同**：`ISA_MASK`、`ISA_MASK_NOSIG` 等，对低 4GB 类地址结果相同，但高位地址差异才显现。[5]
- **`deallocating` 位的消失**：新版 arm64e isa 中不再有独立 `deallocating` 位，通过 `extra_rc == 0 && has_sidetable_rc == 0` 判断是否正在释放。[12]
- **`has_cxx_dtor` 在 arm64e 中消失**：该标志移到 cache 的 flags 中。[7]
- **`magic` 在 arm64e 中消失**：老版 arm64 的 `magic` 值固定为 `0xd2`，用于调试器。[1][10]
- **`weakly_referenced` 位**：只要对象曾被弱引用指向过就会置 1，用于析构时优化（若为 0 则不需处理 weak 表）。[1][10]
- **`isa_t` 是 8 字节对齐**：因此 `shiftcls` 的低 3 位始终为 0，`ISA_MASK` 末 3 位也恰为 `0x8`（二进制 `...1000`）。[1][3]
- **实例变量紧跟 isa**：`_age` 等实例变量在内存中位于 isa 之后 +8 字节处。[5]

## 高频追问

### Q1: 如何判断对象启用了 nonpointer isa？

读取 isa 的第一个位（bit0），若 `nonpointer = 1` 表示启用，否则为普通指针 isa。[1]

### Q2: isa 中的 `shiftcls` 为什么是 33 位？地址不应该是 64 位吗？

64 位地址空间虽大，但实际对象地址只用低 33 位（arm64）或 52 位（arm64e），且掩码后低 3 位为 0，因此可以压缩存储。[1][2]

### Q3: `extra_rc` 存的是引用计数还是引用计数减一？

**最新实现（objc4-818+）中直接存引用计数**。源码 `initIsa` 设置 `extra_rc = 1`，`rootRetainCount()` 直接返回 `extra_rc`（不含 +1）。[12] 老版本（如 objc4-780 之前）存的是 retainCount - 1。[1][8][10] 两者冲突，需指定版本。

### Q4: 引用计数超过 `extra_rc` 最大值会怎样？

`has_sidetable_rc` 置为 1，引用计数溢出到 SideTable。溢出时不是全部转移，而是保留一半（`RC_HALF`，arm64e 中为 128）在 `extra_rc`，另一半存入 SideTable。[4][11] 这样后续 release 在 `extra_rc` 减到 0 前无需加锁访问 SideTable。[4]

### Q5: Non-pointer isa 和 Tagged Pointer 有什么区别？

Non-pointer isa 优化的是堆对象的 isa 指针，对象仍在堆上分配；Tagged Pointer 优化的是小值对象本身（如 `NSNumber`、短 `NSString`），根本不在堆上分配，直接将数据和类型编码在指针中。[9]

### Q6: 如何通过 isa 获取类对象指针？

`isa & ISA_MASK`。在 objc_msgSend 中通过 `GetClassFromIsa_p16` 宏实现。[1][5]

### Q7: `has_assoc` 和 `weakly_referenced` 位的作用是什么？

用于析构优化：若标志为 0，则析构时无需处理关联对象或 weak 表，可直接跳过相关操作，提高性能。[1][10]

### Q8: arm64e 的 isa 为什么去掉了 `magic` 和 `deallocating` 位？

`magic` 因 arm64e 引入 PAC 指针认证，调试器可通过其他方式识别；`deallocating` 被语义替代（`extra_rc == 0 && has_sidetable_rc == 0` 即表示正在释放）。[12] `has_cxx_dtor` 移到了 cache flags。[7]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › isa › 优化的isa指针（Non-Pointer isa） › isa_t 的实现（第104-130行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › isa › 优化的isa指针（Non-Pointer isa）（第56-60行）
[3] /Users/tommywu/Desktop/26暑期内容/iOS底层源码探索/msgSend-demo/实战素材-第1篇-isa.md › 第 1 篇《对象的本质 / isa》实战素材 › 一、源码出处（objc4-951.1） › isa 位域演进时间线（均为各版本真源码实测）（第35-46行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：MRC 的所有权规则.md › MRC 的所有权规则：retain、release 与 autorelease › 四、引用计数存在哪：一个能测出来的问题 › nonpointer isa（第175-181行）
[5] /Users/tommywu/Desktop/26暑期内容/iOS底层源码探索/msgSend-demo/实战素材-第1篇-isa.md › 第 1 篇《对象的本质 / isa》实战素材 › 三、结论（写博客可直接用）（第60-65行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/Part 1 - 对象与类的本质.md › 对象的本质：objc_object › isa_t › isa 位域的历史演进（2015 → 至今）（第362-394行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/Part 1 - 对象与类的本质.md › 对象的本质：objc_object › isa_t › ISA_BITFIELD：isa 的位布局（第254-287行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的内存管理.md › iOS中的内存管理 › 二、引用计数机制 › 引用计数的存储 › isa指针中的内联存储（第140-160行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第1234-1269行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c-引用计数原理.md › 引用计数如何存储 › isa 指针（NONPOINTER_ISA）（第131-156行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：MRC 的所有权规则.md › MRC 的所有权规则：retain、release 与 autorelease › 四、引用计数存在哪：一个能测出来的问题 › 实测（第228-261行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/内存管理/iOS 内存：MRC 的所有权规则.md › MRC 的所有权规则：retain、release 与 autorelease › 四、引用计数存在哪：一个能测出来的问题 › 顺带修正一个我自己差点写错的地方（第263-291行）
