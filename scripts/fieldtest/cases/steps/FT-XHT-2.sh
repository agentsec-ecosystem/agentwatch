ft_up_recorder
ft_start_daemon
if [[ "${OMLX_BASE_URL:-}" == "" ]]; then ft_assert_recorder "xht-opencode-bounded" "python3 /ft/scripts/xht_replay.py --opencode --bounded"; else ft_assert_recorder "xht-opencode" "python3 /ft/scripts/xht_replay.py --opencode --bounded"; fi
ft_capture_store_soft
ft_finalize
