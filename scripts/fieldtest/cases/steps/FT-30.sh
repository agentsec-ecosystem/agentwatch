ft_up_recorder
# v0.1.0: store-format migration is a documented not-implemented stub. The honest
# contract is that it fails closed and names the milestone; the store stays readable.
ft_assert_recorder "migrate-not-implemented" "agentwatch --set store.path=/data/agentwatch migrate 2>&1 | grep -q E_NOT_IMPLEMENTED"
ft_assert_recorder "unknown-version-rejected" "! agentwatch --set store.path=/data/agentwatch migrate"
ft_assert_recorder "verify-store" "agentwatch --set store.path=/data/agentwatch verify-store"
ft_finalize
