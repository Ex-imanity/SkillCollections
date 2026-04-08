# case-lite：小需求测试用例生成

面向单一功能点的小需求，从飞书文档到搬山用例的一站式生成工具。

核心理念：**精准输入** —— 你选章节，AI 写用例。

## 安装

### 1. 安装 skill

```bash
# 方式一：通过 skill-install（推荐）
/skill-install https://github.com/Ex-imanity/SkillCollections

# 方式二：手动复制
git clone https://github.com/Ex-imanity/SkillCollections.git
cp -r SkillCollections/case-lite ~/.cc-switch/skills/case-lite
```

### 2. 配置飞书文档 MCP（必需）

在 Claude Code 的 MCP 配置中添加（`~/.claude/settings.json` 或项目级 `.claude/settings.json`）：

```json
{
  "mcpServers": {
    "feishu-docx-blocks": {
      "command": "uvx",
      "args": ["feishu-docx-blocks@latest"]
    }
  }
}
```

> 默认应用凭证已内置，无需额外配置。重启 Claude Code 后，首次调用工具时会自动弹出浏览器完成飞书授权。
> 需要先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 3. 配置搬山 MCP（推荐）

```json
{
  "mcpServers": {
    "Banshan": {
      "type": "streamable-http",
      "url": "https://tech.baijia.com/mcp-server/banshan/mcp"
    }
  }
}
```

> 用于通过 caseId 获取参考用例。未配置不影响核心流程，写回功能由内置脚本直接完成。

## 使用流程

### 第一步：告诉 AI 你的需求

对话中说 **"case-lite"** 或 **"小需求用例"**，然后提供：

- 需求名称
- 飞书文档链接（支持 docx 和 wiki 链接，可多个）
- 文档类型（可选，如后端技术方案、需求文档等）

```
case-lite

需求名称：用户自助重置密码
后端技术方案：https://xxx.feishu.cn/docx/TOKEN1
前端交互文档：https://xxx.feishu.cn/wiki/TOKEN2
```

### 第二步：浏览章节，选择范围

AI 会展示每个文档的章节目录：

<!-- 截图占位：章节树展示 -->

你可以通过编号或关键词选择相关章节：

```
选 3, 4.1, 4.2
```

选完后 AI 会询问是否有补充信息（如 TAPD 描述、口头约定的规则等），没有就回复"没有了"。

### 第三步：审核场景结构

AI 生成场景和测试点的骨架（structure.md），你只需关注：

- 场景划分是否合理
- 测试点是否有遗漏
- 优先级标注是否准确

<!-- 截图占位：structure.md 审核 -->

确认或提出修改意见。

### 第四步：审核完整用例

AI 基于确认的结构生成完整用例（full.md），包含每个测试点的执行步骤和预期结果。

<!-- 截图占位：full.md 审核 -->

审核无误后进入写回。

### 第五步：写回搬山

提供搬山用例 ID，AI 会自动：

1. 解析 full.md → 构建节点树（不消耗 token）
2. 写入搬山平台
3. 验证写入结果

<!-- 截图占位：搬山平台写入结果 -->

## 产物说明

所有中间产物保存在 `case-lite-output/{需求名称}/` 下：

```
case-lite-output/user-self-reset-password/
├── chapters/            ← 章节目录
├── corpus/              ← 选定章节语料 + 补充信息
├── structure.md         ← 场景结构（已审核）
├── full.md              ← 完整用例（已审核）
└── writeback/           ← 节点树 + 写回日志
```

## 常见问题

**Q: 写回后搬山上结构不对？**
先执行 dry-run 检查：`python writeback.py full.md --case-id xxx --dry-run`。如果场景/测试点数与 full.md 不符，说明有格式问题，检查 full.md 是否严格遵循 `## 场景N：` / `### 测试点N.M：` 格式。

**Q: 搬山用例已有内容，写回会覆盖吗？**
不会。写回是追加模式，脚本会提醒你。如需重新写入，请先在搬山平台手动清空用例。

**Q: 文档中有流程图/截图，AI 能看到吗？**
能。AI 会自动下载文档中的图片和画板，用于理解交互逻辑和分支流程。

**Q: 没有飞书文档，只有 TAPD 描述怎么办？**
选章节步骤后，AI 会询问补充信息，可以直接粘贴 TAPD 内容。
