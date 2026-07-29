---
topic: Dispatch Semaphore
group: GCD与并发
generated_at: 2026-07-29T19:39:39
provider: deepseek
---

# Dispatch Semaphore
## 一句话总结
Dispatch Semaphore 是 GCD 中的同步原语，通过 `dispatch_semaphore_create`、`dispatch_semaphore_wait`、`dispatch_semaphore_signal` 三个方法控制并发访问和线程同步，常配合队列实现资源限制或互斥 [1]；也可用于等一个异步结果、实现 `dispatch_group` 的手工版本 [4]。

## 核心原理
- 信号量维护一个计数器，`dispatch_semaphore_wait` 将计数器减 1，若结果为负数则阻塞当前线程直到计数器变为非负；`dispatch_semaphore_signal` 将计数器加 1，并唤醒等待的线程 [8][9]。
- 典型用法：
  - 初始值为 1 时模拟互斥锁：`dispatch_semaphore_wait(sem, DISPATCH_TIME_FOREVER);` // 临界区代码 `dispatch_semaphore_signal(sem);` [2]
  - 初始值为 0 时异步转同步：先执行异步任务，任务内 `signal()`，调用方 `wait()` 等待信号 [6][8]。
  - 通过调整初始值控制最大并发数 [9]。

## 关键细节与易错点
1. **成对使用**：`wait` 和 `signal` 必须成对出现，否则会导致计数器失衡；信号量析构时如果当前值小于初始值，会直接崩溃并输出错误信息 `"BUG IN CLIENT OF LIBDISPATCH: Semaphore object deallocated while in use (current value < original value)"` [4]。
2. **不是锁**：`dispatch_semaphore_create(1)` 后 wait/signal 的写法很常见，但信号量没有所有权概念，A 线程 wait、B 线程 signal 完全合法，代价是内核不知道优先级该捐给谁；WWDC21 Session 10254 指出信号量在 Swift Concurrency 下不安全，因为它向 Swift 运行时的依赖信息是隐藏的 [4]。
3. **不支持递归**：第二次 `wait` 会直接挂住，且没有诊断信息 [4]。
4. **争用性能差**：在锁的性能对比中，`dispatch_semaphore` 一秒窗口内高优先级线程抢到的次数（约 5~9 万）比 `os_unfair_lock`（约 764~837 万）和 `pthread_mutex`（约 994~1194 万）差两个数量级，平均等待时间从 0.001 ms 级跳到 0.17~0.31 ms，因为每次争用都要走内核 [4]。
5. **死锁风险**：
   - 用信号量将异步接口“包成同步”时，如果回调队列与调用方队列是同一条串行链路，`sem.wait()` 会永远拿不到 `signal()`，导致死锁 [10]。
   - 在 `+load` 方法中同步等待一个后台任务时，若后台任务需要获取 `loadMethodLock`（`+load` 执行期间一直持有），且等待超时或永久等待，就会死锁 [11]。
   - 常见形状：把 `await` 翻译成 `sem.wait()`、将 Core Bluetooth 的 delegate 回调同步化等 [10]。

## 高频追问
- **Q: 信号量和互斥锁的根本区别是什么？**
  A: 信号量没有所有权，不记录谁的 wait，任何线程都可以 signal；互斥锁有所有权（持有锁的线程才能解锁）。信号量更适合限流和等待，而不是保护共享状态 [4]。

- **Q: 信号量死锁如何避免？**
  A: 避免在同一个串行队列的线程上同时 wait 和 signal（如主线程调用 wait 等待一个回调也在主队列的异步任务）[10]；避免在持有递归锁（如 `loadMethodLock`）时同步等待需要同一锁的后台任务 [11]。

- **Q: 信号量性能为什么比 os_unfair_lock 差？**
  A: 因为信号量每次争用都要走一次内核切换，而 `os_unfair_lock` 和 `pthread_mutex` 在争用不激烈时能在用户态解决大部分情况 [4]。

- **Q: 信号量能用于递归锁吗？**
  A: 不能。第二次 `wait` 会直接挂住，且没有错误提示 [4]。

- **Q: 信号量真正该用的场景是什么？**
  A: 限流、等待异步结果、`dispatch_group` 的手工版本 [4]。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-15 12:11 Dispatch Semaphore 的三个方法（第357-363行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › 线程安全 › 线程同步方案 › dispatch_semaphore（第423-432行）
[4] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS 锁：从 OSSpinLock 的废弃说起.md › 锁：从 OSSpinLock 的废弃说起 › 七、把 dispatch_semaphore 当锁用的三个问题（第491-521行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › Dispatch Semaphore和的介绍（第897-915行）
[8] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/GCD.md › GCD › 2026-05-26 12:14:40 GCD调度组与信号量基础用法 ^fcdb0f（第443-456行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/多线程.md › iOS多线程编程 › GCD（Grand Central Dispatch） › 常用GCD函数（第159-175行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/死锁/死锁.md › 死锁（Deadlock）原理、常见场景与治理 › 三、iOS 中常见的死锁场景 › 场景 4：dispatch_semaphore 等待死锁（第185-206行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS Method Swizzling：正确姿势、+load 时机与那些坑.md › Method Swizzling：正确姿势、+load 时机与那些坑 › 四、`+load` 里能碰什么 › 一个能稳定复现的死锁（第559-599行）
