#!/usr/bin/env python3
"""
case-lite writeback: full.md → 搬山平台（无 LLM 处理）

纯确定性流程：解析 markdown → 构建节点树 → 调用搬山 API 写入 → 验证

用法:
  python writeback.py <full.md> --case-id <ID> [--modifier case-lite] [--dry-run]
  python writeback.py case-lite-output/slug/full.md --case-id 12345

退出码:
  0 = 写回成功
  1 = 写回失败
  2 = full.md 解析失败
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Banshan MCP endpoint (JSON-RPC 2.0)
# ---------------------------------------------------------------------------
MCP_ENDPOINT = os.environ.get(
    "BANSHAN_MCP_ENDPOINT",
    "https://tech.baijia.com/mcp-server/banshan/mcp",
)


# ---------------------------------------------------------------------------
# Markdown parser (same logic as casegen-tools/node_builder.py)
# ---------------------------------------------------------------------------

def _parse_priority(text: str) -> tuple[str, int | None]:
    """Extract priority from title text, return (clean_title, priority_int)."""
    m = re.search(r"\(?(P[012])\)?", text, re.IGNORECASE)
    if m:
        p = m.group(1).upper()
        clean = text[: m.start()].rstrip() + text[m.end() :]
        priority = {"P0": 1, "P1": 2, "P2": 3}.get(p)
        return clean.strip(), priority
    return text.strip(), None


def parse_full_md(text: str) -> list[dict[str, Any]]:
    """Parse full.md into Banshan node tree format.

    Correct structure (matches Banshan reference case 20612):
        测试点
          └── [执行步骤]  ← ALL steps merged into one node, joined by \\n
                └── [预期结果]  ← ALL results merged into one node, child of 执行步骤

    Note: **前置条件** sections are intentionally skipped (not generated as nodes).
    Preconditions should be incorporated into execution steps by the agent.
    """
    node_tree: list[dict[str, Any]] = []
    current_scenario: dict | None = None
    current_point: dict | None = None
    step_lines: list[str] = []
    result_lines: list[str] = []
    in_steps = False
    in_results = False
    in_precond = False  # used to skip precondition lines

    def _flush_point(point: dict) -> None:
        """Commit accumulated lines into nodes under the test point."""
        if step_lines:
            step_node: dict[str, Any] = {
                "data": {"text": "\n".join(step_lines), "resource": ["执行步骤"], "sourceDesc": "ai"},
                "children": [],
            }
            if result_lines:
                step_node["children"].append({
                    "data": {"text": "\n".join(result_lines), "resource": ["预期结果"], "sourceDesc": "ai"},
                    "children": [],
                })
            point["children"].append(step_node)
        step_lines.clear()
        result_lines.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 跳过水平分割线（--- / *** / ___）
        if re.match(r"^[-*_]{3,}$", line):
            continue

        # 场景: ## 场景N：标题
        m_s = re.match(r"^##\s*场景\d+[:：]\s*(.+)", line)
        if m_s:
            if current_point is not None:
                _flush_point(current_point)
            title, priority = _parse_priority(m_s.group(1))
            current_scenario = {
                "data": {"text": title, "resource": ["场景"], "sourceDesc": "ai", "priority": priority},
                "children": [],
            }
            node_tree.append(current_scenario)
            current_point = None
            in_steps = in_results = in_precond = False
            continue

        # 测试点: ### 测试点N.M：标题
        m_p = re.match(r"^###\s*测试点\d+\.\d+[:：]\s*(.+)", line)
        if m_p and current_scenario is not None:
            if current_point is not None:
                _flush_point(current_point)
            title, priority = _parse_priority(m_p.group(1))
            current_point = {
                "data": {"text": title, "resource": ["测试点"], "sourceDesc": "ai", "priority": priority},
                "children": [],
            }
            current_scenario["children"].append(current_point)
            in_steps = in_results = in_precond = False
            continue

        # 前置条件标记
        if line.startswith("**前置条件**"):
            in_precond, in_steps, in_results = True, False, False
            continue

        # 执行步骤 / 预期结果 section 标记
        if line.startswith("#### 执行步骤"):
            in_steps, in_results, in_precond = True, False, False
            continue
        if line.startswith("#### 预期结果"):
            in_results, in_steps, in_precond = True, False, False
            continue

        # 跳过前置条件行（不生成节点）
        if in_precond:
            continue

        # 收集执行步骤行（编号列表）
        if in_steps and current_point is not None:
            if re.match(r"^\d+\.", line):
                step_lines.append(line)
            continue

        # 收集预期结果行（编号列表或 bullet）
        if in_results and current_point is not None:
            if re.match(r"^\d+\.", line) or line.startswith("- "):
                result_lines.append(line)
            continue

    # flush 最后一个测试点
    if current_point is not None:
        _flush_point(current_point)

    return node_tree


# ---------------------------------------------------------------------------
# Validation: 检测 full.md 中被解析器跳过的内容
# ---------------------------------------------------------------------------

def validate_full_md(text: str, parsed_tree: list[dict[str, Any]]) -> list[str]:
    """Compare raw markdown against parsed tree, return warnings."""
    warnings: list[str] = []

    # 1. 统计原文中的场景和测试点数
    raw_scenarios = len(re.findall(r"^##\s", text, re.MULTILINE))
    raw_points = len(re.findall(r"^###\s", text, re.MULTILINE))
    # 排除 #### 级别
    raw_scenarios -= len(re.findall(r"^###+\s", text, re.MULTILINE))

    parsed_scenarios = len(parsed_tree)
    parsed_points = sum(len(s.get("children", [])) for s in parsed_tree)

    # 原文中 ## 数量（减去 ### 和 ####）vs 解析出的场景数
    md_scenario_count = len(re.findall(r"^## 场景\d+[:：]", text, re.MULTILINE))
    md_point_count = len(re.findall(r"^### 测试点\d+\.\d+[:：]", text, re.MULTILINE))

    if md_scenario_count != parsed_scenarios:
        warnings.append(f"场景数不匹配: markdown 中有 {md_scenario_count} 个 '## 场景N：'，解析出 {parsed_scenarios} 个")

    if md_point_count != parsed_points:
        warnings.append(f"测试点数不匹配: markdown 中有 {md_point_count} 个 '### 测试点N.M：'，解析出 {parsed_points} 个")

    # 2. 检查是否有未被识别的 ## / ### 行（格式漂移）
    for i, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            if not re.match(r"^##\s*场景\d+[:：]", line):
                warnings.append(f"第 {i} 行: 未识别的 ## 标题（非 '## 场景N：' 格式）: {line[:50]}")
        if line.startswith("### ") and not line.startswith("#### "):
            if not re.match(r"^###\s*测试点\d+\.\d+[:：]", line):
                warnings.append(f"第 {i} 行: 未识别的 ### 标题（非 '### 测试点N.M：' 格式）: {line[:50]}")

    # 3. 检查无执行步骤的测试点
    for s in parsed_tree:
        for p in s.get("children", []):
            has_steps = any(
                c["data"]["resource"] == ["执行步骤"] for c in p.get("children", [])
            )
            if not has_steps:
                warnings.append(f"测试点 '{p['data']['text'][:30]}' 无执行步骤节点")

    return warnings


def count_nodes(tree: list[dict[str, Any]]) -> int:
    total = 0
    for n in tree:
        total += 1 + count_nodes(n.get("children", []))
    return total


def count_test_points(tree: list[dict[str, Any]]) -> int:
    total = 0
    for scenario in tree:
        total += len(scenario.get("children", []))
    return total


# ---------------------------------------------------------------------------
# Banshan MCP client (JSON-RPC 2.0 over HTTP)
# ---------------------------------------------------------------------------

def mcp_call(method_name: str, arguments: dict[str, Any], req_id: int = 1) -> dict[str, Any]:
    """Call a Banshan MCP tool via JSON-RPC 2.0."""
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {
            "name": method_name,
            "arguments": arguments,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        MCP_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": e.read().decode("utf-8", errors="replace")[:500]}}
    except urllib.error.URLError as e:
        return {"error": {"code": -1, "message": f"网络错误: {e.reason}"}}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="case-lite writeback: full.md → 搬山平台（无 LLM）",
    )
    parser.add_argument("full_md", type=Path, help="full.md 路径")
    parser.add_argument("--case-id", type=int, required=True, help="搬山用例 ID")
    parser.add_argument("--modifier", default="case-lite", help="操作人标识（默认 case-lite）")
    parser.add_argument("--dry-run", action="store_true", help="仅解析并输出摘要，不写回")
    parser.add_argument("--output-dir", type=Path, default=None, help="产物输出目录（默认 full.md 同级 writeback/）")
    args = parser.parse_args()

    # --- 1. 解析 full.md ---
    full_md_path = args.full_md.resolve()
    if not full_md_path.exists():
        print(f"ERROR: 文件不存在: {full_md_path}", file=sys.stderr)
        return 2

    markdown = full_md_path.read_text(encoding="utf-8")
    node_tree = parse_full_md(markdown)

    if not node_tree:
        print(f"ERROR: 未从 {full_md_path.name} 中解析出任何场景", file=sys.stderr)
        print("请检查 full.md 是否符合格式：## 场景N：标题 / ### 测试点N.M：标题", file=sys.stderr)
        return 2

    scenario_count = len(node_tree)
    point_count = count_test_points(node_tree)
    total_nodes = count_nodes(node_tree)

    # --- 2. 格式验证 ---
    warnings = validate_full_md(markdown, node_tree)
    if warnings:
        print(f"\n⚠ 格式验证发现 {len(warnings)} 个问题:")
        for w in warnings:
            print(f"  - {w}")
        print()

    # --- 3. 输出摘要 ---
    output_dir = args.output_dir or (full_md_path.parent / "writeback")
    output_dir.mkdir(parents=True, exist_ok=True)

    tree_path = output_dir / "node-tree.json"
    tree_path.write_text(json.dumps(node_tree, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 解析完成: {scenario_count} 个场景, {point_count} 个测试点, {total_nodes} 个节点")
    print(f"  节点树: {tree_path}")

    if args.dry_run:
        print("\n[dry-run] 跳过写回")
        for i, s in enumerate(node_tree, 1):
            pts = len(s.get("children", []))
            print(f"  场景{i}: {s['data']['text']} ({pts} 个测试点)")
        if warnings:
            print(f"\n⚠ 有 {len(warnings)} 个格式警告，请先修复后再写回")
            return 2
        return 0

    # --- 4. 重复写入提醒（不阻塞） ---
    print(f"\n→ 检查用例 {args.case_id} 是否已有节点 ...")
    detail = mcp_call("testCaseDetail", {"caseId": str(args.case_id)}, req_id=0)
    if "error" not in detail:
        try:
            content = json.loads(detail.get("result", {}).get("content", [{}])[0].get("text", "{}"))
            case_data = json.loads(content.get("data", {}).get("caseContent", "{}"))
            root_children = case_data.get("root", {}).get("children", [])
            if root_children:
                print(f"⚠ 注意: 用例 {args.case_id} 已有 {len(root_children)} 个根节点")
                print(f"  本次写入会追加（不是覆盖），如不需要请先在搬山平台删除已有节点。")
        except (json.JSONDecodeError, KeyError, TypeError, IndexError):
            pass  # 解析失败不阻塞

    # --- 5. 写入搬山 ---
    print(f"\n→ 写入搬山用例 {args.case_id} ...")

    write_result = mcp_call("batchAddNode", {
        "caseId": args.case_id,
        "modifier": args.modifier,
        "nodeTreeList": node_tree,
    })

    write_ok = "error" not in write_result
    if not write_ok:
        err = write_result.get("error", {})
        print(f"✗ 写回失败: {err.get('message', '未知错误')}", file=sys.stderr)
        _save_log(output_dir, args.case_id, scenario_count, total_nodes, False, str(err))
        return 1

    print(f"✓ 写回成功: {scenario_count} 个场景已写入")

    # --- 6. 验证 ---
    print(f"\n→ 验证用例 {args.case_id} ...")

    verify_result = mcp_call("testCaseDetail", {"caseId": str(args.case_id)}, req_id=2)
    verify_ok = "error" not in verify_result
    if verify_ok:
        print(f"✓ 验证通过")
    else:
        print(f"⚠ 验证调用失败（写回可能已成功，请在搬山平台确认）")

    # --- 7. 保存日志 ---
    _save_log(output_dir, args.case_id, scenario_count, total_nodes, True, "ok")

    print(f"\n========== 写回完成 ==========")
    print(f"  用例 ID:   {args.case_id}")
    print(f"  场景数:    {scenario_count}")
    print(f"  测试点数:  {point_count}")
    print(f"  总节点数:  {total_nodes}")
    print(f"  操作人:    {args.modifier}")
    print(f"  日志:      {output_dir / 'writeback-log.json'}")
    return 0


def _save_log(output_dir: Path, case_id: int, scenarios: int, nodes: int, success: bool, message: str) -> None:
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "caseId": case_id,
        "scenarios": scenarios,
        "totalNodes": nodes,
        "success": success,
        "message": message,
    }
    log_path = output_dir / "writeback-log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
