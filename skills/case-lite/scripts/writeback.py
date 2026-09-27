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
# Markdown parser：编号即路径（number-as-path）
# ---------------------------------------------------------------------------
#
# 节点树形态（场景可任意层嵌套，深度由编号段数决定）：
#
#   场景3            path=(3)      ← 非叶子场景，子节点只能是场景
#     场景3.1        path=(3,1)    ← 叶子场景，子节点只能是测试点
#       测试点3.1.1  path=(3,1,1)
#         执行步骤                  ← 所有步骤合并为一个节点，\n 连接
#           预期结果                ← 所有结果合并为一个节点，是执行步骤的子节点
#
# 关键约定：
#   1. 深度来自编号段数，不来自标题的 # 级别（# 级别仅供阅读，解析时忽略）
#   2. 执行步骤 / 预期结果 标记与深度解耦，任意 # 级别或 **加粗** 均可识别
#   3. 不允许混搭：任一场景的直接子节点不能同时包含场景和测试点
#   4. **前置条件** section 会被跳过，不生成节点（应融入执行步骤第一步）

# 建议深度上限：超过只在 advisory_notes 里提示，不阻塞
MAX_SCENE_DEPTH = 3
# 硬上限：远高于建议值，纯粹用于挡住畸形输入（递归遍历在千层会 RecursionError）
MAX_HARD_DEPTH = 20

# 每段编号限 1-6 位：既覆盖一切真实用法，也挡住超长数字串
# （Python 3.11+ 对 4300 位以上的 int(str) 会抛 ValueError）
SCENE_RE = re.compile(r"^#{1,6}\s*场景\s*(\d{1,6}(?:\.\d{1,6})*)\s*[:：]\s*(.+?)\s*$")
POINT_RE = re.compile(r"^#{1,6}\s*测试点\s*(\d{1,6}(?:\.\d{1,6})*)\s*[:：]\s*(.+?)\s*$")
STEPS_RE = re.compile(r"^(?:#{1,6}\s*)?\*{0,2}\s*执行步骤\s*\*{0,2}\s*[:：]?\s*$")
RESULTS_RE = re.compile(r"^(?:#{1,6}\s*)?\*{0,2}\s*预期结果\s*\*{0,2}\s*[:：]?\s*$")
PRECOND_RE = re.compile(r"^(?:#{1,6}\s*)?\*{0,2}\s*前置条件\s*\*{0,2}")
HEADING_RE = re.compile(r"^#{2,6}\s+\S")


def _clean_title(text: str) -> str:
    """Strip priority markers like (P0) from title text."""
    return re.sub(r"\s*\(?P[012]\)?\s*", " ", text, flags=re.IGNORECASE).strip()


def _path_of(number: str) -> tuple[int, ...]:
    """'3.1.2' -> (3, 1, 2)"""
    return tuple(int(seg) for seg in number.split("."))


def _fmt_path(path: tuple[int, ...]) -> str:
    return ".".join(str(seg) for seg in path)


def _make_node(text: str, resource: str) -> dict[str, Any]:
    return {
        "data": {"text": text, "resource": [resource], "sourceDesc": "ai"},
        "children": [],
    }


def parse_full_md(text: str) -> list[dict[str, Any]]:
    """Parse full.md into a Banshan node tree. Kept for backward compatibility."""
    tree, _errors = parse_full_md_with_errors(text)
    return tree


