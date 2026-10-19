"""多级场景解析：编号即路径（number-as-path）。"""
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "writeback.py"
SPEC = importlib.util.spec_from_file_location("case_lite_writeback_nested", SCRIPT_PATH)
writeback = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(writeback)


def _kinds(node):
    return node["data"]["resource"][0]


NESTED_MD = """# 完整用例

## 场景1：单层场景

### 测试点1.1：直接挂测试点

#### 执行步骤
1. a

#### 预期结果
1. b

## 场景2：含子场景

### 场景2.1：子场景一

#### 测试点2.1.1：点一

#### 执行步骤
1. a

#### 预期结果
1. b

#### 测试点2.1.2：点二

#### 执行步骤
1. a

### 场景2.2：子场景二

#### 测试点2.2.1：点三

#### 执行步骤
1. a
"""


class NestedSceneParseTest(unittest.TestCase):
    def test_number_path_builds_nested_tree(self):
        tree, errors = writeback.parse_full_md_with_errors(NESTED_MD)
        self.assertEqual(errors, [])
        self.assertEqual(len(tree), 2)

        flat, nested = tree
        self.assertEqual(_kinds(flat), "场景")
        self.assertEqual([_kinds(c) for c in flat["children"]], ["测试点"])

        self.assertEqual([c["data"]["text"] for c in nested["children"]], ["子场景一", "子场景二"])
        self.assertEqual([_kinds(c) for c in nested["children"]], ["场景", "场景"])

        sub1 = nested["children"][0]
        self.assertEqual([c["data"]["text"] for c in sub1["children"]], ["点一", "点二"])

    def test_counts_recurse_through_nesting(self):
        tree = writeback.parse_full_md(NESTED_MD)
        self.assertEqual(writeback.count_scenarios(tree), 4)      # 场景1, 2, 2.1, 2.2
        self.assertEqual(writeback.count_leaf_scenarios(tree), 3)  # 场景1, 2.1, 2.2
        self.assertEqual(writeback.count_test_points(tree), 4)
        self.assertEqual(writeback.max_scene_depth(tree), 2)

    def test_heading_level_is_ignored(self):
        """标题级别不参与解析，写错级别不应改变树结构。"""
        drifted = NESTED_MD.replace("### 场景2.1：", "## 场景2.1：")
        drifted = drifted.replace("#### 测试点2.1.1：", "###### 测试点2.1.1：")
        self.assertEqual(
            writeback.parse_full_md(drifted),
            writeback.parse_full_md(NESTED_MD),
        )

    def test_bold_step_markers_are_recognised(self):
        md = NESTED_MD.replace("#### 执行步骤", "**执行步骤**").replace("#### 预期结果", "**预期结果**")
        self.assertEqual(writeback.parse_full_md(md), writeback.parse_full_md(NESTED_MD))


class StructuralErrorTest(unittest.TestCase):
    def test_mixing_subscenes_and_points_is_rejected(self):
        md = """## 场景1：混搭
### 测试点1.1：点
#### 执行步骤
1. a
### 场景1.1：子场景
#### 测试点1.1.1：点
#### 执行步骤
1. a
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("混搭" in e for e in errors), errors)

    def test_orphan_subscene_is_rejected(self):
        md = """## 场景1：有父
### 测试点1.1：点
#### 执行步骤
1. a
### 场景3.1：父场景3不存在
#### 测试点3.1.1：点
#### 执行步骤
1. a
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("父场景 3 不存在" in e for e in errors), errors)

    def test_duplicate_scene_number_is_rejected(self):
        md = """## 场景1：一
### 测试点1.1：点
#### 执行步骤
1. a
## 场景1：撞车
### 测试点1.2：点
#### 执行步骤
1. a
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("重复定义" in e for e in errors), errors)

    def test_single_segment_test_point_is_rejected(self):
        md = """## 场景1：一
### 测试点1：编号只有一段
#### 执行步骤
1. a
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("至少需要两段" in e for e in errors), errors)


