# 合成维护通知代码

Android A1 / iOS I1 为固定模拟提交。两端为同一账号、有效权限、有效通知配置。下列是本题全部可见代码；省略部分不可假定已实现，未做真机运行。

```text
Android A1:
enter() { if (noticeEnabled && content.isNotBlank()) showMaintenance() }
onResume() { requestRoomConfig() }
onOutsideTouch() { dismissMaintenance() }
roomReply(r) { if (r.occupied) { showConflict(); return }
               if (r.remaining > 0 && r.hasDraft) showResume() }

iOS I1:
enter() { if (noticeEnabled && !confirmed) {
            showMaintenance(content.orDefault()); return }
          requestRoomConfig() }
onOutsideTouch() { /* ignore */ }
onConfirmDismissed() { confirmed = true; enter() }
roomReply(r) { if (r.occupied) { showConflict(); return }
               if (r.remaining > 0 && r.hasDraft) showResume() }

产品：维护通知用于告知用户。
```
