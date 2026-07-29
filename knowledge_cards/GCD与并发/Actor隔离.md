---
topic: Actor隔离
group: GCD与并发
generated_at: 2026-07-29T19:42:02
provider: deepseek
---

# Actor隔离

## 一句话总结
Actor是Swift中通过**数据隔离（actor isolation）**自动保证线程安全的引用类型，所有属性和代码被隔离以防止并发访问，外部访问需要`await`，内部无需等待，且所有Actor类型隐式满足Sendable协议，可在并发域间安全传递。 [6][9][11]

## 核心原理

1. **Actor隔离规则**
   - Actor的实例属性、实例方法（以及扩展中的方法）默认隔离在该Actor上，只能在Actor内部同步访问。外部访问必须通过`await`排队到Actor的串行执行器上。 [6][11]
   - 非Sendable闭包（如传递给`reduce`算法的闭包）留在Actor上下文中，继承Actor隔离；而`Task.detached`中的闭包是`@Sendable`的，不继承隔离，必须通过`await`访问Actor属性。 [6]
   - 使用`nonisolated`标记不需要隔离的成员（如纯计算属性、只读`let`属性），可以同步访问，不涉及Actor可变状态。 [11]

2. **Sendable协议**
   - Sendable类型标记可安全跨并发域传递，是Swift Concurrency数据安全的基石。 [9]
   - 自动满足Sendable的类型：所有存储属性都是Sendable的**值类型**（`struct`、`enum`）；**Actor类型**（自带隔离保护）；只包含不可变`let`+Sendable属性的`final class`。 [9]
   - `@unchecked Sendable`用于开发者通过内部同步机制（如`NSLock`）保证安全，但编译器无法自动验证的场景。若实际不安全，会导致运行时数据竞争。 [9]
   - `@Sendable`闭包要求不能捕获非Sendable的可变外部变量，否则编译错误。 [2][9]

3. **数据竞争静态检查演变**
   - Swift 5.10的完整并发检查禁止传递非Sendable值跨Actor隔离边界；Swift 6改进为：若非Sendable值在传递后原隔离域不再引用它（无法共享），则编译通过。 [1]
   - Swift 6语言模式默认将数据竞争问题变为编译时错误，模块间增量启用。 [1]

4. **默认Actor隔离（Default Actor Isolation）**
   - Xcode构建设置`SWIFT_DEFAULT_ACTOR_ISOLATION`可设为`MainActor`，使得未注解代码推断为@MainActor隔离，减少误报。 [4][10]
   - Swift 6.2进一步优化，可删除大多数@MainActor注解。 [4]

5. **动态Actor隔离断言**
   - SE-0423在数据安全与不安全代码边界注入运行时检查，捕获库依赖中缺失`@Sendable`注解导致的隔离违规。部分崩溃是假阳性——若函数未实际访问任何Actor隔离状态，可省略动态检查。 [7]

6. **Actor Reentrancy（可重入性）**
   - Actor方法遇到`await`挂起点时会释放对该Actor的独占访问，允许其他任务在此期间进入该Actor。因此`await`前后Actor状态可能变化，需在`await`之后重新验证假设。 [11]
   - 这是有意设计以**防止死锁**（如Actor A等待B，B等待A时无法重入会死锁）。 [11][12]

## 关键细节与易错点

- **类作为Actor属性导致数据竞争**：若Actor的某个属性是`class`（引用类型），调用方法向外返回该实例的引用后，外部和Actor都持有同一可变对象的引用，产生数据竞争风险。值类型（struct）和Actor本身是安全的。 [3]
- **闭包的隔离继承**：`Task.init`继承当前上下文的Actor隔离，`Task.detached`不继承。非Sendable闭包留在Actor上，`@Sendable`闭包被认为是非隔离代码。 [6]
- **@MainActor**：专门处理主线程的Actor，用于UI渲染和用户事件处理。 [2]
- **修复数据竞争的方法**：当动态断言指示运行时数据竞争时，要么将该函数运行在Actor上，要么修改函数消除对Actor隔离状态的访问。 [7]
- **Mutex使类Sendable**：Swift 6.2中`Mutex`是使类达到Sendable安全的重要工具，需参考官方文档。 [4]
- **Actor循环依赖与重入**：通过`nonisolated`标记无需隔离的方法减少Actor跳转；用`Task.detached`跳出当前Actor打破循环；在`await`之前完成所有状态修改，避免重入破坏不变量。 [12]
- **`await`后的状态检查**：因重入可能，例如缓存场景中，`await`下载后应检查`cache[url]`是否已被其他任务设置，避免覆盖。 [11]

