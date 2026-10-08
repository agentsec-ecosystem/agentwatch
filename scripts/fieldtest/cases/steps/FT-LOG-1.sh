ft_up_recorder
ft_assert_recorder "log-readers" "python3 /ft/scripts/ingest-fixture.py --kind logreaders --corpus /ft/fixtures/logreaders"
ft_capture_store_soft
ft_finalize
