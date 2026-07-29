---
topic: Category加载与方法覆盖
group: Objective-C Runtime
generated_at: 2026-07-29T19:28:04
provider: deepseek
---

# Category加载与方法覆盖

## 一句话总结
Category 通过将自身方法列表插入到类 `class_rw_t.methods` 的**最前端**，使得在普通消息查找时 Category 方法优先于原类方法被找到，从而造成“覆盖”假象，但原方法并未被删除或替换 [2][3][4]。

## 核心原理

### 1. Category 编译与存储
- 编译器将每个 Category 编译成 `category_t` 结构体，其中包含实例方法列表、类方法列表、协议列表和属性列表 [4]。
- 这些 `category_t` 被放入 Mach-O 文件的 `__objc_catlist` 段中 [2][3][4]。

### 2. Runtime 加载阶段（Pre-main）
- 在 `_read_images` 函数中，Runtime 遍历 `__objc_catlist`，读取所有 Category [2][3]。
- 对每个 Category，找到其目标类 `cls`，将 `category_t` 与 `header_info` 包装成 `locstamped_category_t`，并暂存到该类对应的 `category_list` 中 [2][3]。
- 如果目标类**已 realize**（非懒加载类），则立即调用 `remethodizeClass(cls)` 触发方法附加；如果类**未 realize**（懒加载类），则先将 Category 暂存到全局 `unattachedCategories` 表，等该类被 realize 时再附加 [4]。

### 3. 方法附加过程（`attachCategories`）
- 从 `category_list` 中取出所有 `locstamped_category_t`，遍历其中的 `category_t`，收集其方法列表 [4]。
- 关键步骤（`attachCategories` 内部）：
  1. **从后往前遍历** Category，将每个 Category 的方法列表指针存入临时数组 `mlists` [5]。
  2. 调用 `rw->methods.attachLists(mlists, mcount)`，将整个 `mlists` 数组**整体插入到 `class_rw_t.methods` 的最前面**（即原方法列表之前）[5]。
  3. 附加后**清空方法缓存**，避免 `objc_msgSend` 继续命中旧 IMP [5]。
- Category 的实例方法附加到**类对象**（`isMeta=NO`），类方法附加到**元类对象**（`isMeta=YES`） [2][3][8]。

### 4. “覆盖”的实质
- 由于 Category 的方法列表被插入到方法数组的头部，而消息查找（`objc_msgSend`）从前往后遍历方法列表，因此 Category 中的同名方法**优先被找到**，表现为覆盖了原类方法 [2][3][4]。
- 原类方法依然存在于方法列表的后面，并未被删除或移动，只是查找时不会先命中 [2][4]。

## 关键细节与易错点

1. **多个 Category 的同名方法**：Runtime 从后往前遍历 Category 列表，再将所有方法列表整体插入到前面，因此**最后编译的 Category**（即最后被附加的）的方法会出现在方法数组的最前端，优先被找到。即“后编译的 Category 覆盖前编译的和原类的同名方法” [5][10]。
2. **`+load` 方法不受此规则影响**：`+load` 方法的调用**不通过消息机制**，而是 Runtime 在 `prepare_load_methods` 中直接获取函数指针，通过 `call_class_loads` 和 `call_category_loads` 遍历数组调用。因此，即使类与 Category 都实现 `+load`，两者都会被调用，不会发生“覆盖” [9]。
   - 调用顺序：先调用所有类的 `+load`（按编译顺序，父类先于子类），再调用所有 Category 的 `+load`（完全按编译顺序，与继承关系无关） [7][10]。
3. **无法在 Category 中安全调用原方法**：如果原方法存在于该类本身（而非父类），则通过 Category 直接覆盖后无法通过 `[super method]` 或直接调用原实现，因为原方法被“隐藏”了。若需保留原实现，需使用 Method Swizzling 技术 [11]。
4. **属性 vs 方法**：Category 可以声明 `@property`，但不会自动生成实例变量和 `@synthesize` 的存取方法。Runtime 仅将属性列表附加到类，但实例变量需额外使用关联对象实现（材料未展开关联对象细节） [4][6]。
5. **懒加载类与立即附加**：对于非懒加载类（实现了 `+load` 或 `+initialize`），类在 `_read_images` 阶段就会 realize，此时 Category 立即附加；对于懒加载类，Category 会暂存直到类第一次收到消息时才 realize 并附加 [4]。

## 高频追问

**Q1: 多个 Category 实现了同一个方法，最终哪个会生效？**
- 编译顺序决定最终结果。Runtime 按照 `__objc_catlist` 中的顺序遍历，但 `attachCategories` 中从后往前遍历 list，再将所有方法列表插到最前面，所以**最后被处理的 Category**（即最后编译的）中的方法会出现在方法列表最前端，优先被找到 [5][10]。

**Q2: Category 能覆盖类方法吗？**
- 能。类方法本质上是元类的实例方法，Category 的类方法列表会被附加到元类的 `class_rw_t.methods` 最前面，与实例方法覆盖原理相同 [2][3]。

**Q3: 为什么 `+load` 方法不会被覆盖？**
- 因为 `+load` 不经过消息发送机制。Runtime 在 `load_images` 中先通过 `prepare_load_methods` 将类与 Category 的 `+load` 方法指针分别存入 `loadable_classes` 和 `loadable_categories` 数组，之后直接通过函数指针调用，不会按照普通方法查找的“从前往后”规则 [9]。

**Q4: 如果想在 Category 中调用原方法的实现，有什么办法？**
- 可以使用 Method Swizzling。做法：在 Category 中实现一个具有不同名称的方法，然后在运行时交换该新方法与原始方法的 IMP，这样新方法内部可以通过新名称调用原始实现（实际已交换）。材料明确提到此方案 [11]。注意：普通 Category 覆盖后无法再通过 `[super method]` 调用原实现，因为 `super` 仍指向父类，而非当前类的同名方法。

## 原始资料索引

[2] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Category_OC2_0.md › category如何加载 › Category 加载流程总览（第853-879行）
[3] /Users/tommywu/Obsidian/iOS/Runtime/Part 3 - Category：加载、覆盖与关联对象.md › Category 加载流程总览（第773-799行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 一、冷启动（Cold Launch） › Pre-main 阶段 › 4. ObjC Runtime 初始化 › 4.3 处理 Category（第450-490行）
[5] /Users/tommywu/Obsidian/iOS/Runtime/Part 3 - Category：加载、覆盖与关联对象.md › Runtime 什么时候加载 Category（第765-771行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 1. 分类 category › 1.5 分类信息合并到类源码（第326-326行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/cnblogs.com/ios-load和-initialize方法调用时机.md › 一、+load 调用时机和顺序原理解析（第228-257行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c-runtime.md › [Objective-C Runtime](http://yulingtianxia.com/blog/2014/11/05/objective-c-runtime/) › Runtime 基础数据结构 › Category（第540-540行）
[9] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 2. load方法 › 2.3 源码分析（第708-726行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/cnblogs.com/ios-load和-initialize方法调用时机.md › 总结（第259-267行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2010-01-29-method-replacement-for-fun-and-profit.md › (全文)（第50-73行）
