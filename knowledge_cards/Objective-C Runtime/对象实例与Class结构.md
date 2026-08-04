---
topic: 对象实例与Class结构
group: Objective-C Runtime
generated_at: 2026-07-29T19:24:19
provider: deepseek
---

# 对象实例与Class结构

## 一句话总结

Objective-C 中每个对象（实例、类、元类）底层都是 `objc_object` 结构体，以 `isa` 指针作为第一个成员，这是“万物皆对象”的底层基础；实例对象存储具体数据（isa + 父类/本类实例变量 + 对齐填充），类对象存储类的描述信息（isa + superclass + cache + bits 指向 `class_rw_t`，内含方法、属性、协议列表），元类用于存储类方法；类对象的布局在继承自 NSObject 的 Swift 类中扩展为 ObjC 兼容部分 + Swift 额外部分（vtable、类型描述符等），两个运行时各取所需。 [1][2][3][7]

## 核心原理

### 1. 实例对象的内存布局

- 实例对象本质上是一个结构体，在堆内存中完整布局从上到下（低地址到高地址）依次为：
  1. **isa 指针**：8 字节，所有对象的起点。
  2. **父类实例变量**：按继承顺序、从父类到子类依次排列。
  3. **本类实例变量**：本类定义的实例变量。
  4. **内存对齐填充**：用于优化 CPU 访问的填充字节。 [1]
- 例如 `NSObject` 实例对象：仅包含 isa 指针（8 字节），但实际分配 16 字节（含对齐填充）。 [5]
- `typedef struct objc_object *id;`，id 即 `objc_object` 结构体指针，`objc_object` 内部仅包含 `isa_t isa`（新版 runtime）。 [7][10]
- 实例对象的 `isa` 指向其对应的类对象。 [2]

### 2. 类对象的内存布局

- `Class` 是指向 `objc_class` 结构体的指针：`typedef struct objc_class *Class;`。 [4][7]
- `objc_class` 继承自 `objc_object`，内存布局包含四大件（依次顺序）：
  - **isa**：指向元类（metaclass）。 [2][3][4]
  - **superclass**：父类指针。 [2][3][4]
  - **cache_t**：方法缓存，用于 `objc_msgSend` 快速查找（16 字节）。 [3][8]
  - **class_data_bits_t bits**：8 字节，指向 `class_rw_t` 或 `class_ro_t`。 [2][3][8]
  - `class_rw_t` 结构体包含：methods（方法列表）、properties（属性列表）、protocols（协议列表）等。 [3][8]
  - `class_ro_t` 是编译期确定的只读数据（如实例大小、实例变量偏移量）。 [11][12]
  - 重要时间点：类在编译产物中最初只有 `class_ro_t`，bits 里实际指向 `ro`；当类第一次被使用（消息发送、alloc 等）触发 `realizeClassWithoutSwift` 时，runtime 才分配 `class_rw_t` 并将 `ro` 塞入其中，回写 bits。因此 `class_rw_t` 是“类被实现”的产物，`class_ro_t` 是“类被编译”的产物。 [12]
- 类对象用于存储实例方法、属性描述、协议信息等，所有同类的实例共享一份，减少内存占用。 [6]

### 3. 元类（metaclass）

- 元类是**类对象的类**，类对象的 `isa` 指向元类。 [2][6]
- 元类自身也是 `objc_class` 类型，内存结构与类对象相同，但用途不同：元类的 method list 存储**类方法**。当向类对象发送消息（如 `[NSObject alloc]`）时，`objc_msgSend` 根据类对象的 isa 找到元类（及父元类）的方法列表进行查找。 [6]
- 所有元类的 isa 最终都指向 `NSObject` 基类的元类（即根元类），而根元类的 isa 指向自身。 [6]
- 内存中，同一个类只有唯一一份类对象和唯一一份元类对象，但可以有多个实例对象。 [2][6]

### 4. 继承自 NSObject 的 Swift 类对象的特殊布局

- 对于继承自 NSObject 的 Swift 类，类对象的内存布局在 ObjC 兼容部分之后扩展了 Swift 特有数据，形成一个**混合结构**： [3]
  - **Objective-C 部分**：完全兼容 `objc_class` 布局（isa、superclass、cache、bits），ObjC 运行时只访问该范围内的内存。因此 `objc_msgSend`、method swizzling、KVO 等机制正常工作。
  - **Swift 扩展部分**（紧接在 ObjC 布局之后）：
    - flags：Swift 运行时标志
    - instanceSize / instanceAlignMask：实例大小和对齐掩码
    - typeDescriptor：类型描述符（泛型参数信息、字段描述等）
    - vtable[]：虚函数表，存储 Swift 可重写方法槽位（含实例方法和可重写的 `class func`）
    - Protocol Conformance Records：协议一致性记录
  - 两个运行时各取所需：ObjC 部分走方法列表，Swift 部分走 vtable 快速派发。 [3]

### 5. isa 走位与继承链

- 实例对象的 isa → 类对象 → 元类 → … → 根元类（isa 指向自身）；类对象的 superclass 指向父类对象，元类的 superclass 指向父元类，形成闭环（需要 realize 后才能接环）。 [5]

## 关键细节与易错点

