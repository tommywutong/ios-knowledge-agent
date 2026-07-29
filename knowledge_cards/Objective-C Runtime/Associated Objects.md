---
topic: Associated Objects
group: Objective-C Runtime
generated_at: 2026-07-29T19:28:38
provider: deepseek
---

# Associated Objects

## 一句话总结

关联对象（Associated Objects）是 Objective-C Runtime 提供的机制，允许在运行时将任意值关联到任意对象，常用于在分类（Category）中模拟存储属性，其本质是存储在 Runtime 维护的一张全局哈希表中，而非对象本身 [1] [9] [10]。

## 核心原理

### 1. 存储结构
关联对象不存储在对象的内存中，而是由 Runtime 维护的全局哈希表管理 [9] [10]。这个全局结构是一个三级映射 [2] [5] [6]：

- **顶层**：`AssociationsManager`，持有一个 `AssociationsHashMap` 单例 [2] [6]。
- **中层**：`AssociationsHashMap`，是一个以 `DisguisedPtr<objc_object>`（对象指针的伪装值）为 key、`ObjectAssociationMap` 为 value 的哈希表 [2] [6]。
- **底层**：`ObjectAssociationMap`，是一个以 `const void *key` 为 key、`ObjcAssociation` 为 value 的映射 [2] [6]。
- **条目**：`ObjcAssociation` 封装了关联值（value）和内存管理策略（policy） [6] [11] [12]。

简而言之：每个对象对应一个 `ObjectAssociationMap`，一个 `ObjectAssociationMap` 保存该对象的所有关联记录 [6]。

### 2. 核心 API
三个运行时函数构成关联操作的基础 [1] [3] [7] [10]：

- `objc_setAssociatedObject(id object, const void *key, id value, objc_AssociationPolicy policy)`：为指定对象关联值，当 value 为 nil 时相当于清除关联 [1] [4]。
- `objc_getAssociatedObject(id object, const void *key)`：取出指定对象的关联值 [1] [7]。
- `objc_removeAssociatedObjects(id object)`：清除指定对象的所有关联对象 [1] [4] [10]。

### 3. 实现流程（objc_setAssociatedObject）
设置关联对象的核心实现位于 `_object_set_associative_reference` 函数，其调用栈为：`objc_setAssociatedObject` → `objc_setAssociatedObject_non_gc` → `_object_set_associative_reference` [5]。

该方法分为两种情况 [8]：

1. **new_value != nil**：从 `AssociationsManager` 中根据对象指针找到或创建 `ObjectAssociationMap`，再以传入的 key 存储 `ObjcAssociation`（含 value 和 policy） [2] [5]。
2. **new_value == nil**：删除指定的关联对象，即从 `ObjectAssociationMap` 中移除该 key 对应的条目 [5] [8]。

### 4. 生命周期与释放
- **关联对象不引用 object**：`AssociationsHashMap` 仅使用 object 的地址计算伪装值，但不会 retain 对象本身 [2]。
- **自动清理**：当对象 dealloc 时，Runtime 会自动检查并清理其所有关联对象（路径为 `objc_destructInstance` → `_object_remove_assocations`），因此一般无需手动调用 `objc_removeAssociatedObjects` [9] [10]。
- **手动移除**：推荐使用 `objc_setAssociatedObject` 传入 nil 来移除单个关联，而非调用 `objc_removeAssociatedObjects`，后者会移除对象的所有关联对象，可能造成意外副作用 [1] [4]。

### 5. Key 的使用
- `key` 是 `const void *` 类型，即一个地址值，因此只需定义即可使用，无需为其分配值 [1]。
- 常用的 key 选用方式包括：静态全局变量、`SEL`（因为 SEL 是唯一的常量） [3] [9]。

## 关键细节与易错点

| 关键点 | 说明 | 来源 |
|--------|------|------|
| **不要滥用 `objc_removeAssociatedObjects`** | 该函数主要用于将对象还原为“初始状态”，会删除该对象的所有关联；正确的移除方式是传 nil 给 `objc_setAssociatedObject`。 | [1] [4] |
| **关联对象不是分类的属性替代品** | 应作为万不得已的方法，而非首选解决方案。 | [4] |
| **内存管理策略与 property 的对应关系** | 关联策略枚举决定值的存储方式，详见 [11] [12]（注意两个表格在 `OBJC_ASSOCIATION_COPY` 与 `OBJC_ASSOCIATION_RETAIN` 对 property 描述的对应上存在冲突，需自行验证）。 | [11] [12] |
| **key 必须是唯一常量** | key 是一个指针，应使用静态变量或 SEL 等唯一标识符，确保不与其他关联混淆。 | [1] [3] [9] |
| **分类无法直接添加 ivar** | 分类的编译期结构体 `category_t` 中没有 `ivar_list`，因此无法直接添加实例变量，只能通过关联对象间接实现。 | [9] |

