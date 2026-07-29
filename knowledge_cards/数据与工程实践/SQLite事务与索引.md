---
topic: SQLite事务与索引
group: 数据与工程实践
generated_at: 2026-07-29T20:01:13
provider: deepseek
---

# SQLite事务与索引
## 一句话总结
SQLite通过**日志模式**（WAL或回滚日志）实现事务原子性，WAL模式允许多读单写并发，是iOS推荐选择；索引本质是B-Tree，以O(log N)加速查找，但需避免在低选择性、小数据量或频繁更新的列上滥用。

## 核心原理
- **事务原子性与日志模式**：SQLite的原子提交和回滚通过**日志模式**实现[10]。默认**回滚日志模式**（Rollback Journal）：写入前将原始页面复制到日志文件，修改数据库文件，提交时删除日志；崩溃时用日志恢复[3]。**WAL模式**（Write-Ahead Logging）：写入者将修改追加到WAL文件，不直接修改数据库文件；提交时在WAL文件头部标记提交点；读取者先查WAL文件获取最新内容[6][7]。Checkpoint操作将WAL内容合并回主库，默认阈值为1000个变更页面（约4MB）[1][6][7]。
- **WAL模式的并发语义**：WAL模式下，**多个读取者与一个写入者可以同时访问**数据库，读取者看到的是最近一次提交前的一致性快照，写入操作不阻塞读取[3][6][7]。注意：**仍然只允许一个写入者**，多个写入者会串行等待[3][6]。WAL模式相比回滚日志减少磁盘写入和`fsync`调用，效率更高[4][6]。
- **索引加速原理**：没有索引时，数据库进行全表扫描（O(N)）。索引是一棵独立的B-Tree，将被索引列的值按顺序组织，树高度极低（百万级数据通常3~4层），查找任意值只需3~4次节点比较，时间复杂度O(log N)[5][8]。
- **部分索引（Partial Index）**：使用WHERE子句描述索引作用范围，只对符合条件的行建立索引，既能享受索引收益，又免去索引维护开销[9]。

## 关键细节与易错点
- **WAL相关文件**：WAL模式下数据库目录生成三个文件：`*.db`（主库）、`*.db-wal`（WAL日志）、`*.db-shm`（共享内存）[2]。**三个文件共同组成数据库完整状态**，拷贝或移动时需三者同时拷贝，或先执行`PRAGMA wal_checkpoint(TRUNCATE)`将WAL内容合并到主库，再使用SQLite Online Backup API[1][2]。实验表明只拷贝`.db`会丢失WAL中的页面，导致表结构缺失[2]。
- **网络文件系统限制**：WAL模式依赖`mmap`创建共享内存，仅当客户端在同一主机设备时有效，因此**WAL模式不能在网络文件系统上正常工作**，除非禁用共享内存[1][6][7]。iOS上需注意iCloud Drive或共享容器场景[1]。
- **自动checkpoint**：默认阈值1000页，写入快、读得少的场景下WAL文件会持续增长至阈值才回写[1]。最后一个连接关闭时，`-wal`和`-shm`文件会被自动删除[2]。
- **索引失效场景**：不该建索引的情况包括：低选择性列（如`is_deleted`只有0/1）、数据量很小的表（全表扫描本就很快）、写多读少的表（每次写入都要维护索引）、频繁更新的列（每次UPDATE触发索引重排）、查询条件中对列使用了函数（如`WHERE LOWER(name)`，索引存原始值无法命中）[5][8]。
- **覆盖索引（Covering Index）**：当查询所需的所有列都包含在索引中时，SQLite可直接通过索引返回数据，无需回表，效率远高于普通索引扫描[11][12]。可通过`EXPLAIN QUERY PLAN`验证，若输出`SEARCH TABLE ... USING COVERING INDEX`则命中覆盖索引[11][12]。
- **事务打包优化**：使用多条INSERT、UPDATE、DELETE语句组成**单个事务**，SQLite可以进行优化，减少磁盘写入[4][9]。WWDC建议尽可能使用多语句事务[9]。

## 高频追问
（以下问题均基于材料回答，材料未涉及的方面会标注“本卡片材料不足”）

**Q: WAL模式下为什么读取者看到的是一致性的快照？**
读取者在查找页面时，会先检查WAL日志文件以确保读取最新内容；但WAL提交时只修改文件头部的提交标记，读取者在该标记之前看到的是一致性快照[6][7]。材料未进一步解释快照隔离的实现细节，以上为材料直接描述。

**Q: WAL模式下如果copy只copy了.db文件会怎样？**
实验证明，只拷贝`.db`文件会导致数据丢失——连表结构都不存在，因为CREATE TABLE的页面可能仍在WAL中。必须三文件一起拷贝，或先checkpoint[1][2]。

