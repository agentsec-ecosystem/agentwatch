ft_up_recorder
ft_recorder bash -lc 'printf "nope = 1\n" > /tmp/bad.toml'
ft_assert_recorder "fail-closed" "! agentwatch --config /tmp/bad.toml status"
ft_assert_recorder "config-error-surface" "agentwatch --config /tmp/bad.toml status 2>&1 | grep -q E_CONFIG"
ft_finalize
