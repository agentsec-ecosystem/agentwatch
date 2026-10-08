if [[ "${FT_WIN_AVAILABLE:-0}" == "1" ]]; then ft_assert "windows-pipeline" bash -lc "agentwatch verify-store"; else ft_declare "Windows host unavailable; run on the windows-latest CI leg (#350)" "PRD 40 §5-expanded 13 / WIN-1"; fi
ft_finalize
