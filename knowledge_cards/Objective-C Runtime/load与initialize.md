---
topic: load与initialize
group: Objective-C Runtime
generated_at: 2026-07-29T19:28:57
provider: deepseek
---

# load与initialize

## 一句话总结

`+load`和`+initialize`是Objective-C中两个特殊的类方法，均由Runtime自动调用。`+load`在main()之前、镜像加载时由dyld触发，通过函数指针直接调用，只要实现就必定执行；`+initialize`在类第一次收到消息时由objc_msgSend触发，通过消息发送机制调用，只有类被使用时才会执行。[1][2]

## 核心原理

### 调用时机与触发机制

- **+load**：在dyld加载镜像（image）后，通过`notifyObjCInit`回调Runtime的`load_images`函数，由`call_load_methods`串行执行所有待处理的类与分类的`+load`方法。发生在main()之前。[1][7]
- **+initialize**：在类第一次接收消息时，由`objc_msgSend`内部调用`_class_initialize`（最终由`initializeNonMetaClass`实现），通过`objc_msgSend(cls, SEL_initialize)`发送消息触发。[1][9]

### 调用方式

- **+load**：通过函数指针直接调用，不经过`objc_msgSend`。源码可见`call_class_loads`中从`loadable_classes`数组取出函数指针直接调用。[7][1] 因此，分类的`+load`不会覆盖主类的`+load`，两者都会被执行。[7]
- **+initialize**：通过消息发送机制（`objc_msgSend`）调用，遵循消息转发链。这意味着如果子类未实现`+initialize`，会沿继承链调用父类的实现；如果分类实现了`+initialize`，则会覆盖类本身的实现。[9]

### 调用顺序

**+load调用顺序**：
1. 父类优先于子类。[1][3][7]
2. 类优先于分类。[1][3][7]
3. 同一镜像内按编译顺序（Compile Sources中的文件顺序）。[3][7]
4. 不同镜像按依赖顺序：被依赖的动态库先于依赖方。[7]
5. 分类之间也按编译顺序。[1][3]

**+initialize调用顺序**：
1. 先初始化父类，再初始化子类。[1][3][9]
2. 如果子类未实现`+initialize`，会调用父类的`+initialize`（导致父类的`+initialize`可能被调用多次）。[1][9]
3. 如果分类实现了`+initialize`，则覆盖类的实现。[9]

### 调用次数与线程

| 特性 | +load | +initialize |
|------|-------|-------------|
| 调用次数 | 每个类/分类全局只调用一次[1] | 每个类只调用一次，但子类未实现时父类会被多次调用[1] |
| 是否必定调用 | 是（只要有实现）[1] | 否（类可能从未被使用）[1][4] |
| 线程 | 主线程串行执行[1][7] | 任意线程，Runtime内部加锁保证线程安全[1] |
| 继承 | 不继承，子类不实现则不调用父类的[1] | 继承，子类不实现则调用父类的[1][9] |
| autorelease pool | 由libobjc自动管理[1] | 由触发消息的调用栈管理 |

## 关键细节与易错点

1. **+load是阻塞启动的**：所有`+load`在main函数之前同步串行执行，会影响App冷启动时间。不要在`+load`中做耗时操作。[1][7]

2. **+initialize的安全写法**：由于子类未实现时父类会被多次调用，应在`+initialize`中加类判断防止重复初始化：
   ```objc
   + (void)initialize {
       if (self == [MyClass class]) {
           // 只执行一次
       }
   }
   ```
   [1]

3. **Method Swizzling应放在+load中**：因为`+load`保证在类初始化期间一定会被调用（只要有实现），而`+initialize`的调用时间不确定，甚至可能永远不会被调用。在`+load`中做Swizzling可以避免race condition。[4]

4. **+load时Runtime已就绪但UIApplicationMain未执行**：此时ObjC Runtime已完全初始化（`_objc_init`已执行），可以进行method swizzling、注册工厂类等操作，但UI相关操作不安全。[1]

5. **+initialize的OC2.0消息发送特性**：因为走`objc_msgSend`，分类的`+initialize`会覆盖主类；而`+load`不走消息发送，所以分类的`+load`不会覆盖主类，两者都会调用。[9]

## 高频追问

### Q1: 父类的+initialize会被调用几次？
**答**：可能被调用多次。如果父类和多个子类都没有实现`+initialize`，那么每个子类第一次收到消息时，都会沿继承链调用父类的`+initialize`。只有某个类自己实现了`+initialize`，它才会阻止父类被再次调用（因为该类会调用自己的实现）。[1][9]

### Q2: 为什么+load中可以做method swizzling，而+initialize不行？
**答**：因为`+load`在类加载时必定被调用（只要有实现），且调用顺序明确（父类→子类→分类），保证Swizzling在类被使用前完成；而`+initialize`的调用时机不确定，如果消息发送前突然被触发，可能导致Swizzling未生效的竞争条件。[4]

### Q3: +load和+initialize哪个更适合进行全局配置？
**答**：`+initialize`更适合。因为`+initialize`采用懒加载，只在类第一次被使用时触发，不影响启动时间；而`+load`会阻塞启动。但`+initialize`的缺点是调用时机不确定，可能被分类覆盖。如果需要非常早期的初始化（如Method Swizzling），应选择`+load`。[1][5]

### Q4: 如果分类和主类都实现了+load，调用顺序是怎样的？主类的+load还会被调用吗？
**答**：主类的`+load`先于分类的`+load`被调用（类优先于分类）。分类的`+load`不会覆盖主类的`+load`，两者都会执行。这是因为`+load`通过函数指针直接调用，不走消息发送。[1][3][7]

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/编译链接与启动/dyld.md › dyld源码 › +load 与 +initialize 的区别（第582-623行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/load与initialize的区别.md › +load与+initialize的区别（第1-5行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 4. 面试题 › 4.5 load、initialize调用顺序？（第1126-1136行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶二.md › 3. 具体应用 › 3.1 交换方法 Method Swizzling › 3.1.1 load vs initialize（第449-455行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/分类category、load、initialize的本质和源码分析.md › 总结（第1138-1152行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/App启动流程.md › 一、冷启动（Cold Launch） › Pre-main 阶段 › 6. 调用 +load 方法（第533-594行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/cnblogs.com/ios-load和-initialize方法调用时机.md › 3、+initialize方法调用的时机（第364-387行）
