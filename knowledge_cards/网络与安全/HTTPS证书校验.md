---
topic: HTTPS证书校验
group: 网络与安全
generated_at: 2026-07-29T19:58:16
provider: deepseek
---

# HTTPS证书校验

## 一句话总结

HTTPS证书校验是TLS握手阶段通过`URLAuthenticationChallenge`回调（由`URLSessionDelegate`或`URLSessionTaskDelegate`处理），由客户端验证服务端证书链合法性（默认由系统自动完成），并允许开发者通过自定义`SecTrust`评估实现证书锁定（Certificate Pinning）或信任自签名证书等定制行为 [6][7][9]。

## 核心原理

- **TLS握手中的认证挑战**：当客户端与服务端首次建立SSL/TLS连接时，系统会产生一个`NSURLAuthenticationChallenge`，其`protectionSpace.authenticationMethod`为`NSURLAuthenticationMethodServerTrust` [7][9]。
- **委托回调的优先级**：
  - 对于`NSURLAuthenticationMethodServerTrust`及`NSURLAuthenticationMethodNTLM`、`NSURLAuthenticationMethodNegotiate`、`NSURLAuthenticationMethodClientCertificate`类型的挑战，系统优先调用`URLSessionDelegate`的`urlSession(_:didReceive:completionHandler:)`方法（会话级）；如果未实现，则降级为`URLSessionTaskDelegate`的`urlSession(_:task:didReceive:completionHandler:)`方法处理 [2][7]。
  - 其他类型挑战（如HTTP Basic/Digest）直接调用`URLSessionTaskDelegate`方法，不会调用会话级方法 [2]。
- **自定义信任评估流程**（手动服务器信任认证）[5][9]：
  1. 在回调中检查`challenge.protectionSpace.authenticationMethod`是否为`NSURLAuthenticationMethodServerTrust`。
  2. 检查`challenge.protectionSpace.host`是否与期望的主机名匹配。
  3. 若条件满足，自行评估`challenge.protectionSpace.serverTrust`（`SecTrust`对象），判断证书链是否可接受。
  4. 若信任有效：创建`URLCredential(trust: serverTrust)`，调用`completionHandler(.useCredential, credential)`，告诉系统接受服务端凭证 [5]。
  5. 若信任无效：调用`completionHandler(.cancelAuthenticationChallenge, nil)`，拒绝服务端凭证 [5]。
  6. 若不满足前两个条件，则调用`completionHandler(.performDefaultHandling, nil)`让系统默认处理 [9]。
- **框架实现模式**：
  - Alamofire 将不同类型的认证挑战分派给内部方法：`ServerTrust`走`ServerTrustManager.serverTrustEvaluator(forHost:)`，执行自定义信任评估 [1]。
  - AFNetworking 的`AFSecurityPolicy`通过`evaluateServerTrust:forDomain:`对`challenge.protectionSpace.serverTrust`进行校验，成功时创建`URLCredential`，失败时通过`objc_setAssociatedObject`将错误关联到task，在`didCompleteWithError:`中提供详细失败原因 [4]。
- **系统默认行为**：`URLSession`自动执行服务器信任评估（验证证书链、过期时间、CA签名等），开发者无需额外处理即可获得标准HTTPS信任 [6]。ATS启用后，默认信任策略更为严格；开发者仍可通过手动服务器信任认证**收紧**（例如实现证书固定），但不能**放宽**已启用的ATS要求 [6]。

## 关键细节与易错点

- **区分会话级与任务级回调**：如果app实现了`URLSessionDelegate`的认证挑战方法，则对于ServerTrust等挑战不会调用`URLSessionTaskDelegate`的方法；如果未实现会话级方法，系统会尝试调用任务级方法 [2][7]。因此开发者应确保在正确的层级实现处理逻辑。
- **必须检查`authenticationMethod`和`host`**：回调可能因多种原因被调用（如代理认证、客户端证书等），不加判断直接评估可能导致误处理或安全风险 [9]。
- **`performDefaultHandling`的恰当使用**：当挑战类型不是ServerTrust或主机名不符时，应调用`completionHandler(.performDefaultHandling, nil)`让系统继续默认行为，而不是尝试自行处理 [9]。
- **AFNetworking的错误关联技巧**：校验失败时用`objc_setAssociatedObject`将失败原因关联到task，确保用户最终收到的`error.userInfo`中包含完整的信任评估失败详情，而非笼统的`NSURLErrorCancelled` [4]。
- **证书锁定（Certificate Pinning）实现方式**：通过手动服务器信任认证，在`SecTrustEvaluate`基础上额外对比服务端证书的哈希值或公钥，要求服务端必须使用特定证书或由特定CA签发 [8]；ATS启用后仍可收紧信任但不可放宽 [6]。
- **自定义信任与ATS的关系**：ATS实际上是系统级安全策略，强制TLS加密和更强的信任规则。手动服务器信任认证只在系统默认信任流程之后被调用，且ATS生效时不能绕过ATS限制（如信任过期证书），但可以增加更严格的条件（如证书固定）[6]。

