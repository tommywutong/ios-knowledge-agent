---
topic: 通知代理与Block对比
group: KVC与KVO
generated_at: 2026-07-29T19:45:04
provider: deepseek
---

# 通知代理与Block对比

## 一句话总结
Delegate（一对一、编译检查、返回/拦截能力）适合强关联场景；Block（默认强持有、轻量语法）适合一次性异步回调；通知（一对多、完全解耦）适合跨模块广播。

## 核心原理

- **关系模型**：delegate 是“一对一”强关联，委托方和代理双方互相知道；通知是“一对多”弱关联，发布者不知道谁在监听 [1][7]；Block 回调也是一对一，但调用方通过捕获变量“知道”对方 [3]。
- **内存所有权**：delegate 及通知的 selector 版观察者默认**不持有**回调方（delegate 用 weak，通知中心对 selector 观察者为弱引用）；**Block 反过来默认强持有捕获的一切，这个持有是隐式的、语法上看不见** [7]。block 版通知观察者系统仍持有强引用，其 token 必须显式移除 [6]。
- **性能开销（单次调用）**：block 调用最快（约 0.3 纳秒），直接消息发送约 2.6 纳秒，delegate 完整写法约 26 纳秒（大头是读一次 weak 的 16.5 纳秒），`postNotificationName:` 最慢约 200–213 纳秒 [3][6]。

## 关键细节与易错点

- **Block 会将回调方的寿命延长到 Block 自己被释放为止**：如网络请求 completion 持有 ViewController，用户已退出界面但 controller 得等请求回来才能死。这不算泄漏（Instruments Leaks 查不出），但影响真实行为 [7]。
- **通知的 selector 版观察者从 iOS 9 起免移除**，靠的是 zeroing weak 存储；**但 Block 版不行**，系统仍持有强引用，token 必须存下来并在 dealloc 里移除 [6]。
- **`addObserverForName:object:queue:usingBlock:` 的 `queue:` 参数有陷阱**：传 nil 不表示异步，实测 block 内 sleep 300 毫秒，post 稳定耗时 303–305 毫秒。若注册在 mainQueue 且主线程 post 会死锁 [6]。
- **Block 判空不解决并发问题**：`if (completion) completion();` 只解决空指针，不解决属性在判断与调用间被另一线程修改。真要并发安全需先取到局部变量再调 [7]。

## 高频追问

**Q：既然 delegate 是强关联、一对一，如何处理一对多场景？**
**A：** 可用 `NSPointerArray`（允许弱引用避免循环）存储多个代理对象，定义协议让所有代理遵守，遍历数组依次调用协议方法即可 [1]。

**Q：Block 循环引用怎么解决？**
**A：** Block 默认强持有捕获的变量，形成环时用 weak-strong dance 解决 [7]。

**Q：通知在哪些场景下不可用？**
**A：** 需要返回值或拦截时不可用，因为通知无法从观察者获取返回值；想获取响应只能走 delegate [3]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第1284-1328行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS 对象通信：delegate、通知、target-action 与 block 回调.md › 对象通信：delegate、通知、target-action 与 block 回调 › 七、怎么选（第763-790行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/架构与网络/iOS 综合项目设计文档：把这个系列用一遍.md › 综合项目设计文档：把这个系列用一遍 › 四、六十条决策，每条回指一篇 › G. 回调与通信（第319-331行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/Runtime 与对象通信/iOS 对象通信：delegate、通知、target-action 与 block 回调.md › 对象通信：delegate、通知、target-action 与 block 回调 › 五、block 回调：唯一默认强持有的那个（第693-709行）
