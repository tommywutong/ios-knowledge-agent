---
topic: TCP连接与HTTP版本
group: 网络与安全
generated_at: 2026-07-29T19:59:10
provider: deepseek
---

# TCP连接与HTTP版本

## 一句话总结

TCP 通过三次握手建立可靠连接，HTTPS 在此之上还需要 TLS 四次握手；HTTP/1.1 通过持久连接（Keep-Alive）复用 TCP 连接。HTTP/2 在单一 TCP 连接上实现多路复用但存在队头阻塞（Head-of-Line Blocking）问题，HTTP/3 改用基于 UDP 的 QUIC 协议，把 TCP 和 TLS 握手合并为一次三次握手，从根本上消除 TCP 队头阻塞 [1][3][11]。

## 核心原理

### TCP 三次握手与 TLS 握手

- **TCP 三次握手**：客户端和服务端建立可靠连接之前需要经过三次握手，交换 SYN 和 ACK 报文 [1]。在移动网络环境下，一个数据包从用户 iPhone 到 Web 服务器的单程时间可能达到约 250 毫秒（一个 RTT [Round-Trip Time]），三次握手总共约 750 毫秒，且此时尚未发送任何应用负载数据 [3]。
- **HTTPS 需要额外四次握手**：HTTPS 在 TCP 可靠连接基础上使用 TLS 协议，TLS 需要四次握手才能建立安全连接；因此 HTTPS 建立连接总握手次数为七次（三次 TCP + 四次 TLS）[1]。粗略估算，HTTPS 连接在发送任何数据前需要耗费两倍于 HTTP 连接的时间。如果 RTT 为 500 毫秒（250 ms 单程），累计可达 1.5 秒 [3]。

### HTTP 版本中的连接复用

- **HTTP/1.1 持久连接（Keep-Alive）**：默认复用 TCP 连接，通过 `Connection: keep-alive` 头部控制；一个 TCP 连接可以服务多次请求，无须为每个请求重新握手 [9][2]。该复用机制能够：减少握手与 Radio 时间、减少 CPU 加密开销、避免多次 Radio 唤醒 [5]。
- **HTTP/1.1 管道化（Pipelining）**：允许在一个 TCP 连接上连续发送多个请求，不需要等待上一个响应；但响应必须按请求顺序返回，存在队头阻塞问题 [9]。
- **HTTP/2 多路复用**：在单一 TCP 连接上支持多个数据流（stream）并行传输，避免了 HTTP/1.1 的队头阻塞 [2][6]。但 TCP 层面的队头阻塞依然存在——若 TCP 层发生丢包，所有流都会被阻塞 [2][11]。
- **HTTP/3 使用 QUIC 协议**：QUIC 是基于 UDP 的协议，替代 TCP 作为传输层；HTTP/3 运行在 QUIC 之上。QUIC 将 TCP 和 TLS 握手过程结合起来，握手次数从七次减少到三次 [1]。QUIC 允许流真正独立，避免了 TCP 的队头阻塞——丢包只会影响单个流，不会拖慢连接上的所有流 [11]。

### TCP 分段与 IP 分片的关系

- TCP 会在传输层对数据进行分段，发送端分段后 IP 层不会再分片 [2]。
- 但传输链路中其他网络层设备的 MTU（Maximum Transmission Unit）可能小于发送端的 MTU，此时数据包在传输过程中仍可能在 IP 层被再次分片 [2]。

### TCP 保活与 HTTP 持久连接的区分

- **TCP 保活（Keepalive）**：由内核实现，当连接长时间无数据交互时，内核发送探测报文检测对方是否在线，以决定是否关闭连接（常用于防火墙/NAT 存活检测）[2]。iOS 中可通过 `nw_tcp_options_set_enable_keepalive` 等 API 配置保活参数 [10]。
- **HTTP Keep-Alive（持久连接）**：核心功能是延长 TCP 连接的使用时间，允许一个 TCP 连接服务多次请求，直到任意一方主动断开 [2]。
- **心跳机制**：由客户端和服务端定期双向发送小数据包（心跳包），若超时未收到响应则判定连接失效并触发重连，常见于即时通信和主动推送场景 [2]。

## 关键细节与易错点

