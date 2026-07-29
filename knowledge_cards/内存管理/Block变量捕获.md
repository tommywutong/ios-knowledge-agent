---
topic: Block变量捕获
group: 内存管理
generated_at: 2026-07-29T19:33:37
provider: deepseek
---

# Block变量捕获

## 一句话总结

Block 对变量的捕获遵循“最小必要”原则：只会捕获那些在 Block 定义作用域中存活、同时地址不能编译期确定的变量——即局部自动变量（auto）和 `__block` 修饰的局部变量；全局变量和静态变量（包括函数内 static）的地址在编译期已知，Block 直接通过符号访问而不将其塞入 Block 结构体，因此相关 Block 属于 `__NSGlobalBlock__` 类型，连堆都不上。[1][3]

## 核心原理

### 变量捕获矩阵

| 变量类型 | 是否捕获 | 捕获方式 | Block 内能否修改 | 底层原理 |
|---------|---------|---------|----------------|---------|
| 局部自动变量（auto） | **捕获** | **值拷贝** | 不能（编译报错 `Variable is not assignable`） | Block 结构体多出 4 字节存放副本，修改副本无意义 [1][5][10] |
| `__block` 修饰的局部变量 | **捕获** | **包装为 byref 结构体，捕获结构体指针** | 能 | 通过 `__forwarding` 指针间接访问同一块内存 [5][6] |
| 函数内 `static` 变量 | **不捕获**（有冲突，见下方说明） | 不保存到 Block 结构体，直接按符号访问 | 能 | 地址在数据段固定，Block 的 invoke 函数直接访问 [1] |
| 全局变量 / 文件内 `static` 变量 | **不捕获** | 直接访问全局地址 | 能 | 地址编译期可确定 [1][2][5][6] |
| 对象类型局部变量 | **捕获** | 指针值拷贝 + 引用管理 | 能修改对象内容，不能修改指针指向 | copy 到堆时通过 `_Block_object_assign` 管理引用关系 [5][6] |

### 核心证据：Block 描述符大小

从 objc4 源码或实际运行测量，Block 结构体的大小可验证捕获情况 [1]：
- 未捕获任何变量（包括仅访问全局/static）：**size = 32**，flags 含 `BLOCK_IS_GLOBAL`
- 捕获了 auto 变量：**size = 36**（多 4 字节，即一个 `int` 副本）
- 捕获了 `__block` 变量或对象变量：size 进一步增加，flags 含 `BLOCK_HAS_COPY_DISPOSE`

### 全局 Block 的判定

仅访问全局变量或 static 变量（包括函数内 static）的 Block，size = 32 且 flags 含 `BLOCK_IS_GLOBAL`，类型为 `__NSGlobalBlock__`，位于数据区，`copy` 是空操作。[1][3][4][9]

### 三种 Block 类型与内存分布

| 类型 | isa | 存储位置 | 典型场景 | copy 行为 |
|------|-----|---------|---------|-----------|
| `__NSGlobalBlock__` | `_NSConcreteGlobalBlock` | 数据区 | 不捕获局部自动变量（仅访问全局/static） | 什么也不做，返回自身 [3][4][11] |
| `__NSStackBlock__` | `_NSConcreteStackBlock` | 栈 | 捕获了局部自动变量，且尚未被 copy（MRC 典型） | 拷贝到堆，变为 Malloc Block [4][9][11] |
| `__NSMallocBlock__` | `_NSConcreteMallocBlock` | 堆 | Stack Block copy 后；ARC 下大多数场景自动 copy [4][9] | 引用计数 +1，返回自身 [11] |

注意：**ARC 下捕获 auto 变量的 Block 直接就是 `__NSMallocBlock__`**，因为编译器会在赋值给强引用等场景自动插入 `copy`，因此中文教程常说的“捕获 auto 变量就是栈 Block”仅在 MRC 下成立。[9]

## 关键细节与易错点

### 冲突：函数内 static 变量是否被捕获

- **材料 [1] 明确否定**：通过测量 Block 描述符 size = 32 显示函数内 static 变量**不被捕获**，它和全局变量一样直接按符号访问；同时指出基于 `-rewrite-objc` 的旧说法（认为捕获指针）是教学用工具的产物，不反映真实编译器行为 [1]。
- **材料 [2][5][6] 支持“捕获指针”**：称 Block 捕获的是 static 局部变量的指针，因此可以修改 [2][5][6]，这个说法常见于多数博客，其依据可能是 `-rewrite-objc` 改写结果或早期实现。
- **现状**：两派说法冲突，需明确指出。实际苹果 LLVM 编译器行为以 [1] 的实验结果为准（size=32 表明未捕获），但在面试中两种说法均可能出现，建议说明材料差异。

### auto 变量值拷贝的后果

```objc
int a = 10;
void (^block)(void) = ^{ NSLog(@"%d", a); };
a = 20;
block(); // 输出 10，因为 Block 内部持有的是创建时的副本
```
Block 内不能直接修改 `a`，编译器报错阻止语义模糊的尝试。[5][8]

