"""op_matrix.py 的判定规则。每条规则对应一个真实缺陷形态，fixture 用最小读写集复现它。"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import op_matrix  # noqa: E402


def model(**overrides):
    base = {
        "feature": "fixture",
        "write_points": [
            {"id": "W1", "field": "msg.content", "layers": {"redis": "sync", "hbase": "async"}},
            {"id": "W2", "field": "msg.snapshot", "layers": {"redis": "sync", "hbase": "async"}},
            {"id": "W3", "field": "msg.like", "layers": {"redis": "sync", "hbase": "sync"}},
            {"id": "W4", "field": "msg.content", "layers": {"redis": "sync", "hbase": "sync"}},
        ],
        "read_points": [
            {"id": "R1", "field": "msg.content", "layer": "hbase"},
            {"id": "R2", "field": "msg.snapshot", "layer": "redis"},
            {"id": "R3", "field": "msg.like", "layer": "redis"},
        ],
        "atoms": [
            {"id": "ASK", "name": "提问", "writes": ["W1", "W2"], "reads": [], "creates_scope": True},
            {"id": "LIKE", "name": "点赞", "writes": ["W3"], "reads": ["R1"]},
            {"id": "REGEN", "name": "重新生成", "writes": ["W4"], "reads": ["R1"], "replaces": ["msg"]},
            {"id": "REENTER", "name": "重进", "writes": [], "reads": ["R2", "R3"]},
        ],
        "implicit_checklist": {x: "N/A: fixture" for x in op_matrix.IMPLICIT_ACTIONS},
    }
    base.update(overrides)
    return base


def flags(data, a_id, b_id):
    m = op_matrix.Model(data)
    by = {a["id"]: a for a in m.all_atoms}
    return op_matrix.pair_flags(m, by[a_id], by[b_id])


class PairRuleTest(unittest.TestCase):
    def test_async_write_then_read_on_that_layer_is_race(self):
        # 首轮 HBase 异步落库，update 路径只查 HBase → 紧接着点赞会查不到记录
        kinds = [k for k, _ in flags(model(), "ASK", "LIKE")]
        self.assertIn("RACE", kinds)

    def test_sync_write_then_read_is_plain_raw(self):
        kinds = [k for k, _ in flags(model(), "REGEN", "LIKE")]
        self.assertIn("RAW", kinds)
        self.assertNotIn("RACE", kinds)

    def test_replacer_missing_field_read_later_is_stale(self):
        # 重新生成替换了回答，却没重写 snapshot；重进读 snapshot → 旧值
        details = [v for k, v in flags(model(), "REGEN", "REENTER") if k == "STALE"]
        self.assertTrue(any(v.startswith("msg.snapshot") for v in details), details)

    def test_partial_update_without_replaces_is_not_stale(self):
        # 点赞本来就只改 like，不应要求它重写 snapshot
        kinds = [k for k, _ in flags(model(), "LIKE", "REENTER")]
        self.assertNotIn("STALE", kinds)

    def test_read_layer_never_written_is_layer_asymmetry(self):
        data = model()
        data["write_points"].append({"id": "W5", "field": "msg.like", "layer": "hbase", "mode": "sync"})
        data["atoms"][1]["writes"] = ["W5"]  # 点赞只写 HBase，重进读 Redis
        kinds = [k for k, _ in flags(data, "LIKE", "REENTER")]
        self.assertIn("LAYER", kinds)


class RenderTest(unittest.TestCase):
    def test_creation_atom_never_comes_second(self):
        text = op_matrix.render(model())
        self.assertNotIn("→ `ASK`", text)

    def test_replacer_gap_listed_in_coverage(self):
        text = op_matrix.render(model())
        self.assertIn("`REGEN` 重新生成 替换 `msg`，但没有重写：`msg.like`、`msg.snapshot`", text)

    def test_revived_value_chain(self):
        # 点赞 → 重新生成（没重置 like）→ 重进读到 like：赞复活并挂到新答案上
        text = op_matrix.render(model())
        self.assertIn("`LIKE` 点赞 → `REGEN` 重新生成 → `REENTER` 重进：`msg.like`", text)

    def test_orphan_write_point_reported(self):
        data = model()
        data["write_points"].append({"id": "W9", "field": "msg.extra", "layer": "redis"})
        text = op_matrix.render(data)
        self.assertIn("### 孤儿写入点（1）", text)
        self.assertIn("`W9` msg.extra", text)

    def test_unanswered_implicit_actions_reported(self):
        text = op_matrix.render(model(implicit_checklist={}))
        self.assertIn(f"### 隐式动作清单未作答或答案无效（{len(op_matrix.IMPLICIT_ACTIONS)}/", text)

    def test_implicit_answer_must_reference_real_atom_or_na_reason(self):
        answers = {x: "N/A: fixture" for x in op_matrix.IMPLICIT_ACTIONS}
        first, second, third, fourth = op_matrix.IMPLICIT_ACTIONS[:4]
        answers[first] = "已覆盖"          # 自由文本，没有引用原子
        answers[second] = "A9"             # 不存在的原子
        answers[third] = "N/A:"            # 没写理由
        answers[fourth] = "REENTER（冷启动另补一条）"  # 有效：引用已有原子并附说明
        text = op_matrix.render(model(implicit_checklist=answers))
        self.assertIn("### 隐式动作清单未作答或答案无效（3/", text)
        self.assertIn(f"- {first}：「已覆盖」既没有引用已有原子", text)
        self.assertIn(f"- {second}：引用了不存在的原子 A9", text)
        self.assertIn(f"- {third}：`N/A` 后没有写理由", text)
        self.assertNotIn(f"- {fourth}：", text)

    def test_paraphrased_checklist_key_is_reported(self):
        answers = {x: "N/A: fixture" for x in op_matrix.IMPLICIT_ACTIONS}
        answers["退出重进"] = answers.pop(op_matrix.IMPLICIT_ACTIONS[0])
        text = op_matrix.render(model(implicit_checklist=answers))
        self.assertIn(f"- {op_matrix.IMPLICIT_ACTIONS[0]}：未作答", text)
        self.assertIn("不在内置清单中", text)
        self.assertIn("- 退出重进", text)

    def test_missing_layer_is_reported(self):
        data = model()
        data["read_points"][0].pop("layer")
        text = op_matrix.render(data)
        self.assertIn("### 缺少层信息的读写点（1）", text)
        self.assertIn("`R1` msg.content", text)

    def test_stale_without_field_intersection_is_kept(self):
        data = model()
        data["atoms"].append({"id": "VIEW", "name": "只看点赞", "writes": [], "reads": ["R3"]})
        kinds = [k for k, _ in flags(data, "REGEN", "VIEW")]
        self.assertEqual(kinds, ["STALE"])
        self.assertIn("无任何依赖标记已剪枝", op_matrix.render(data))

    def test_represented_variant_is_folded(self):
        data = model()
        data["atoms"].append({"id": "SKIP", "name": "跳过思考", "writes": ["W4"], "reads": ["R1"],
                              "replaces": ["msg"], "represented_by": "REGEN"})
        text = op_matrix.render(data)
        self.assertNotIn("`SKIP` 跳过思考 →", text)
        self.assertIn("`REGEN` 重新生成 ≡ `SKIP` 跳过思考", text)
        self.assertNotIn("未指定代表：", text)

    def test_represented_by_with_different_sets_is_flagged(self):
        data = model()
        data["atoms"].append({"id": "SKIP", "name": "跳过思考", "writes": ["W3"], "reads": [],
                              "represented_by": "REGEN"})
        self.assertIn("不能折叠", op_matrix.render(data))


class CliTest(unittest.TestCase):
    def test_bad_reference_exits_nonzero(self):
        data = model()
        data["atoms"][1]["writes"] = ["NOPE"]
        path = SKILL_DIR / "tests" / "_bad_atoms.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "op_matrix.py"), str(path)],
                                  capture_output=True, text=True)
        finally:
            path.unlink()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("不存在的写入点 NOPE", proc.stdout)

    def test_represented_by_cycle_is_an_error(self):
        data = model()
        data["atoms"][1]["represented_by"] = "REENTER"
        data["atoms"][3]["represented_by"] = "LIKE"
        errors = op_matrix.Model(data).errors
        self.assertTrue(any("代表 REENTER 自己也标了 represented_by" in e for e in errors), errors)
        self.assertEqual(op_matrix.main([str(self._dump(data))]), 1)

    def test_malformed_entries_are_errors_not_crashes(self):
        data = model()
        data["atoms"].append({"id": "NONAME", "writes": ["W3"]})
        data["write_points"].append({"field": "msg.x"})
        data["read_points"].append({"id": "R1", "field": "msg.dup", "layer": "redis"})
        errors = op_matrix.Model(data).errors
        self.assertIn("原子第 5 项（NONAME）缺少必填字段 name", errors)
        self.assertIn("写入点第 5 项（无 id）缺少必填字段 id", errors)
        self.assertIn("读取点 id 重复：R1", errors)
        op_matrix.render(data)  # 不应抛异常

    def _dump(self, data):
        path = SKILL_DIR / "tests" / "_cycle_atoms.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(path.unlink)
        return path

    def test_bundled_example_reproduces_known_findings(self):
        data = json.loads((SKILL_DIR / "examples" / "ai-search-answer-card" / "atoms.json").read_text(encoding="utf-8"))
        text = op_matrix.render(data)
        self.assertIn("`A2` 重新生成 替换 `msg`，但没有重写：`msg.extData.feedback`、`msg.mistakeMessage`", text)
        self.assertIn("`A1` 点赞/点踩 → `A2` 重新生成 → `A3` 退出搜索页再重进：`msg.extData.feedback`", text)
        self.assertIn("**RACE** msg.content：A0 对 hbase 是异步写，A1 读该层", text)


if __name__ == "__main__":
    unittest.main()
