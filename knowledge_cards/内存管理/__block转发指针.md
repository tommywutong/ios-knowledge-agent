---
topic: __block转发指针
group: 内存管理
generated_at: 2026-07-29T19:33:55
provider: deepseek
---

# __block转发指针

## 一句话总结

`__forwarding` 是 `__Block_byref` 结构体中的关键指针，确保 `__block` 变量从栈复制到堆后，所有对该变量的读写始终访问堆上的同一份数据，从而解决变量生命周期和修改一致性问题 [1][2][3][4]。

## 核心原理

1. **byref 结构体**
   编译器将 `__block` 变量包装为 `__Block_byref` 结构体，其中包含 `isa`、`forwarding` 指针、`flags`、`size` 以及变量本体 [4][8][9]。例如 `__block int a` 生成的结构体：
   ```c
   struct __Block_byref_a_0 {
       void *__isa;
       struct __Block_byref_a_0 *__forwarding;
       int __flags;
       int __size;
       int a;
   };
   ```
   [10]

2. **`__forwarding` 的初始化**
   初始时，栈上结构体的 `__forwarding` 指向自身 [1][2][4]：
   ```c
   __Block_byref_i_0 i = {
       (void*)0,
       (__Block_byref_i_0 *)&i, // forwarding 指向自己
       0, sizeof(__Block_byref_i_0), 0
   };
   ```
   [8]

3. **Block copy 到堆时的转发机制**
   当 Block 被 copy 到堆时，`_Block_byref_copy` 函数会：
   - 将 byref 结构体拷贝到堆上
   - 堆上副本的 `forwarding` 指向自身
   - 栈上原结构体的 `forwarding` 改为指向堆上的副本 [1][4][8]
   - 源码核心逻辑：
     ```c
     copy->forwarding = copy;  // 堆上那份指向自己
     src->forwarding  = copy;  // 栈上那份改指向堆上副本
     ```
     [4]

4. **所有访问通过 `forwarding` 跳转**
   编译器将每次对 `__block` 变量的读写转换为 `byref->__forwarding->variable` 的形式 [2][5][8]。例如：
   ```c
   (age->__forwarding->age) = 20;
   ```
   [5] 这保证无论从栈环境还是堆环境访问，最终都操作堆上的数据 [1][7][9]。

5. **生命周期问题的解决**
   `__block` 解决的核心是生命周期问题：栈上的变量在栈帧返回后失效，而 Block 可能活得更久。通过 `forwarding` 把变量“搬家”到堆上，使得 Block 释放前变量始终有效 [3]。“能修改”只是搬家的自然结果 [3]。

## 关键细节与易错点

- **`__forwarding` 不会形成链**：堆上的 `forwarding` 指向自身，栈上的 `forwarding` 直接指向堆上副本，最多跳一次 [4]。
- **初始化处不走 `forwarding`**：变量声明处的初始化是直接赋值字段的，不通过 `forwarding` [4]。
- **销毁时传的是栈上原始指针**：`_Block_object_dispose` 传入的是栈上 byref 结构体的指针，但通过 `forwarding` 找到堆上副本处理 [4]。
- **ARC 下 `__block` 对象的引用管理**：当 `__block` 修饰的是对象类型时，byref 结构体还会包含 copy/dispose 辅助函数，用于管理引用计数 [11]。
- **多个 Block 共享同一个 `__block` 变量**：第一次 copy 会将 byref 结构体拷贝到堆，后续 copy 仅通过 `flags` 中的引用计数来管理，不重复拷贝 [11]。
- **`__forwarding` 指针类型**：它是指向 `Block_byref *` 的指针，而不是直接指向变量值 [4][9]。
- **`__block int` 与 `__block id` 的 byref 结构体大小不同**：实测 `__block int` 的 byref size 是 32（无 copy/dispose 段），ARC 下 `__block id` 是 48（有 copy/dispose 段） [4]。
- **`BLOCK_HAS_COPY_DISPOSE` 标志位**：捕获 `int` 的 Block 没有此标志，因为不需要辅助函数；但 `__block int` 会有此标志，因为需要处理 `forwarding` 指针的拷贝 [12]。

## 高频追问

**1. 为什么 `__block` 变量通过 `__forwarding` 访问，而不是直接修改值？**
因为 Block 可能从栈 copy 到堆，栈上变量的地址会失效。`forwarding` 确保所有访问最终都指向堆上的副本，这是解决变量生命周期问题的关键设计 [1][2][3][8]。

**2. 如果 Block 没有被 copy，`__forwarding` 还会有用吗？**
即使 Block 在栈上，`forwarding` 最初指向自身（栈上的结构体），通过 `forwarding` 访问与直接访问效果相同，但编译器统一生成了 `forwarding` 跳转代码，以保持一致性 [8]。

**3. 栈上的 byref 结构体在 copy 后会被删除吗？**
不会删除。栈上结构体的 `forwarding` 被改为指向堆上副本，但其本身仍然存在（残留旧值），不再被读写 [1][3][4]。

**4. `__forwarding` 指针会不会出现循环引用或无限跳转？**
不会。堆上副本的 `forwarding` 始终指向自身，栈上结构体的 `forwarding` 直接指向堆上副本，最多一次跳转 [4]。

**5. 两个不同的 Block 捕获同一个 `__block` 变量，`forwarding` 如何处理？**
第一次 copy 时 byref 结构体被拷贝到堆上；第二次 copy 时仅增加引用计数，所有 Block 持有的 `forwarding` 都指向同一份堆上数据 [11]。

**6. `__block` 修饰对象时，byref 结构体中为什么会有 copy/dispose 函数？**
因为对象需要内存管理（retain/release），当 Block copy 时，通过 `byref_keep` 函数强持有对象；当 Block 释放时，通过 `byref_destroy` 释放对象 [9][11]。

**7. `__forwarding` 在 MRC 和 ARC 下有区别吗？**
核心机制一致。无论是 MRC 还是 ARC，Block copy 时都会触发 forwarding 重定向。区别在于 MRC 下需要手动 copy Block，而 ARC 下编译器可能自动 copy [8]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › 变量捕获机制 › `__block` 修饰符的底层原理 › `__forwarding` 指针的精妙设计（第474-504行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › 常见面试题 › `__block` 的作用和原理是什么？（第793-801行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的变量捕获与 __block.md › Block 的变量捕获与 __block › 三、同一行 &shared，前后两个地址 › Block_byref 与 forwarding（第161-182行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的变量捕获与 __block.md › Block 的变量捕获与 __block › 三、同一行 &shared，前后两个地址 › Block_byref 与 forwarding（第120-159行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Block的本质.md › 6. Block 内修改外部变量 › 6.2 使用`__block`修饰外部变量（第761-773行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第841-841行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/halfrost.com/深入研究-block-捕获外部变量和-block-实现原理.md › 三.Block中__block实现原理 › 1.普通非对象的变量（第674-739行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/informit.com/big-nerd-ranch-advanced-mac-os-x-programming-blocks.md › [Big Nerd Ranch Advanced Mac OS X 编程：Block](https://www.informit.com/articles/article.aspx?p=1749597) › 更进一步：Block 内部实现 › 实现 › `__block` 变量（第210-257行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第821-882行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Block底层原理.md › Block底层原理 › 变量捕获机制 › `__block` 修饰符的底层原理 › `__block` 变量的内存管理（第527-544行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/Block/iOS Block 的结构：ABI、descriptor 与三种类型.md › Block 的结构：ABI、descriptor 与三种类型 › 四、flags 里有什么 › HAS_COPY_DISPOSE 标的不是"捕获了对象"（第202-206行）
