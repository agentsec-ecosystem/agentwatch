ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "range-hash-capture" "python3 /ft/scripts/provenance-repo.py --range-hash"
ft_capture_store
ft_finalize
