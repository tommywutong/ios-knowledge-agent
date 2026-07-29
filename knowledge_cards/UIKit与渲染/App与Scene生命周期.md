---
topic: App与Scene生命周期
group: UIKit与渲染
generated_at: 2026-07-29T19:53:14
provider: deepseek
---

# App与Scene生命周期

## 一句话总结
iOS 13+ 引入了基于 Scene 的生命周期管理方式，通过 `UISceneDelegate` 替代部分 `UIApplicationDelegate` 职责以支持多窗口场景；SwiftUI 的 `ScenePhase` 仅提供 active、inactive、background 三种状态，缺少首次启动和终止事件，因此在处理冷启动/终止等场景时需借助 `UIApplicationDelegate` 适配器或混合使用 UIKit 组件。[1][2][4][6]

## 核心原理

- **生命周期代理模式**：App 和 Scene 的生命周期通过委托（Delegate）模式实现回调，`UIApplicationDelegate` 和 `UISceneDelegate` 是标准接口。[8]
- **iOS 13+ 场景化变革**：从 iOS 13 开始，Apple 引入 Scene-based 生命周期，每个 Scene 有独立的激活状态，支持多窗口场景。[6]
- **Scene 的状态机**：每个 Scene 可处于 Unattached、Foreground Inactive、Foreground Active、Background、Suspended 五种状态，且互相独立。[12]
- **核心回调方法**：
  - `UIApplicationDelegate` 中：`application:didFinishLaunchingWithOptions:`（启动完成）、`applicationWillTerminate:`（即将终止）、`application:configurationForConnecting:options:`（为新 Scene 提供配置）、`application:didDiscardSceneSessions:`（丢弃场景会话）。[1]
  - `UISceneDelegate` 中：`scene:willConnectTo:options:`（连接 Scene）、`sceneDidDisconnect:`（断开连接）、`sceneDidBecomeActive:`（变为活跃）、`sceneWillResignActive:`（即将非活跃）、`sceneWillEnterForeground:`（即将进入前台）。[1]
- **SwiftUI 生命周期方案**：SwiftUI 使用 `@main` 和 `App` 协议定义应用入口，但 `App` 的生命周期管理能力不如 `UIApplicationDelegate` 灵活。实际开发中常将两者结合使用。[4][10]
- **@UIApplicationMain 废弃**：Swift 5.x 起编译器推荐用 `@main` 替代 `@UIApplicationMain`，Swift 6 后原属性将被视为错误。[10]
- **后台 URLSession 生命周期**：后台网络任务的完成回调通过 `application:handleEventsForBackgroundURLSession:completionHandler:` 和 `urlSessionDidFinishEvents(forBackgroundURLSession:)` 处理。[7]

## 关键细节与易错点

- **`ScenePhase` 的局限性**：SwiftUI 提供的 `ScenePhase` 仅有 `active`、`inactive`、`background` 三个状态，没有 `didLaunch` 和 `willTerminate` 事件。试图从这三个状态推断冷启动、热恢复或终止非常困难且易出错。[2]
- **冷启动 vs 后台恢复**：在 UIKit 中可以通过 `application:didFinishLaunchingWithOptions:` 区分冷启动（`launchOptions` 为 nil 时通常是冷启动，但需结合具体场景）；在 SwiftUI 中 `ScenePhase` 无法直接区分，需要借助 `UIApplicationDelegate` 适配器或手动记录状态。[1][2]
- **多 Scene 独立性**：每个 Scene 有自己的生命周期回调，例如一个 Scene 在前台活跃时另一个 Scene 可能处于后台挂起状态。[12]
- **Scene 断开 ≠ 终止**：`sceneDidDisconnect:` 不代表 Scene 被销毁，系统可能暂时断开连接以回收资源，后续仍可能重新连接。[1]
- **SwiftUI 与 UIKit 混合使用**：可以通过 `UIApplicationDelegateAdaptor` 在 SwiftUI 应用中引入传统的 App Delegate，从而获得完善的启动/终止回调。[1]
- **后台任务回调**：使用 `NSURLSession` Background Configuration 时，必须在 App Delegate 中实现 `handleEventsForBackgroundURLSession` 保存 completionHandler，否则系统不会调用 session delegate 的回调。[7]

