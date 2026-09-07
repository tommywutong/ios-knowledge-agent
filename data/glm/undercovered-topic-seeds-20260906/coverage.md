# coverage —— 种子池覆盖报告

## 1. 题量与配额达成

| 主题 | 配额 | 实际 | 达成 |
|---|---|---|---|
| network | 20-30 | **20** | ✓ |
| persistence | 15-25 | **21** | ✓ |
| build-startup | 20-30 | **25** | ✓ |
| swift-interop | 15-25 | **19** | ✓ |
| **合计** | 80-120 | **85** | ✓ |

类别分布：answerable 84 / follow_up 1。难度：easy 22 / medium 40 / hard 23。

## 2. 实际使用的来源（85 个小节，21 个文件）

| 主题 | 主要来源 | 小节数 |
|---|---|---|
| network | Obsidian《iOS 网络分层：URLSession 之上该有几层》（6 篇小节）+ tips《URLSession详解》《三次握手、七次握手、四次挥手》《网络模型》《HTTP Live Streaming 详解》《五种常见流媒体协议》 | 20 |
| persistence | Obsidian《iOS 数据库：SQLite 事务与索引…》《iOS 持久化选型》《iOS 序列化》《iOS YYModel 源码》+ tips《SQLite的使用一》《NSFileManager》 | 21 |
| build-startup | Obsidian《iOS App 启动》《iOS Mach-O》《iOS 从源码到可执行文件》《iOS 静态库与动态库》+ tips《Crash日志符号化》《ASLR》 | 25 |
| swift-interop | tips《Swift方法调用》《协议、泛型和Existential Container》《struct和class区别》《Swift指针的使用》《Swift编、解码协议Codable》 | 19 |

全部为完整正文的专题小节；未使用目录/标题句/时间戳/README/计划文档/meta 工作文档/知识卡片。

## 3. 主动放弃（12 条，见 rejected-seed-ideas.jsonl）

| 类别 | 数量 | 代表 |
|---|---|---|
| 文档结构标题/meta/知识卡片 | 3 | 『两种格式，四点六倍』（r2 红队同款反例）、meta 工作文档、知识卡片目录（任务禁止） |
| 证据不足 | 1 | WWDC 10254（仅 57 行且逐字稿压成超长单行，行号风险） |
| 概念重复 | 2 | tips《静态库和动态库对比》《Mach-O可执行文件》与 Obsidian 专题重复 |
| 不自然问法 | 4 | CocoaPods 安装步骤、LLDB 命令清单、NSURLSession 新建工程教程、若干行文碎片小节 |
| 自动拒收 | 2 | URLSessionDownloadDelegate 小节正文过薄、TCP/IP OSI 排错小节正文过薄 |

## 4. 覆盖后仍薄弱的方向（如实说明）

- **network 的 HTTP 协议细节层**（证书校验/TLS 握手细节、HTTP/2、URLSession 后台下载完整机制）：
  本地无对应完整笔记，仅 WWDC 可能有零散场次，本轮未纳入。
- **persistence 的 Core Data**：Obsidian 笔记只在《iOS 数据库》中以『代价』视角提及，缺独立小节，只出了间接题。
- **build-startup 的 Swift 链接特性**（Swift metadata、protocol conformance descriptor）：语料缺失。
- **swift-interop 的 WWDC en 场次**：SwiftData/并发/性能场次均为英文逐字稿且部分行号风险高，本轮只用了已被
  r3 验证过的 10133（不出新题避免重复），其余未纳入。

## 5. 最值得 Codex 再审的 20 条候选

seed-000021（SQLite 900 倍归因）、seed-000024（索引失效写法）、seed-000025（WAL 并发）、
seed-000032（归档产物结构与循环引用）、seed-000034（白名单递归）、seed-000035/36/37（YYModel 三问）、
seed-000041（安全解码防线）、seed-000042/43（三代 dyld 分界与关系）、seed-000045（dyld 环境变量现状）、
seed-000049（__LINKEDIT）、seed-000051（#import 代价）、seed-000053（_objc_msgSend$greet）、
seed-000054（重复符号与 weak）、seed-000056（三个 @ 前缀）、seed-000058（弱链接）、
seed-000063（镜像个数计价）、seed-000064（400 微秒盲区）。

优先理由：全部为 hard 级机制题，锚定小节信息密度高，且多为"以讹传讹澄清类"（dyld 分界、镜像个数、
首写分配），生产检索的召回与重排最容易在这类题上暴露差距。
