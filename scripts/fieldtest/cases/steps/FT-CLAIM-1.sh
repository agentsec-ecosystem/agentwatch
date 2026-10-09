ft_up_recorder
ft_start_daemon
ft_assert "claims-ledger-backed" python3 "$REPO_ROOT/scripts/fieldtest/claims_ledger_check.py"
ft_capture_store_soft
ft_finalize
