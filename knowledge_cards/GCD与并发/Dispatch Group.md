---
topic: Dispatch Group
group: GCD与并发
generated_at: 2026-07-29T19:39:25
provider: deepseek
---

# Dispatch Group

## 一句话总结

Dispatch Group 是 GCD 提供的一种机制，通过 `dispatch_group_enter` / `dispatch_group_leave` 的配对来跟踪一组异步任务的完成状态，并在所有任务完成后通过 `dispatch_group_notify` 异步执行回调或通过 `dispatch_group_wait` 同步等待。[1][8]

## 核心原理

- **基本操作**：`dispatch_group_enter` 表示一个任务开始，`dispatch_group_leave` 表示任务完成。当每个 `enter` 都有对应的 `leave` 后，Group 的计数归零，即所有任务完成。[1][8]
- **通知机制**：`dispatch_group_notify` 可以在所有任务完成后异步执行一个 block，不阻塞当前线程。[5][9]
  实现时存在一个 race condition：如果 `notify` 在检查 count 后发现非零，但随后所有 pending 的 `leave` 将计数减为零，而动作尚未设置，则动作永远不会运行。
  **解决方案**：将动作的赋值包裹在一对 `enter`/`leave` 中。这样在设置动作时至少有一个未平衡的 `enter`，从而消除立即执行的 case，并保证动作设置发生于任何 pending `leave` 之前。[2][7]
- **同步等待**：`dispatch_group_wait` 会阻塞当前线程，直到所有任务完成（或超时）。内部实现可以通过 `notify` 配合一个通知机制（比如信号量或条件变量）来避免忙等。[2] 若使用轮询（如 `while(!done);`）会导致 CPU 空转 100%，因此不推荐。[2]
- **线程安全**：所有 Dispatch Group 的操作都是线程安全的。[1][8]

## 关键细节与易错点

1. **`dispatch_group_async` 的局限性**
   `dispatch_group_async` 将 block 提交到队列，Group 跟踪的是 block 本身的执行完成，而不是 block 内部发起的异步操作（如网络请求、`dispatch_after`）。若 block 内调用的是异步 API 并立即返回，`notify` 会在子任务的实际回调前触发。[3]
   示例：
   ```objc
   dispatch_group_async(grp, g, ^{
       fakeRequest(i, ^(int k) { /* 回调 */ }); // block 立即返回
   });
   dispatch_group_notify(grp, mainQueue, ^{
       // 会在回调之前触发
   });
   ``` [3]

2. **enter/leave 必须严格配对**
   - `leave` 多于 `enter` → 会触发 `Trace/BPT trap`（崩溃）。[3]
   - `leave` 少于 `enter` → `notify` 永远不执行，造成 UI 旋转或等待永久阻塞。[3]
   - 在回调有多个出口（成功、失败、提前 return）时，每个出口都必须调用 `dispatch_group_leave`。[3][4]

3. **推荐实践**
   - 对于需要等待异步回调完成的任务（网络请求、文件 I/O 等），应始终使用 `dispatch_group_enter` 在任务开始前、`dispatch_group_leave` 在回调内，而不是用 `dispatch_group_async`。[3][10]
   - 封装已有异步 API 时，可在 wrapper 内部加入 enter/leave 配对，并确保 enter 在 leave 之前发生，且错误分支也调用 leave。[10]

4. **dispatch_group_wait 阻塞线程**
   `dispatch_group_wait` 会同步阻塞当前线程，不适合在主线程调用；而 `dispatch_group_notify` 是非阻塞的，更适合在主线程等待多个任务完成。[5][9]

## 高频追问

**Q1: `dispatch_group_async` 和 `enter`/`leave` 有什么区别？什么时候该用哪个？**
A: `dispatch_group_async` 只跟踪 block 本身的返回值，对于 block 内部发起的异步操作无效。[3] 实际项目中九成场景是网络请求汇合，应一律使用 `enter`/`leave` 手动配对，将 `leave` 放在回调里。[3]

**Q2: `dispatch_group_notify` 的实现为什么需要包裹 enter/leave？**
A: 防止 race condition：当 `notify` 检查 count 为非零，然后所有 pending leave 将计数减为零，但动作尚未设置时，会导致回调永不执行。将动作赋值包裹在 enter/leave 中，保证至少有一个未平衡的 enter，从而避免该问题。[2][7]

**Q3: 如果 enter 和 leave 数量不匹配会发生什么？**
A: leave 多于 enter → 崩溃（`Trace/BPT trap`）。leave 少于 enter → `notify` 永远不触发，可能造成永久阻塞。[3]

**Q4: `dispatch_group_wait` 和 `dispatch_group_notify` 在使用上有什么本质区别？**
A: `wait` 是同步阻塞的（阻塞当前线程直到完成或超时），`notify` 是异步非阻塞的（所有任务完成后在指定队列执行回调）。[5][9] `notify` 避免阻塞线程，更推荐用于主线程等待多个任务完成。[5]

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2013-08-16-let-s-build-dispatch-groups.md › (全文)（第29-72行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2013-08-16-let-s-build-dispatch-groups.md › (全文)（第186-215行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/并发与运行循环/iOS GCD：队列不是线程，以及死锁的准确边界.md › GCD：队列不是线程，以及死锁的准确边界 › 六、group 的两种用法，以及那个反例（第572-621行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › 使用dispatch block object（调度块）在任务执行前进行取消（第744-754行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Grand Central Dispatch的使用.md › 9. 使用dispatch group修复弹窗过早问题 › 9.2 `dispatch_group_notify`的使用（第618-622行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/mikeash/friday-q-a-2013-08-16-let-s-build-dispatch-groups.md › (全文)（第144-200行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/mikeash/friday-q-a-2013-08-16-let-s-build-dispatch-groups.md › (全文)（第36-85行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ming1016.github.io/细说-gcd-grand-central-dispatch-如何用.md › 队列（dispatch queue） › Block组合Dispatch_groups（第496-545行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/low-level-concurrency-apis.md › Groups › Using dispatch_group_t with Existing API（第384-409行）
