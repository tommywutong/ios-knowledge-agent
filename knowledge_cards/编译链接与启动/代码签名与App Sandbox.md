---
topic: 代码签名与App Sandbox
group: 编译链接与启动
generated_at: 2026-07-29T19:49:27
provider: deepseek
---

# 代码签名与App Sandbox
## 一句话总结
代码签名（Code Signing）确保应用内容未被篡改，而 App Sandbox 限制应用对系统资源的访问；两者通过 entitlements 紧密绑定，且必须同时启用——未签名代码无法被沙盒化 [1][7][8]。

## 核心原理
- **沙盒与代码签名的分工**：代码签名用于验证应用仅包含它声称的内容，沙盒则限制对系统资源的访问。两者协同工作，均可阻止代码运行，日常开发中沙盒更常引发问题 [1]。
- **Entitlements 的存储方式**：所有 entitlements（包括启用 App Sandbox 的 `com.apple.security.app-sandbox`）都物理存储在应用的代码签名中，并由签名密封（sealed）[9][7]。系统信任签名中的 entitlements 即为开发者预期的资源请求 [9]。
- **App Sandbox 强制依赖代码签名**：没有代码签名的应用无法被沙盒化，因为系统无法明确识别应用身份，而 entitlements 自身也存在于签名中 [7][8]。macOS 强制将应用的容器（container）与代码签名绑定，确保其他沙盒应用无法访问该容器 [7]。
- **代码签名中 entitlements 的双重存在**：app 内的 entitlements 存在于两处（例如二进制和嵌入的签名结构中），它们必须匹配或兼容，否则会导致验证失败 [10]。
- **运行时检查沙盒状态**：可通过 Security 框架的 `SecStaticCodeCheckValidityWithErrors()` 函数并传入基于代码签名需求语言（Code Signing Requirement Language）的额外需求（如 `entitlement["com.apple.security.app-sandbox"] exists`）来判断应用是否沙盒化 [3]。
- **命令行工具 `codesign`**：使用 `codesign --display --verbose=4` 可显示签名详情（标识符、格式、运行期标志、签名权威等）；使用 `codesign --display --entitlements -` 可查看嵌入的 entitlements 属性列表 [4][5]。

## 关键细节与易错点
- **Provisioning Profile 的作用**：它是将签名、entitlements 和沙盒绑定在一起的容器，包含操作系统决定能否运行应用所需的信息 [2]。它以 CMS（Cryptographic Message Syntax）格式编码并由 Apple 签名，可通过 `security cms -D -i example.mobileprovision` 解码查看 [11]。
- **App ID 硬编码问题**：构建时使用的 provisioning profile 的 App ID 会硬编码到二进制文件中；若后续使用不同 App ID 的 profile 重新签名，二进制中的 App ID 将不再匹配，可能引发 keychain 访问、推送通知、应用内购买等服务的异常 [12]。
- **Helper Tool 的沙盒 entitlements 要求**：在沙盒化应用中嵌入命令行工具时，工具应仅包含 `com.apple.security.app-sandbox` 和 `com.apple.security.inherit` 两个 entitlements；添加其他 entitlements 可能导致工具立即崩溃（代码签名错误）[5]。
- **Associated Domains entitlements 配置**：在 Xcode Capabilities 中启用 Associated Domains 后，会生成 .entitlements 文件，需要指定服务前缀（如 `webcredentials:`, `applinks:`, `activitycontinuation:`）和域名 [6]。
- **沙盒与代码签名的常见错误**：沙盒比代码签名更常干扰日常开发，通常由 entitlements 引起 [1]。

## 高频追问
1. **如何判断一个 app 是否启用了沙盒？**
   可在代码中使用 `SecStaticCodeCheckValidityWithErrors()` 并传入需求 `entitlement["com.apple.security.app-sandbox"] exists` [3]；也可在命令行使用 `codesign --display --entitlements -` 查看是否包含该 entitlement [4]。

2. **未签名的 app 能否被沙盒化？**
   不能。未签名代码无法被沙盒化，因为 entitlements（包括启用沙盒的 entitlement）存储在代码签名中，且系统无法识别未签名应用的身份 [7][8]。材料明确陈述："unsigned code is not sandboxed" [7]。

3. **重新签名时使用不同的 provisioning profile 会有什么风险？**
   构建时所用的 provisioning profile 的 App ID 会硬编码到二进制中。若后续用不同 App ID 的 profile 重新签名，二进制中的 App ID 与 profile 的 App ID 不匹配，会导致 keychain 访问、推送通知、应用内购买等服务失效 [12]。应确保 resign 时使用相同 App ID 的 profile。

4. **如何查看 provisioning profile 的内容？**
   provisioning profile 以 CMS 格式编码，可以使用 `security cms -D -i [profile文件名]` 解码为 XML 格式的属性列表进行查看 [11]。

5. **沙盒化应用的 helper tool 需要哪些 entitlements？**
   只需 `com.apple.security.app-sandbox` 和 `com.apple.security.inherit` 两个 entitlements。添加其他 entitlements 会导致工具在运行时立即崩溃（代码签名错误）[5]。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/inside-code-signing.md › Entitlements and Provisioning（第134-134行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/inside-code-signing.md › Entitlements and Provisioning › Provisioning Profiles（第179-189行）
[3] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/checking-code-signing-and-sandboxing-status-in-code.md › Doing it in Code › Additional Requirements for the Signature (Sandboxing)（第110-119行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/checking-code-signing-and-sandboxing-status-in-code.md › The codesign Utility（第26-46行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/apple-docs/en/xcode/embedding-a-helper-tool-in-a-sandboxed-app.md › Embedding a command-line tool in a sandboxed app › Overview › Build and validate（第148-157行）
[6] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/Password AutoFill 的使用.md › 2. 设置 app、域名相互关联 › 2.6 添加 associated domains entitlement（第218-252行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/documentation/Security/App Sandbox Design Guide/App Sandbox in Depth.md › App Sandbox in Depth › App Sandbox and Code Signing（第294-300行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/documentation/Mac OSX/Mac Technology Overview/Core OS Layer.md › Core OS Layer（第30-39行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/documentation/Security/Code Signing Guide/Understanding the Code Signature.md › Understanding the Code Signature（第67-74行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/technotes/Troubleshooting Failed Signature Verification/Troubleshooting Failed Signature Verification.md › Troubleshooting Failed Signature Verification › Resolving Signature Verification Failure › Code Signing Entitlements Troubleshooting（第153-155行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/inside-code-signing.md › Entitlements and Provisioning › Provisioning Profiles（第191-201行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/oleb/code-signing-changes-in-xcode-4.md › Step by Step Guide to Code Signing with Xcode 4（第38-44行）
