from pathlib import Path


PRIVATE_REPORT_MARKER = ".research-harness" + "/reports"
TEST_ROOTS = (
    Path(__file__).resolve().parent,
    Path(__file__).resolve().parents[2] / "research_harness_mcp/tests",
)


def test_public_tests_do_not_reference_private_report_roots():
    violations: list[str] = []
    for root in TEST_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("test_*.py")):
            text = path.read_text(encoding="utf-8")
            if PRIVATE_REPORT_MARKER in text:
                violations.append(str(path.relative_to(root.parents[1])))

    assert violations == []
