# 合成决定与旧产物

全部材料为合成输入，A1/I1/A2/I2是模拟提交标识。

批次 `demo-entry` 下有 `notice` 与 `room-entry` 两个 slug，共享行为 ID `notice.entry-order`，`room-entry.conflict-order` 是相邻行为。notice 的 `analysis.md#f1`、`cases.md#c1`、模拟 `full.md#u1` 记串行问题；room-entry 的 `analysis.md#f2`、`cases.md#c2` 引用同一决定。旧 SHA 为 A1/I1，新提交标识为 A2/I2；旧清单曾按用户要求仅保留共同行为。用户现在明确决定“维护通知完全关闭后才请求配置；设备冲突优先于继续学习”。只赋予分析和生成建议权限，不赋予外部写回；A2/I2 代码未提供。要求给出一个批次对照表和各 slug 反向定位建议，不能声称新代码已修复。
