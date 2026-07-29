---
topic: KVC取值查找顺序
group: KVC与KVO
generated_at: 2026-07-29T19:43:07
provider: deepseek
---

# KVC取值查找顺序

## 一句话总结
`valueForKey:` 按 **getter 方法 → 集合代理方法 → 检查是否允许直接访问实例变量 → 实例变量 → `valueForUndefinedKey:`** 的顺序查找，每一步的查找都有固定命名模式，最终若都失败则抛出异常。

## 核心原理

当调用 `[obj valueForKey:@"name"]` 时，Runtime 依次执行以下步骤 [1][2][4][6][9]：

1. **查找 getter 方法**
   按 `get<Key>` → `<key>` → `is<Key>` → `_<key>` 的顺序查找（此处 `<key>` 即键名 `name`，对应 `getName`、`name`、`isName`、`_name`）。找到任意一个则通过 `objc_msgSend` 调用该方法；若返回值是基本类型（如 `int`、`float`），自动包装为 `NSNumber` 或 `NSValue` [2][6][7][10]。
   注意：`_is<Key>` 作为方法名不在这个链上，它仅作为实例变量名存在；取值端和设值端在这里不对称 [9]。

2. **查找集合类代理方法**
   若上一步未找到任何 getter，则检查对象是否实现了集合相关的代理方法 [1][2][6][9]：
   - **NSArray 模式**：需同时实现 `countOf<Key>` + `objectIn<Key>AtIndex:`，返回 `NSKeyValueArray` 代理对象。
   - **NSSet 模式**：需同时实现 `countOf<Key>` + `enumeratorOf<Key>` + `memberOf<Key>:`，返回 `NSKeyValueSet` 代理对象。
   - **NSOrderedSet 模式**：需同时实现 `countOf<Key>` + `indexIn<Key>OfObject:` + `objectIn<Key>AtIndex:`，返回 `NSKeyValueOrderedSet` 代理对象 [9]。
   这些代理对象不是真容器，只是将容器协议的消息翻译成用户实现的几个原语方法 [9]。

3. **检查是否允许直接访问实例变量**
   调用类方法 `+accessInstanceVariablesDirectly`，默认返回 `YES` [1][2][4][6][8]。
   - 若返回 `NO`，则直接跳转到步骤 5（异常处理）。
   - 若返回 `YES`，继续步骤 4。

4. **查找实例变量**
   按 `_<key>` → `_is<Key>` → `<key>` → `is<Key>` 的顺序查找实例变量（例如 `_name`、`_isName`、`name`、`isName`）[1][2][4][6][9]。找到则直接返回其值。

5. **异常处理**
   若以上所有步骤都未找到，调用 `valueForUndefinedKey:`，默认实现抛出 `NSUndefinedKeyException` [1][2][4][6]。

> 各来源对 getter 方法搜索顺序的表述一致 [1][2][4][9]，实例变量顺序的描述也一致 [1][2][4][6][9]；[4] 中 getter 顺序写为 `getKey:`、`key`、`isKey`、`_key`，与 `get<Key>` 等同，无冲突。

## 关键细节与易错点

- **getter 方法顺序对大小写敏感**：`getName` 优先于 `name`，`name` 优先于 `isName`，`isName` 优先于 `_name` [1][2][9]。
- **集合代理方法的检测是严格的**：必须完整实现对应模式所需的所有方法，否则 KVC 会认为集合代理不存在，继续下一步 [1][2][6]。
- **`accessInstanceVariablesDirectly` 的返回值**：默认 `YES`，若重写为 `NO`，则即使存在实例变量，KVC 也不会直接访问，而是直接抛异常 [1][2][4][6][8]。
- **基本类型自动装箱**：`valueForKey:` 返回的基本类型（`int`、`float`、`struct` 等）会被自动包装为 `NSNumber` 或 `NSValue`，这是 KVC 独有的行为，常规方法调用或属性语法不具备 [7][10]。
- **KVC 的代价**：使用 KVC 访问属性的开销比直接调用存取方法要大，建议只在必要时使用 [7]。
- **`_is<Key>` 方法不在 getter 链上**：取值端不会去查找名为 `_isName` 的方法，但它可以作为实例变量名被搜索到（在 ivar 顺序的第二步 `_is<Key>`）[9]。

## 高频追问

**Q1：如果同时实现了 `getName` 和 `name` 方法，`valueForKey:` 会调用哪一个？**
A：会调用 `getName`，因为 getter 搜索顺序中 `get<Key>` 优先于 `<key>` [1][2][4][9]。

**Q2：`valueForKey:` 在什么情况下会返回 `nil`？什么情况下会抛出异常？**
A：
- 返回 `nil` 的情况：找到的 getter 返回 `nil`，或找到的实例变量值为 `nil`。
- 抛出异常的情况：经过全部查找步骤（包括 ivar 搜索）后仍未找到任何匹配项，最终调用 `valueForUndefinedKey:` 默认抛出 `NSUndefinedKeyException` [1][2][6]。
若 `accessInstanceVariablesDirectly` 返回 `NO`，则即便存在 ivar 也会直接抛异常 [2][4]。

**Q3：如果要让一个 `readonly` 属性也能被 KVC 读取（或写入），KVC 取值会受影响吗？**
A：取值不影响。`readonly` 属性只是编译器不生成 setter，但 getter（如果有）和 ivar 仍然会被 KVC 搜索到。`valueForKey:` 会正常返回 ivar 值 [12]（注：材料 [12] 主要讨论设值，但取值逻辑与此一致）。

**Q4：集合代理方法的三种模式分别需要实现哪些方法？**
A：
- **NSArray 模式**：`countOf<Key>` + `objectIn<Key>AtIndex:`
- **NSSet 模式**：`countOf<Key>` + `enumeratorOf<Key>` + `memberOf<Key>:`
- **NSOrderedSet 模式**：`countOf<Key>` + `indexIn<Key>OfObject:` + `objectIn<Key>AtIndex:` [1][2][9]

**Q5：KVC 在取值时如何自动处理标量类型？**
A：当 getter 方法返回 `int`、`float`、`struct` 等标量值时，`valueForKey:` 会自动将其包装为 `NSNumber` 或 `NSValue` 对象返回 [7][10]。这一过程对调用者透明。

**Q6：`get<Key>` 方法是否存在命名特殊要求？**
A：根据 KVC 规范，getter 名字应为 `get` + 键名（首字母大写），例如 `getName`。CamelCase 部分下划线不转义。各来源均使用此模式 [1][2][4][9]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › valueForKey: 的底层流程（第104-120行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › 面试题：KVC 的底层原理是什么 › `valueForKey:` 的查找流程（第433-441行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC、KVO的本质.md › 2. KVC的本质 › 2.3 取值原理valueForKey:（第363-396行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第643-672行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/yulingtianxia/objective-c中的kvc和kvo.md › [Objective-C中的KVC和KVO](http://yulingtianxia.com/blog/2014/05/12/objective-czhong-de-kvche-kvo/) › KVC（第45-88行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/neroxie.com/kvc实现原理.md › 搜索规则（第21-27行）
[9] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md › KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发 › 三、取值端：四个 getter 和三个集合代理（第181-216行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2013-02-08-let-s-build-key-value-coding.md › (全文)（第29-45行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md › KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发 › 二、落到 ivar 那一步，语义变了 › readonly 属性能被 KVC 改（第145-160行）