- **所有对象都是 `objc_object`**：实例、类、元类底层都是 `objc_object`（因为 `objc_class` 继承自 `objc_object`），所以它们第一个成员都是 `isa`。这正是“万物皆对象”的底层基础。但 isa 之后的内存布局不同：实例对象存放实例变量值，类对象存放 superclass 等描述信息。 [2][7]
- **类对象 vs 实例对象数量**：同类实例可以有多个，但类对象和元类对象在内存中分别只有一个。 [2]
- **isa 指向**：实例的 isa → 类对象，类对象的 isa → 元类（不是元类对象？注意：类对象的 isa 指向元类对象本身，元类对象也是 Class 类型）。易混：不要误以为类对象的 isa 指向根类（如 NSObject），实际上指向其对应的元类。 [2][6]
- **内存对齐**：实例对象在存储完所有实例变量后可能添加填充字节以满足 CPU 对齐要求，导致实际分配大小可能大于所有变量大小之和（如 NSObject 实例 8 字节需求但分配 16 字节）。 [1][5]
- **`class_rw_t` 与 `class_ro_t` 的区分**：编译产物中 bits 存放的是 `class_ro_t`（只读），但当类被 realize 后，bits 改为指向 `class_rw_t`（其中包含 `ro` 的指针）。在未 realize 时调用 `data()` 会断言失败，需使用 `safe_ro()` 安全获取只读数据。 [11][12]
- **Swift 类的方法派发**：对于 `dynamic` 或 ObjC 可见的成员，通过 ObjC 消息派发（走前半部分 method list）；普通 Swift 可重写成员则通过 Swift vtable 派发（走后半部分虚表）。 [3]

## 高频追问

### Q1：一个 NSObject 实例占多少内存？
- NSObject 实例只有一个 isa 指针（8 字节），但为了内存对齐，系统实际分配 16 字节（ISA 指针 8 字节 + 对齐填充 8 字节）。 [1][5][7]

### Q2：isa 的核心作用是什么？
- isa 指针用于标识对象的类型。对于实例，isa 指向类对象，runtime 通过 isa 找到类的方法列表来响应实例方法；对于类对象，isa 指向元类，用于查找类方法。 [2][6][10]

### Q3：类方法存储在什么地方？
- 类方法存储在元类（metaclass）的方法列表中。当调用类方法时，通过类对象的 isa 找到元类，再从元类的方法列表中查找实现。 [6]

### Q4：为什么要有元类？
- 因为类本身也是一个对象，需要能够接收消息（类方法）。元类作为类对象的“类”，其方法列表存储了所有类方法，使得 `objc_msgSend` 机制对类对象也适用，统一了消息发送机制。 [6]

### Q5：实例方法、类方法、协议、属性等描述信息存在哪里？
- 实例方法存在类对象的 method list（`class_rw_t` / `class_ro_t`）中；类方法存在元类的 method list 中；协议和属性也存在对应的 `class_rw_t` 中（或 `class_ro_t` 初始数据）。 [2][4][8]

### Q6：一个类对象有多大？（objc_class 结构体大小）
- 根据 [8] 的简化结构：isa（8）+ superclass（8）+ cache_t（16）+ bits（8）= 40 字节；但实际 `cache_t` 内部可能包含更多字段，现代 runtime 中 class 对象大小约为 40+ 字节。更精确的大小依赖于具体版本，但可以明确其内存布局包含这四个固定字段。 [3][8]

### Q7：继承自 NSObject 的 Swift 类的方法调用为什么既有 ObjC 消息发送又有 vtable？
- 因为类对象布局中前半部分是 ObjC 兼容的 `objc_class`，包含 `class_rw_t` 的 method list（用于 ObjC 或 `dynamic` 方法）；后半部分是 Swift 扩展，包含 vtable（用于 Swift 可重写方法的快速派发）。运行时根据方法声明选择合适的方式：`dynamic` 或 ObjC 暴露的方法走 `objc_msgSend`，普通 Swift 可重写方法走 vtable。 [3]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › 内存分布 › 实例对象的内存布局（第361-368行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Objective-C底层原理-NSObject.md › Objective-C底层原理 - NSObject › 内存分布 › 实例对象与类对象的内存对比（第498-511行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/Swift底层原理-结构体、类和协议.md › Swift底层原理-结构体、类和协议 › Swift类的底层实现 › 继承自NSObject的Swift类 › 类对象的内部结构（第59-82行）
[4] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶一.md › 2. 对象和类 › 2.2 类 Class（第99-117行）
[5] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/_系列大纲.md › 已写篇章 · 展开目录 › Part 1 · 对象与类的本质  ✅ `draft: false`（第38-45行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Runtime从入门到进阶一.md › 2. 对象和类 › 2.3 元类 meta class（第238-254行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/Part 1 - 对象与类的本质.md › 对象的本质：objc_object › objc_object：对象的骨架（第48-78行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/包瘦身/包瘦身-可执行文件优化.md › 包瘦身-可执行文件优化 › ObjC元数据优化 › 类的内存布局（第499-523行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/objective-c-runtime-运行时之一-类与对象.md › 类与对象基础数据结构 › objc_object与id（第82-98行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/Part 1 - 对象与类的本质.md › 类的本质：objc_class › 类的四大件：isa / superclass / cache / bits › bits ：class_rw_t → class_ro_t（第1056-1077行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime/Part 1 - 对象与类的本质.md › 类的本质：objc_class › 类的四大件：isa / superclass / cache / bits › bits ：class_rw_t → class_ro_t（第1114-1115行）
