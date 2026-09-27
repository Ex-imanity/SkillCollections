# 操作组合矩阵：AI 搜索 · 单条回答卡片（带图问答 + 加入错题本）

## 1. 覆盖检查

### 孤儿写入点（0）

无。

### 孤儿读取点（0）

无。

### 空原子（0）

无。

### 读写集完全相同的原子（1 组，未指定代表 0 组）

读写集相同意味着对共享状态是同一个动作。给变体标 `represented_by`，组合时只保留代表；变体仍需单独覆盖它自己的入口可见性和交互。
- `A2` 重新生成 ≡ `A2b` 跳过深度思考


### 缺少层信息的读写点（0）

无。

### 替换型原子漏写的字段

- `A2` 重新生成 替换 `msg`，但没有重写：`msg.extData.feedback`、`msg.mistakeMessage`。逐个判定：本应重置（缺陷候选）还是有意保留（写明理由）

### 隐式动作清单未作答或答案无效（0/10）

全部已作答。

## 2. 两两有序组合（A 先 → B 后）

共 49 个有序对（含同一动作重复）：创建动作排在后面不成立 **7** 对，无任何依赖标记已剪枝 **14** 对，剩余 **28** 对待分析。

依赖标记：RAW / WAW / RACE / LAYER 要求 A 的写与 B 的读写在同一字段上相交；STALE 不要求相交——A 替换了实体、B 读该实体里 A 没重写的字段即成立。

分值只用于排序：STALE 5 / RACE 4 / LAYER 4 / WAW 3 / RAW 1。RAW 单独出现通常只是「正常的先写后读」，但仍需确认 B 读到的是 A 写的值。

