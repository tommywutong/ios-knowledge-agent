---
topic: WebSocket与SSE
group: 网络与安全
generated_at: 2026-07-29T19:59:27
provider: deepseek
---

# WebSocket与SSE

## 一句话总结

WebSocket是建立在HTTP升级握手之上的全双工通信协议，支持文本和二进制消息；SSE是基于标准HTTP的服务端单向推送技术，天然支持自动重连。两者选择取决于是否需要双向实时交互。[1][2][3]

## 核心原理

- **WebSocket**：握手阶段通过HTTP Upgrade机制（客户端发送Upgrade请求，服务端响应101 Switching Protocols）将连接从HTTP升级为WebSocket协议，之后底层TCP连接不再传输HTTP报文，改为传输WebSocket帧（二进制紧凑格式，帧头仅2-14字节）。[2][3]
- **SSE**（Server-Sent Events）：基于标准HTTP的持久连接，客户端发起普通HTTP请求，服务端持续推送`text/event-stream`格式的事件流。[1][2][11]
- **Streamable HTTP**：一种渐进式设计，简单场景为普通HTTP请求/响应，复杂场景可升级为SSE流式响应。[2][4]

### 帧格式关键字段（WebSocket）
- **FIN**：1位，标记消息最后一帧
- **Opcode**：4位：0x1=文本, 0x2=二进制, 0x8=关闭, 0x9=Ping, 0xA=Pong
- **MASK**：1位，客户端→服务端必须为1
- **Payload Length**：7位（可扩展至16位或64位）
- **Masking Key**：4字节（MASK=1时存在）[2][4]

### 客户端帧必须掩码的原因
防止**缓存投毒攻击（Cache Poisoning）**。恶意网页中JavaScript通过WebSocket向目标服务器发送数据，若中间存在不理解WebSocket的HTTP代理，可能误将WebSocket帧当作HTTP请求/响应缓存。掩码使得每次发送的帧在比特层面不同，干扰代理判断。掩码算法：`masked_payload[i] = original_payload[i] XOR masking_key[i % 4]`。这不是加密，Key明文传输，是协议层防护。[2][4]

## 关键细节与易错点

- **WebSocket与HTTP的关系**：两者是平级的应用层协议，WebSocket仅在握手阶段“借用”HTTP（Upgrade机制），连接建立后不再承载HTTP报文。共用80/443端口以穿透防火墙。[2]
- **SSE的自动重连**：内置支持`Last-Event-ID`机制，断线后自动恢复。[1][2]
- **数据格式**：SSE仅支持纯文本（UTF-8）；WebSocket支持文本和二进制。[1][2]
- **连接数限制**：HTTP/1.1下SSE每域名最多6个连接（受浏览器限制）；WebSocket无此限制。[1]
- **代理/防火墙友好性**：SSE为标准HTTP流量，最友好；WebSocket可能需要额外配置；Streamable HTTP请求可独立路由，最友好。[1][2][4]
- **Apple平台实现**：WWDC 2019宣布`URLSessionWebSocketTask`，通过传入URL并调用`resume()`启动握手，无需处理状态码。使用现有`URLSession`配置，支持cookie和凭证查找。[3] 消息类型为`URLSessionWebSocketTask.Message.data`和`URLSessionWebSocketTask.Message.string`。[9] `SessionDelegate`实现`URLSessionWebSocketDelegate`协议，弱引用回调`SessionStateProvider`，设计解耦。[7]

## 高频追问

### Q1：SSE和WebSocket如何选择？

**回答要点**：
- 只需服务端→客户端推送（如AI流式输出、通知推送、实时日志）→ 选SSE，更简单轻量，兼容HTTP。[1][2]
- 需要双向实时交互（如聊天、协同编辑、游戏）→ 选WebSocket。[1][2]
- Streamable HTTP适用于按需流式API（如MCP工具调用），可渐进升级。[2][4]

### Q2：WebSocket握手过程是怎样的？

**回答要点**：
1. 客户端向服务端发送HTTP请求，包含`Upgrade: websocket`等头，表示要升级协议。
2. 服务端响应`101 Switching Protocols`状态码，之后连接变为全双工WebSocket流。
3. 两端可自由发送数据字符串、Ping/Pong帧，无HTTP开销。[3]

### Q3：WebSocket帧掩码（Masking）是加密吗？为什么需要？

**回答要点**：
- 不是加密。Masking Key明文传输，掩码是异或运算，可轻松还原。
- 目的：防止缓存投毒攻击。恶意网页JS通过WebSocket发送数据时，中间HTTP代理可能误将帧当作HTTP请求/响应并缓存。掩码使每次帧比特不同，防止代理混淆。[2][4]

### Q4：URLSessionWebSocketTask如何使用？

**回答要点**：
- 创建：`URLSession(configuration:).webSocketTask(with: url)`
- 调用`resume()`启动握手，系统处理状态码。
- 使用已有`URLSession`配置对象，支持cookie和凭证查找。
- 连接后发送：`send(_:completionHandler:)`，接收：`receive(completionHandler:)`。
- 消息类型：`.data(Data)`或`.string(String)`。[3][9]

### Q5：SSE的自动重连机制如何工作？

**回答要点**：
- SSE协议内置支持`Last-Event-ID`字段。断线后客户端重连时可携带该字段，服务端据此从断点继续推送事件流。
- 不需要业务手动实现重连逻辑。[2][11]

### Q6：HTTP/1.1下SSE每域名最多连接数是多少？WebSocket有同样限制吗？

**回答要点**：
- HTTP/1.1标准规定每域名最多6个并发连接，SSE同样受此限制。
- WebSocket没有此限制，因为它是独立协议，不占用HTTP连接池。[1]

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/计算机网络.md › 计算机网络 › 实时通信协议 › SSE（Server-Sent Events） › SSE vs WebSocket（第1314-1327行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/计算机网络.md › 计算机网络 › 常见面试问题（第2248-2277行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2019/712-advances-in-networking-part-1.md › Advances in Networking, Part 1 › Transcript（第224-234行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 计算机网络（第4446-4480行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/Alamofire源码导读.md › Alamofire源码导读 › 五、SessionDelegate — URLSession 桥接层（第552-579行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/foundation/urlsessionwebsockettask/message.md › URLSessionWebSocketTask.Message › Topics › Message types（第38-41行）
[11] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/计算机网络.md › 计算机网络 › 实时通信协议 › SSE（Server-Sent Events）（第1310-1312行）
