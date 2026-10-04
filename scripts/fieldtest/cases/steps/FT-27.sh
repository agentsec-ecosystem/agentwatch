venv="$FT_CASE_DIR/artifacts/venv"
ft_record "host venv + native agentwatch"
ft_run python3 -m venv "$venv"
ft_run "$venv/bin/pip" install -q -e "$REPO_ROOT/packages/python-sdk"
ft_assert "host-native-demo" "$venv/bin/agentwatch" --set store.path="$FT_CASE_DIR/artifacts/hoststore" demo --json
ft_finalize
