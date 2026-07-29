---
topic: NSOperation依赖与取消
group: GCD与并发
generated_at: 2026-07-29T19:40:44
provider: deepseek
---

# NSOperation依赖与取消

## 一句话总结

NSOperation 通过 KVO 状态属性（isReady、isExecuting、isFinished、isCancelled）管理执行生命周期与依赖关系，队列依赖 isFinished 的 KVO 通知来清除依赖并出队下一个操作；取消操作需手动通知 isFinished 以避免队列阻塞 [1][2][12]。

## 核心原理

### 1. 状态机与 KVO 合规
- `NSOperationQueue` 使用 KVO 观察队列中 operation 的状态属性（`isFinished`、`isExecuting`、`isCancelled`）的改变，当状态改变时队列会收到 KVO 通知 [2][5]。
- 这些状态属性必须实现为 KVO 合规的。如果子类自定义实现，必须在状态变化时手动发送适当的 KVO 通知 [1][6]。
- KVO 机制相比 delegate 模式更合适，因为 state 属性在 operation 队列之外也很有用，且 operation 不需要额外调用 delegate 方法 [2][5]。

### 2. 状态转换流程（同步子类自动管理，异步子类需自行管理）
- **isReady**：`NO` 时 operation 不会被队列出队；变为 `YES` 后（且队列有容量）即可开始执行 [3][8][12]。
- **isExecuting**：operation 启动时从 `NO` 变为 `YES`；工作完成后变回 `NO` [3][8]。
- **isFinished**：工作完成后从 `NO` 变为 `YES`。**关键**：队列不会清除依赖，直到 `isFinished` 的 KVO 值变为 `true`；同样，队列不会将 operation 出队，直到 `isFinished` 为 `true`。因此，即使 operation 被取消，也必须通知 KVO 观察者 operation 已完成 [1][12]。
- **isCancelled**：调用 `cancel` 只会将 `isCancelled` 翻转为 `YES`。`isCancelled` 是唯一一个官方明确说“不用自己发 KVO 通知”的属性 [1][3][8]。工作代码负责在合适的时机检查 `isCancelled` 并提前结束 [6][8]。

### 3. 依赖与取消的关系
- 依赖关系：operation 对象在 `isFinished` 的 KVO 值变为 `true` 之前不会清除依赖。同样，队列在 `isFinished` 为 `true` 之前不会将该 operation 出队 [1]。
- 取消时：必须将 `isCancelled` 和 `isFinished` 都设置为 `true`，`isExecuting` 设置为 `false`，并发送相应的 KVO 通知。不发送 finish 通知会导致队列中其他 operation 无法执行 [1][7]。

### 4. 自定义 subClass 注意事项
- 实现自定义 `isReady` 时，必须从 `super` 获取默认属性值并整合到新值中 [1]。
- 若实现 `start()` 方法，需自己维护 `isExecuting` 和 `isFinished` 并在状态变化时发送 KVO 通知 [12]。
- 异步子类必须完全自行管理所有状态及其过渡 [3][8]。`main()` 调用异步任务后，不应立即设置 `isFinished`，需等待异步回调 [11]。

## 关键细节与易错点

1. **取消时必须发送 isFinished 的 KVO 通知**：即使 operation 被取消，也必须通知观察者 operation 已完成。否则队列可能阻塞，阻止其他 operation 执行 [1][7]。
2. **isCancelled 不需要手动发送 KVO 通知**：与 `isExecuting`、`isFinished` 不同，`isCancelled` 的状态变化由系统自动管理 [1][12]。
3. **依赖清除依赖于 KVO 通知，而非 property 赋值**：必须通过 KVO 机制使 `isFinished` 变化，队列才能正确响应 [1][2]。
4. **异步 operation 的生命周期管理**：异步 operation 的 `main()` 返回后 operation 不应进入 `isFinished`，必须在异步回调中手动转换状态 [11]。
5. **拼写注意**：函数 `cancel` 使用一个 L（动词），属性 `cancelled` 使用两个 L（形容词）[7]。
6. **KVO 崩溃风险**：若未正确移除观察者或重复移除，会导致崩溃。可使用安全代理封装 [9]。KVO 底层通过 isa-swizzling 生成动态子类，并在 `dealloc` 中执行清理 [10]。