### 对象变量捕获的引用管理

- 捕获 `__strong` 对象：堆 Block 强持有该对象
- 捕获 `__weak` 对象：Block 保存弱引用
- 捕获 `__unsafe_unretained` 对象：保存裸指针
- Block 的 copy/dispose 辅助函数通过 `_Block_object_assign` / `_Block_object_dispose` 管理引用 [5]

### `__block` 非引用捕获

`__block` 变量被包装成 `__Block_byref` 结构体，该结构体包含 `__forwarding` 指针。Block 内部访问时通过 `byref->__forwarding->变量` 间接读写，因此即使 Block 被拷贝到堆上，修改仍能同步回原变量。[5][7]

### 几个易混淆说法辨析

- “全局变量和 static 变量会被 Block 捕获” ❌ → 三种都不会，证据是 size=32、类型为 Global Block。[1][7]
- “`__block` 修饰对象可以打破循环引用” ❌ → 仅 MRC 下成立，ARC 下 byref layout 是 `STRONG`，持有对象。[7]
- “C 数组也能捕获” ❌ → 编译报错，结构体可以按值捕获。[7]
- “Block 里改了 `__block` 变量，外面要等 Block 执行完才能看到” ❌ → 立刻可见，因为访问同一块内存。[7]

### Block 的 copy 底层流程（`_Block_copy`）

1. 若已经是 Malloc Block（`BLOCK_NEEDS_FREE`），引用计数原子 +1
2. 若为 Global Block（`BLOCK_IS_GLOBAL`），直接返回原 Block
3. 若是 Stack Block，`malloc(size)` 分配堆内存，`memmove` 复制，设置 `BLOCK_NEEDS_FREE | 1`，修改 isa 为 `_NSConcreteMallocBlock`，调用 copy 辅助函数处理捕获的对象/__block 变量 [11][12]

## 高频追问

**Q1：Block 为什么不能修改 auto 变量？**
A：因为 Block 通过值拷贝持有 auto 变量的副本，修改副本对外部变量无影响，编译器直接禁止这种无意义的操作。[1][5][8]

**Q2：ARC 下是否能看到栈 Block？**
A：通常看不到，因为赋值给 `__strong` Block 变量、作为函数返回值、传给 GCD 等场景编译器都会自动插入 `copy`。但在一些未触发 copy 的场合（如作为参数传递给非 `usingBlock` 方法且不赋值）可能短暂存在栈 Block，不过极难观测。[9]

**Q3：static 局部变量在 Block 中为什么可以修改？**
A：根据材料 [1]，static 局部变量**不被捕获**，Block 直接通过符号访问其地址（地址编译期确定），因此修改的是原始变量。根据材料 [2][5]，另一种说法是 Block 捕获了该变量的指针（地址），同样可以修改原始变量。两种解释均允许修改，但捕获机制描述存在冲突。[1][2]

**Q4：`__block` 变量被 Block 捕获后，内存布局是怎样的？**
A：`__block` 变量被包装为 `__Block_byref` 结构体，包含 isa、`__forwarding` 指针、flags、size 以及原始变量的存储空间。Block 结构体中保存的是该结构体的指针，通过 `__forwarding` 间接访问，确保 Block 从栈拷贝到堆后仍能正确指向同一变量。[5]

**Q5：对象类型变量被 Block 捕获后，Block 内部能否修改对象内容？**
A：可以修改对象内容（如调用 `addObject:`），但不能修改指针指向（如赋值 `array = nil`）。因为 Block 捕获的是对象指针的值（副本），修改指针不影响外部，所以编译器禁止；但通过该指针修改对象内存则允许。[5][6]

**Q6：Global Block 的 copy 行为？**
A：`copy` 是空操作，直接返回自身。因为 Global Block 位于数据区，生命周期与应用一致，无需内存管理。[3][4][11]

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的变量捕获与 __block.md › Block 的变量捕获与 __block › 一、捕获矩阵（第24-71行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/static关键字详解.md › static关键字详解 › 一、静态局部变量 › 与 Block 捕获的关系（第72-88行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › Block 的类型与内存分布 › Global Block（第163-182行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第765-819行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第821-882行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › 变量捕获机制 › 捕获规则总览（第360-368行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的变量捕获与 __block.md › Block 的变量捕获与 __block › 七、几个说法需要辨析（第276-288行）
[8] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Block的本质.md › 6. Block 内修改外部变量（第679-684行）
[9] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的结构：ABI、descriptor 与三种类型.md › Block 的结构：ABI、descriptor 与三种类型 › 五、三种类型，以及一个测量假象（第236-260行）
[10] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Block的本质.md › 2. 变量捕获 › 2.1 局部变量 › 2.1.1 auto变量（第189-193行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › Block 的类型与内存分布 › Block 的 copy 行为（第281-314行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/halfrost.com/深入研究-block-捕获外部变量和-block-实现原理.md › 二.Block的copy和dispose › 2.从持有对象的角度上来看：（第500-546行）
