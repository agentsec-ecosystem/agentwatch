ft_up_recorder
ft_start_daemon
if [[ "$(uname -s)" == "Linux" ]]; then ft_assert_recorder "system-ingest" "python3 /ft/scripts/ingest-fixture.py --kind system --corpus /ft/fixtures/system"; else ft_declare "System-effects ingest is Linux-only (opt-in)" "PRD 40 §1b / SYS-1"; fi
ft_capture_store_soft
ft_finalize
