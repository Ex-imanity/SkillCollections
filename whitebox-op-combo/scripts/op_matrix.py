#!/usr/bin/env python3
"""原子动作读写集 → 覆盖缺口 + 冲突组合候选。

输入 atoms.json（结构见 references/atomization.md「atoms.json 结构」），输出 markdown 报告：

1. 覆盖检查：孤儿写入点 / 孤儿读取点 / 空原子 / 可合并原子 / 缺少层信息的读写点 / 隐式动作清单未作答或答案无效
   + 替换不完整：声明 replaces 的原子（语义上产出该实体的新版本），漏写了实体的哪些字段
2. 两两组合：只保留至少带一个依赖标记的有序对，其余计入「已剪枝」
   - RAW   A 写 → B 读 同一字段（顺序决定 B 看到什么）
   - WAW   A、B 写同一字段（覆盖 / 合并语义）
   - STALE A 替换了实体 E（replaces），B 读取 E 中 A 没重写的字段（陈旧值）
   - RACE  B 读取的层上，A 对该字段的写入是异步的（异步窗口）
   - LAYER B 读取的层，A 根本不写（读写层不对称）
   creates_scope 的原子（创建范围对象的那一步）只能排第一，(X, 创建) 与 (创建, 创建) 不成立
   represented_by 的原子（读写集与代表原子相同的变体）不参与组合，由代表原子替它出现
3. 三元穿透链：A 写 F，B 替换了 F 所在实体却没重写 F，C 读 F（B 本该重置 F）
4. 中断点：声明了 stages 的原子，逐阶段列出需要追踪的中断场景

只依赖标准库。用法：
    python op_matrix.py atoms.json [--out pairs.md] [--max-chains 30]
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

# 业务无关的「非 UI 动作」清单：最容易被漏掉，也最常出问题。
# atoms.json 的 implicit_checklist 必须对每一项作答：原子 id，或 "N/A: 理由"。
IMPLICIT_ACTIONS = [
    "退出页面再重进",
    "切后台再回前台",
    "杀进程后重启",
    "断网或弱网下操作",
    "同账号另一设备操作",
    "登录态变化（登出/切号）",
    "等待超过缓存或临时状态的TTL",
    "连点或重复提交",
    "操作进行中被打断（流式输出中退出等）",
    "他人或后台修改了同一对象",
]

FLAG_WEIGHT = {"STALE": 5, "RACE": 4, "LAYER": 4, "WAW": 3, "RAW": 1}

# 形如 A3、A2b、B12 的记号：出现在隐式清单答案里却不是已有原子时，判为无效引用
ATOM_ID_LIKE = re.compile(r"(?<![A-Za-z0-9_])[A-Z]\d+[a-z]?(?![A-Za-z0-9_])")
NA_PREFIX = re.compile(r"^N/A\s*[:：]\s*(.*)$", re.S)


def entity_of(field: str) -> str:
    return field.split(".", 1)[0]


def layer_modes(point: dict) -> dict[str | None, str]:
    """写入点的层 → 同步/异步。支持 {"layer": "redis", "mode": "sync"} 或 {"layers": {"redis": "sync", "hbase": "async"}}。"""
    if isinstance(point.get("layers"), dict):
        return dict(point["layers"])
    return {point.get("layer"): point.get("mode", "sync")}


def layer_label(point: dict) -> str:
    return "/".join(f"{k}({v})" if v == "async" else str(k) for k, v in layer_modes(point).items())


def _well_formed(items: Any, required: tuple[str, ...], kind: str, errors: list[str]) -> list[dict]:
    """缺必填键或 id 重复的条目记为错误并丢弃，避免后续 KeyError。"""
    kept: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(items or []):
        if not isinstance(item, dict):
            errors.append(f"{kind}第 {i + 1} 项不是对象")
            continue
        lacking = [k for k in required if not item.get(k)]
        if lacking:
            errors.append(f"{kind}第 {i + 1} 项（{item.get('id', '无 id')}）缺少必填字段 {'、'.join(lacking)}")
            continue
        if item["id"] in seen:
            errors.append(f"{kind} id 重复：{item['id']}")
            continue
        seen.add(item["id"])
        kept.append(item)
    return kept


class Model:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.errors: list[str] = []
        self.wp = {p["id"]: p for p in _well_formed(data.get("write_points"), ("id", "field"), "写入点", self.errors)}
        self.rp = {p["id"]: p for p in _well_formed(data.get("read_points"), ("id", "field"), "读取点", self.errors)}
        self.all_atoms = _well_formed(data.get("atoms"), ("id", "name"), "原子", self.errors)
        by_id = {a["id"]: a for a in self.all_atoms}
        # 组合只用代表原子；变体只参与覆盖检查
        self.atoms = [a for a in self.all_atoms if not a.get("represented_by")]
        for a in self.all_atoms:
            rep = a.get("represented_by")
            if not rep:
                continue
            if rep not in by_id:
                self.errors.append(f"原子 {a['id']} 的 represented_by 指向不存在的 {rep}")
            elif by_id[rep].get("represented_by"):
                # 代表本身也是变体（含互相指向、自指）：两者都会从组合中消失
                self.errors.append(f"原子 {a['id']} 的代表 {rep} 自己也标了 represented_by，代表必须是不折叠的原子")
        for a in self.all_atoms:
            for pid in a.get("writes", []):
                if pid not in self.wp:
                    self.errors.append(f"原子 {a['id']} 引用了不存在的写入点 {pid}")
            for pid in a.get("reads", []):
                if pid not in self.rp:
                    self.errors.append(f"原子 {a['id']} 引用了不存在的读取点 {pid}")

    def writes(self, a: dict) -> list[dict]:
        return [self.wp[i] for i in a.get("writes", []) if i in self.wp]

    def reads(self, a: dict) -> list[dict]:
        return [self.rp[i] for i in a.get("reads", []) if i in self.rp]

    def wfields(self, a: dict) -> set[str]:
        return {p["field"] for p in self.writes(a)}

    def rfields(self, a: dict) -> set[str]:
        return {p["field"] for p in self.reads(a)}

    def entity_fields(self, entity: str) -> set[str]:
        """实体的全部已知字段：所有读写点里出现过的该实体字段。"""
        pts = list(self.wp.values()) + list(self.rp.values())
        return {p["field"] for p in pts if entity_of(p["field"]) == entity}

    def ordered_pairs(self):
        for a, b in itertools.product(self.atoms, repeat=2):
            if b.get("creates_scope"):
                continue
            yield a, b


def coverage(m: Model) -> list[str]:
    out = ["## 1. 覆盖检查", ""]
    used_w = {i for a in m.all_atoms for i in a.get("writes", [])}
    used_r = {i for a in m.all_atoms for i in a.get("reads", [])}
    orphan_w = [p for i, p in m.wp.items() if i not in used_w]
    orphan_r = [p for i, p in m.rp.items() if i not in used_r]

    def plist(title: str, items: list[dict], hint: str) -> None:
        out.append(f"### {title}（{len(items)}）")
        out.append("")
        if not items:
            out.append("无。")
        else:
            out.append(hint)
            out.append("")
            for p in items:
                out.append(f"- `{p['id']}` {p['field']} @ {layer_label(p)} — {p.get('where', '')}")
        out.append("")

    plist("孤儿写入点", orphan_w,
          "没有任何原子动作会触发这些写入：要么漏了原子动作，要么是死代码——两者都要在 atoms.md 里给出结论。")
    plist("孤儿读取点", orphan_r,
          "没有任何原子动作会走到这些读取：检查是否漏了「读」类动作（重进、刷新、另一端查看）。")

    empty = [a for a in m.all_atoms if not a.get("writes") and not a.get("reads")]
    out.append(f"### 空原子（{len(empty)}）")
    out.append("")
    out.append("无。" if not empty else "未映射到任何读写点：补映射，或说明它为何不影响共享状态并移出范围。")
    for a in empty:
        out.append(f"- `{a['id']}` {a['name']}")
    out.append("")

    groups: dict[tuple, list[str]] = {}
    for a in m.all_atoms:
        if a.get("writes") or a.get("reads"):
            key = (tuple(sorted(a.get("writes", []))), tuple(sorted(a.get("reads", []))))
            groups.setdefault(key, []).append(f"`{a['id']}` {a['name']}")
    by_id = {a["id"]: a for a in m.all_atoms}
    dup = [g for g in groups.values() if len(g) > 1]
    unresolved = [g for g in dup
                  if sum(1 for x in g if not by_id[x.split("`")[1]].get("represented_by")) > 1]
    out.append(f"### 读写集完全相同的原子（{len(dup)} 组，未指定代表 {len(unresolved)} 组）")
    out.append("")
    out.append("无。" if not dup else "读写集相同意味着对共享状态是同一个动作。给变体标 `represented_by`，组合时只保留代表；"
               "变体仍需单独覆盖它自己的入口可见性和交互。")
    for g in dup:
        mark = "⚠ 未指定代表：" if g in unresolved else ""
        out.append(f"- {mark}" + " ≡ ".join(g))
    out.append("")
    variants = [a for a in m.all_atoms if a.get("represented_by")]
    for a in variants:
        rep = by_id.get(a["represented_by"])
        if rep and (sorted(a.get("writes", [])), sorted(a.get("reads", []))) != (sorted(rep.get("writes", [])), sorted(rep.get("reads", []))):
            out.append(f"- ⚠ `{a['id']}` 标了 represented_by `{rep['id']}`，但两者读写集不同，不能折叠")
    if variants:
        out.append("")

    no_layer = [p for p in m.wp.values() if None in layer_modes(p)] + [p for p in m.rp.values() if not p.get("layer")]
    out.append(f"### 缺少层信息的读写点（{len(no_layer)}）")
    out.append("")
    out.append("无。" if not no_layer else "这些点不参与 RACE / LAYER 判定（只剩 RAW / WAW），异步窗口和读写层不对称会被漏掉：补 `layer` / `layers`。")
    for p in no_layer:
        out.append(f"- `{p['id']}` {p['field']} — {p.get('where', '')}")
    out.append("")

    out.append("### 替换型原子漏写的字段")
    out.append("")
    replacers = [a for a in m.all_atoms if a.get("replaces") and not a.get("represented_by")]
    if not replacers:
        out.append("无声明 replaces 的原子。若有「重新生成 / 覆盖提交 / 重新上传」这类产出新版本的动作，应声明 replaces。")
    for a in replacers:
        for e in a["replaces"]:
            missing = sorted(m.entity_fields(e) - m.wfields(a))
            if missing:
                out.append(f"- `{a['id']}` {a['name']} 替换 `{e}`，但没有重写：" + "、".join(f"`{f}`" for f in missing)
                           + "。逐个判定：本应重置（缺陷候选）还是有意保留（写明理由）")
            else:
                out.append(f"- `{a['id']}` {a['name']} 替换 `{e}`：已覆盖全部已知字段")
    out.append("")

    answered = m.data.get("implicit_checklist") or {}
    ids = {a["id"] for a in m.all_atoms}
    problems = []
    for x in IMPLICIT_ACTIONS:
        why = checklist_problem(str(answered.get(x, "")), ids)
        if why:
            problems.append(f"- {x}：{why}")
    extra = [k for k in answered if k not in IMPLICIT_ACTIONS]
    out.append(f"### 隐式动作清单未作答或答案无效（{len(problems)}/{len(IMPLICIT_ACTIONS)}）")
    out.append("")
    out.append("全部已作答。" if not problems else
               "每项须引用至少一个已有原子 id（可附说明），或写 `N/A: 理由`。键必须与内置清单原文一致：")
    out += problems
    if extra:
        out.append("")
        out.append("以下键不在内置清单中（自定义项可以保留；若是改写了内置项的原文，对应内置项会被判为未作答）：")
        out += [f"- {k}" for k in extra]
    out.append("")
    return out


def checklist_problem(answer: str, ids: set[str]) -> str | None:
    """隐式清单的一项答案是否有效；有效返回 None，否则返回原因。"""
    answer = answer.strip()
    if not answer:
        return "未作答"
    na = NA_PREFIX.match(answer)
    if na:
        return None if na.group(1).strip() else "`N/A` 后没有写理由"
    unknown = sorted({t for t in ATOM_ID_LIKE.findall(answer) if t not in ids})
    if unknown:
        return f"引用了不存在的原子 {'、'.join(unknown)}"
    if not any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(i)}(?![A-Za-z0-9_])", answer) for i in ids):
        return f"「{answer}」既没有引用已有原子，也不是 `N/A: 理由`"
    return None


def pair_flags(m: Model, a: dict, b: dict) -> list[tuple[str, str]]:
    flags: list[tuple[str, str]] = []
    aw, bw, br = m.wfields(a), m.wfields(b), m.rfields(b)

    for f in sorted(aw & br):
        flags.append(("RAW", f))
        a_layers: dict = {}
        for p in m.writes(a):
            if p["field"] == f:
                a_layers.update(layer_modes(p))
        for r in (p for p in m.reads(b) if p["field"] == f):
            layer = r.get("layer")
            if layer is None or None in a_layers:
                continue
            if layer not in a_layers:
                flags.append(("LAYER", f"{f}：{b['id']} 读 {layer}，{a['id']} 只写 {'/'.join(sorted(map(str, a_layers)))}"))
            elif a_layers[layer] == "async":
                flags.append(("RACE", f"{f}：{a['id']} 对 {layer} 是异步写，{b['id']} 读该层——存在异步窗口，能否撞上取决于操作间隔与补偿逻辑"))

    for f in sorted(aw & bw):
        flags.append(("WAW", f))

    replaced = set(a.get("replaces", []))
    for f in sorted(br - aw):
        if entity_of(f) in replaced:
            flags.append(("STALE", f"{f}：{a['id']} 替换了 {entity_of(f)} 却没重写该字段，{b['id']} 读到的是替换前的旧值"))
    return flags


def pairs(m: Model) -> tuple[list[str], list[tuple[int, dict, dict, list]]]:
    rows = []
    pruned = 0
    candidates = list(m.ordered_pairs())
    for a, b in candidates:
        fl = pair_flags(m, a, b)
        if not fl:
            pruned += 1
            continue
        score = sum(FLAG_WEIGHT[k] for k, _ in fl)
        rows.append((score, a, b, fl))
    rows.sort(key=lambda r: (-r[0], r[1]["id"], r[2]["id"]))
    total = len(m.atoms) ** 2
    impossible = total - len(candidates)
    out = ["## 2. 两两有序组合（A 先 → B 后）", "",
           f"共 {total} 个有序对（含同一动作重复）：创建动作排在后面不成立 **{impossible}** 对，"
           f"无任何依赖标记已剪枝 **{pruned}** 对，剩余 **{len(rows)}** 对待分析。", "",
           "依赖标记：RAW / WAW / RACE / LAYER 要求 A 的写与 B 的读写在同一字段上相交；"
           "STALE 不要求相交——A 替换了实体、B 读该实体里 A 没重写的字段即成立。", "",
           "分值只用于排序：STALE 5 / RACE 4 / LAYER 4 / WAW 3 / RAW 1。RAW 单独出现通常只是「正常的先写后读」，"
           "但仍需确认 B 读到的是 A 写的值。", "",
           "| 分 | A → B | 标记 |", "|---|---|---|"]
    for score, a, b, fl in rows:
        marks = "<br>".join(f"**{k}** {v}" for k, v in fl)
        out.append(f"| {score} | `{a['id']}` {a['name']} → `{b['id']}` {b['name']} | {marks} |")
    out.append("")
    return out, rows


def chains(m: Model, limit: int) -> list[str]:
    found = []
    for a, b, c in itertools.permutations(m.atoms, 3):
        if b.get("creates_scope") or c.get("creates_scope"):
            continue
        replaced = set(b.get("replaces", []))
        for f in sorted(m.wfields(a) & m.rfields(c)):
            if entity_of(f) in replaced and f not in m.wfields(b):
                found.append((a, b, c, f))
    # A 是创建动作的链只是在复述「B 漏写了 F」，已由替换检查与 STALE 覆盖；用户操作写入的值被复活更值得看
    found.sort(key=lambda t: (bool(t[0].get("creates_scope")), t[0]["id"], t[1]["id"], t[2]["id"]))
    out = ["## 3. 三元穿透链（A → B → C）", "",
           "A 写了字段 F；B 替换了 F 所在的实体却没重写 F；C 读 F。"
           "若按产品语义 B 应当重置 F（如重新生成应清空旧的点赞），C 就会看到「复活」的旧值，而且挂在了新版本上。", ""]
    if not found:
        out.append("无。")
    for a, b, c, f in found[:limit]:
        out.append(f"- `{a['id']}` {a['name']} → `{b['id']}` {b['name']} → `{c['id']}` {c['name']}：`{f}`")
    if len(found) > limit:
        out.append(f"- ……另有 {len(found) - limit} 条，用 --max-chains 调大查看")
    out.append("")
    return out


def interrupts(m: Model) -> list[str]:
    out = ["## 4. 中断点", "",
           "对每个阶段追踪：断开被谁、在哪一刻探测到 → 已写入/未写入的状态 → 重进后读到什么 → 其他原子紧接着操作会怎样。", ""]
    staged = [a for a in m.atoms if a.get("stages")]
    if not staged:
        out.append("无声明 stages 的原子。若存在流式输出、多步提交、长任务，应在 atoms.json 中补 stages。")
    for a in staged:
        for s in a["stages"]:
            out.append(f"- `{a['id']}` {a['name']} 中断于「{s}」")
    out.append("")
    return out


def render(data: dict[str, Any], max_chains: int = 30) -> str:
    m = Model(data)
    out = [f"# 操作组合矩阵：{data.get('feature', '未命名')}", ""]
    if m.errors:
        out += ["## ⚠ atoms.json 引用错误", ""] + [f"- {e}" for e in m.errors] + [""]
    out += coverage(m)
    pair_lines, _ = pairs(m)
    out += pair_lines
    out += chains(m, max_chains)
    out += interrupts(m)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("atoms", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max-chains", type=int, default=30)
    args = ap.parse_args(argv)
    data = json.loads(args.atoms.read_text(encoding="utf-8"))
    text = render(data, args.max_chains)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        sys.stdout.write(text + "\n")
    return 1 if Model(data).errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
