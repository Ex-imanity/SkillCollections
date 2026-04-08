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
MCP_ENDPOINT = "https://tech.baijia.com/mcp-server/banshan/mcp"


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
    """Parse full.md into Banshan node tree format."""
    node_tree: list[dict[str, Any]] = []
    current_scenario: dict | None = None
    current_point: dict | None = None
    current_step: dict | None = None
    in_steps = False
    in_results = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 场景: ## 场景N：标题
        m_s = re.match(r"^##\s*场景\d+[:：]\s*(.+)", line)
        if m_s:
            title, priority = _parse_priority(m_s.group(1))
            current_scenario = {
                "data": {"text": title, "resource": ["场景"], "sourceDesc": "ai", "priority": priority},
                "children": [],
            }
            node_tree.append(current_scenario)
            current_point, current_step = None, None
            in_steps = in_results = False
            continue

        # 测试点: ### 测试点N.M：标题
        m_p = re.match(r"^###\s*测试点\d+\.\d+[:：]\s*(.+)", line)
        if m_p and current_scenario is not None:
            title, priority = _parse_priority(m_p.group(1))
            current_point = {
                "data": {"text": title, "resource": ["测试点"], "sourceDesc": "ai", "priority": priority},
                "children": [],
            }
            current_scenario["children"].append(current_point)
            current_step = None
            in_steps = in_results = False
            continue

        # 执行步骤 / 预期结果 标记
        if line.startswith("#### 执行步骤"):
            in_steps, in_results = True, False
            continue
        if line.startswith("#### 预期结果"):
            in_results, in_steps = True, False
            continue

        # 执行步骤行
        if in_steps and current_point is not None:
            if re.match(r"^\d+\.", line):
                current_step = {
                    "data": {"text": line, "resource": ["执行步骤"], "sourceDesc": "ai"},
                    "children": [],
                }
                current_point["children"].append(current_step)
            continue

        # 预期结果行
        if in_results and current_step is not None:
            if re.match(r"^\d+\.", line) or line.startswith("-"):
                current_step["children"].append({
                    "data": {"text": line, "resource": ["预期结果"], "sourceDesc": "ai"},
                    "children": [],
                })
            continue

    return node_tree


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

    # --- 2. 输出摘要 ---
    output_dir = args.output_dir or (full_md_path.parent / "writeback")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存节点树
    tree_path = output_dir / "node-tree.json"
    tree_path.write_text(json.dumps(node_tree, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 解析完成: {scenario_count} 个场景, {point_count} 个测试点, {total_nodes} 个节点")
    print(f"  节点树: {tree_path}")

    if args.dry_run:
        print("\n[dry-run] 跳过写回")
        # 场景概览
        for i, s in enumerate(node_tree, 1):
            pts = len(s.get("children", []))
            print(f"  场景{i}: {s['data']['text']} ({pts} 个测试点)")
        return 0

    # --- 3. 写入搬山 ---
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

    # --- 4. 验证 ---
    print(f"\n→ 验证用例 {args.case_id} ...")

    verify_result = mcp_call("testCaseDetail", {"caseId": str(args.case_id)}, req_id=2)
    verify_ok = "error" not in verify_result
    if verify_ok:
        print(f"✓ 验证通过")
    else:
        print(f"⚠ 验证调用失败（写回可能已成功，请在搬山平台确认）")

    # --- 5. 保存日志 ---
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
