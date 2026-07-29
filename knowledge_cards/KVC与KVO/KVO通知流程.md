---
topic: KVO通知流程
group: KVC与KVO
generated_at: 2026-07-29T19:44:39
provider: deepseek
---

# KVO通知流程

## 一句话总结
KVO（Key-Value Observing）通过动态子类（isa-swizzling）重写被观察属性的 setter，在赋值前后插入 `willChangeValueForKey:` 和 `didChangeValueForKey:`，`didChangeValueForKey:` 内部负责回调观察者的 `observeValueForKeyPath:ofObject:change:context:` 方法 [4][6]。KVO 监听的本质是“通知”而非“值” [8]。

## 核心原理

- **动态子类与 setter 织入**：运行时为被观察对象创建一个动态子类（如 `NSKVONotifying_Student`），重写被观察属性的 setter，在原始赋值前后分别调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` [6]。
- **`willChangeValueForKey:` 的作用**：在值改变前调用，KVO 在该时刻捕获当前值作为 change 字典中的 `NSKeyValueChangeOldKey`，并标记该 key“正处于变化中” [8][10]。
- **`didChangeValueForKey:` 的作用**：在值改变后调用，KVO 读取新值填入 `NSKeyValueChangeNewKey`，组装好 change 字典，然后调用观察者的 `observeValueForKeyPath:ofObject:change:context:` [4][8]。验证表明，只有 `didChangeValueForKey:` 中的 `[super didChangeValueForKey:key]` 才会触发回调，如果只调用 `willChangeValueForKey:` 而不调用 `willChangeValueForKey:`，或者只调用 `didChangeValueForKey:` 而没有对应的 `willChangeValueForKey:`，都不会触发通知 [4]。
- **自动通知的触发路径**：
  - 通过 setter 赋值：`stu.name = @"Tom"` 或 `[stu setName:@"Tom"]` → 动态子类 setter 插入 will/did [6]。
  - 通过 KVC 赋值：`[stu setValue:@"Tom" forKey:@"name"]` → KVC 内部在设置值前后自动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` [1][2][6]。
  - Foundation 内部通过 `_NSSetObjectValueAndNotify` 等辅助函数封装“willChange → 原始赋值 → didChange”的流程 [8]。

## 关键细节与易错点

- **直接修改实例变量不会触发 KVO**：例如 `person->_name = @"Tom"` 绕过了 setter，KVO 没有切入点。除非手动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` 包裹赋值 [1][6]。
- **集合类型属性的监听**：直接操作 `NSArray`、`NSSet` 等集合不会触发 KVO，必须通过 `mutableArrayValueForKey:` 等 NSObject 声明的代理方法操作，这些方法会自动包裹 `willChange:valuesAtIndexes:forKey:` 和 `didChange:valuesAtIndexes:forKey:` [1]。
- **手动触发 KVO**：在需要控制通知时机的场景（如合并多次变更为一次通知、只在值真正变化时通知、在非 setter 方法中修改属性），可以自己调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` [1][3][5]。示例：
  ```objc
  [self willChangeValueForKey:@"name"];
  _name = name;
  [self didChangeValueForKey:@"name"];
  ```
- **关闭自动通知**：重写类方法 `automaticallyNotifiesObserversForKey:`，对指定 key 返回 `NO`，然后手动调用 will/did 来控制通知 [1][9]。
- **嵌套手动通知**：如果单个操作导致多个键改变，必须嵌套调用 will/did，且每个手动通知只能观察到该键最新一次的改变，之前的改变会被覆盖 [7]。
- **移除观察者是强制要求**：每个 `addObserver:forKeyPath:options:context:` 必须对应一个 `removeObserver:forKeyPath:context:`，否则在对象释放、控制器 dealloc 时会导致崩溃。移除操作通常在 `viewWillDisappear:` 或 `dealloc` 中执行 [7]。

## 高频追问

**Q1：如何手动触发 KVO？**
手动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` 包裹赋值语句 [1][3][5]。注意必须先调用 `willChangeValueForKey:`，然后修改值，最后调用 `didChangeValueForKey:`，顺序不能颠倒 [8]。

**Q2：如何关闭某个属性的自动 KVO？**
重写 `+ (BOOL)automaticallyNotifiesObserversForKey:(NSString *)key`，对目标 key 返回 `NO`，其他 key 通过 `[super automaticallyNotifiesObserversForKey:key]` 交由父类处理 [1][9]。

**Q3：KVC 与 KVO 有什么关系？**
KVC 是 KVO 的基础。通过 KVC 的 `setValue:forKey:` 修改属性值时，即使该类没有定义 setter、直接修改实例变量，KVC 也会在内部自动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:`，从而触发 KVO 通知 [2][6]。因此 KVC 赋值的路径总会被 KVO 自动覆盖 [8]。

**Q4：直接修改实例变量会触发 KVO 吗？**
不会。因为直接修改实例变量绕过了 setter，KVO 的自动通知无法插入 will/did。如果需要触发通知，必须手动调用 `willChangeValueForKey:` 和 `didChangeValueForKey:` 进行包裹 [1][6]。

**Q5：`didChangeValueForKey:` 内部具体做了什么？**
`didChangeValueForKey:` 内部会调用观察者的 `observeValueForKeyPath:ofObject:change:context:` 方法 [4]。如果没有对应的 `willChangeValueForKey:` 调用，即使单独调用 `didChangeValueForKey:` 也不会触发回调 [4]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 常见面试题 › KVO 的底层原理是什么？（第348-350行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVC底层原理.md › KVC底层原理 › KVC 与 KVO 的关系（第402-416行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC、KVO的本质.md › 1. KVO的本质 › 1.5 KVO 面试题 › 1.5.2 如何手动触发KVO？（第242-244行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC、KVO的本质.md › 1. KVO的本质 › 1.4 验证didChangeValueForKey:内部会调用observeValueForKeyPath:ofObject:change:context:方法（第187-228行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 手动触发 KVO › 手动触发（第168-183行）
[6] /Users/tommywu/Obsidian/iOS/Runtime/Part 4 - Runtime 应用篇.md › 7. Isa Swizzling 与 KVO › 7.2 重写 setter：插入 will / did 通知（第1192-1259行）
[7] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC和KVO学习笔记.md › 3. 键值观察 › 3.4 手动发送通知（第664-696行）
[8] /Users/tommywu/Obsidian/iOS/Runtime/Part 4 - Runtime 应用篇.md › 7. Isa Swizzling 与 KVO › 7.2 重写 setter：插入 will / did 通知（第1261-1281行）
[9] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/KVC和KVO学习笔记.md › 3. 键值观察 › 3.4 手动发送通知（第606-662行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/kvc-和-kvo.md › 进阶 KVO › 值（第320-331行）
