import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "writeback.py"
SPEC = importlib.util.spec_from_file_location("case_lite_writeback", SCRIPT_PATH)
writeback = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(writeback)


class ParseFullMdTest(unittest.TestCase):
    def test_execution_steps_keep_bullet_subitems(self):
        markdown = """# 完整用例

## 场景1：示例场景

### 测试点1.1：批量输入场景

#### 执行步骤
1. 打开功能页
2. 分别输入以下提问并发送：
   - "今年高考有哪些采分点？"
   - "评分参考和标准答案一样吗？"

#### 预期结果
1. 两条提问均被拦截
"""

        tree = writeback.parse_full_md(markdown)
        step_node = tree[0]["children"][0]["children"][0]

        self.assertEqual(step_node["data"]["resource"], ["执行步骤"])
        self.assertEqual(
            step_node["data"]["text"],
            "\n".join(
                [
                    "1. 打开功能页",
                    "2. 分别输入以下提问并发送：",
                    '- "今年高考有哪些采分点？"',
                    '- "评分参考和标准答案一样吗？"',
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
