---
topic: KVC设值与异常
group: KVC与KVO
generated_at: 2026-07-29T19:43:36
provider: deepseek
---

# KVC设值与异常

## 一句话总结

KVC 设值通过 `setValue:forKey:` 按照“先找 setter、再找 ivar、最后抛异常”的顺序间接访问对象的属性，内部会自动调用 `willChangeValueForKey:` / `didChangeValueForKey:` 从而触发 KVO 通知，即使对象没有 setter 也能通过 ivar 路径成功赋值。

## 核心原理

### `setValue:forKey:` 的查找流程

以 `[obj setValue:@"Tom" forKey:@"name"]` 为例，底层按以下顺序查找：

1. **查找 setter 方法**：Runtime 按 `setName:` → `_setName:` 顺序查找，找到任意一个就通过 `objc_msgSend` 调用并结束 [3] [10] [7]。
2. **检查是否允许直接访问实例变量**：若未找到 setter，调用类方法 `+accessInstanceVariablesDirectly`，默认返回 `YES`；若重写为 `NO`，则跳过 ivar 查找直接进入步骤 4 [3] [6] [7]。
3. **查找实例变量**：按 `_name` → `_isName` → `name` → `isName` 顺序查找，找到则通过 `object_setIvar` 直接赋值 [3] [6] [7]。
4. **异常处理**：若以上步骤均未找到，调用 `setValue:forUndefinedKey:`，其默认实现抛出 `NSUndefinedKeyException`（字符串值为 `@"NSUnknownKeyException"`，历史遗留）[3] [10] [12]。

### 基本类型 nil 的处理

当对基本类型（`int`、`float`、`BOOL` 等）的属性调用 `setValue:nil forKey:` 时，KVC 会调用 `setNilValueForKey:`，默认实现抛出 `NSInvalidArgumentException`。可重写此方法设置默认值来避免崩溃 [3] [11] [12]。

### KVC 触发 KVO 的原理

