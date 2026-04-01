"""Tests for JudgeNode route parsing logic."""


from codyflow.nodes.base import NodeConfig
from codyflow.nodes.builtin import JudgeNode


def _make_judge() -> JudgeNode:
    config = NodeConfig(id="judge_1", type="judge")
    return JudgeNode(config)


class TestParseRoute:
    """Test JudgeNode._parse_route() with various output formats."""

    def test_explicit_route_passed(self):
        judge = _make_judge()
        route, reasoning = judge._parse_route("ROUTE: passed\nAll looks good.")
        assert route == "passed"
        assert "All looks good" in reasoning

    def test_explicit_route_needs_fix(self):
        judge = _make_judge()
        route, _ = judge._parse_route("ROUTE: needs_fix\nSome issues found.")
        assert route == "needs_fix"

    def test_case_insensitive_route(self):
        judge = _make_judge()
        route, _ = judge._parse_route("route: Passed\nDone.")
        assert route == "passed"

    def test_decision_marker(self):
        judge = _make_judge()
        route, _ = judge._parse_route("Decision: passed\nEverything is fine.")
        assert route == "passed"

    def test_chinese_marker(self):
        judge = _make_judge()
        route, _ = judge._parse_route("判断: needs_fix\n需要修改一些地方。")
        assert route == "needs_fix"

    def test_chinese_result_marker(self):
        judge = _make_judge()
        route, _ = judge._parse_route("判断结果: passed\n质量达标。")
        assert route == "passed"

    def test_conclusion_marker(self):
        judge = _make_judge()
        route, _ = judge._parse_route("结论: passed\n没有问题。")
        assert route == "passed"

    def test_keyword_fallback_pass(self):
        judge = _make_judge()
        route, _ = judge._parse_route("经过审查，代码质量通过，可以合并。")
        assert route == "passed"

    def test_keyword_fallback_fix(self):
        judge = _make_judge()
        route, _ = judge._parse_route("发现了几个问题，需要修改后重新审查。")
        assert route == "needs_fix"

    def test_both_keywords_defaults_to_fix(self):
        judge = _make_judge()
        route, _ = judge._parse_route("虽然部分通过了，但还需要修改一些地方。")
        assert route == "needs_fix"

    def test_no_keywords_defaults_to_fix(self):
        judge = _make_judge()
        route, _ = judge._parse_route("这是一段没有任何关键词的文本。")
        assert route == "needs_fix"

    def test_route_with_punctuation(self):
        judge = _make_judge()
        route, _ = judge._parse_route("ROUTE: passed.\nDone!")
        assert route == "passed"

    def test_reasoning_extraction(self):
        judge = _make_judge()
        _, reasoning = judge._parse_route(
            "ROUTE: passed\nLine 1\nLine 2\nLine 3"
        )
        assert "Line 1" in reasoning
        assert "Line 3" in reasoning

    def test_reasoning_truncated(self):
        judge = _make_judge()
        long_text = "ROUTE: passed\n" + "x" * 2000
        _, reasoning = judge._parse_route(long_text)
        assert len(reasoning) <= 1004  # 1000 + "..."

    def test_normalize_pass_variants(self):
        judge = _make_judge()
        for keyword in ["pass", "ok", "approved", "lgtm", "通过"]:
            route, _ = judge._parse_route(f"ROUTE: {keyword}")
            assert route == "passed", f"Failed for keyword: {keyword}"

    def test_normalize_fix_variants(self):
        judge = _make_judge()
        for keyword in ["fix", "failed", "reject", "需要修改", "不通过"]:
            route, _ = judge._parse_route(f"ROUTE: {keyword}")
            assert route == "needs_fix", f"Failed for keyword: {keyword}"

    def test_custom_route_preserved(self):
        judge = _make_judge()
        route, _ = judge._parse_route("ROUTE: deploy\nReady to deploy.")
        assert route == "deploy"
