# 合成升级和历史数据

以下仅是合成代码规则和样本，不是生产协议、实际服务回包或真机表现。全部可用材料如下。

```text
服务端共享规则：按整数元组比较版本，policy.enabled && version(current) < version(target) 时返回目标版本；否则无升级数据；相等不提醒。
平台记录：Android A1 current=10.2 target=10.3 enabled=true；iOS I1 current=4.7 target=4.8 enabled=true；Harmony H1 current=5.0 target=5.1 enabled=true。
iOS 对照组 I2：current=4.7 target=4.8 enabled=false；其他条件不变。
Android 解码片段：parse({createdAt:number, content:string}) -> Message；render(Message.content)。
iOS 解码片段：parse({createdAt:string, content:string}) -> Message；render(Message.content)。
Android 合成样本：{"createdAt":1700000000000,"content":"SAMPLE"}。
iOS 合成样本：{"createdAt":"1700000000000","content":"SAMPLE"}。
客户端升级片段（仅 Android/iOS 可见）：有服务端目标版本则展示升级入口；无升级数据则不展示。
Harmony 仅有服务端配置，无客户端源码、解码规则或设备表现。
```