KVC 的 `setValue:forKey:` 内部在设置值前后自动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:`，因此即使对象没有 setter（仅通过 ivar 赋值），也会触发 KVO 通知 [1] [2] [8]。这与直接修改实例变量（如 `_name = @"x"`）不同——后者不会经过任何通知机制 [2] [8]。

## 关键细节与易错点

### `+accessInstanceVariablesDirectly` 的作用

- 默认为 `YES`，允许 KVC 通过 ivar 路径赋值；返回 `NO` 则禁止该路径，若 setter 也不存在，直接走异常 [3] [4] [6]。
- 重写为 `NO` 可以阻止 KVC 修改 `readonly` 属性或未公开的 ivar，例如：
  ```objc
  @interface IvarBlocked : NSObject
  @end
  // 调用 [obj setValue:@"secret" forKey:@"token"] 会抛出 NSUnknownKeyException [4]
  ```

### 落到 ivar 时失去 `copy` 语义

- 当 KVC 找不到 setter 而落在 ivar 路径时，它是 **retain** 而不是 **copy**。声明为 `copy` 的属性如果被 KVC 通过 ivar 赋值，将不会获得副本 [5]。
- 正常 `@property`（有编译器合成的 setter）命中搜索链第一步，不会走入此坑 [5]。
- `readonly` 属性编译器不生成 setter，但仍会合成 `_<key>` ivar，因此 KVC 可以修改其值——除非 `+accessInstanceVariablesDirectly` 返回 `NO` [4]。

### 异常名称的历史遗留

- 头文件中常量名是 `NSUndefinedKeyException`，但其实际字符串值是 `@"NSUnknownKeyException"`。这是为了匹配旧版已废弃的 KVC 方法遗留的异常名称，导致按崩溃日志搜索时可能找不到常量 [12]。
- 对基本类型传 nil 引发的异常是 `NSInvalidArgumentException`，提示信息为 `setNilValueForKey: could not set nil as the value for the key age.` [12]。

### 不依赖 isa 的 KVO 触发路径

- KVO 有两种独立触发通知的路径：一是被 isa-swizzling 改造后的 setter；二是在 `setValue:forKey:` 内部自动调用的 `willChangeValueForKey:` / `didChangeValueForKey:` [2]。
- 因此即使对象没有 setter（如只声明了 `_tag` ivar），使用 KVC 赋值仍会发出通知，而直接写 `_tag = @"x"` 则不会 [2]。

### 集合类型属性的设值

- 直接操作集合（如 NSArray、NSSet）不会触发 KVO，应通过 `mutableArrayValueForKey:` 等代理方法操作，这些方法内部会自动调用 `willChange:valuesAtIndexes:forKey:` 和 `didChange:valuesAtIndexes:forKey:` [8]。

## 高频追问

### 1. 如果一个类只声明了成员变量（没有 `@property`、没有 setter），KVC 能赋值吗？

**能**。`setValue:forKey:` 在找不到 setter 后会检查 `+accessInstanceVariablesDirectly`（默认 YES），然后按 `_key` → `_isKey` → `key` → `isKey` 顺序查找 ivar 并赋值 [3] [2]。此过程中会自动触发 KVO 通知 [2]。

### 2. 给 `int` 类型的属性传 `nil` 为什么会崩溃？

因为 KVC 会调用 `setNilValueForKey:`，其默认实现抛出 `NSInvalidArgumentException` [3] [11]。重写该方法即可避免崩溃，例如设置默认值 [11]。

### 3. 如何阻止 KVC 修改某个 `readonly` 属性？

在类中重写 `+ (BOOL)accessInstanceVariablesDirectly` 返回 `NO`，这样 KVC 找不到 setter 后会直接调用 `setValue:forUndefinedKey:` 抛出异常 [4]。也可以重写 `setValue:forUndefinedKey:` 自行处理。

### 4. KVC 设值时，搜索顺序中 `setName:` 和 `_setName:` 哪个优先级更高？

`setName:` 优先于 `_setName:`。如果同时实现了两个方法，只会调用 `setName:` [10] [3]。

### 5. 为什么 KVC 能够触发 KVO 而直接修改 ivar 不能？

因为 `setValue:forKey:` 内部在赋值前后会自动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:`，即使最终走的是 ivar 路径也会触发。而直接写 ivar（如 `obj->_name = ...`）是编译时的内存写指令，没有任何拦截点，不经过 KVC 内部机制 [1] [2]。

### 6. 如果 `+accessInstanceVariablesDirectly` 返回 NO，但存在匹配的 ivar，KVC 会成功吗？

不会。返回 NO 意味着不允许通过 ivar 赋值，KVC 直接调用 `setValue:forUndefinedKey:` 抛出异常，不会检查 ivar [3] [6] [7]。

### 7. 本卡片材料中未包含关于 KVC 设值中类型转换或验证的细节，是否有相关说明？

本卡片材料不足。现有内容主要描述查找顺序和异常处理，未提及验证或自动类型转换的具体实现。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › KVC 与 KVO 的关系（第402-416行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md › KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发 › 七、观察一个没有 setter 的 key（第548-583行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › 面试题：KVC 的底层原理是什么 › `setValue:forKey:` 的查找流程（第422-431行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md › KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发 › 二、落到 ivar 那一步，语义变了 › readonly 属性能被 KVC 改（第145-160行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS JSONModel 源码：Runtime 驱动的属性映射.md › JSONModel 源码：Runtime 驱动的属性映射 › 四、它在哪里用 KVC，在哪里不用 › 一个 KVC 的坑在这里恰好不成立（第521-532行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/neroxie.com/kvc实现原理.md › 搜索规则 › 赋值原理（第99-156行）
[7] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC、KVO的本质.md › 2. KVC的本质 › 2.1 设值原理setValue:forKey:（第254-271行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 常见面试题 › KVO 的底层原理是什么？（第348-350行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/neroxie.com/kvc实现原理.md › 搜索规则 › 赋值原理（第29-97行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › setValue:forKey: 的底层流程 › 对基本类型的处理（第58-70行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md › KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发 › 二、落到 ivar 那一步，语义变了 › 一个能省半小时的细节（第162-179行）
