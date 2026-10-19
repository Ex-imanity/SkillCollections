#!/usr/bin/env python3
"""Read reference cases over the existing Banshan HTTP endpoint; no MCP configuration."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from writeback import case_children, mcp_call


def render(nodes: list, depth: int = 1) -> str:
    parts = []
    for node in nodes:
        parts.append(f"{'#' * min(depth, 6)} {node['data']['text']}\n")
        parts.append(render(node.get("children", []), depth + 1))
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.case_id <= 0:
        parser.error("case-id 必须为正数")
    try:
        nodes = case_children(mcp_call("testCaseDetail", {"caseId": str(args.case_id)}))
        if not nodes:
            raise ValueError("参考用例没有节点")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render(nodes), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        print("读取参考用例失败；可粘贴 Markdown 或跳过参考，不阻塞生成", file=sys.stderr)
        return 1
    print(f"参考用例已保存: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
