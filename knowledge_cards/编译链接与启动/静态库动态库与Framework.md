---
topic: 静态库动态库与Framework
group: 编译链接与启动
generated_at: 2026-07-29T19:49:09
provider: deepseek
---

# 静态库动态库与Framework

## 一句话总结

静态库在编译期被链接进主二进制，动态库在运行时由动态链接器加载；Framework是一种包含动态库或静态库、头文件、资源的包结构，iOS上存在静态Framework和动态Framework，而XCFramework是多平台分发容器。[2][4][5]

## 核心原理

### 库（Library）与框架（Framework）的定义
- **库**：预编译的代码集合，分为静态库（`.a`）和动态库（`.dylib`）。
- **框架**：Apple平台上的一个捆绑包（bundle），可包含动态库、头文件和资源。传统上Framework内含动态库，但iOS上也可以创建静态Framework（即包含静态库而非动态库的Framework）。[5][6]
- **XCFramework**：一种用于分发多平台（iOS、macOS等）二进制文件或库的容器格式，可包含多个架构/平台的变体。[2]

### 链接时机
- **静态链接**：发生在构建过程（build process）中，静态库的代码被复制到最终的可执行文件（app binary）中，运行时不再需要该库文件。[4]
- **动态链接**：发生在运行时，动态库由动态链接器（dyld）在启动时加载；动态库本身是一个独立的Mach-O映像，其依赖的库也由动态链接器递归解析。[11]

### iOS与macOS的差异
- iOS最初不允许使用自定义动态库（仅系统框架），后来通过Embedded Framework（嵌入到App包中的动态Framework）支持，但受代码签名限制，动态库必须在主App中嵌入且由App签名。[2][7]
- macOS上动态库可以放在标准系统路径，多个应用共享。[2]

### 静态与动态的权衡：包体积与启动时间
- **静态库**：代码进入主二进制，增加包体积；但启动时无需加载额外dylib，所以启动时间更快。[4][9]
- **动态库**：代码独立于主二进制，不直接增加主二进制体积（但动态库本身仍占用App包空间）；运行时需要加载，会增加启动时间（特别是大量动态库时）。[4][9]
- iOS 13引入了自定义动态框架缓存，但将动态库改为静态库后仍可能获得性能收益。[8]

## 关键细节与易错点

### “静态/动态”不是文件后缀，而是链接方式
- 同一个`.a`文件可以被静态链接，`.dylib`是动态库；但Framework既可以包含静态库也可以包含动态库。不能仅凭后缀或文件类型判断链接方式，需看链接命令或产物。[2][5]

### 动态库的“install name”
- 每个动态库在其Mach-O头中记录一个“install name”（规范路径），运行时动态链接器根据该路径查找库文件。`otool -L`可以查看动态库的依赖及其install name。[12]

### 名称冲突与“静态Framework”的真实性
- 虽然传统上Framework应包含动态库，但iOS上可以创建静态Framework（即把静态`.a`打包成Framework结构）。实际开发中，通过CocoaPods的`use_frameworks!`或SwiftPM的`type: .static`可以生成静态Framework。[4][5][10]

### 默认链接行为
- Xcode在处理Swift Package时，默认选择静态库。如果需要动态库，需在`Package.swift`中显式指定`type: .dynamic`。[10]

### 多二进制共享动态库
- 动态库的一个主要优势是可以在不同二进制之间共享内存和资源（如App与Extension之间），从而减少总包体积。这是一种常见的优化手段。[9][10]

## 高频追问

### Q1：动态库一定比静态库慢吗？为什么？
**A**：动态库在启动时需要由dyld加载，因此通常比静态库启动慢；但iOS 13后的缓存机制部分缓解了问题。静态库因为代码已在主二进制中，无需运行时加载，所以启动更快。[8][9][11]

### Q2：Framework一定是动态的？
**A**：不一定。传统macOS上Framework默认包含动态库，但在iOS上可以创建静态Framework，其中包含静态库而非动态库。静态Framework本质上是将静态库包装成Framework格式，便于管理头文件和资源。[5]

### Q3：SwiftPM如何控制链接方式？
**A**：通过在`Package.swift`的`.library`产品中指定`type: .static`或`type: .dynamic`。若不指定，Xcode默认选择静态库。[10]

### Q4：什么是XCFramework？和普通Framework有何区别？
**A**：XCFramework是一个分发格式，用于打包多个平台或架构的二进制文件（可同时包含静态库和动态库）。普通Framework通常只针对单一平台和架构。XCFramework解决的是多平台分发问题，而非链接方式。[2]

### Q5：能否在iOS中使用不嵌入到App包中的动态库？
**A**：不能。iOS上所有自定义动态库必须嵌入到App包（或框架包）中，由App签名控制，无法像macOS那样从系统路径加载。[2][7]

## 原始资料索引

[2] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第七周：编译、链接、Mach-O、dyld 与 App 启动 › 本周精读路线 › Day 3｜静态/动态不是文件后缀问答（对应 W1-09）（第717-728行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/emergetools/emerge-tools-blog-static-vs-dynamic-frameworks-on-ios-a-discussion-with-chatgpt.md › Static vs Dynamic Frameworks on iOS — a discussion with ChatGPT › [Static vs dynamic frameworks](https://www.emergetools.com/blog/posts/static-vs-dynamic-frameworks-ios-discussion-chat-gpt#static-vs-dynamic) › [Intro](https://www.emergetools.com/blog/posts/static-vs-dynamic-frameworks-ios-discussion-chat-gpt#intro)（第33-37行）
[5] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ddeville.me/dynamic-linking-on-ios.md › Library linking › Framework（第39-43行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/bpoplauschi.github.io/introduction-to-static-vs-dynamic-libraries-and-frameworks-on-ios-and-macos.md › Introduction to Static vs Dynamic libraries and frameworks on iOS (and macOS) › Introduction（第23-36行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/ddeville.me/dynamic-linking-on-ios.md › Dynamic libraries on iOS › Building a dynamic library on iOS（第255-265行）
[8] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/avanderlee.com/app-launch-time-7-tips-to-increase-performance.md › 4: Manage frameworks using DYLD statistics（第117-133行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/emergetools/emerge-tools-blog-static-vs-dynamic-frameworks-on-ios-a-discussion-with-chatgpt.md › X-Ray › [Summary](https://www.emergetools.com/blog/posts/static-vs-dynamic-frameworks-ios-discussion-chat-gpt#summary)（第183-197行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/emergetools/emerge-tools-blog-make-your-ios-app-smaller-with-dynamic-frameworks.md › Make Your iOS App Smaller with Dynamic Frameworks › [Making a Dynamic Framework with SwiftPM](https://www.emergetools.com/blog/posts/make-your-ios-app-smaller-with-dynamic-frameworks#making-a-dynamic-framework-with-swiftpm)（第79-113行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/pewpewthespells.com/static-and-dynamic-libraries.md › Static and Dynamic Libraries › Dynamic Linking › • Linking（第150-154行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/mikeash/friday-q-a-2011-12-02-object-file-inspection-tools.md › (全文)（第112-128行）