## 高频追问

1. **Q: 如何实现 HTTPS 证书锁定（Pinning）？**
   A: 需在`URLSessionDelegate`的认证挑战回调中手动评估`serverTrust`，并在标准评估通过后额外验证服务端证书的SHA-256指纹或公钥是否与本地预置值一致。具体可参考Apple官方文档《Performing Manual Server Trust Authentication》[5][6]及AFNetworking/AFNetworking源码中的`AFSecurityPolicy`实现 [4]。

2. **Q: URLSession 默认如何处理证书校验？若不实现任何委托方法，安全性如何？**
   A: 默认情况下`URLSession`自动执行完整的证书链验证（包括CA签名、有效期、吊销状态等），无需任何代码即提供标准HTTPS安全保护 [6]。ATS启用时要求更强，默认拒绝不符合证书要求的连接。因此多数应用无需额外实现即可获得足够的安全性。

3. **Q: Alamofire 和 AFNetworking 的证书校验策略有何异同？**
   A: 两者均基于`URLSession`的认证挑战机制。Alamofire通过`ServerTrustManager`将评估逻辑抽象为可组合的`ServerTrustEvaluating`协议（如`PinnedCertificatesTrustEvaluator`、`PublicKeysTrustEvaluator`）[1]；AFNetworking通过`AFSecurityPolicy`对象配置校验模式（SSL Pinning、证书信任策略等），并在失败时关联详细错误到task [4]。核心目的都是提供声明式的证书校验与绑定能力。

4. **Q: 什么是会话级挑战与任务级挑战？如何选择实现哪个委托方法？**
   A: 会话级挑战由`URLSessionDelegate`的`urlSession(_:didReceive:completionHandler:)`处理，适用于与session建立连接时统一的身份验证（如ServerTrust、NTLM、客户端证书）；任务级挑战由`URLSessionTaskDelegate`的`urlSession(_:task:didReceive:completionHandler:)`处理，适用于每个task独立的认证（如HTTP Basic/Digest）[2][7]。推荐对ServerTrust等SSL/TLS信任挑战实现会话级方法，因为它是跨所有task共享的连接属性；对非会话级认证挑战实现任务级方法。

5. **Q: AFNetworking 如何处理证书校验失败时的错误传播？**
   A: 当`evaluateServerTrust`返回失败时，AFNetworking通过`objc_setAssociatedObject`将`NSError`（包含信任评估失败原因）关联到当前task对象上。在`URLSessionTaskDelegate`的`didCompleteWithError:`回调中，首先检查task上是否有该关联错误，若有则优先返回（替换系统默认的`NSURLErrorCancelled`），从而向用户提供精确的失败原因 [4]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/Alamofire源码导读.md › Alamofire源码导读 › 五、SessionDelegate — URLSession 桥接层 › 5.1 身份验证 Challenge 派发（第581-612行）
[2] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 5. URLSessionTaskDelegate › 5.4 处理 authentication challenge（第130-135行）
[4] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/三方库源码/AFNetworking源码导读.md › AFNetworking 源码导读 › 八、AFSecurityPolicy：HTTPS 证书校验（第940-958行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/foundation/performing-manual-server-trust-authentication.md › Performing manual server trust authentication › Overview › Evaluate the credential in the challenge（第93-97行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/security/preventing-insecure-network-connections.md › Preventing Insecure Network Connections › Overview › Ensure the Network Server Meets Minimum Requirements（第64-65行）
[7] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 4. URLSessionDelegate（第87-100行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/technotes/HTTPS Server Trust Evaluation.md › HTTPS Server Trust Evaluation › Appendix B: Glossary（第714-720行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/foundation/performing-manual-server-trust-authentication.md › Performing manual server trust authentication › Overview › Handle server trust authentication challenges（第49-56行）