1. 握手次数因版本而异：本文所述三次握手（TCP）、七次握手（TCP+TLS）适用于特定版本协议。HTTP/3 使用 QUIC 协议，握手次数从七次减至三次 [1]。
2. **HTTP 和 TCP 的队头阻塞有本质区别**：HTTP/1.1 的队头阻塞发生在应用层（因请求-响应必须按顺序处理），HTTP/2 多路复用解决了应用层队头阻塞，但 TCP 层的队头阻塞依然存在——丢包会阻塞同一 TCP 连接上的所有流。只有 HTTP/3 通过 QUIC 从根本上消除了 TCP 队头阻塞 [2][11]。
3. **TCP 分段后 IP 层仍可能再次分片**：虽然发送端 TCP 分段后 IP 层不再分片，但链路中其他设备若 MTU 更小，会触发 IP 分片，且可能多次分片 [2]。
4. **持久连接和心跳机制是两回事**：HTTP Keep-Alive 是长连接复用，由一方主动断开；心跳机制则用于定期检测对方是否在线，超时未响应则判定连接失效。

## 高频追问

#### 1. 建立 HTTPS 连接需要几次握手？为什么比 HTTP 慢？
建立 HTTPS 连接需要七次握手（三次 TCP + 四次 TLS）[1]。HTTPS 比 HTTP 慢的主要原因是需要在 TCP 三次握手之后，额外进行 TLS 四次握手来协商加密参数和验证证书，在移动网络下，如果 RTT 是 500 毫秒，HTTPS 连接建立时间累计可达 1.5 秒 [3]。

#### 2. 为什么 TCP 层需要分段而不直接交给 IP 层分片？
如果将整个 TCP 报文交给 IP 层分片，IP 层没有超时重传机制，它只能依赖 TCP 负责超时和重传。如果某个 IP 分片丢失，IP 层无法组装成完整 TCP 报头，发送方无法收到 ACK 确认，因此必须重传整个 TCP 报文（而非仅丢失的分片）。TCP 层分段可避免这种低效的重传 [2]。

#### 3. 怎么用 HTTP 实现断点续传？
客户端先发送 HEAD 请求获取文件大小，然后在 GET 请求头中加入 `Range` 字段（如 `Range: bytes=50000000`），服务端响应时在响应头中加入 `Content-Range` 字段告知本次响应的内容范围，客户端将收到的内容拼接到已下载部分 [2]。

#### 4. 为什么应用层需要复用连接？
因为每次 TCP 建连加上 TLS 握手需要 2~3 个 RTT，并会持续持有 Radio 资源。复用连接可以：减少握手 Radio 时间、减少 CPU 加密开销、避免多次 Radio 唤醒 [5]。

#### 5. iOS 中如何利用 URLSession 优化连接复用？
使用同一个 URLSession 对象创建任务，因为每个 URLSession 对象拥有一个连接池，创建多个对象无法获得连接复用收益。从 iOS 12 和 macOS Mojave 开始，URLSession 还支持 HTTP/2 连接合并（Connection Coalescing），当多个子域名解析到同一 IP 地址且证书覆盖所有子域名时，可复用已有连接 [12]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/三次握手、七次握手、四次挥手.md › 总结（第136-157行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/计算机网络（持续更新）_副本.md › (全文)（第149-199行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/ip-tcp-and-http.md › Putting the Pieces Together › Efficiently Using Connections › Setup（第442-448行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-网络优化.md › 耗电-网络优化 › 四、连接复用与HTTP/2 / HTTP/3 › Keep-Alive的能效意义（第171-177行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-网络优化.md › 耗电-网络优化 › 四、连接复用与HTTP/2 / HTTP/3 › HTTP/2多路复用（第201-203行）
[9] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/计算机网络.md › 计算机网络 › HTTP协议 › HTTP版本演进 › HTTP/1.1（第358-363行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/network/tcp-options.md › TCP Options › Topics › Configuring Keepalives（第44-49行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/fbeng/how-facebook-is-bringing-quic-to-billions.md › What are QUIC and HTTP/3?（第21-25行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2018/714-optimizing-your-app-for-today-s-internet.md › Optimizing Your App for Today’s Internet › Transcript（第243-251行）