**Q: 什么是部分索引？什么时候该用？**
部分索引使用`WHERE`子句限定索引范围，例如`CREATE INDEX idx_active ON users(age) WHERE active=1`。它适用于你只关心特定条件子集的行，可以减少索引维护开销，同时保持查询加速[9]。WWDC推荐在可行时使用部分索引替代普通索引[9]。

**Q: EXPLAIN QUERY PLAN输出中SCAN TABLE和SEARCH TABLE有什么区别？**
`SCAN TABLE`表示全表扫描或索引扫描（可能读取大量行），`SEARCH TABLE`表示通过索引快速查找（预计返回行数少）。使用覆盖索引时输出`SEARCH TABLE ... USING COVERING INDEX`，效率更高[11][12]。

**Q: WAL模式下checkpoint是如何触发的？默认阈值是多少？**
当WAL文件中的变更页面达到1000页时，会自动触发checkpoint将修改合并回主库文件[1][6][7]。也可以通过`PRAGMA wal_checkpoint(TRUNCATE)`手动触发[1]。

**Q: 索引为什么不能加快`LOWER(name)='test'`的查询？**
因为B-Tree索引存储的是原始值，函数调用会破坏索引的有序性，使得无法通过索引直接定位，导致全表扫描[5][8]。材料未提供解决方案，本卡片材料不足。

**Q: WAL模式下能否有多个写入者同时写入？**
不能。WAL模式仍然只允许一个写入者，多个写入者会串行等待[3][6]。SQLite在用户空间强制这一约束，但即使使用客户端-服务器数据库，文件系统或磁盘层面也往往只能处理一个并发写入者，所以对大多数用户不是问题[7]。本卡片材料未提及如何并行写入。

**Q: iOS上文件保护等级（如`NSFileProtectionComplete`）对SQLite WAL模式有何影响？**
材料中[2]提到待真机补测：设备锁屏后数据库文件不可读，后台任务里的读写会失败；App被挂起时若正持有写事务，`-wal`会残留。但材料明确表示“在macOS上无法复现”，且SQLite引擎本身在iOS和macOS上是同一套实现，上述关于事务、索引、WAL的结论不受平台影响[2]。因此该问题目前无肯定结论，需实测验证。

**Q: 什么情况下不该建索引？**
低选择性列（如布尔标志）、数据量很小的表、写多读少的表、频繁更新的列、查询条件中对列使用了函数[5][8]。

## 原始资料索引

[1] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS 数据库：SQLite 事务与索引、FMDB 的并发模型、Core Data 的代价.md › SQLite 事务与索引、FMDB 的并发模型、Core Data 的代价 › 参考资料 › 官方（第644-651行）
[2] /Users/tommywu/Obsidian/iOS/20 专题笔记/持久化与序列化/iOS 数据库：SQLite 事务与索引、FMDB 的并发模型、Core Data 的代价.md › SQLite 事务与索引、FMDB 的并发模型、Core Data 的代价 › 三、WAL：并发行为到底改了什么 › -wal 和 -shm（第238-281行）
[3] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的数据库.md › iOS中的数据库 › 三、SQLite——iOS数据库的基石 › 3.3 WAL模式与并发（第274-316行）
[4] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2019/419-optimizing-storage-in-your-app.md › Optimizing Storage in Your App › Transcript（第146-150行）
[5] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/README.md › awesome-ios-interview › iOS 相关面试题 › 数据持久化（第4163-4202行）
[6] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/bswanson.dev/exploring-sqlite-s-internals.md › Exploring SQLite's Internals › How SQLite transactions are atomic › Write-Ahead Logging (WAL)（第300-314行）
[7] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots-zh/bswanson.dev/exploring-sqlite-s-internals.md › 探索 SQLite 的内部机制 › SQLite 事务如何实现原子性 › 预写式日志（WAL）（第301-315行）
[8] /Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-basics/iOS中的数据库.md › iOS中的数据库 › 十一、常见面试问题（第1188-1204行）
[9] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/wwdc/en/wwdc2019/419-optimizing-storage-in-your-app.md › Optimizing Storage in Your App › Transcript（第182-190行）
[10] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/snapshots/bswanson.dev/exploring-sqlite-s-internals.md › Exploring SQLite's Internals › How SQLite transactions are atomic（第264-274行）
[11] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/en/objcio/on-using-sqlite-and-fmdb-instead-of-core-data.md › Performance Tips › Real-Life Example（第345-381行）
[12] /Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault/blogs/zh/objccn/用-sqlite-和-fmdb-替代-core-data.md › 性能技巧 › 真实的例子（第355-391行）