## 高频追问

### Q1：分类为什么不能直接添加属性？关联对象如何解决这一问题？
**回答要点**：
- 分类在编译期的 `category_t` 结构体中不含 `ivar_list`，因此无法直接添加实例变量 [9]。
- 关联对象通过 Runtime 的全局哈希表间接实现存储，使得分类的 setter/getter 可以在外部维护变量的存取 [9]。
- 核心代码模式：在 setter 中调用 `objc_setAssociatedObject`，在 getter 中调用 `objc_getAssociatedObject` [1] [9]。

### Q2：关联对象存储在哪？和对象本身的关系是什么？
**回答要点**：
- 关联对象存储在 Runtime 全局的哈希表 `AssociationsHashMap` 中，不占用对象实例的内存空间 [9] [10]。
- 该表以对象地址的伪装值为 key 进行索引，但关联对象**不会引用（retain）对象本身** [2]。
- 对象释放时，Runtime 自动清理由该对象触发的所有关联条目，因此不会造成内存泄漏 [9] [10]。

### Q3：关联对象的内存管理策略有哪些？如何理解它们的含义？
**回答要点**：
- `OBJC_ASSOCIATION_ASSIGN`：弱引用关联值（对应 `assign`） [11] [12]。
- `OBJC_ASSOCIATION_RETAIN_NONATOMIC`：强引用、非原子性（对应 `nonatomic, strong`） [11] [12]。注意 [11] 的表格中 `OBJC_ASSOCIATION_COPY` 被描述为对应 `nonatomic, strong`，而 [12] 的表格中 `OBJC_ASSOCIATION_RETAIN_NONATOMIC` 被描述为对应 `atomic, copy`，说明两个材料在字符串描述上有冲突，应以实际行为为准。
- `OBJC_ASSOCIATION_COPY_NONATOMIC`：复制关联值、非原子性（对应 `nonatomic, copy`） [11] [12]。
- `OBJC_ASSOCIATION_RETAIN`：强引用、原子性（对应 `atomic, strong`） [11]。
- `OBJC_ASSOCIATION_COPY`：复制关联值、原子性（对应 `atomic, copy`） [11] [12]。

### Q4：关联对象在对象释放时如何处理？是否需要手动清理？
**回答要点**：
- 当对象 dealloc 时，Runtime 会沿着 `objc_destructInstance` → `_object_remove_assocations` 路径自动清理属于该对象的所有关联对象 [9] [10]。
- 因此，一般情况下无需手动调用 `objc_removeAssociatedObjects` 或逐一清空关联值 [10]。
- 唯一推荐的手动移除方式：为 `objc_setAssociatedObject` 传入 `nil` 清理单个关联 [1] [4]。

### Q5：如何移除关联对象？为什么不推荐使用 `objc_removeAssociatedObjects`？
**回答要点**：
- 推荐方法：调用 `objc_setAssociatedObject(object, key, nil, policy)` 清除指定 key 的关联 [1] [4]。
- **不推荐使用 `objc_removeAssociatedObjects`** 的原因是它会移除该对象的**所有**关联值，可能破坏其他代码添加的关联，该函数主要用于将对象还原为初始状态 [1] [4] 。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/关联对象 Associated Object 的本质.md › 1. 分类添加成员变量方案 › 1.3 关联对象 Associated Object（第109-146行）
[2] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/关联对象 Associated Object 的本质.md › 2. 关联对象的本质 › 2.1 objc_setAssociatedObject源码（第289-327行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 4. 关联对象 Associated Objects（第587-614行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 4. 关联对象 Associated Objects › 4.2 移除关联对象的值（第628-632行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/draveness.me/关联对象-associatedobject-完全解析-面向信仰编程.md › 关联对象的实现 › objc_setAssociatedObject（第200-233行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/leichunfeng/objective-c-associated-objects-的实现原理.md › Objective-C Associated Objects 的实现原理 › 实现原理 › objc_setAssociatedObject（第308-319行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/objective-c-runtime-运行时之二-成员变量与属性.md › 成员变量、属性 › 成员变量、属性的操作方法 › 关联对象（第191-206行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/draveness.me/关联对象-associatedobject-完全解析-面向信仰编程.md › 关联对象的实现 › objc_setAssociatedObject › 如何存储 ObjcAssociation（第319-328行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runtime.md › Runtime › 常见面试题 › Q4: 如何给分类（Category）添加成员变量？（第832-866行）
[10] /Users/tommywu/Obsidian/iOS/99 归档/Runtime 旧稿/Category_OC2_0.md › Category 与关联对象 › 三个 API（第928-948行）
[11] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/关联对象 Associated Object 的本质.md › 1. 分类添加成员变量方案 › 1.3 关联对象 Associated Object › 1.3.2 内存管理（第180-190行）
[12] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 4. 关联对象 Associated Objects › 4.1 内存管理（第616-626行）
