---
name: case-reorganize
description: 将搬山中已有的测试用例整理为链路 case。支持合并冗余用例、去除边界 case、将串联操作合并为一个场景。输出 full.md 后写回搬山（替换原 case 或追加到目标 case）。当用户说"整理搬山用例"、"用例重构"、"链路case"、"合并冗余用例"时触发。
---

# case-reorganize：搬山测试用例整理为链路 case

## 定位

针对**搬山中已有的测试用例**，将分散的、边界偏多的、不成链路的用例重新整理为**以用户操作链路为主线**的用例结构。

核心原则：
- **以用户操作链路为主**：每个测试点描述一段完整的操作流程，前提→操作→结果
- **合并串联步骤**：将多个顺序执行的原子步骤合并为一条链路用例
- **去除冗余**：合并重复覆盖同一路径的用例；可选去除边界 case（由用户决定）
- **不改内容**：整理结构，不新增未覆盖的场景，不删除用户要求保留的内容

## 与 case-lite 的区别

| | case-lite | case-reorganize |
|---|---|---|
| 输入来源 | 飞书文档（需求/技术方案） | 搬山已有用例 |
| 内容来源 | 从文档生成新用例 | 整理/重构已有用例 |
| 典型场景 | 新需求上线前生成用例 | 旧用例维护、回归精简 |
| 飞书 MCP | 必需 | 不需要 |

---

## 执行流程

### Step 1：收集输入

从用户消息中提取：

1. **源 case URL(s)**（必须）→ 要整理的搬山用例链接，可多个
2. **目标 case**（必须）→ 整理后写回的位置：
   - `替换`：写回到源 case，覆盖原内容（先 deleteNode 再写入）
   - `追加`：追加到另一个 case（如汇总用的 case 23375），保留原内容
3. **整理参考 case**（可选）→ 格式参考，如 case 23375
4. **内容策略**（可选，默认询问）→ 是否去除边界 case

引导话术：

```
请提供以下信息：
1. 要整理的搬山用例链接（可多个）
2. 整理后写回的位置：替换原 case，还是追加到其他 case？
3. 是否去除边界 case？（默认询问，或"去除"/"全部保留"）
4. 有没有参考格式的 case 链接？（可选）
```

### Step 2：获取源用例内容 [HITL]

对每个源 case，从 URL 中解析 caseId（URL 路径中的数字，如 `#/caseManager/91/17210/` 中的 `17210`）。

调用搬山 MCP 获取用例树：

```
testCaseDetail(caseId)
```

> **搬山 MCP 端点**：`https://tech.baijia.com/mcp-server/banshan/mcp`（JSON-RPC 2.0）

返回的节点树结构（四级串联）：
- 深度 0：场景（`resource: ["场景"]`）
- 深度 1：测试点（`resource: ["测试点", "UI"/"逻辑"]`）
- 深度 2：前置条件（`resource: ["前置条件"]`，text = 前置条件内容）
- 深度 3：执行步骤（`resource: ["执行步骤"]`，text = 所有步骤合并多行，是前置条件的子节点）
- 深度 4：预期结果（`resource: ["预期结果"]`，text = 所有结果合并多行，是执行步骤的子节点）

> **注意**：执行步骤和预期结果的 text 字段是将所有编号步骤/结果合并为一个多行字符串，不是每条步骤单独一个子节点。

将内容整理为可读摘要展示给用户：

```
已获取 case XXXXX 内容：

场景1：XXX（N 个测试点）
  - 测试点1.1：XXX
  - 测试点1.2：XXX（可能与 1.1 重复：都在测试 XX）
场景2：XXX（N 个测试点）
  ...

共 N 个场景，N 个测试点。

初步整理意见：
- 测试点 1.2 和 1.3 可合并为一条链路
- 测试点 2.4 为边界 case（验证码格式校验），可考虑去除
- 测试点 3.x 和 3.y 步骤串联，建议合并

请确认整理方向，或说明需要特别保留 / 去除的内容。
```

### Step 3：生成场景结构 [HITL]

基于用户确认的整理方向，生成 `structure.md`。

**整理原则（按优先级）**：

1. **合并串联步骤**：如「点击按钮 A」→「查看页面 B」→「点击按钮 C」属于同一链路，合并为一个测试点
2. **合并重复路径**：多个测试点覆盖同一主路径时，保留最完整的一个
3. **拆分无关场景**：一个测试点同时覆盖多个不相关功能时，按场景拆分
4. **去除边界 case**（若用户同意）：纯参数校验（空值/格式/长度）、平台兼容性边界、低优先级异常分支
5. **保留核心场景**：用户登录/注册、主功能操作链路、已明确要求保留的测试点

**命名规范**：
- 场景：`XX 链路`（如"登录链路"、"启动流程链路"）
- 测试点：`主功能 + 分支特征`（如"验证码登录链路"、"微信登录未绑定手机号冲突链路"）
- **不使用**"验证"、"测试"、"检查"等前缀

生成后展示 `structure.md` 给用户审核：

```
场景结构已整理，请审核：
[展示 structure.md 内容]

与原用例对比：
- 原 N 个测试点 → 整理后 N 个测试点
- 去除/合并：XX, XX
- 保留：XX, XX

确认后将生成完整用例。
```

