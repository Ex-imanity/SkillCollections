"""仓库级约定校验：版本号与变更日志。

约定（见根 README「版本与变更日志约定」）：

1. 每个 skill 目录（含 SKILL.md 者）的 frontmatter 必须有合法 semver `version`
2. 每个 skill 必须有 CHANGELOG.md
3. CHANGELOG.md 顶部条目的版本必须与 frontmatter 一致
4. 根 README「Skills 总览」表的 Version 列必须与 frontmatter 一致

5. frontmatter 应当是合法 YAML（装了 pyyaml 才校验）

新增 skill 会被自动纳入，无需改本文件。

注：约定校验用**宽松的逐行解析** frontmatter，与 Claude Code 自身的解析行为一致，
不引入第三方依赖。严格 YAML 校验单独作为可选测试（见 FrontmatterStrictYamlTest）。
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
# CHANGELOG 顶部条目：## <version> - <YYYY-MM-DD>
CHANGELOG_ENTRY_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s+-\s+(\d{4}-\d{2}-\d{2})\s*$", re.M)


def skill_dirs() -> list[Path]:
    return sorted(d for d in REPO_ROOT.iterdir() if d.is_dir() and (d / "SKILL.md").is_file())


def read_frontmatter(skill_md: Path) -> dict[str, str]:
    """宽松逐行解析 frontmatter，只取顶层 `key: value`。"""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].split("\n"):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"\'')
    return fields


def readme_version_table() -> dict[str, str]:
    """从根 README「Skills 总览」表解析 skill → version。"""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    versions: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*([0-9]+\.[0-9]+\.[0-9]+)\s*\|", line)
        if m:
            versions[m.group(1)] = m.group(2)
    return versions


try:
    import yaml  # 可选依赖：装了就顺带做严格 YAML 校验
except ImportError:  # pragma: no cover
    yaml = None


class FrontmatterStrictYamlTest(unittest.TestCase):
    """frontmatter 应当是合法 YAML。

    Claude Code 自身的解析器是宽松的，非法 YAML 也能加载，所以这不是致命问题。
    但任何严格解析的消费方都会挂——曾出现 description 内含未加引号的
    `): it teaches` 导致严格解析失败的情况。此测试锁住修复，防止再次引入。
    长文本或含冒号的 description 用折叠块标量 `>-` 最省心。
    """

    @unittest.skipIf(yaml is None, "未安装 pyyaml，跳过严格 YAML 校验")
    def test_frontmatter_is_valid_yaml(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                text = (d / "SKILL.md").read_text(encoding="utf-8")
                end = text.find("\n---\n", 4)
                self.assertNotEqual(end, -1, f"{d.name}/SKILL.md frontmatter 未正确闭合")
                try:
                    parsed = yaml.safe_load(text[4:end])
                except yaml.YAMLError as exc:
                    self.fail(
                        f"{d.name}/SKILL.md frontmatter 不是合法 YAML: "
                        f"{str(exc).splitlines()[0]}\n"
                        f"提示：description 含冒号时改用折叠块标量 `description: >-`"
                    )
                self.assertIsInstance(parsed, dict)
                self.assertEqual(parsed.get("name"), d.name,
                                 f"{d.name}: frontmatter 的 name 与目录名不一致")


class SkillVersionConventionTest(unittest.TestCase):
    def test_repo_has_skills(self):
        self.assertTrue(skill_dirs(), "未发现任何含 SKILL.md 的目录")

    def test_every_skill_declares_semver_version(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                fields = read_frontmatter(d / "SKILL.md")
                self.assertIn("version", fields, f"{d.name}/SKILL.md frontmatter 缺少 version 字段")
                self.assertRegex(
                    fields["version"], SEMVER_RE,
                    f"{d.name} 的 version {fields['version']!r} 不是合法 semver（如 1.2.0）",
                )

    def test_every_skill_has_changelog(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertTrue(
                    (d / "CHANGELOG.md").is_file(),
                    f"{d.name} 缺少 CHANGELOG.md；每次升版本必须留下条目",
                )

    def test_changelog_top_entry_matches_frontmatter_version(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                declared = read_frontmatter(d / "SKILL.md").get("version")
                entries = CHANGELOG_ENTRY_RE.findall((d / "CHANGELOG.md").read_text(encoding="utf-8"))
                self.assertTrue(
                    entries,
                    f"{d.name}/CHANGELOG.md 没有任何 '## <version> - <YYYY-MM-DD>' 条目",
                )
                self.assertEqual(
                    entries[0][0], declared,
                    f"{d.name}: CHANGELOG 顶部是 {entries[0][0]}，"
                    f"但 SKILL.md 声明的是 {declared}。升版本时两处必须同步。",
                )

    def test_changelog_entries_are_ordered_newest_first(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                entries = CHANGELOG_ENTRY_RE.findall((d / "CHANGELOG.md").read_text(encoding="utf-8"))
                versions = [tuple(int(p) for p in v.split(".")) for v, _ in entries]
                self.assertEqual(
                    versions, sorted(versions, reverse=True),
                    f"{d.name}/CHANGELOG.md 条目未按版本从新到旧排列：{[v for v, _ in entries]}",
                )

    def test_readme_overview_table_matches_frontmatter_version(self):
        table = readme_version_table()
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                declared = read_frontmatter(d / "SKILL.md").get("version")
                self.assertIn(
                    d.name, table,
                    f"根 README「Skills 总览」表缺少 {d.name} 的 Version 列",
                )
                self.assertEqual(
                    table[d.name], declared,
                    f"{d.name}: README 总览表是 {table[d.name]}，SKILL.md 是 {declared}",
                )

    def test_readme_table_has_no_stale_skills(self):
        known = {d.name for d in skill_dirs()}
        for name in readme_version_table():
            with self.subTest(skill=name):
                self.assertIn(name, known, f"README 总览表列了不存在的 skill: {name}")


if __name__ == "__main__":
    unittest.main()
