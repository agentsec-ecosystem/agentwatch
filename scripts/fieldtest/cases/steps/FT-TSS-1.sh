ft_assert "ts-spike-tracked" grep -q TSS-1 "$REPO_ROOT/docs/wbs/v0.2.0/wbs-v0.2.0-index.md"

ft_assert "ts-spike-deliverables" python3 "$REPO_ROOT/scripts/fieldtest/tss_spike.py"
ft_assert "ts-portability-contract" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" tests/test_ts_schema_portability.py
ft_finalize
