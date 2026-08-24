from scripts.verify_deployment import CheckResult, _parse_version, _summary, _tail, reserve_port


def test_parse_version_handles_node_prefix_and_suffix():
    assert _parse_version("v24.16.0") == (24, 16, 0)
    assert _parse_version("20.19.1 LTS") == (20, 19, 1)


def test_tail_keeps_last_non_empty_lines():
    assert _tail("one\n\ntwo\nthree\n", lines=2) == "two\nthree"


def test_tail_removes_ansi_sequences_without_dropping_unicode():
    assert _tail("\x1b[32m✓ built\x1b[39m\n") == "✓ built"


def test_summary_only_fails_on_explicit_failure():
    healthy = [
        CheckResult("one", "pass", "ok"),
        CheckResult("two", "skip", "optional"),
    ]
    assert _summary(healthy)["all_passed"] is True

    unhealthy = healthy + [CheckResult("three", "fail", "bad")]
    summary = _summary(unhealthy)
    assert summary["failed"] == 1
    assert summary["all_passed"] is False


def test_reserve_port_returns_bindable_port():
    port = reserve_port()
    assert isinstance(port, int)
    assert 0 < port < 65536