class CodexReviewRegressionTest(unittest.TestCase):
    """回归：2026-09-03 Codex 跨 agent 审核提出的四个缺陷。"""

    def test_duplicate_test_point_number_is_error_not_warning(self):
        """P1: 文档把「编号不重复」列为硬约束，测试点必须和场景一样按 error 处理。"""
        md = """## 场景1：一
### 测试点1.1：第一个
#### 执行步骤
1. a
### 测试点1.1：撞车
#### 执行步骤
1. b
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("测试点编号 1.1 重复定义" in e for e in errors), errors)

    def test_oversized_number_degrades_cleanly(self):
        """P3: 4300+ 位数字在 Python 3.11+ 会让 int() 抛 ValueError，必须先被正则挡掉。"""
        md = "## 场景" + "5" * 5000 + "：巨号\n### 测试点1.1：x\n#### 执行步骤\n1. a\n"
        tree, errors = writeback.parse_full_md_with_errors(md)  # 关键：不得抛 ValueError
        self.assertEqual(tree, [])
        # 超长标题不被识别为场景 → 走「未识别的标题」告警
        self.assertTrue(any("未识别的标题" in w for w in writeback.validate_full_md(md, tree)))
        # 级联结果：其下的测试点因父场景未注册而报孤儿错误，这是正确行为
        self.assertTrue(any("父场景 1 不存在" in e for e in errors), errors)

    def test_out_of_order_siblings_are_warned(self):
        """P1: 乱序不是跳号，sorted() 会掩盖它，必须单独检测。"""
        md = """## 场景1：一
### 测试点1.2：先写的
#### 执行步骤
1. a
### 测试点1.1：后写的
#### 执行步骤
1. b
"""
        tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertEqual(errors, [])
        warnings = writeback.validate_full_md(md, tree)
        self.assertTrue(any("乱序" in w for w in warnings), warnings)

    def test_summary_keeps_original_numbers(self):
        """P1: 概览按位置重编号会把标签和内容配错，必须用 markdown 原始编号。"""
        md = """## 场景1：一
### 测试点1.2：先写的
#### 执行步骤
1. a
### 测试点1.1：后写的
#### 执行步骤
1. b
"""
        tree = writeback.parse_full_md(md)
        summary = writeback.render_tree_summary(tree)
        self.assertTrue(any("测试点1.2: 先写的" in l for l in summary), summary)
        self.assertTrue(any("测试点1.1: 后写的" in l for l in summary), summary)

    def test_hard_depth_cap_prevents_recursion_error(self):
        """P3: iter_nodes/count_nodes 是递归的，千层输入会 RecursionError。"""
        md = "\n".join("## 场景" + ".".join(["1"] * d) + f"：L{d}" for d in range(1, 1200))
        tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertTrue(any("超过硬上限" in e for e in errors), errors[:2])
        writeback.count_nodes(tree)          # 不得 RecursionError
        writeback.max_scene_depth(tree)

    def test_internal_path_never_reaches_wire_payload(self):
        """_path 是解析器内部键，不能出现在发给搬山的 payload 里。"""
        md = "## 场景1：一\n### 场景1.1：子\n#### 测试点1.1.1：x\n#### 执行步骤\n1. a\n"
        tree = writeback.parse_full_md(md)
        self.assertIn("_path", tree[0])

        def assert_clean(nodes):
            for n in nodes:
                self.assertEqual(set(n.keys()), {"data", "children"})
                assert_clean(n["children"])

        assert_clean(writeback.strip_internal_keys(tree))


class AdvisoryTest(unittest.TestCase):
    def test_excess_depth_is_advisory_not_blocking(self):
        md = """## 场景1：一
### 场景1.1：二
#### 场景1.1.1：三
##### 场景1.1.1.1：四
###### 测试点1.1.1.1.1：点
**执行步骤**
1. a
"""
        _tree, errors = writeback.parse_full_md_with_errors(md)
        self.assertEqual(errors, [])
        tree = writeback.parse_full_md(md)
        self.assertTrue(any("超过建议上限" in n for n in writeback.advisory_notes(tree)))
        self.assertFalse(any("超过建议上限" in w for w in writeback.validate_full_md(md, tree)))


class BackwardCompatTest(unittest.TestCase):
    def test_legacy_flat_markdown_is_unchanged(self):
        legacy = """## 场景1：速搭端-下发重置密码链接

### 测试点1.1：未输入userId时执行

#### 执行步骤
1. 打开页面
2. 点击执行

#### 预期结果
1. 不出现链接
"""
        tree, errors = writeback.parse_full_md_with_errors(legacy)
        self.assertEqual(errors, [])
        self.assertEqual(len(tree), 1)
        point = tree[0]["children"][0]
        step = point["children"][0]
        self.assertEqual(step["data"]["text"], "1. 打开页面\n2. 点击执行")
        self.assertEqual(step["children"][0]["data"]["text"], "1. 不出现链接")


if __name__ == "__main__":
    unittest.main()