## 高频追问

### Q1: 取消一个 operation 后，它的依赖操作还会执行吗？
**依据材料**：如果一个 operation 被取消，但它的 `isFinished` 没有变为 `true`（例如忘记发送 finish 通知），则依赖它的其他 operation 永远不会被清除依赖，从而无法执行 [1]。正确的做法是在取消时将 `isFinished` 置为 `true`，这样依赖它的操作可以正常开始（只要其他依赖也满足）。材料未明确说明“依赖操作是否还会执行”，只强调取消后必须标记完成才能让队列继续推进。

### Q2: 为什么 NSOperationQueue 用 KVO 而不是 delegate 来监听状态？
- 队列知道具体的 operation 对象并 retain 它，控制其生命周期。状态改变可以建模为值变化，而 KVO 天然适合值变化的通知 [2][5]。
- 如果用 delegate，operation 需要同时维护 state 属性和调用 delegate 方法，且队列无法主动获取 state，需要保存所有 operation 的 state [2][5]。

### Q3: 自定义异步 NSOperation 时，如何确保 KVO 合规？
- 必须手动管理 `isExecuting` 和 `isFinished` 的状态转换，并在每次变化时显式发送 KVO 通知（例如使用 `willChangeValueForKey:` / `didChangeValueForKey:` 或通过默认存取器）[1][3][6][8]。
- `isCancelled` 不需要手动发送 KVO 通知 [1][12]。
- `isReady` 若自定义实现，需调用 `super` 合并结果 [1]。

### Q4: 取消操作时，已经执行到一半的任务如何处理？
- 默认 `cancel` 只设置 `isCancelled = YES`。工作代码应定期检查 `isCancelled`，并在检查到取消时提前结束（同步操作提前返回；异步操作将 `isExecuting` 设为 `NO`、`isFinished` 设为 `YES`）[3][6][8]。
- 材料未说明任务一旦开始是否会自动停止，依赖开发者主动检查。

### Q5: 一个 operation 被取消但未发送 isFinished 通知会有什么后果？
- 队列会认为该 operation 仍处于“进行中”或“未完成”状态，导致队列中其他被依赖的 operation 永远无法出队执行，造成队列阻塞 [1]。
- 即使 operation 被取消，也必须发送 finish 通知 [1][7]。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/10 学习计划/claude工程文件/_研究简报-NSOperation.md › NSOperation / NSOperationQueue 研究简报 › 二、状态机与 KVO 合规 › 关键原文（第116-126行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/消息传递机制.md › Framework 示例 › KVO（第145-153行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/nsprogrammer.github.io/nsoperation-subclassing.md › NSOperation 的 KVO 属性（第84-100行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/communication-patterns.md › Framework Examples › KVO（第133-141行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/concurrent-programming-apis-and-challenges.md › Concurrency APIs on OS X and iOS › Operation Queues（第224-253行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/nshipster/nsoperation.md › [NSOperation](https://nshipster.com/nsoperation/) › Cancellation（第61-70行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/nsprogrammer.github.io/nsoperation-subclassing.md › The KVO Properties of NSOperation（第84-100行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/崩溃/崩溃-治理.md › 崩溃-治理 › 常见崩溃类型及修复 › 4. KVO崩溃（第153-205行）
[10] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/KVO底层原理.md › KVO底层原理 › KVO 的底层实现原理：isa-swizzling › 第四步：重写 dealloc 和 _isKVOA（第148-151行）
[11] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Operation、OperationQueue的使用.md › 3. Asynchronous Operation（第308-318行）
[12] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Operation、OperationQueue的使用.md › 1. Operations › 1.1 Operation 状态（第13-31行）