## 高频追问

**1. ScenePhase 有哪些状态？为什么说它不够用？**
ScenePhase 只有 active、inactive、background 三种状态。[2] 它缺少 `didLaunch` 和 `willTerminate` 事件，因此无法区分首次冷启动和从后台返回活跃，也无法区分进入后台和即将终止。[2] 这在需要根据启动类型（如打点、恢复状态）做不同处理的场景下造成困难。

**2. iOS 13 前后 App 生命周期有什么区别？**
iOS 13 之前通过 `UIApplicationDelegate` 集中管理 App 生命周期（如 didFinishLaunching、didEnterBackground 等）。[8] iOS 13 后引入 `UISceneDelegate`，每个 Scene 有独立的生命周期回调（如 sceneDidBecomeActive、sceneDidEnterBackground），支持多窗口。[6] App Delegate 仍保留全局回调（如 didFinishLaunching、willTerminate），但部分职责下放给 Scene Delegate。[1]

**3. 如何在 SwiftUI 中实现冷启动/终止的检测？**
SwiftUI 的 `ScenePhase` 无法直接提供此能力。使用 `UIApplicationDelegateAdaptor` 在 SwiftUI 中集成传统的 App Delegate（如代码片段中的 `UIAppDelegate`），在其中实现 `application(_:didFinishLaunchingWithOptions:)` 和 `applicationWillTerminate(_:)` 即可获得准确的启动和终止事件。[1][2]

**4. @UIApplicationMain 和 @main 有什么关系？**
`@UIApplicationMain` 是早期 Swift 中用于声明 App 入口的 property wrapper，它自动生成 `UIApplicationMain` 调用。Swift 5.x 起 Apple 提案将其废弃，推荐使用通用的 `@main` 属性，未来版本中 `@UIApplicationMain` 将产生编译错误。[10] 使用 `@main` 时，需要手动在 `AppDelegate` 类上添加 `@main`，或者通过 SwiftUI 的 `@main struct MyApp: App` 方式。

**5. 后台 URLSession 任务完成后如何恢复 App？**
系统会通过调用 `application(_:handleEventsForBackgroundURLSession:completionHandler:)` 通知 App。[7] 你需要在 App Delegate 中保存 completionHandler，并在 `URLSessionDelegate` 的 `urlSessionDidFinishEvents(forBackgroundURLSession:)` 方法中调用该 completionHandler 以更新 UI。[7] 注意 completionHandler 必须在主线程中调用。

## 原始资料索引

[1] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/jessesquires/swiftui-app-lifecycle-issues-with-scenephase-and-using-appdelegate-adaptors.md › Using app delegate adaptors (and their issues)（第233-284行）
[2] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/jessesquires/swiftui-app-lifecycle-issues-with-scenephase-and-using-appdelegate-adaptors.md › Limitations of `ScenePhase` events (and view lifecycle events)（第19-23行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/jessesquires/is-swiftui-ready.md › What should you expect? › * * *（第66-72行）
[6] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/生命周期.md › iOS中的生命周期 › 应用生命周期（App Lifecycle） › UISceneDelegate 方法（iOS 13+）（第74-76行）
[7] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/耗电/耗电-网络优化.md › 耗电-网络优化 › 三、后台下载：使用NSURLSession的BackgroundConfiguration › 后台Session的生命周期（第149-167行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/design-patterns/代理模式.md › 代理模式 › 三、使用场景对比 › Delegate Pattern 使用场景（第708-716行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/oss/swift-evolution/proposals/0383-deprecate-uiapplicationmain-and-nsapplicationmain.md › Deprecate @UIApplicationMain and @NSApplicationMain › Detailed design（第49-74行）
[12] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/生命周期.md › iOS中的生命周期 › 应用生命周期（App Lifecycle） › UISceneDelegate 方法（iOS 13+） › Scene的状态（第137-147行）
