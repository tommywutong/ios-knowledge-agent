---
topic: ATS与网络安全
group: 网络与安全
generated_at: 2026-07-29T19:58:39
provider: deepseek
---

# ATS与网络安全

## 一句话总结

ATS (App Transport Security) 是 Apple 在 iOS 9.0+ 和 OS X 10.11+ 中默认启用的安全机制，要求 App 与服务器之间的 HTTP 连接必须使用 HTTPS 协议，且满足特定的 TLS 版本、密码套件和证书要求，以防止中间人攻击和数据篡改 [1][2][4]。

## 核心原理

- **目标**：为 App 与服务器提供安全的通信方式，防止中间人窃听和篡改传输的数据 [2]。
- **技术基石**：基于 TLS (Transport Layer Security) 协议，它是基于 TCP 的加密协议，支持通信双方身份验证和数据加密 [9]。基于 TLS 的 HTTP 请求就是 HTTPS [9]。
- **核心技术要求**：服务端必须满足以下三点 [1]：
    1.  **协议版本**：支持至少 TLS 1.2 版本。
    2.  **密码套件**：仅限使用提供前向保密 (Forward Secrecy) 的密码。
    3.  **证书**：必须使用 SHA-256 或更好的签名哈希算法签名，且必须使用 2048 位或以上的 RSA 密钥，或 256 位或以上的椭圆曲线 (ECC) 密钥。
- **启用方式**：在 iOS 9.0 和 OS X 10.11 中，默认情况下，使用 `NSURLSession` 建立的 HTTP 连接都会被要求启用 HTTPS [2][4]。开发者可在 Info.plist 文件中通过 `NSAppTransportSecurity` 字典进行配置 [4][5]。

## 关键细节与易错点

- **配置结构与 Key**：`NSAppTransportSecurity` 字典结构包含多个键，用于精细控制 ATS 行为 [12]：
    - `NSAllowsArbitraryLoads` (Boolean)：设置为 `YES` 可完全禁用 ATS，但 Apple 已收紧此权限 [5]。
    - `NSExceptionDomains` (Dictionary)：用于为特定域名（如 `<domain-name-string>`）配置 ATS 例外，允许针对该域名的自定义设置 [10][12]。
    - `NSExceptionDomains` 下的子键：
        - `NSExceptionAllowsInsecureHTTPLoads` (Boolean)：是否允许该域名使用不安全的 HTTP 连接。
        - `NSExceptionMinimumTLSVersion` (String)：设置该域名允许的最低 TLS 版本。
        - `NSExceptionRequiresForwardSecrecy` (Boolean)：默认值为 `YES`，是否要求前向保密密码套件 [12]。
        - `NSRequiresCertificateTransparency` (Boolean)：是否要求证书透明度。
    - `NSAllowsArbitraryLoadsForMedia` (Boolean)：是否允许媒体资源的任意加载。
    - `NSAllowsArbitraryLoadsInWebContent` (Boolean)：是否允许 Web 视图内容的任意加载 [12]。
    - `NSAllowsLocalNetworking` (Boolean)：是否允许本地网络访问 [12]。
    - `NSIncludesSubdomains` (Boolean)：此例外是否适用于该域名的所有子域 [12]。
- **Apple 的推动与时间线**：
    - Apple 从 WWDC 15 开始推行 ATS，最初在 iOS 9 中默认禁止非 HTTPS 访问 [2][5]。
    - 从 2017 年 1 月 1 日起，所有新提交的 App 默认不允许使用 `NSAllowsArbitraryLoads` 来绕过 ATS 限制，以此强制开发者使用 HTTPS [5]。
- **TLS 1.3**：TLS 1.3 发布于 2018 年，是对 TLS 1.2 的全面修订，在性能和安全性方面有更大提升，且只支持 Diffie-Hellman 非对称加密算法，移除了 RSA 算法 [3]。
- **证书锁定 (Certificate Pinning)**：除了通过 ATS 的 `NSPinnedDomains` 进行系统级的声明式证书/公钥固定外，也有第三方库（如 AFNetworking）提供 `AFSSLPinningMode`（`None` / `PublicKey` / `Certificate`）来实现证书固定 [11]。
- **正确理解**：`NSExceptionDomains` 不是用来**禁用**该域名的 ATS，而是为了在特定域名下**放宽或收紧** ATS 的要求 [12]。如果将该域名的 `NSExceptionAllowsInsecureHTTPLoads` 设为 `YES`，则允许该域名使用不安全的 HTTP 连接。

## 高频追问

1.  **ATS 有哪些豁免 (Exception) 机制？**
    - 开发者可以通过在 Info.plist 文件中配置 `NSAppTransportSecurity` 字典来实现。核心有两种方式 [5][12]：
        1.  全局禁用：将 `NSAllowsArbitraryLoads` 设置为 `YES`。
        2.  域名例外：在 `NSExceptionDomains` 字典下为特定域名添加配置，例如将 `NSExceptionAllowsInsecureHTTPLoads` 设为 `YES` 可允许该域名使用 HTTP。

2.  **ATS 是否兼容 TLS 1.3？**
    - ATS 的核心要求之一是服务端必须支持至少 TLS 1.2 [1]。TLS 1.3 是对 TLS 1.2 的全面修订，在性能和安全性方面都有很大提升 [3]。因此，支持 TLS 1.3 的服务端不仅满足 ATS 的基础版本要求，而且能提供更好的安全连接。

3.  **为什么 Apple 会逐渐禁用 `NSAllowsArbitraryLoads`？**
    - 这是 Apple 推动整个生态向更安全的 HTTPS 迁移的策略。他们通过收紧审核政策，鼓励开发者适配更进步和安全的使用方式，为所有用户构建更安全的使用环境 [5][12]。

4.  **什么是证书固定 (Certificate Pinning)，与 ATS 的关系是什么？**
    - 证书固定是一种安全策略，用于验证服务器提供的是特定的、预先已知的证书或公钥，而不是信任任何由受信任 CA 签署的证书，以防止攻击者使用伪造的证书发动中间人攻击 [11]。
    - ATS 本身不强制要求证书固定，但系统在 iOS 的 Info.plist 文件中提供了 `NSPinnedDomains` 键，允许开发者进行声明式、无需编写代码的证书公钥固定 [11]。第三方库如 AFNetworking 也提供了相应的 `AFSSLPinningMode` 来实现 [11]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/app-transport-security-ats.md › App Transport Security技术要求（第21-31行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/southpeak/app-transport-security-ats.md › (全文)（第1-19行）
[3] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/三次握手、七次握手、四次挥手.md › 2. 七次握手 › 2.5 TLS（Transport Security Layer）协议（第82-88行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/dirtmelon/url-loading-system.md › NSURLSession › App Transport Security (ATS)（第210-212行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/onevcat/关于-ios-10-中-ats-的问题.md › (全文)（第1-25行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/ip-tcp-和-http.md › HTTPS - 安全的 HTTP（第422-426行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/bundleresources/information-property-list/nsapptransportsecurity.md › NSAppTransportSecurity › Topics › Domain-Specific Exceptions（第61-63行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/架构与网络/iOS 网络分层：URLSession 之上该有几层.md › 网络分层：URLSession 之上该有几层 › 九、AFNetworking 在 URLSession 之上加了什么 › 安全策略（第515-517行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/onevcat/关于-ios-10-中-ats-的问题.md › (全文)（第55-77行）
