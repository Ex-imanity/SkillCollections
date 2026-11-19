# 合成单端回答卡

全部材料为合成输入，A1/I1/A2/I2是模拟提交标识。

只给 Android A1，一张卡 `Card{text, reaction}`，`like()` 写 `reaction=1`；`regenerate(text)` 请求服务端；可见服务端仅保存新 `text`，保留旧 `reaction`；`history()` 读取这两个字段。产品仅说明生成新回答，不规定旧反馈应保留还是重置；无其他端资料。只要求按普通白盒流程产生原子表并等待审阅，不把缺少其他端当阻塞。
