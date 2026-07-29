---
topic: UserDefaults与Keychain
group: 数据与工程实践
generated_at: 2026-07-29T20:00:24
provider: deepseek
---

# UserDefaults与Keychain

## 一句话总结

UserDefaults是适合存储少量简单配置数据（几KB到几十KB）的轻量级KV存储，底层以plist格式序列化到磁盘[2]；Keychain是iOS提供的系统级安全存储方案，数据受iOS Data Protection机制保护，使用AES加密，适合存储敏感数据如密码[1]。

## 核心原理

### UserDefaults

**存储机制**：底层将数据以plist格式序列化到磁盘；启动时系统将整个plist文件反序列化到内存中的一个`NSDictionary`；读操作直接访问内存字典，写操作先修改内存字典，再由系统择机将整个字典序列化写回磁盘[2]。

**性能特点**：
- 首次访问时加载整个plist到内存，文件越大启动越慢
- 读取O(1)（内存字典查找）
- 写入时将整个字典重新序列化，单次写入的数据量与总数据量成正比[2]

"落盘不及时会丢"的担忧被实验拆解：进程被`kill -9`之后（退出码137），磁盘上确实还没有值，但另一个进程经`NSUserDefaults`立刻就读到了刚写的内容——数据在`cfprefsd`手里，不在进程里。真正会丢的场景只剩整机断电或内核panic，且刚好落在十秒窗口里[3]。`setObject:forKey:`返回时磁盘上什么都没有，稳态要等十秒，`synchronize`一毫秒都没提前，落盘时是临时文件加rename，每次都换inode[6]。

**适用边界**：适合存储少量简单配置数据（几KB到几十KB）。当数据量超过几百KB，或需要频繁写入时，应考虑MMKV等替代方案[2]。整域100 KB的线是硬的，因为改一个字段会整个文件重写[3]。

### Keychain

**存储机制**：数据存储在系统级的SQLite数据库中（`/var/Keychains/keychain-2.db`），由`securityd`守护进程管理[1]。系统使用设备唯一密钥（UID Key，烧录在芯片中）和用户密码派生的密钥构成分层加密体系，对Keychain条目进行AES加密[1]。

**核心特性**：
- 支持Access Control——可要求生物认证（Face ID/Touch ID）才能读取，此时密钥操作由Secure Enclave执行[1]
- App卸载后Keychain数据默认保留（iOS会保留非`ThisDeviceOnly`的条目，重装App后仍可访问）[1]
- 通过Keychain Sharing可在同一开发者的不同App间共享数据[1]
- Default session会将凭据（credential）保存到用户keychain[5]

**保护级别**：`kSecAttrAccessible`有六个等级，差别全在"什么时候能读到"和"会不会跟着备份走"两个维度上[11]：
- `kSecAttrAccessibleWhenUnlocked`：仅在设备解锁时可访问；建议仅在前台时需要的条目；使用加密备份时会迁移到新设备
- `kSecAttrAccessibleAfterFirstUnlock`：设备重启后首次解锁后可访问；建议后台应用需要的条目；使用加密备份时会迁移
- `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly`：要求设备设有密码；永远不会迁移到新设备；设备没有密码时不可用；禁用密码会导致此前受保护条目被删除
- `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` / `AfterFirstUnlockThisDeviceOnly`：语义同前两条，但不会迁移到新设备
- `kSecAttrAccessibleAlways` 和 `AlwaysThisDeviceOnly`：从iOS 12/macOS 10.14起已废弃，替代建议是`kSecAttrAccessibleAfterFirstUnlock`[11]

## 关键细节与易错点

### UserDefaults

- **数据持久化的真实代理**：`setObject:forKey:`返回时磁盘上什么都没写，数据在`cfprefsd`进程中，稳态等待约十秒[6]。但进程被SIGKILL也不会丢失，仅整机断电或内核panic且在十秒窗口内才可能丢[3]
- **`registerDefaults:`特殊行为**：`registerDefaults:`的值永远不进plist，每次启动都得重新调[6]
- **类型限制**：plist只认六种Property List类型（`NSData`、`NSString`、`NSNumber`、`NSDate`、`NSArray`、`NSDictionary`）[2]；`NSNull`和`NSSet`都会导致`NSInvalidArgumentException`崩溃[6]
- **写入格式**：默认写XML，比二进制大4.63倍，而系统给自己写的`Preferences`全是`bplist00`[6]
- **自定义对象存储**：自定义对象需要先转换为`Data`（通过`NSCoding`或`Codable`）[2]
- **存储上限**：合理上限约100 KB（整域重写线），超过时应考虑其他方案[2][3]
- **不需要手动同步**：`synchronize()`在iOS 12+已不需要手动调用，调用也不会有提前效果[2][6]

### Keychain

