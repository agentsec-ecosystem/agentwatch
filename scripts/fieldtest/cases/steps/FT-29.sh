ft_up_recorder
ft_assert_recorder "adapters-conform" "cd /work/packages/python-sdk && PYTHONPATH=src:tests python3 -c \"import conformance_registry; from agentwatch import conformance; r=conformance.run_registered(); assert r and all(x.ok for x in r), [x.summary() for x in r]\""
ft_finalize
