ft_record "build recorder image"
"${STACK_COMPOSE[@]}" build recorder >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
# No network namespace: the recorder must run record -> verify entirely offline.
ft_assert "offline-record-verify" docker run --rm --network none agentwatch-fieldtest-recorder:local bash -lc 'agentwatch --set store.path=/data demo --json >/dev/null && agentwatch --set store.path=/data verify-store'
ft_finalize
