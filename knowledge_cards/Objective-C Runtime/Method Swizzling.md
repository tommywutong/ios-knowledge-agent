---
topic: Method Swizzling
group: Objective-C Runtime
generated_at: 2026-07-29T19:27:35
provider: deepseek
---

# Method Swizzling
## 一句话总结
Method Swizzling 是在运行时交换两个方法实现的技术，本质是改变 selector 到 IMP 的映射 [6][3]，常用于 Hook 系统方法、AOP 编程等场景 [6][10]。

## 核心原理
- **最小实现**：直接调用 `method_exchangeImplementations(originalMethod, swizzledMethod)`，效果相当于先取两个 IMP 再分别用 `method_setImplementation` 赋值 [7]。
- **标准工程模板**（安全交换）：
  1. 保证执行时机：在 `+load` 中执行 [3][4][11]。
  2. 保证幂等：用 `dispatch_once` 包裹 [3][4]。
  3. 避免污染父类：先调用 `class_addMethod(class, originalSelector, imp_swizzled, type_swizzled)` 尝试向当前类添加方法，若添加成功（说明 originalMethod 来自父类），则用 `class_replaceMethod` 替换 swizzledSelector 的实现 [1][2][4][9]；若添加失败（说明当前类本身已有实现），则直接调用 `method_exchangeImplementations` [2]。
- **代码示例**（来自统一 Swizzle 工具）：
```objc
+ (void)swizzleInstanceMethod:(SEL)originalSel with:(SEL)swizzledSel {
    Class class = [self class];
    Method originalMethod = class_getInstanceMethod(class, originalSel);
    Method swizzledMethod = class_getInstanceMethod(class, swizzledSel);
    BOOL didAddMethod = class_addMethod(class, originalSel,
                method_getImplementation(swizzledMethod),
                method_getTypeEncoding(swizzledMethod));
    if (didAddMethod) {
        class_replaceMethod(class, swizzledSel,
                method_getImplementation(originalMethod),
                method_getTypeEncoding(originalMethod));
    } else {
        method_exchangeImplementations(originalMethod, swizzledMethod);
    }
}
```
  该模板解决了“直接交换继承来的 Method 可能改到父类行为”的问题 [8]。

## 关键细节与易错点
- **执行时机**：
  - 推荐在 `+load` 中执行。原因：`+load` 由 Runtime 保证每个类只调用一次，且在串行加锁环境下执行，无需 `dispatch_once` 也能保证天然只执行一次 [11][12]。
  - 不推荐在 `+initialize` 中执行。原因：子类未实现时父类的 `+initialize` 会被多次调用，导致多次 `method_exchangeImplementations` 将 IMP 换回；swizzling 操作（`class_addMethod` + `method_exchangeImplementations`）非原子，`+initialize` 可能在多线程环境下被调用，存在竞争窗口；`+initialize` 内部有锁，复杂场景下可能死锁 [5][11]。
- **不要在 `+load` 中调用 `[super load]`**：会导致父类的 swizzle 被重复执行两次，使交换失效 [3]。
- **调用完自定义实现后，记得调用原生方法实现**：因为交换后，自定义方法里调用原 selector 实际上会调用到原生实现（通过递归调用 swizzled 方法名实现）[3][4]。
- **命名冲突**：swizzled 方法名若与其他 Category 重名会静默覆盖，建议加前缀（如 `af_`）[3]。
- **多次 swizzle 同一方法的风险**：不同框架处理方式不同，如 JRSwizzle 使用全局 SEL 有冲突风险，RSSwizzle 用 block 捕获 IMP 各自独立 [3]。

## 高频追问
### Q1: Method Swizzling 应该在 `+load` 还是 `+initialize` 中执行？为什么？
**A**：应该在 `+load` 中执行。理由三点：
1. `+load` 天然只执行一次，且在串行加锁环境下执行，不需要 `dispatch_once` 保护；而 `+initialize` 可能因子类继承被多次调用 [11][12]。
2. 线程安全：`+load` 在 `loadMethodLock` 保护下串行执行，天然避免竞争；`+initialize` 可能在多线程下被调用，即使 `dispatch_once` 保护入口，内部多步操作之间仍有竞争窗口 [11]。
3. 调用顺序：`+load` 保证父类先于子类执行；`+initialize` 的调用顺序取决于哪个类先收到消息，不可控 [11]。

### Q2: 为什么要在 Method Swizzling 模板中先调用 `class_addMethod`？
**A**：为了安全处理“方法来自父类”的情况。如果当前类没有重写 originalSelector，`class_getInstanceMethod` 会返回父类的 Method 对象，直接 `method_exchangeImplementations` 会修改父类的方法表，污染父类。先通过 `class_addMethod` 尝试将 swizzled 实现添加到当前类（如果返回 YES，说明当前类本来没有该方法），再用 `class_replaceMethod` 将 swizzledSelector 指向原始实现，这样就只影响当前类 [2][8][9]。如果 `class_addMethod` 返回 NO（当前类已有实现），则直接交换是安全的 [2]。

### Q3: Method Swizzling 的缺陷有哪些？
**A**：
- 最小实现（直接 `method_exchangeImplementations`）没有 `dispatch_once` 保护，重复执行会换回；没有处理方法来自父类，可能污染父类；执行时机随调用点而定，不适合全局 hook [7]。
- 即使使用标准模板，仍存在命名冲突风险、多次 swizzle 同一方法的冲突风险 [3]。
- 应避免在非 `+load` 时执行，否则可能导致线程安全问题或交换失效 [5][11]。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/Runtime/Method - Swizzling.md › Method Swizzling › 方式二：安全交换（class_addMethod + method_exchangeImplementations）（第76-76行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 防崩溃保护机制 › Method Swizzling防护（第1086-1114行）
[3] /Users/tommywu/Obsidian/iOS/Runtime/Method - Swizzling.md › Method Swizzling › 三方框架对比（第327-362行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 3.1 交换方法 Method Swizzling（第408-447行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/load与initialize的区别.md › +load与+initialize的区别 › Method Swizzling应该在+load还是+initialize中执行 › 不推荐：在+initialize中执行（第327-357行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/runtime.md › Runtime › Method Swizzling（第467-469行）
[7] /Users/tommywu/Obsidian/iOS/Runtime/Part 4 - Runtime 应用篇.md › 3. Method Swizzling › 最小实现：`method_exchangeImplementations`（第187-230行）
[8] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第三周：Runtime 行为与 Cocoa 对象通信 › 本周精读路线 › Day 2｜有了方法查找，才学习 Swizzling（对应 W4-04）（第278-290行）
[9] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 3.1 交换方法 Method Swizzling › 3.1.4 为何要先添加 method（第520-547行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/OOP-POP-AOP.md › OOP、POP与AOP › AOP - 面向切面编程 › iOS中AOP的实现方式 › 1. Method Swizzling（第527-529行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/load与initialize的区别.md › +load与+initialize的区别 › 常见面试问题 › Q4: Method Swizzling应该在+load还是+initialize中执行？为什么？（第460-468行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 生命周期（第274-336行）
