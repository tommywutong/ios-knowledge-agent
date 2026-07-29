---
topic: HTTP缓存策略
group: 网络与安全
generated_at: 2026-07-29T19:57:44
provider: deepseek
---

# HTTP缓存策略

## 一句话总结

HTTP缓存通过强制缓存（`Cache-Control`/`Expires`）和协商缓存（`Last-Modified`/`ETag`）两个阶段避免重复请求完整资源，iOS 中 `NSURLCache` 配合默认缓存策略（`NSURLRequestUseProtocolCachePolicy`）自动处理大部分细节，但 `URLSession` 会吞掉 304 响应，导致业务层无法直接判断 304 状态码 [7][9]。

## 核心原理

### 1. 强制缓存（Freshness）

- 服务端通过 `Cache-Control` 头部（如 `max-age=1296000`）或 `Expires` 指定资源的有效期 [2][3][9]。
- 浏览器/客户端在有效期内直接使用本地缓存，不发请求 [9]。
- 注意：`no-cache` 并非不缓存，而是每次使用前必须回源验证（协商） [7][9]；`no-store` 才是不允许缓存 [7]。

### 2. 协商缓存（Validation）

- 当强制缓存过期或设置为 `no-cache` 时，客户端携带条件头部向服务器验证资源是否修改 [9]。
- 两种验证机制：
  - **`Last-Modified` / `If-Modified-Since`**：服务端返回资源的最后修改时间，客户端后续请求带上该时间 [1][2][4][9]。
  - **`ETag` / `If-None-Match`**：服务端返回资源的唯一标识（如 MD5 散列），客户端后续请求带上该标识 [1][2][4][9]。`ETag` 优先级高于 `Last-Modified` [9]。
- 若资源未变，服务端返回 `304 Not Modified`，客户端使用本地缓存 [7][9]。

### 3. iOS 中的缓存实现

- `NSURLSession` 默认使用 `NSURLCache.sharedURLCache`，其 `requestCachePolicy` 默认为 `NSURLRequestUseProtocolCachePolicy` [7][11][12]。
- 缓存数据存储在 SQLite 数据库 `Cache.db` 中（路径 `~/Library/Caches/<进程名或 bundle id>/Cache.db`），包含 `cfurl_cache_blob_data`、`cfurl_cache_response`、`cfurl_cache_receiver_data` 三个表 [7]。
- 默认容量：内存约 512KB，磁盘约 19.1MB [7]。

### 4. 实际响应示例（来自 Apple iTunes 音频资源）

```http
Cache-Control: public, max-age=1296000
Etag: "4960EBB73736A6F72AF3281A6A757CE1"
Last-Modified: Tue, 30 Oct 2018 20:22:39 GMT
```

该资源可被公开缓存 15 天，并同时提供了 `ETag` 和 `Last-Modified` 两种验证标识 [3]。

## 关键细节与易错点

### 1. `URLSession` 吞掉 304 状态码

- 当使用 `ETag`+`max-age=0` 时，第二次请求会自动带上 `If-None-Match: "v1"`，服务端返回 `304 Not Modified` 且 body 为空。但 `URLSession` 的 `completionHandler` 中看到的 **`statusCode` 是 200，body 是完整的原始数据**，`cacheEntry` 为 YES。这意味着业务代码中写的 `if (statusCode == 304)` **永远不会执行** [7]。

### 2. 不同 `Cache-Control` 值的行为对比（来自实测）

| 服务端响应头 | 第2次是否发出真实请求 | URLCache 里有条目 | 说明 |
|---|---|---|---|
| `max-age=60` | 否 | 有 | 直接读缓存，回调 status 仍为 200 |
| `no-store` | 是 | 无 | 连条目都不建 |
| `no-cache` | 是 | 有 | 存了但每次都回源 |
| 什么都不给 | 是 | 有 | 存了但没有新鲜度依据，回源 |
| `ETag` + `max-age=0` | 是，且带上 `If-None-Match` | 有 | 服务端答 304，但客户端看不到 304 |

[7]

### 3. 绕过缓存的情况

- 如果请求使用 `NSURLRequestReloadIgnoringCacheData` 等策略（通过 `requestWithURL:cachePolicy:timeoutInterval:` 设置），则会绕过缓存 [11]。
- 默认情况下（`NSURLRequestUseProtocolCachePolicy`）很少绕过，但可能存在极少数情况 [11]。

### 4. 必须包含的缓存头部

- 对于 HTTP 传输的资源，应确保响应包含 `Cache-Control`（指定缓存时间）、`Last-Modified` 和 `ETag`（提供验证机制） [4]。

## 高频追问

### 问：如何让某个请求不使用缓存，每次都从服务器获取最新数据？

设置 `request` 的 `cachePolicy` 为 `NSURLRequestReloadIgnoringCacheData`，或覆盖 `NSURLSessionConfiguration` 的 `requestCachePolicy` [11][12]。注意此策略会使请求完全不查缓存。

### 问：强制缓存和协商缓存的执行顺序是什么？

先执行强制缓存：检查 `Cache-Control` 的 `max-age` 是否过期。如果没过期直接使用本地缓存；如果过期（或 `no-cache`），则进入协商缓存：优先用 `ETag`/`If-None-Match`，否则用 `If-Modified-Since`/`Last-Modified`。若资源未变返回 304 使用缓存，否则返回 200 和新资源 [9]。

### 问：`NSURLCache` 的默认容量是多少？存储在哪儿？

默认内存容量 512KB，磁盘容量 19.1MB。磁盘存储在 `~/Library/Caches/<进程名或 bundle id>/Cache.db`，是一个 SQLite 数据库 [7]。

### 问：如果服务端既返回 `Last-Modified` 又返回 `ETag`，客户端如何选择？

`ETag` 优先级更高，客户端会优先使用 `If-None-Match` 进行协商 [9]。这两个可以同时存在，服务端将按 `ETag` 优先判断。

### 问：`no-cache` 和 `no-store` 有什么区别？

- `no-cache`：允许缓存条目，但每次使用前必须回源验证（协商缓存） [7][9]。
- `no-store`：不允许缓存，连条目都不建 [7]。

### 问：在 iOS 中如何查看当前缓存的条目？

可以通过 `URLCache` 的相关 API（如 `cachedResponseForRequest:`）查看，或直接打开 SQLite 数据库文件 `Cache.db`，查询 `cfurl_cache_response` 等表 [7]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/nshipster/nsurlcache.md › [NSURLCache](https://nshipster.com/nsurlcache/) › HTTP Cache Semantics › Request Cache Headers（第87-92行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/nshipster/nsurlcache.md › [NSURLCache](https://nshipster.com/nsurlcache/) › HTTP Cache Semantics › Response Cache Headers（第94-103行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 5. URLSessionTaskDelegate › 5.6 采集数据（第195-245行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/dirtmelon/web-性能权威指南-阅读笔记-http.md › 优化应用的交付 › 性能优化的最佳实践 › 在客户端缓存资源（第312-314行）
[7] /Users/tommywu/Obsidian/iOS/20 专题笔记/架构与网络/iOS 网络分层：URLSession 之上该有几层.md › 网络分层：URLSession 之上该有几层 › 一、你已经有一层缓存了（第43-89行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/计算机网络（持续更新）_副本.md › (全文)（第378-426行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/cocoawithlove/substituting-local-data-for-remote-uiwebview-requests-cocoa-with-love.md › A limitation...（第128-134行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/from-nsurlconnection-to-nsurlsession.md › NSURLSessionConfiguration › Properties › Caching Policies（第211-215行）