- **主键构成**：`kSecClassGenericPassword`的主键包含`kSecAttrService`和`kSecAttrAccount`，但不包含`kSecAttrLabel`；同样的service和account、只改label仍然报重复[12]
- **无upsert操作**：Keychain没有upsert；重复`SecItemAdd`返回`errSecDuplicateItem`（-25299），不会覆盖；正确写法是先`SecItemUpdate`，拿到`errSecItemNotFound`（-25300）再`SecItemAdd`；或先无脑`SecItemDelete`再`Add`，后者会丢失创建时间等属性[12]
- **`kSecAttrAccessible`传统钥匙串行为**：`kSecAttrAccessible`在传统钥匙串上读回来是`(null)`，它是数据保护钥匙串的概念，传统钥匙串的访问控制走另一套（ACL加上钥匙串本身是否解锁）[12]
- **保护等级与备份**：`ThisDeviceOnly`后缀的条目不会随备份迁移到新设备；部分等级要求设备设有密码，禁用密码会导致条目被删除[11]
- **卸载保留**：App卸载后，非`ThisDeviceOnly`的Keychain条目默认保留，重装App后仍可访问[1]
- **密码存储的官方推荐**：需要使用密码的场景，应使用Keychain Services，不推荐iCloud存储API[7]

## 高频追问

### Q1：为什么不能用UserDefaults存密码？

因为UserDefaults是轻量级配置存储，数据以plist格式明文序列化到磁盘，缺乏系统级加密保护。Keychain是系统级安全存储，使用AES加密和iOS Data Protection机制保护敏感数据[1]；Apple官方文档明确要求"密码不进UserDefaults"[4]；如果应用需要存储密码，正确的API是Keychain Services[7]。

### Q2：UserDefaults写入后需要调用`synchronize()`吗？

不需要。iOS 12+系统会自动同步，手动调用`[NSUserDefaults synchronize]`没有任何加速效果，一毫秒都不会提前[2][6]。即使进程被SIGKILL也不会丢失数据，因为数据在`cfprefsd`守护进程中[3][6]。

### Q3：Keychain在App卸载后数据会保留吗？

默认会保留（非`ThisDeviceOnly`的条目）。iOS会保留Keychain数据，重装App后仍可访问[1]。带`ThisDeviceOnly`后缀的保护级别则不会随备份迁移到新设备[11]。

### Q4：UserDefaults存自定义对象应该怎么做？

UserDefaults只支持六种Property List类型，自定义对象需要先转换为`NSData`再存储：通过`Codable`（使用`JSONEncoder`）或`NSCoding`协议归档，且为安全应实现`NSSecureCoding`防止反序列化时被注入恶意类[2][10]。

### Q5：Keychain的`kSecAttrAccessible`六个等级怎么区分？

六个等级的差别在"什么时候能读到"和"会不会跟着备份走"两个维度上[11]：是否要求设备解锁才能访问（WhenUnlocked / AfterFirstUnlock / Always（已废弃）），以及是否带`ThisDeviceOnly`后缀（不影响访问时间，但影响备份迁移行为）[11]。

### Q6：Keychain的主键由哪些属性组成？为什么两个看似不同的条目会冲突？

`kSecClassGenericPassword`的主键包含`kSecAttrService`和`kSecAttrAccount`，但不包含`kSecAttrLabel`；同样的service和account、只改label仍然报重复（`errSecDuplicateItem`）[12]。

### Q7：Keychain支持upsert吗？

不支持。重复`SecItemAdd`会返回`errSecDuplicateItem`（-25299），不会自动覆盖。正确做法是先尝试`SecItemUpdate`，若返回`errSecItemNotFound`再`SecItemAdd`；或先`SecItemDelete`再`Add`（后者会丢失创建时间等属性）[12]。

### Q8：Keychain在大批量场景下应该注意什么？

Keychain内置支持批量操作：`SecItemDelete`的查询字典只需指定`kSecClass`和`kSecAttrService`而不给具体的account，即可一次删除整个service下的所有记录[12]；支持按属性匹配，不需要遍历[12]。

## 原始资料索引

[1] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的数据库.md › iOS中的数据库 › 二、轻量级KV存储 › 2.2 Keychain（第93-129行）
[2] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的数据库.md › iOS中的数据库 › 二、轻量级KV存储 › 2.1 UserDefaults（第55-91行）
[3] /Users/tommywu/Obsidian/iOS/20 专题笔记/架构与网络/iOS 综合项目设计文档：把这个系列用一遍.md › 综合项目设计文档：把这个系列用一遍 › 五、这个设计里有争议的六处 › 争议四：收藏用 `NSUserDefaults` 还是文件（第398-406行）
[4] /Users/tommywu/Desktop/26暑期内容/2026 暑假 iOS 底层学习计划.md › 2026 暑假 iOS 底层学习计划 › 第八阶段：持久化、序列化、源码、架构与网络串联（建议 10 天） › 本阶段精读路线 › Day 1｜先做存储选择，不先钻数据库实现（对应 W3-10）（第800-812行）
[5] /Users/tommywu/Desktop/26暑期内容/tips-master/sources/URLSession详解.md › 2. URLSessionConfiguration › 2.1 default（第43-45行）
[6] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain.md › 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain › 总结（第624-636行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault/documentation/General/iCloud Design Guide/iCloud Fundamentals (Key-Value and Document Storage).md › iCloud Fundamentals (Key-Value and Document Storage)（第237-243行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/converted/summer2026/iOS记忆提纲.md › (全文)（第4395-4441行）
[11] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain.md › 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain › 八、Keychain：四件套跑通了，但只跑通了一半 › `kSecAttrAccessible` 的六个等级（第556-573行）
[12] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain.md › 持久化选型：沙盒、plist、NSUserDefaults 与 Keychain › 八、Keychain：四件套跑通了，但只跑通了一半（第531-554行）
