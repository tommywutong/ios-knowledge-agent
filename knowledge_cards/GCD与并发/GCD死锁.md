---
topic: GCD死锁
group: GCD与并发
generated_at: 2026-07-29T19:38:49
provider: deepseek
---

# GCD死锁

## 一句话总结

GCD死锁的本质是“向当前所在的串行队列同步派发”：当前线程在串行队列上执行时，调用`dispatch_sync`向同一个串行队列追加任务，导致当前线程阻塞等待新任务执行、而新任务又要等当前任务完成才能被调度，形成循环等待 [2][6]。

## 核心原理

### 1. 死锁的四个必要条件（Coffman条件）

死锁的发生需要同时满足：**互斥**（资源同一时间只能被一个线程持有）、**持有并等待**、**不可抢占**、**循环等待**。破坏其中任意一个条件即可避免死锁 [6]。

### 2. GCD死锁的触发机制

`sync`的语义是“把 block 排到目标队列尾部，阻塞当前线程直到 block 执行完”。**串行队列**同一时刻只能执行一个 block，当当前队列正在等待当前任务（包含 `sync` 调用的任务）完成时，队列无法调度被 `sync` 追加的新任务，形成循环等待 [3][6]。

**为什么不死锁的情况：**
- **并发队列** `sync`：并发队列可以同时执行多个任务，不会排队等待 [3][6]
- **子线程**对主队列 `sync`：当前线程不在主队列的执行线程上，主队列可以调度新任务 [1][3][6]
- 不同串行队列之间 `sync`：只要不构成 A→B→A 的环 [3]

### 3. `dispatch_async` 为什么不会死锁

`dispatch_async` 不阻塞当前线程，调用后立即返回，因此不会形成循环等待的条件 [1][4]。

## 关键细节与易错点

### 1. 五种经典死锁场景（ming1016 归纳）

| 场景 | 结果 |
|------|------|
| 主线程直接 `dispatch_sync(dispatch_get_main_queue())` | 死锁 [2][9] |
| 主线程 `dispatch_sync(global_queue)` | 不死锁 [2][9] |
| `dispatch_async(serialQueue){ dispatch_sync(同一个 serialQueue){} }` | 死锁 [2][3][9] |
| `dispatch_async(global){ dispatch_sync(main){} }` | 不死锁 [2][9] |
| 子线程 `dispatch_sync(main)` + 主线程 `while(1)` 死循环 | 卡死（主队列永远得不到调度）[2][9] |

### 2. 死锁的准确边界（实验验证，不同结果类型）

通过带有 `alarm(3)` 超时机制的实验，可以将 GCD 死锁失败区分为两种表现 [8]：

- **SIGTRAP（当场崩溃）**：libdispatch 主动检测到并 trap
- **挂住三秒**：真正死锁，App 转圈

实验测试结果表（部分）[8]：

| 场景 | 结果 |
|------|------|
| 主线程上 `dispatch_sync(主队列)` | SIGTRAP，当场崩 |
| 串行队列内 `dispatch_sync(同一队列)` | SIGTRAP |
| 串行队列 A 内 `dispatch_sync(无关的串行队列 B)` | 正常返回 |
| A target 到串行队列 B，A 内 `dispatch_sync(B)` | SIGTRAP |
| A、C 都 target 到串行队列 B，A 内 `dispatch_sync(C)` | SIGTRAP |
| A、C 都 target 到并发队列 B，A 内 `dispatch_sync(C)` | 正常返回 |
| 并发队列内 `dispatch_sync(同一并发队列)` | 正常返回，且同线程 |
| 并发队列内 `dispatch_barrier_sync(同一并发队列)` | 三秒挂住 |
| A 内 sync B，同时 B 内 sync A | 三秒挂住 |
| 子线程 `dispatch_sync(主队列)`，主线程跑 `while(1)` | 三秒挂住 |

**关键点**：死锁不仅发生在直接“同一队列 sync 同一队列”，还发生在通过 `dispatch_set_target_queue` 形成**间接层级关系**的队列之间 [8]。

### 3. 主队列 vs 主线程

- `dispatch_get_main_queue()` 上的任务**一定在主线程**执行 [5]
- 主线程上跑的**不一定是**主队列的任务 [5]
- 因此在子线程调用 `dispatch_sync(主队列)` 不会死锁，因为当前阻塞线程（子线程）与目标队列执行线程（主线程）不同 [1][7]

### 4. 隐式自我 sync（实战中最隐蔽的死锁）

二级封装场景：方法 A 在队列的 `sync` 内部，方法 A 又同步调用了同一个队列的另一个方法 [3]。

```swift
class Cache {
    private let queue = DispatchQueue(label: "cache")

    func get(_ key: String) -> Any? {
        queue.sync { _storage[key] }
    }

    func getOrCompute(_ key: String, _ compute: () -> Any) -> Any {
        queue.sync {
            if let v = _storage[key] { return v }
            let v = compute()
            _storage[key] = v
            return v
        }
    }
}

// 调用方：在 queue.sync 内部又调用了 queue.sync → 死锁
let result = cache.getOrCompute("k") {
    cache.get("otherKey") ?? "default"
}
```

### 5. 避免死锁的工程实践（FMDB 方案）

