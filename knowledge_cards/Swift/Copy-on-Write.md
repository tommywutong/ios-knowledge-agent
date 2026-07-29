---
topic: Copy-on-Write
group: Swift
generated_at: 2026-07-29T19:50:25
provider: deepseek
---

# Copy-on-Write

## 一句话总结
Copy-on-Write（写时拷贝，COW）是 Swift 为了平衡值语义与性能而采用的优化：赋值时共享底层引用类型存储，仅在首次修改时深拷贝一份独立副本 [4][7]。标准库中的 `Array`、`Dictionary`、`Set` 等集合类型都内置了 COW 优化 [2][4]。

## 核心原理
1. **值语义与引用底层**：Swift 的集合类型（如 `Array`）是值类型，但底层使用引用计数的类实例（如 `ManagedBuffer`）来存储元素 [4]。赋值操作复制的是外层的轻量级结构体，它们共享同一份堆上 buffer；这样避免了不必要的深拷贝 [7]。
2. **检查唯一引用**：当执行修改操作（如 `append`、`remove` 等）时，会调用 `isKnownUniquelyReferenced(&storage)` 函数检测底层存储是否只有当前一个强引用 [1][2][4]。如果是唯一引用，直接原地修改；否则先执行 `storage.copy()` 创建副本，再在新副本上修改 [2][4]。
3. **实现模板**：自定义结构体实现 COW 的典型模式如下 [2][5]：
   ```swift
   struct MyArray<Element> {
       private var storage: ArrayStorage<Element>
       mutating func append(_ element: Element) {
           if !isKnownUniquelyReferenced(&storage) {
               storage = storage.copy() // 写时拷贝
           }
           storage.append(element)
       }
   }
   ```
4. **应用场景**：Swift 标准库的 `Array`、`Dictionary`、`Set` 等都采用了 COW [4][11]（材料 [11] 提到字符串也会间接将值保存在堆中，但未明确说明 COW；[4] 明确说 Array/Dictionary/Set 行为如此）。

## 关键细节与易错点
- **COW 不是对所有值类型默认生效**：只有那些底层使用引用类型存储的值类型才能应用 COW。例如自定义的纯 Swift 值类型（如 struct 嵌套基本类型）在赋值时就会直接拷贝，不存在共享 buffer [2][5]（材料 [2] 指出 Array 等内置了 COW，[5] 示例显示包含引用类型的结构体才能用）。
- **`isKnownUniquelyReferenced` 的限制**：该函数适用于任何类实例，但它仅检查当前线程的强引用计数是否为 1，不考虑弱引用或无主引用 [1][2]。另外，它要求传入 `inout` 参数，且不适用于 Objective-C 对象或 Swift 原生类型（如 `Array` 本身）[4]（材料 [4] 提到它测试类类型是否有单引用或多引用；[1] 示例中对 `Node` 类使用）。
- **COW 与链表等自定义类型**：如果自定义链表使用引用类型作为节点，直接赋值会导致引用语义（修改共享节点影响所有副本）[11][12]。需要手动实现 COW：在每次修改前调用 `copyNodes()` 遍历复制完整链表，再使用 `isKnownUniquelyReferenced` 优化：仅当引用不唯一时才复制 [1][12]。
- **性能权衡**：COW 在多次共享后首次修改时产生 `O(n)` 拷贝开销，同一次修改后续不再重新拷贝（因为此时 storage 已唯一）。对于链表，不加优化每次修改都 `O(n)`，但结合 `isKnownUniquelyReferenced` 后可降到只在多引用时复制 [1]。

## 高频追问
1. **面试官：自定义值类型如何实现 COW？**
   答：需要让存储使用引用类型（class），在结构体内部持有一个私有存储属性。所有修改方法（标记为 `mutating`）中先调用 `isKnownUniquelyReferenced(&storage)`，如果返回 `false` 则执行 `storage = storage.copy()` 创建副本，然后在新副本上修改。[2][5]

2. **面试官：`isKnownUniquelyReferenced` 的工作原理是什么？**
   答：它是 Swift 运行时提供的函数，接收一个 `inout` 参数（必须是类类型），返回一个布尔值表示该实例是否只有唯一的强引用。它依赖于 Swift 的引用计数机制，但不考虑弱引用和无主引用。[1][4]（材料 [1][4] 提到它测试单/多引用，[2] 给出了代码示例）。

3. **面试官：Array、Dictionary、Set 什么时候真正复制内存？**
   答：赋值时（如 `var array2 = array1`）仅增加引用计数，底层存储共享。直到对其中一个变量执行修改操作（如 `append`、`remove`、下标赋值等），才触发 COW 进行深拷贝。[4][7]

4. **面试官：COW 和值语义的关系？**
   答：COW 是值语义的一种优化实现。值语义要求每个变量独立，但通过“先共享再复制”避免了不必要的拷贝，兼顾了性能和逻辑正确性。[4][7]

5. **面试官：如果多次赋值后修改，复制发生几次？**
   答：只有第一次修改时触发一次深拷贝（因为此时 `isKnownUniquelyReferenced` 为 `false`），之后该变量持有唯一存储，后续修改不再复制。[1]（材料中 [1] 的示例显示 list1 和 list2，list2 append 后 list1 不受影响，且 `isKnownUniquelyReferenced` 在复制后变为 `true`）。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/链表 LinkedList.md › 7. 优化 COW › 7.1 isKnownUniquelyReferenced（第594-636行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/值类型和引用类型的区别.md › 值类型和引用类型的区别 › 写时拷贝（Copy-on-Write） › 实现机制（第219-240行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/optimizing-a-copy-on-write-double-ended-queue-in-swift-cocoa-with-love.md › Copy-on-write in Swift（第59-67行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Swift底层原理-结构体、类和协议.md › Swift底层原理-结构体、类和协议 › Swift结构体的底层实现 › 值类型的核心特征 › 3. 写时拷贝优化（COW）（第343-358行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2025/312-improve-memory-usage-and-performance-with-swift.md › Improve memory usage and performance with Swift › Transcript（第170-172行）
[11] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/链表 LinkedList.md › 6 值语义和写时拷贝（第466-526行）
[12] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/链表 LinkedList.md › 6 值语义和写时拷贝（第528-585行）