### Step 4：生成完整用例 [HITL]

基于审核通过的 `structure.md` + 原用例内容生成 `full.md`。

**生成要点**：
- 每个测试点描述完整的操作链路：前置条件 → 执行步骤 → 预期结果
- 步骤中的"查看..."应拆解为具体的观察对象（"查看按钮状态"→"确认按钮变为灰色不可点击状态"）
- 预期结果写具体可观测的状态，不写"正常展示"等模糊描述
- 不在 full.md 中加优先级标记（P0/P1/P2）

生成后展示 `full.md` 摘要并请用户审核：

```
完整用例已生成：
[展示各场景和测试点标题]

共 N 个场景，N 个测试点，N 个节点。
请确认后进行写回。
```

### Step 5：dry-run 验证

**必须先执行 dry-run，不可跳过**。用以下 Python 片段解析 full.md 并统计节点数：

```python
import re
from pathlib import Path

def dry_run(md_path):
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    scenes, points = 0, 0
    cur_has_steps = False
    warnings = []
    point_title = ""
    for line in lines:
        if re.match(r"^## 场景\d+[：:]", line):
            scenes += 1
        elif re.match(r"^### 测试点\d+\.\d+[：:]", line):
            if points > 0 and not cur_has_steps:
                warnings.append(f"测试点「{point_title}」缺少执行步骤")
            points += 1
            point_title = line.strip()
            cur_has_steps = False
        elif re.match(r"^#### 执行步骤", line):
            cur_has_steps = True
    if points > 0 and not cur_has_steps:
        warnings.append(f"测试点「{point_title}」缺少执行步骤")
    print(f"{scenes} 个场景，{points} 个测试点")
    for w in warnings:
        print(f"⚠ {w}")
    if not warnings:
        print("✓ 无警告")

dry_run("case-lite-output/{slug}/full.md")
```

检查：场景/测试点数与 full.md 一致，无测试点缺失执行步骤的警告。如有警告，先修复 full.md 再继续。

dry-run 通过后，展示摘要并**等待用户明确确认后才能执行写回**：

```
dry-run 通过：N 个场景，N 个测试点，无警告。

写回目标：case XXXXX（[替换原内容 / 追加到现有 N 个场景之后]）

确认写回请回复「确认」或「写回」，如需修改请继续反馈。
```

**不得在用户确认前自动执行写回。**

### Step 6：写回搬山 [HITL]

写回使用内联 Python 脚本直接调用搬山 MCP，不依赖 writeback.py。核心解析函数：

```python
import json, re, urllib.request
from pathlib import Path

MCP_ENDPOINT = "https://tech.baijia.com/mcp-server/banshan/mcp"

def mcp_call(method, args):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": method, "arguments": args}}
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(MCP_ENDPOINT, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def parse_full_md(md_text, ui_points=None):
    """解析 full.md，输出节点树（前置条件串联在测试点与执行步骤之间）"""
    if ui_points is None:
        ui_points = set()
    lines = md_text.splitlines()
    node_tree, cur_scene, cur_point, cur_section = [], None, None, None
    precond_lines, steps_lines, results_lines = [], [], []
    scene_idx, point_idx = 0, 0

    def flush_point():
        if cur_point is None:
            return
        precond_text = "\n".join(precond_lines).strip()
        steps_text   = "\n".join(steps_lines).strip()
        results_text = "\n".join(results_lines).strip()
        if steps_text:
            steps_node = {"data": {"text": steps_text, "resource": ["执行步骤"], "sourceDesc": "ai"}, "children": []}
            if results_text:
                steps_node["children"].append(
                    {"data": {"text": results_text, "resource": ["预期结果"], "sourceDesc": "ai"}, "children": []})
            if precond_text:
                cur_point["children"].append(
                    {"data": {"text": precond_text, "resource": ["前置条件"], "sourceDesc": "ai"}, "children": [steps_node]})
            else:
                cur_point["children"].append(steps_node)

    for line in lines:
        m = re.match(r"^## 场景\d+[：:](.+)", line)
        if m:
            flush_point()
            cur_scene = {"data": {"text": m.group(1).strip(), "resource": ["场景"], "sourceDesc": "ai"}, "children": []}
            node_tree.append(cur_scene)
            scene_idx += 1; point_idx = 0
            cur_point = cur_section = None
            precond_lines = steps_lines = results_lines = []
            continue
        m = re.match(r"^### 测试点\d+\.\d+[：:](.+)", line)
        if m and cur_scene is not None:
            flush_point()
            point_idx += 1
            label = "UI" if (scene_idx, point_idx) in ui_points else "逻辑"
            cur_point = {"data": {"text": m.group(1).strip(), "resource": ["测试点", label], "sourceDesc": "ai"}, "children": []}
            cur_scene["children"].append(cur_point)
            cur_section = None
            precond_lines = steps_lines = results_lines = []
            continue
        if re.match(r"^#### 前置条件", line): cur_section = "precond"; continue
        if re.match(r"^#### 执行步骤", line): cur_section = "steps"; continue
        if re.match(r"^#### 预期结果", line): cur_section = "results"; continue
        stripped = line.strip()
        if not stripped or stripped == "---": continue
        if cur_section == "precond": precond_lines.append(stripped)
        elif cur_section == "steps": steps_lines.append(stripped)
        elif cur_section == "results": results_lines.append(stripped)

    flush_point()
    return node_tree
```