| 分 | A → B | 标记 |
|---|---|---|
| 21 | `A0` 带图提问 → `A2` 重新生成 | **RAW** msg.content<br>**RACE** msg.content：A0 对 hbase 是异步写，A2 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑<br>**RAW** regenCache.request<br>**WAW** mem.card<br>**WAW** mem.mistakeMessage<br>**WAW** msg.content<br>**WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 19 | `A2` 重新生成 → `A3` 退出搜索页再重进 | **RAW** msg.content<br>**RAW** msg.extData.mistakeBook<br>**RAW** msg.siblingCards<br>**WAW** mem.card<br>**WAW** mem.mistakeMessage<br>**STALE** msg.extData.feedback：A2 替换了 msg 却没重写该字段，A3 读到的是替换前的旧值<br>**STALE** msg.mistakeMessage：A2 替换了 msg 却没重写该字段，A3 读到的是替换前的旧值 |
| 18 | `A0` 带图提问 → `A4` 加入错题本 | **RAW** mem.card<br>**RAW** mem.mistakeMessage<br>**RAW** msg.content<br>**RACE** msg.content：A0 对 hbase 是异步写，A4 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑<br>**RAW** msg.siblingCards<br>**RACE** msg.siblingCards：A0 对 hbase 是异步写，A4 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑<br>**WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 17 | `A0` 带图提问 → `A1` 点赞/点踩 | **RAW** mem.card<br>**RAW** msg.content<br>**RACE** msg.content：A0 对 hbase 是异步写，A1 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑<br>**RAW** msg.siblingCards<br>**RACE** msg.siblingCards：A0 对 hbase 是异步写，A1 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑<br>**WAW** msg.content<br>**WAW** msg.siblingCards |
| 16 | `A2` 重新生成 → `A2` 重新生成 | **RAW** msg.content<br>**WAW** mem.card<br>**WAW** mem.mistakeMessage<br>**WAW** msg.content<br>**WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 11 | `A1` 点赞/点踩 → `A1` 点赞/点踩 | **RAW** msg.content<br>**RAW** msg.siblingCards<br>**WAW** msg.content<br>**WAW** msg.extData.feedback<br>**WAW** msg.siblingCards |
| 10 | `A0` 带图提问 → `A3` 退出搜索页再重进 | **RAW** msg.content<br>**RAW** msg.extData.mistakeBook<br>**RAW** msg.mistakeMessage<br>**RAW** msg.siblingCards<br>**WAW** mem.card<br>**WAW** mem.mistakeMessage |
| 10 | `A2` 重新生成 → `A4` 加入错题本 | **RAW** mem.card<br>**RAW** mem.mistakeMessage<br>**RAW** msg.content<br>**RAW** msg.siblingCards<br>**WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 10 | `A4` 加入错题本 → `A4` 加入错题本 | **RAW** msg.siblingCards<br>**WAW** book.item<br>**WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 9 | `A2` 重新生成 → `A1` 点赞/点踩 | **RAW** mem.card<br>**RAW** msg.content<br>**RAW** msg.siblingCards<br>**WAW** msg.content<br>**WAW** msg.siblingCards |
| 7 | `A1` 点赞/点踩 → `A2` 重新生成 | **RAW** msg.content<br>**WAW** msg.content<br>**WAW** msg.siblingCards |
| 6 | `A3` 退出搜索页再重进 → `A2` 重新生成 | **WAW** mem.card<br>**WAW** mem.mistakeMessage |
| 6 | `A3` 退出搜索页再重进 → `A3` 退出搜索页再重进 | **WAW** mem.card<br>**WAW** mem.mistakeMessage |
| 6 | `A4` 加入错题本 → `A2` 重新生成 | **WAW** msg.extData.mistakeBook<br>**WAW** msg.siblingCards |
| 5 | `A1` 点赞/点踩 → `A4` 加入错题本 | **RAW** msg.content<br>**RAW** msg.siblingCards<br>**WAW** msg.siblingCards |
| 4 | `A4` 加入错题本 → `A1` 点赞/点踩 | **RAW** msg.siblingCards<br>**WAW** msg.siblingCards |
| 3 | `A0` 带图提问 → `A5` 停留超过 5 分钟 | **WAW** regenCache.request |
| 3 | `A0` 带图提问 → `A6` 同账号另一轮带图提问（可在另一设备） | **WAW** regenCache.request |
| 3 | `A1` 点赞/点踩 → `A3` 退出搜索页再重进 | **RAW** msg.content<br>**RAW** msg.extData.feedback<br>**RAW** msg.siblingCards |
| 3 | `A5` 停留超过 5 分钟 → `A5` 停留超过 5 分钟 | **WAW** regenCache.request |
| 3 | `A5` 停留超过 5 分钟 → `A6` 同账号另一轮带图提问（可在另一设备） | **WAW** regenCache.request |
| 3 | `A6` 同账号另一轮带图提问（可在另一设备） → `A5` 停留超过 5 分钟 | **WAW** regenCache.request |
| 3 | `A6` 同账号另一轮带图提问（可在另一设备） → `A6` 同账号另一轮带图提问（可在另一设备） | **WAW** regenCache.request |
| 2 | `A3` 退出搜索页再重进 → `A4` 加入错题本 | **RAW** mem.card<br>**RAW** mem.mistakeMessage |
| 2 | `A4` 加入错题本 → `A3` 退出搜索页再重进 | **RAW** msg.extData.mistakeBook<br>**RAW** msg.siblingCards |
| 1 | `A3` 退出搜索页再重进 → `A1` 点赞/点踩 | **RAW** mem.card |
| 1 | `A5` 停留超过 5 分钟 → `A2` 重新生成 | **RAW** regenCache.request |
| 1 | `A6` 同账号另一轮带图提问（可在另一设备） → `A2` 重新生成 | **RAW** regenCache.request |

## 3. 三元穿透链（A → B → C）

A 写了字段 F；B 替换了 F 所在的实体却没重写 F；C 读 F。若按产品语义 B 应当重置 F（如重新生成应清空旧的点赞），C 就会看到「复活」的旧值，而且挂在了新版本上。

- `A1` 点赞/点踩 → `A2` 重新生成 → `A3` 退出搜索页再重进：`msg.extData.feedback`
- `A0` 带图提问 → `A2` 重新生成 → `A3` 退出搜索页再重进：`msg.mistakeMessage`

## 4. 中断点

对每个阶段追踪：断开被谁、在哪一刻探测到 → 已写入/未写入的状态 → 重进后读到什么 → 其他原子紧接着操作会怎样。

- `A0` 带图提问 中断于「深度思考输出中」
- `A0` 带图提问 中断于「正文输出中」
- `A2` 重新生成 中断于「深度思考输出中」
- `A2` 重新生成 中断于「正文输出中」