## 高频追问

**Q1: Actor与类的区别是什么？**
- Actor是引用类型，但隔离所有属性和代码防止并发访问，而类不提供隔离。因此持有Actor的引用是安全的（类似地图指向岛屿，访问需“靠岸”手续），所有Actor类型隐式Sendable。 [6]
- 类实例在跨Actor传递时若引用可变状态则可能导致数据竞争，除非使用同步机制（如`Mutex`）并声明`@unchecked Sendable`。 [4][9]

**Q2: 为什么外部访问Actor需要`await`？**
- 因为Actor保证其隔离域内状态的安全修改，外部调用需要被序列化到Actor的执行器上排队执行，所以必须异步等待。 [6][11]

**Q3: 如何解决Actor重入导致的状态损坏？**
- 在`await`之后重新验证状态假设（例如检查缓存是否已被填充）；将状态修改尽量放在`await`之前完成。 [11][12]
- 也可使用TaskGate模式：在修改状态之前锁定，防止重入破坏不变量。 [12]

**Q4: 如何让一个类变成Sendable？**
- 编译器自动检查：如果类被声明为`final`且所有属性都是不可变（`let`）+Sendable，可以显式声明`Sendable`。 [9]
- 如果类内部使用锁等同步机制保证线程安全，可以标注`@unchecked Sendable`并自己保证安全。 [9]
- 使用`Mutex`（Swift 6.2+）来保护可变状态，从而让类符合Sendable要求。 [4]

**Q5: Swift 6默认如何检查数据竞争？**
- 开启Swift 6语言模式后，数据竞争变为编译时错误。 [1]
- 改进规则：如果非Sendable值被传递到另一个隔离域后，原域不再保留引用（无法共享），则编译通过（Swift 5.10会报错）。 [1]
- 模块间增量迁移，依赖库未迁移时通过动态断言（SE-0423）捕获运行时隔离违规。 [1][7]

**Q6: `nonisolated`和`@MainActor`如何一起使用？**
- 材料未直接说明，但从原理看：`nonisolated`用于标记不在任何Actor隔离域内的方法，可同步访问；若该方法需要访问主线程专用UI，则仍应标注`@MainActor`而不是`nonisolated`。材料中无进一步细节，**本卡片材料不足**。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2024/10136-what-s-new-in-swift.md › What’s new in Swift › Transcript（第298-304行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10133-protect-mutable-state-with-swift-actors.md › Protect mutable state with Swift actors › Transcript（第475-505行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10133-protect-mutable-state-with-swift-actors.md › Protect mutable state with Swift actors › Transcript（第379-411行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2025/266-explore-concurrency-in-swiftui.md › Explore concurrency in SwiftUI › Transcript（第242-250行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2022/110351-eliminate-data-races-using-swift-concurrency.md › Eliminate data races using Swift Concurrency › Transcript（第264-292行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/oss/swift-evolution/visions/approachable-concurrency.md › Improving the approachability of data-race safety › Easing incremental migration to data-race safety › Mitigating runtime assertions due to isolation mismatches（第177-183行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › Swift Concurrency（Swift 5.5+） › Sendable协议（第792-845行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/xcode/build-settings-reference.md › Build settings reference › Overview › Default Actor Isolation（第4171-4175行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › Swift Concurrency（Swift 5.5+） › 核心概念 › Actor（第604-658行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/死锁/死锁.md › 死锁（Deadlock）原理、常见场景与治理 › 三、iOS 中常见的死锁场景 › 场景 9：Swift Concurrency 下的死锁 › (c) actor 循环依赖（较少见，系统通过重入避免）（第315-324行）