**根据写回模式执行不同操作**：

#### 模式 A：替换原 case

```python
# 1. 获取原 case 所有场景节点 ID（注意是 s["data"]["id"]，不是 s["id"]）
r = mcp_call("testCaseDetail", {"caseId": str(CASE_ID)})
root = json.loads(r["result"]["content"][0]["text"])["data"]["caseContent"]
if isinstance(root, str): root = json.loads(root)
scene_ids = [(s["data"]["id"], s["data"]["text"]) for s in root["root"]["children"]]

# 2. 依次删除（deleteNode 会级联删除子节点）
for node_id, title in scene_ids:
    mcp_call("deleteNode", {"caseId": CASE_ID, "nodeId": node_id, "modifier": "case-lite"})

# 3. 解析并写回
node_tree = parse_full_md(Path("full.md").read_text(encoding="utf-8"), ui_points=UI_POINTS)
mcp_call("batchAddNode", {"caseId": CASE_ID, "modifier": "case-lite", "nodeTreeList": node_tree})
```

> **注意**：deleteNode 操作不可逆，执行前务必确认。

#### 模式 B：追加到目标 case

不需要删除节点，也不需要调整场景编号，直接追加：

```python
# 1. 查询目标 case 当前场景数（仅用于日志展示）
r = mcp_call("testCaseDetail", {"caseId": str(TARGET_CASE_ID)})
root = json.loads(r["result"]["content"][0]["text"])["data"]["caseContent"]
if isinstance(root, str): root = json.loads(root)
current_count = len(root["root"]["children"])
print(f"当前已有 {current_count} 个场景")

# 2. 解析并追加（full.md 场景编号从1开始即可，不需要偏移）
node_tree = parse_full_md(Path("full.md").read_text(encoding="utf-8"), ui_points=UI_POINTS)
mcp_call("batchAddNode", {"caseId": TARGET_CASE_ID, "modifier": "case-lite", "nodeTreeList": node_tree})
```

### Step 7：打 UI / 逻辑 标签（可选）[HITL]

写回时已在 `parse_full_md` 的 `ui_points` 参数中注入标签，**写回完成即已打标**，无需额外步骤。

写回前需整理出 `UI_POINTS` 集合：

- 格式：`{(场景序号, 场景内测试点序号), ...}`，1-based，相对于 full.md 文件内位置
- 依据：展示类（按钮状态、页面渲染、动效）→ `"UI"`；交互逻辑、接口调用、状态流转 → `"逻辑"`

如需重新打标（已写回后才发现标签有误），使用模式 A 全量重建。

---

## 产物目录

```
case-lite-output/{slug}/
├── structure.md        ← 场景结构（用户审核）
├── full.md             ← 完整用例（用户审核）
└── writeback.py        ← 写回脚本（含 parse_full_md + mcp_call）
```

`slug` 由 case 名称或功能名生成，如 `app-common-flow`。

---

## full.md 格式规范

与 case-lite 完全一致，核心约束：

| 规则 | 正确 | 错误 |
|------|------|------|
| 场景标题 | `## 场景1：标题` | `## 场景一：标题` |
| 测试点标题 | `### 测试点1.1：标题` | `### 1.1 标题` |
| 前置条件标题 | `#### 前置条件` | 写入步骤中 / 省略 |
| 步骤标题 | `#### 执行步骤` | `### 执行步骤` |
| 结果标题 | `#### 预期结果` | `**预期结果**` |
| 步骤格式 | `1. 操作内容` | `- 操作内容` |

> 前置条件会被解析为独立节点，串联在测试点与执行步骤之间，**不可省略**。

---

## 工具依赖

| 工具 | 用途 | 必需 |
|------|------|------|
| Banshan MCP | 获取原用例内容、写回节点 | 是 |
| 飞书 MCP | 不需要 | 否 |

写回逻辑通过 Step 6 中的内联 Python 脚本直接调用搬山 MCP，**不依赖 writeback.py**。

---

## 常见决策参考

### 哪些测试点适合合并？

- 步骤有明确前后依赖关系（步骤 A 的结果是步骤 B 的前提）
- 同一功能的正向路径拆成了多个测试点
- 同一弹窗/页面的多个按钮分开测试（可合并为"弹窗交互链路"）

### 哪些测试点可以去除（边界 case）？

- 输入框格式校验（手机号格式、密码长度）
- 网络异常/超时等低频场景（除非该功能有专门的降级逻辑）
- UI 细节检查（字体大小、颜色、间距）
- 已被其他测试点覆盖的重复路径

### 哪些测试点必须保留？

- 用户核心操作链路（登录、支付、主功能入口）
- 有明确分叉的流程（如"已绑定"vs"未绑定"、"首次"vs"非首次"）
- 用户明确说要保留的内容
