---
topic: Swift async await
group: GCD与并发
generated_at: 2026-07-29T19:41:33
provider: deepseek
---

# Swift async await

## 一句话总结

`async/await` 是 Swift 并发特性的基础，通过 `async` 声明异步函数、`await` 标记暂停点，配合结构化并发（`async let`、`TaskGroup`）提供一种高效、可预测的并发模型 [1][7][10]。该模型要求 `checked continuation` 在所有路径上恰好被调用一次 [1][3]，并支持任务取消传播与优先级继承等结构化行为 [4][9]。

## 核心原理

- **异步函数（async function）**：以 `async` 关键字声明的函数可以在执行过程中暂停并放弃线程，等待某个操作完成后恢复 [10]。
- **暂停点（suspension point）**：通过 `await` 标记，当前执行分支在此挂起，等待子任务完成；结果在此重新汇合 [9]。
- **结构化并发（Structured Concurrency）**：并发任务通过 `async let` 或 `TaskGroup` 创建，它们必须在其作用域结束前完成，从而形成可预测的父子任务树 [9][10][11]。这种结构自动支持：
  - 任务取消的层级传播（父任务取消时子任务自动取消）[9]
  - 优先级的继承与传递 [9]
  - 任务本地值（task-local values）的继承 [9]
- **任务组（Task Group）**：使用 `withThrowingTaskGroup` 或 `withTaskGroup` 创建，用于动态数量的并发任务。子任务通过 `group.addTask` 添加，它们立即开始执行，当组作用域结束时隐式等待所有子任务完成 [11][12]。
  - `async let` 适用于**固定数量**的任意异步函数并发 [11]
  - 任务组适用于**动态数量**的专用异步函数并发 [11][12]
- **继续体（Continuation）**：用于桥接传统的闭包回调 API 与 `async/await`。通过 `withCheckedThrowingContinuation`（或 `withCheckedContinuation`）创建一个继续体，在回调中调用 `continuation.resume(returning:)` 或 `continuation.resume(throwing:)` 返回结果 [3]。
  - **checked continuation 必须恰好被调用一次**，否则会导致运行时错误或未定义行为 [1]。
- **`withTaskCancellationHandler`**：在父任务被取消时，自动将取消信号传递给底层请求，避免资源浪费。Alamofire 的 `DataTask` 使用此机制 [4]。

## 关键细节与易错点

1. **continuation 的契约**：`checked continuation` 值代表手动恢复异步调用的能力，因此**必须在所有代码路径上调用它**。如果委托 API 可能被多次调用或从不被调用，必须在适当位置确保活跃的 continuation 被调用且仅调用一次，并注意在调用后置空以防止重复调用 [1]。
2. **异步函数不会自动增加并发**：虽然 `async` 允许挂起线程，但两个 `await` 之间默认是顺序执行的。要实现真正的并发，必须显式使用 `async let` 或任务组 [10][11]。
3. **任务取消是协作式的**：`withTaskCancellationHandler` 可以帮助传递取消信号，但任务本身需要检查 `Task.isCancelled` 或响应取消。材料中 Alamofire 的例子展示了 `shouldAutomaticallyCancel` 属性配合 `withTaskCancellationHandler` 自动取消底层请求 [4]。
4. **`@MainActor` 保证 UI 更新在主线程**：使用 `@MainActor` 标记的异步方法会在主线程执行，无需手动 `DispatchQueue.main.async` [5]。
5. **非结构化任务**：`Task.detached` 创建一个不继承父任务优先级、取消等属性的独立任务，适用于需要在独立执行上下文中运行的后台操作 [5]。但结构化并发更推荐使用结构化方式 [9]。
6. **编译器强制的结构化约束**：任务组和 `async let` 的作用域必须与所创建的任务生命周期一致，编译器会保证子任务不会逃逸出闭包范围 [11]。

## 高频追问

### Q1：`async/await` 和传统 GCD 的主要区别是什么？
**回答要点**：基于材料的表述，`async/await` 是结构化并发的基础，通过暂停点（await）和任务层次提供自动取消传播、优先级继承等行为 [9][10]；而 GCD 非结构化，需要手动管理回调、取消和生命周期。Swift 并发模型旨在使异步代码像同步代码一样易于理解和推理 [10]。

### Q2：什么场景下应使用 `async let` 而非任务组？
**回答要点**：`async let` 适用于**固定数量**的异步函数并发，例如同时获取用户信息和配置；任务组适用于**动态数量**的并发，例如根据数组长度创建未知数量的子任务 [11][12]。

### Q3：`checked continuation` 为什么必须恰好调用一次？不调用或多次调用的后果是什么？
**回答要点**：continuation 代表手动恢复异步调用的能力，调用一次会释放挂起状态并返回结果。如果不调用，调用者将永远挂起；如果多次调用，会导致未定义行为。为了调试保护，`withCheckedContinuation` 会在检测到违反契约时抛出错误或崩溃 [1]。

### Q4：如何将已有的闭包回调 API 适配为 `async/await` 接口？
**回答要点**：使用 `withCheckedThrowingContinuation`（或 `withCheckedContinuation`）包装回调，在回调闭包中获取结果并调用 `continuation.resume`。Apple 在 WWDC 中推荐这种做法，并强调要确保所有路径上 resume 恰好一次 [1][3]。

### Q5：`withTaskCancellationHandler` 的作用是什么？
**回答要点**：它允许在父任务（例如 SwiftUI 视图）取消时，注册一个取消处理器，自动将取消信号传递到底层异步操作（如网络请求），避免资源浪费。Alamofire 的 `DataTask` 使用此机制自动取消对应的 `DataRequest` [4]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10132-meet-async-await-in-swift.md › Meet async/await in Swift › Transcript（第215-225行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/emergetools/emerge-tools-blog-async-await-in-swift-the-full-toolkit.md › Async await in Swift: The Full Toolkit › [The Toolkit](https://www.emergetools.com/blog/posts/swift-async-await-the-full-toolkit#the-toolkit) › [Continuations (practice)](https://www.emergetools.com/blog/posts/swift-async-await-the-full-toolkit#continuations-practice)（第350-380行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/Alamofire源码导读.md › Alamofire源码导读 › 十三、async/await 与 Combine 集成 › 13.1 Concurrency.swift — async/await（第1145-1190行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-主线程优化.md › 卡顿-主线程优化 › 任务异步化 › Swift Concurrency（第180-225行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/zh/wwdc2021/10132-meet-async-await-in-swift.md › 认识 Swift 中的 async/await › 逐字稿（第221-225行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2023/10170-beyond-the-basics-of-structured-concurrency.md › Beyond the basics of structured concurrency › Transcript（第89-106行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/onevcat/swift-结构化并发.md › (全文)（第1-19行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2021/10134-explore-structured-concurrency-in-swift.md › Explore structured concurrency in Swift › Transcript（第65-65行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/emergetools/emerge-tools-blog-async-await-in-swift-the-full-toolkit.md › Async await in Swift: The Full Toolkit › [The Toolkit](https://www.emergetools.com/blog/posts/swift-async-await-the-full-toolkit#the-toolkit) › [Task group](https://www.emergetools.com/blog/posts/swift-async-await-the-full-toolkit#task-group)（第147-173行）