def parse_full_md_with_errors(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse full.md into a Banshan node tree, returning structural errors alongside.

    Returns (node_tree, errors). A non-empty ``errors`` list means the tree is
    unsafe to write back and the caller must abort.
    """
    node_tree: list[dict[str, Any]] = []
    errors: list[str] = []

    # 编号路径 → 场景节点，用于把子场景/测试点挂到正确的父节点下
    scenes: dict[tuple[int, ...], dict[str, Any]] = {}
    # 场景路径 → 该场景直接子节点的类型集合，用于混搭检测
    scene_child_kinds: dict[tuple[int, ...], set[str]] = {}
    # 编号路径 → 测试点节点，用于重复编号检测
    points: dict[tuple[int, ...], dict[str, Any]] = {}

    current_point: dict | None = None
    step_lines: list[str] = []
    result_lines: list[str] = []
    in_steps = False
    in_results = False
    in_precond = False

    def _flush_point(point: dict) -> None:
        """Commit accumulated lines into 执行步骤 / 预期结果 nodes under the test point."""
        if step_lines:
            step_node = _make_node("\n".join(step_lines), "执行步骤")
            if result_lines:
                step_node["children"].append(_make_node("\n".join(result_lines), "预期结果"))
            point["children"].append(step_node)
        step_lines.clear()
        result_lines.clear()

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue

        # 跳过水平分割线（--- / *** / ___）
        if re.match(r"^[-*_]{3,}$", line):
            continue

        # --- 场景（任意深度） ---
        m_s = SCENE_RE.match(line)
        if m_s:
            if current_point is not None:
                _flush_point(current_point)
                current_point = None
            in_steps = in_results = in_precond = False

            path = _path_of(m_s.group(1))
            title = _clean_title(m_s.group(2))

            if path in scenes:
                errors.append(f"第 {lineno} 行: 场景编号 {_fmt_path(path)} 重复定义")
                continue

            if len(path) > MAX_HARD_DEPTH:
                errors.append(
                    f"第 {lineno} 行: 场景 {_fmt_path(path)} 嵌套 {len(path)} 层，"
                    f"超过硬上限 {MAX_HARD_DEPTH} 层（建议上限是 {MAX_SCENE_DEPTH} 层）"
                )
                continue

            node = _make_node(title, "场景")
            node["_path"] = path
            if len(path) == 1:
                node_tree.append(node)
            else:
                parent_path = path[:-1]
                parent = scenes.get(parent_path)
                if parent is None:
                    errors.append(
                        f"第 {lineno} 行: 场景 {_fmt_path(path)} 的父场景 "
                        f"{_fmt_path(parent_path)} 不存在（编号断层，或父场景写在了它后面）"
                    )
                    continue
                parent["children"].append(node)
                scene_child_kinds.setdefault(parent_path, set()).add("场景")

            scenes[path] = node
            scene_child_kinds.setdefault(path, set())
            continue

        # --- 测试点 ---
        m_p = POINT_RE.match(line)
        if m_p:
            if current_point is not None:
                _flush_point(current_point)
                current_point = None
            in_steps = in_results = in_precond = False

            path = _path_of(m_p.group(1))
            title = _clean_title(m_p.group(2))

            if len(path) < 2:
                errors.append(
                    f"第 {lineno} 行: 测试点编号 {_fmt_path(path)} 至少需要两段"
                    f"（如 测试点1.1），测试点不能挂在根节点下"
                )
                continue

            if path in points:
                errors.append(f"第 {lineno} 行: 测试点编号 {_fmt_path(path)} 重复定义")
                continue

            parent_path = path[:-1]
            parent = scenes.get(parent_path)
            if parent is None:
                errors.append(
                    f"第 {lineno} 行: 测试点 {_fmt_path(path)} 的父场景 "
                    f"{_fmt_path(parent_path)} 不存在（编号写错，或场景写在了它后面）"
                )
                continue

            node = _make_node(title, "测试点")
            node["_path"] = path
            points[path] = node
            parent["children"].append(node)
            scene_child_kinds.setdefault(parent_path, set()).add("测试点")
            current_point = node
            continue

        # --- 前置条件（跳过，不生成节点） ---
        if PRECOND_RE.match(line):
            in_precond, in_steps, in_results = True, False, False
            continue

        # --- 执行步骤 / 预期结果 标记（级别无关） ---
        if STEPS_RE.match(line):
            in_steps, in_results, in_precond = True, False, False
            continue
        if RESULTS_RE.match(line):
            in_results, in_steps, in_precond = True, False, False
            continue

        if in_precond:
            continue

        # 收集执行步骤行（编号列表或 bullet）
        if in_steps and current_point is not None:
            if re.match(r"^\d+\.", line) or line.startswith("- "):
                step_lines.append(line)
            continue

        # 收集预期结果行（编号列表或 bullet）
        if in_results and current_point is not None:
            if re.match(r"^\d+\.", line) or line.startswith("- "):
                result_lines.append(line)
            continue

    if current_point is not None:
        _flush_point(current_point)

    # --- 混搭检测：任一场景的直接子节点不能同时含场景和测试点 ---
    for path, kinds in sorted(scene_child_kinds.items()):
        if len(kinds) > 1:
            errors.append(
                f"场景 {_fmt_path(path)}「{scenes[path]['data']['text'][:20]}」的直接子节点"
                f"同时包含子场景和测试点，不允许混搭：要么全部下沉为子场景，要么全部改为测试点"
            )

    return node_tree, errors


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------

def iter_nodes(tree: list[dict[str, Any]]):
    """Depth-first walk over (node, depth), depth starting at 1."""
    def _walk(nodes: list[dict[str, Any]], depth: int):
        for n in nodes:
            yield n, depth
            yield from _walk(n.get("children", []), depth + 1)
    yield from _walk(tree, 1)


def _kind(node: dict[str, Any]) -> str:
    resource = node.get("data", {}).get("resource") or []
    return resource[0] if resource else ""


def count_scenarios(tree: list[dict[str, Any]]) -> int:
    return sum(1 for n, _ in iter_nodes(tree) if _kind(n) == "场景")


def count_leaf_scenarios(tree: list[dict[str, Any]]) -> int:
    """场景 whose children are 测试点 (i.e. the scenarios that actually hold cases)."""
    total = 0
    for n, _ in iter_nodes(tree):
        if _kind(n) != "场景":
            continue
        if any(_kind(c) == "测试点" for c in n.get("children", [])):
            total += 1
    return total


def max_scene_depth(tree: list[dict[str, Any]]) -> int:
    """Deepest 场景 nesting level (1 = 顶层场景)."""
    best = 0
    for n, depth in iter_nodes(tree):
        if _kind(n) == "场景":
            best = max(best, depth)
    return best


# ---------------------------------------------------------------------------
# Validation: 检测 full.md 中被解析器跳过或不合规的内容
# ---------------------------------------------------------------------------

def validate_full_md(text: str, parsed_tree: list[dict[str, Any]]) -> list[str]:
    """Compare raw markdown against parsed tree, return non-blocking warnings.

    Structural violations (混搭 / 断层 / 重复编号) are returned as errors by
    ``parse_full_md_with_errors`` instead, and always block the writeback.
    """
    warnings: list[str] = []

    # 1. 数量校验：原文标题数 vs 解析出的节点数
    md_scene_count = sum(1 for line in text.splitlines() if SCENE_RE.match(line.strip()))
    md_point_count = sum(1 for line in text.splitlines() if POINT_RE.match(line.strip()))

    parsed_scenes = count_scenarios(parsed_tree)
    parsed_points = sum(1 for n, _ in iter_nodes(parsed_tree) if _kind(n) == "测试点")

    if md_scene_count != parsed_scenes:
        warnings.append(
            f"场景数不匹配: markdown 中有 {md_scene_count} 个「场景N：」标题，解析出 {parsed_scenes} 个"
        )
    if md_point_count != parsed_points:
        warnings.append(
            f"测试点数不匹配: markdown 中有 {md_point_count} 个「测试点N.M：」标题，解析出 {parsed_points} 个"
        )

    # 2. 未识别的标题行（格式漂移）
    for i, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not HEADING_RE.match(line):
            continue
        if (SCENE_RE.match(line) or POINT_RE.match(line) or STEPS_RE.match(line)
                or RESULTS_RE.match(line) or PRECOND_RE.match(line)):
            continue
        warnings.append(f"第 {i} 行: 未识别的标题（非 场景N： / 测试点N.M： / 执行步骤 / 预期结果）: {line[:50]}")

    # 3. 空场景 / 无执行步骤的测试点
    for n, _ in iter_nodes(parsed_tree):
        kind = _kind(n)
        title = n["data"]["text"][:30]
        if kind == "场景" and not n.get("children"):
            warnings.append(f"场景「{title}」下没有任何子场景或测试点")
        if kind == "测试点":
            if not any(_kind(c) == "执行步骤" for c in n.get("children", [])):
                warnings.append(f"测试点「{title}」无执行步骤节点")

    # 4. 编号连续性（漏号通常意味着生成时被截断）
    numbers: dict[str, list[tuple[int, ...]]] = {"场景": [], "测试点": []}
    for line in text.splitlines():
        line = line.strip()
        m = SCENE_RE.match(line)
        if m:
            numbers["场景"].append(_path_of(m.group(1)))
            continue
        m = POINT_RE.match(line)
        if m:
            numbers["测试点"].append(_path_of(m.group(1)))
    for kind, paths in numbers.items():
        siblings: dict[tuple[int, ...], list[int]] = {}
        for path in paths:
            siblings.setdefault(path[:-1], []).append(path[-1])
        for parent, seq in siblings.items():
            scope = f"{_fmt_path(parent)}." if parent else ""
            # 乱序：sorted() 会掩盖顺序问题，必须单独判
            if seq != sorted(seq):
                warnings.append(
                    f"{kind}编号乱序: {scope}* 出现顺序为 {seq}，应按升序书写"
                    f"（顺序决定写入搬山后的节点次序，与编号不一致会造成误读）"
                )
            uniq = sorted(set(seq))
            expected = list(range(1, len(uniq) + 1))
            if uniq != expected:
                warnings.append(
                    f"{kind}编号不连续: {scope}* 实际为 {uniq}，期望 {expected}（可能漏写或截断）"
                )

    return warnings


def advisory_notes(tree: list[dict[str, Any]]) -> list[str]:
    """建议性提示：只打印，永不阻塞写回。"""
    notes: list[str] = []

    depth = max_scene_depth(tree)
    if depth > MAX_SCENE_DEPTH:
        notes.append(
            f"场景嵌套 {depth} 层，超过建议上限 {MAX_SCENE_DEPTH} 层。"
            f"平台支持更深，但过深通常说明该需求应拆成多个搬山用例。"
        )

    for n, _ in iter_nodes(tree):
        if _kind(n) != "场景":
            continue
        children = n.get("children", [])
        subs = [c for c in children if _kind(c) == "场景"]
        points = [c for c in children if _kind(c) == "测试点"]
        title = n["data"]["text"][:24]
        if len(subs) == 1:
            notes.append(f"场景「{title}」只有 1 个子场景，拆分收益不大，可考虑合并回上层")
        if len(points) > 10:
            notes.append(
                f"场景「{title}」下有 {len(points)} 个测试点，可考虑按维度拆成子场景"
            )

    return notes


def count_nodes(tree: list[dict[str, Any]]) -> int:
    total = 0
    for n in tree:
        total += 1 + count_nodes(n.get("children", []))
    return total


def count_test_points(tree: list[dict[str, Any]]) -> int:
    """测试点总数（场景可任意层嵌套，需递归统计）。"""
    return sum(1 for n, _ in iter_nodes(tree) if _kind(n) == "测试点")


def render_tree_summary(tree: list[dict[str, Any]], indent: str = "  ") -> list[str]:
    """Render 场景/测试点 outline for the dry-run summary.

    编号取自 markdown 原文（解析时记录在 ``_path``），**不按节点位置重新编号**，
    否则乱序书写时概览会把标签和内容配错，产生比不显示更糟的误导。
    """
    lines: list[str] = []

    def _walk(nodes: list[dict[str, Any]], depth: int) -> None:
        for node in nodes:
            kind = _kind(node)
            if kind not in ("场景", "测试点"):
                continue
            path = node.get("_path")
            label = _fmt_path(path) if path else "?"
            pad = indent * depth
            if kind == "场景":
                children = node.get("children", [])
                point_count = sum(1 for c in children if _kind(c) == "测试点")
                sub_count = sum(1 for c in children if _kind(c) == "场景")
                tail = f"({sub_count} 个子场景)" if sub_count else f"({point_count} 个测试点)"
                lines.append(f"{pad}场景{label}: {node['data']['text']} {tail}")
                _walk(children, depth + 1)
            else:
                lines.append(f"{pad}测试点{label}: {node['data']['text']}")

    _walk(tree, 1)
    return lines


def strip_internal_keys(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop parser-internal keys (``_path``) so only the API contract is emitted."""
    return [
        {
            "data": n["data"],
            "children": strip_internal_keys(n.get("children", [])),
        }
        for n in tree
    ]


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
    node_tree, errors = parse_full_md_with_errors(markdown)

    # 结构性错误一律阻塞，dry-run 与写回模式都不放行
    if errors:
        print(f"\n✗ 结构校验发现 {len(errors)} 个错误，已中止:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\n请修复 full.md 后重试。结构规则见 SKILL.md「full.md 格式规范」。", file=sys.stderr)
        return 2

    if not node_tree:
        print(f"ERROR: 未从 {full_md_path.name} 中解析出任何场景", file=sys.stderr)
        print("请检查 full.md 是否符合格式：## 场景N：标题 / ### 测试点N.M：标题", file=sys.stderr)
        return 2

    scenario_count = count_scenarios(node_tree)
    leaf_scenario_count = count_leaf_scenarios(node_tree)
    point_count = count_test_points(node_tree)
    total_nodes = count_nodes(node_tree)
    scene_depth = max_scene_depth(node_tree)

    # --- 2. 格式验证 ---
    notes = advisory_notes(node_tree)
    if notes:
        print("\nℹ 建议（不阻塞写回）:")
        for n in notes:
            print(f"  - {n}")

    warnings = validate_full_md(markdown, node_tree)
    if warnings:
        print(f"\n⚠ 格式验证发现 {len(warnings)} 个问题:")
        for w in warnings:
            print(f"  - {w}")
        print()

    # --- 3. 输出摘要 ---
    output_dir = args.output_dir or (full_md_path.parent / "writeback")
    output_dir.mkdir(parents=True, exist_ok=True)

    wire_tree = strip_internal_keys(node_tree)
    tree_path = output_dir / "node-tree.json"
    tree_path.write_text(json.dumps(wire_tree, ensure_ascii=False, indent=2), encoding="utf-8")

    depth_note = f", 场景最深 {scene_depth} 层" if scene_depth > 1 else ""
    print(
        f"✓ 解析完成: {scenario_count} 个场景（{leaf_scenario_count} 个含测试点）, "
        f"{point_count} 个测试点, {total_nodes} 个节点{depth_note}"
    )
    print(f"  节点树: {tree_path}")

    if args.dry_run:
        print("\n[dry-run] 跳过写回")
        for outline in render_tree_summary(node_tree):
            print(f"  {outline}")
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
        "nodeTreeList": wire_tree,
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