FMDB 通过 `dispatch_queue_set_specific` 和 `dispatch_get_specific` 在运行时检查是否在同一队列重入，避免死锁 [11]：

- 在创建串行队列时，用 `dispatch_queue_set_specific` 绑定一个唯一标识
- 在进入同步方法时，用 `dispatch_get_specific` 检查当前是否已在该队列上
- 如果是同一队列重入，直接 `assert` 退出，避免死锁

## 高频追问

### 追问1：`DispatchQueue.main.sync` 为什么会死锁？什么时候不会？

**答**：`sync` 把 block 排到队列尾部，阻塞当前线程等它完成。主队列是串行的，如果**调用方当前就在主线程**，主线程就会卡在 `sync`，而主队列需要等当前任务完成才能调度这个 block，形成循环等待 [7]。

**不死锁的情况**：在**子线程**调用 `main.sync`（当前线程不是主队列的执行线程，可以阻塞等待）[7]。

### 追问2：什么时候 gcd 死锁会直接崩溃，什么时候会挂住？

**答**：从实验数据来看 [8]：
- 直接对**当前串行队列**做 `dispatch_sync` 时，libdispatch 会在**编译期或运行期检测到并主动 SIGTRAP**，表现为当场崩溃
- 涉及**跨队列循环等待**（如 A sync B 同时 B sync A）、**队列 targeting 链**、或者**子线程 sync 主队列但主线程卡在 while(1)** 等场景时，由于死锁链条跨越多条线程和多个队列，libdispatch 无法提前检测，表现为**真正挂住**（实验设置 3 秒超时）

### 追问3：FMDB 如何防止死锁？

**答**：FMDB 通过 `dispatch_queue_set_specific` 和 `dispatch_get_specific` 在运行时检查当前队列的“身份” [11]：

1. 创建串行数据库队列时，用 `dispatch_queue_set_specific` 将自身指针绑定到队列上
2. 在 `inDatabase:` 方法的入口，通过 `dispatch_get_specific` 获取当前执行队列的标识
3. 如果获取到的标识等于 `self`，说明当前方法被**递归/重入**调用，会触发 `assert` 警告，防止死锁

### 追问4：如何定位和复现 GCD 死锁？

**答**：基于材料，有以下实践建议 [5][8]：
- **边界实验**：用 `alarm(3)` 设置超时，区分 SIGTRAP 和真正挂住两种失败模式
- **五种边界**：主队列 sync 主队列 / 串行队列 sync 同一队列 / 串行队列 sync 另一串行队列 / 并发队列 sync 自己 / barrie 在并发队列中的行为 —— 分别验证
- **队列 targeting 链**：关注通过 `dispatch_set_target_queue` 建立层级关系的队列间的 sync 调用
- **二级封装**：检查“线程安全的缓存”或“数据库访问层”等封装类，看是否存在 queue.sync 内部调用同一 queue 的其他方法

### 追问5：破坏死锁四个条件中的哪一个可以避免 GCD 死锁？

**答**：从 GCD 死锁的典型场景来看，主要是通过**打破“循环等待”条件**来避免 [6]：
- 使用并发队列代替串行队列 → 并发队列可以同时处理多个任务，不形成排队等待链
- 在子线程对主队列 sync → 当前线程（子线程）不在主队列的执行线程上，破坏等待环路
- 用 `dispatch_async` 代替 `dispatch_sync` → 不阻塞当前线程，破坏等待关系
- 所有线程以相同的顺序获取锁 → 破坏循环等待条件（适用于 NSLock 类的死锁）[6]

> 注意：以上基于材料[6]和材料[1-4]的交叉印证。对于通过`破坏互斥`或`破坏不可抢占`条件来避免 GCD 死锁的情况，本卡片材料不足。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-15 11:02 GCD同步执行主队列死锁分析（第126-133行）
[2] /Users/tommywu/Obsidian/iOS/10 学习计划/claude工程文件/_研究简报-GCD.md › GCD 研究简报 › 三、死锁的五种情况（ming1016 归纳，可作为实验设计参考）（第124-134行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/死锁/死锁.md › 死锁（Deadlock）原理、常见场景与治理 › 三、iOS 中常见的死锁场景 › 场景 1：GCD 串行队列对自身执行 sync（第85-136行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-15 11:06 GCD 死锁原理解析 › 整理后内容（第205-215行）
[5] /Users/tommywu/Obsidian/iOS/10 学习计划/claude工程文件/_研究简报-GCD.md › GCD 研究简报 › 六、建议主实验清单（第160-169行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › 常见面试题 › 1. 死锁的发生条件及常见场景（第914-976行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/死锁/死锁.md › 死锁（Deadlock）原理、常见场景与治理 › 七、常见面试题 › Q2：`DispatchQueue.main.sync` 为什么会死锁？什么时候不会？（第776-780行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS GCD：队列不是线程，以及死锁的准确边界.md › GCD：队列不是线程，以及死锁的准确边界 › 三、死锁的准确边界（第207-226行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › GCD死锁（第941-1002行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › GCD实际使用 › FMDB如何使用dispatch_queue_set_specific和dispatch_get_specific来防止死锁（第1006-1022行）
