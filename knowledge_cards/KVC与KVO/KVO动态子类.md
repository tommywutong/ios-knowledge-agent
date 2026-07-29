---
topic: KVO动态子类
group: KVC与KVO
generated_at: 2026-07-29T19:44:18
provider: deepseek
---

# KVO动态子类

## 一句话总结
KVO（Key-Value Observing）基于**isa-swizzling**机制实现，当对象被添加观察者后，系统动态创建一个继承自原类的`NSKVONotifying_ClassName`子类，将对象的**isa**指针指向该子类，并在子类中重写被观察属性的setter方法插入通知逻辑。[1][2][3][5]

## 核心原理

### 1. 动态创建子类
- 当对一个对象调用`addObserver:forKeyPath:options:context:`时，Runtime首先检查是否已存在`NSKVONotifying_ClassName`子类[2]
- 子类不存在时，通过`objc_allocateClassPair`动态创建，并通过`objc_registerClassPair`注册[2]
- 创建完成后，将被观察对象的**isa指针**从原类指向该动态子类[2][5][9]
  添加观察前：`instance.isa → ClassName`
  添加观察后：`instance.isa → NSKVONotifying_ClassName → ClassName（superclass）`[2]

### 2. 重写setter方法
- 动态子类重写被观察属性的setter方法，将setter的IMP替换为Foundation内部的`_NSSetXXXValueAndNotify`系列函数[2][4]
- Foundation根据属性类型选择对应的函数，例如对象类型用`_NSSetObjectValueAndNotify`，int用`_NSSetIntValueAndNotify`等[2][4]
- 重写后的setter执行逻辑如下[2][9]：
  ```objc
  - (void)setName:(NSString *)name {
      [self willChangeValueForKey:@"name"];
      [super setName:name];  // 调用原始 setter
      [self didChangeValueForKey:@"name"];
  }
  ```

### 3. 重写辅助方法
- **重写`class`方法**：返回原始父类而非`NSKVONotifying_`前缀的子类，对外隐藏KVO实现细节[2][4]
  因此`[person class]`返回`Person`，但`object_getClass(person)`能获取到真实的`NSKVONotifying_Person`[2][4]
- **重写`dealloc`**：在对象销毁时执行KVO相关的清理工作[2]
- **重写`_isKVOA`**：返回YES，供Runtime内部判断这是KVO动态生成的类[2][4]

### 4. 观察者的存储与通知
- 观察者信息存储在被观察对象的`observationInfo`属性中（声明在`NSObject`上）[2]
- `observationInfo`指向Foundation内部的`NSKeyValueObservationInfo`对象，维护一组`NSKeyValueObservance`记录，每条包含observer、keyPath、options、context[2]
- 每次`addObserver:`时添加记录，`removeObserver:`时移除记录[2]
- 当`didChangeValueForKey:`被调用时，从`observationInfo`中找到该keyPath的所有观察记录，逐一调用`observeValueForKeyPath:ofObject:change:context:`完成通知[2]

## 关键细节与易错点

### 动态子类命名冲突
- 若开发者手动创建一个名为`NSKVONotifying_ClassName`的类，当系统运行到注册KVO的那段代码时程序会崩溃，因为系统动态创建同名子类时会产生冲突[9][10]

### `class`与`object_getClass`的区别
- `class`是方法，可以被KVO子类覆写返回原始类[2][4]
- `object_getClass`是Runtime API，直接沿对象的isa取真实类，不受覆写影响[4]
- 工程中不要用“直接读isa”判断类型关系，应该用`class`、`isKindOfClass:`、协议或明确的业务字段[4]

### 直接修改实例变量的影响
- **直接通过实例变量赋值不会触发KVO**，因为动态子类只重写了setter方法并插入通知，绕过setter直接修改实例变量不会触发`willChangeValueForKey:`和`didChangeValueForKey:`[2][11]
- **通过KVC的`setValue:forKey:`会触发KVO**，即使类没有定义setter方法，KVC在直接设置实例变量时也会自动调用`willChangeValueForKey:`和`didChangeValueForKey:`[11]

## 高频追问

### Q1: 为什么`person.class`返回的还是`Person`，而不是`NSKVONotifying_Person`？
因为动态子类重写了`class`方法，使其返回原始父类，对外隐藏了KVO实现细节。[2][4] 若想获取真实类应使用`object_getClass()`。[4]

### Q2: KVO如何处理非对象类型的属性（如int、结构体）？
Foundation内部有对应的`_NSSetXXXValueAndNotify`函数，例如int类型用`_NSSetIntValueAndNotify`，浮点类型、常见结构体也有对应处理路径。[2][4]

### Q3: 手动触发KVO如何实现？
（本卡片材料不足）材料未提供手动触发KVO的具体实现方式，仅提及存在手动控制KVO触发的可能性。[12]

### Q4: 在Swift中如何使用KVO？
Swift中继承`NSObject`且属性标记为`@objc dynamic`的走同样的ObjC Runtime流程。而Swift原生的KeyPath（如`\Person.name`）是完全不同的机制，不经过KVO动态子类流程。[8]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/design-patterns/观察者模式.md › 观察者模式 › 面试常见问题 › Q1: KVO的实现原理是什么？（第693-695行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 常见面试题 › KVO 的底层原理是什么？（第311-346行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › KVO 的底层实现原理：isa-swizzling（第30-32行）
[4] /Users/tommywu/Obsidian/iOS/Runtime/Part 4 - Runtime 应用篇.md › 7. Isa Swizzling 与 KVO › 7.4 重写 `_isKVOA`：标记 KVO 动态子类（第1300-1313行）
[5] /Users/tommywu/Obsidian/iOS/Runtime/Part 4 - Runtime 应用篇.md › 7. Isa Swizzling 与 KVO（第1097-1124行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 底层原理（第674-711行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/jianshu.com/ios开发-kvo的实现原理与具体应用.md › 二、**实现原理？** › **深入剖析**：（第55-74行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/huberyyang.com/kvo实现原理.md › (全文)（第39-54行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 直接修改实例变量能否触发 KVO？（第185-203行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › 手动触发 KVO（第153-155行）
