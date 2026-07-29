---
topic: URLSession任务与Delegate
group: 网络与安全
generated_at: 2026-07-29T19:57:21
provider: deepseek
---

# URLSession任务与Delegate

## 一句话总结

URLSession 通过 delegate 设计模式将网络事件分发给监听者，支持 data、download、upload 等任务类型；调用方需实现对应协议方法（URLSessionTaskDelegate、URLSessionDownloadDelegate 等），且 session 强持有 delegate 直至失效。[1][3][11]

## 核心原理

- **Delegate 协议层级**：`URLSessionDownloadDelegate` 继承自 `URLSessionTaskDelegate`[6]，所有任务通用事件（如完成、认证挑战）定义在 `URLSessionTaskDelegate` 中[12]；具体任务类型增加专属协议：data task 对应 `URLSessionDataDelegate`，download task 对应 `URLSessionDownloadDelegate`[1][6][8]。
- **创建 session 并设置 delegate**：通过 `URLSession(configuration:delegate:delegateQueue:)` 初始化时指定 delegate[1][3][5]。delegate 队列为 nil 时默认使用串行队列，保证回调顺序[11]。
- **任务创建与启动**：通过 session 调用 `downloadTask(with:)` 等工厂方法创建任务，调用 `resume()` 开始[1][3][5]。
- **回调分发机制**：三方库（SDWebImage、Alamofire、AFNetworking）常采用“集中式 delegate + 反查任务”模式——session 的 delegate 只有一个（manager 或自定义对象），收到回调后通过 `taskIdentifier` 或弱引用 stateProvider 分发给具体操作对象[2][7][9][11]。
- **进度更新通知**：download task 的下载进度通过 `URLSessionDownloadDelegate` 的 `urlSession(_:downloadTask:didWriteData:totalBytesWritten:totalBytesExpectedToWrite:)` 获取[8]；data task 的数据接收通过 `urlSession(_:dataTask:didReceiveData:)` 逐段获取[5][8]。
- **错误处理统一方法**：无论成功或失败，最终都会调用 `URLSessionTaskDelegate` 的 `urlSession(_:task:didCompleteWithError:)`[4][12]，成功时 error 为 nil[12]。
- **session 生命周期管理**：`NSURLSession` 创建时强持有 delegate，必须通过 `invalidateAndCancel` 或 `finishTasksAndInvalidate` 打破循环引用；使用懒加载可在失效后重置为 nil 重建[11]。

## 关键细节与易错点

1. **delegate 的线程安全**：Apple 文档明确 `NSURLSession` 代理方法本身是线程不安全的[11]。AFNetworking 将 `operationQueue.maxConcurrentOperationCount` 设为 1 串行化回调，并用 `NSLock` 保护 `mutableTaskDelegatesKeyedByTaskIdentifier` 字典[11]。
2. **主动销毁 Session 的必要性**：懒加载 session 的对象必须适时调用 `invalidate` 方法，否则 delegate 不会被释放，可能造成内存泄漏[11]。
3. **两种认证挑战方法**：session 级别的委托方法处理连接级挑战（Server Trust、客户端证书、NTLM、Kerberos），task 级别的委托方法处理请求级挑战（Basic、Digest、Proxy 验证）[12]。
4. **文件下载完成需手动移动文件**：`urlSession(_:downloadTask:didFinishDownloadingTo:)` 提供临时文件路径，需调用 `FileManager.default.moveItem(at:to:)` 保存到持久化位置[4]。
5. **渐进式图片加载实现**：data task 的 `didReceiveData` 可配合 `CGImageSourceCreateIncremental` 实现边下载边渲染，每收到数据后调用 `CGImageSourceUpdateData` 更新增量源，即时生成当前分辨率图片[5]。
6. **参数类型变更**：`NSURLSession` 中字节传输进度的参数类型为 `int64_t`，而 `NSURLConnection` 使用 `long long`[12]。

## 高频追问

**Q1：为什么调用 download 但必须实现 data task 的 delegate 方法？**
A：只有在 `URLSessionDataDelegate` 中实现 `urlSession(_:dataTask:didBecome:)` 才能捕获 data task 自动变为 download task 的事件[7][10]。某些情况下系统（如 MIME 类型匹配）会将 data task 转换为 download task。

**Q2：如何自定义 Delegate 的子类又不影响 session 的正常工作？**
A：可以继承 `SessionDelegate`（如 Alamofire），通过 `weak var stateProvider: SessionStateProvider?` 桥接回调，子类重写特定方法并调用 super 或转发，保持与 `Session` 的解耦[9]。

**Q3：进度回调不触发可能是什么原因？**
A：需要同时满足：① session 创建时设置了 delegate；② 实现了正确的协议方法（download task 需 `URLSessionDownloadDelegate` 的 `didWriteData` 方法，data task 需 `URLSessionDataDelegate` 的 `didReceiveData` 方法）；③ 任务已调用 `resume()`[1][3][5][8]。

**Q4：一个 session 管理多个 task 时如何区分各自的回调？**
A：通常通过 `task.taskIdentifier` 逆查对应的操作对象（如 SDWebImage 的 `operationWithTask:` 或 AFNetworking 的 `mutableTaskDelegatesKeyedByTaskIdentifier` 字典）[2][7][11]，或通过状态提供者协议（如 Alamofire 的 `SessionStateProvider`）[9]。

**Q5：delegate 队列设置为 nil 有什么影响？**
A：系统会创建串行队列来顺序调用 delegate 方法，保证回调的线程安全；如果自行传入并行队列，则需额外加锁[1][3][11]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 10. 将数据下载到文件系统 › 10.2 使用 delegate 接收下载进度更新（第512-535行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/SDWebImage源码导读.md › SDWebImage源码导读 › 七、SDWebImageDownloader — 下载调度器 › 7.4 URLSession delegate 的分发（第767-797行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/dirtmelon/url-loading-system.md › 下载来自网站的文件 › 使用 delegate 来接收进度更新（第472-485行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/dirtmelon/url-loading-system.md › 下载来自网站的文件 › 在 delegate中处理下载错误（第510-536行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/卡顿/卡顿-图片优化.md › 卡顿-图片优化 › 大图处理 › 渐进式加载（第640-684行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 7. URLSessionDownloadDelegate（第313-315行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/samplecode/CustomHTTPProtocol/CustomHTTPProtocol-Core Code-QNSURLSessionDemux.m.md › CustomHTTPProtocol/Core Code/QNSURLSessionDemux.m（第298-330行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/foundation/urlsessiontask/countofbytesreceived.md › countOfBytesReceived › Discussion（第32-34行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/Alamofire源码导读.md › Alamofire源码导读 › 五、SessionDelegate — URLSession 桥接层（第552-579行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/foundation/urlsessiondatadelegate/urlsession(__datatask_didbecome_)-60op5.md › urlSession(_:dataTask:didBecome:)（第20-30行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/AFNetworking源码导读.md › AFNetworking 源码导读 › 三、AFURLSessionManager：整个库的心脏 › 3.1 初始化与会话创建（第168-185行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/from-nsurlconnection-to-nsurlsession.md › NSURLSessionTask › NSURLSession & NSURLConnection Delegate Methods（第126-136行）
