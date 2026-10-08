ft_up_recorder
ft_assert_recorder "cursor-blocking" "python3 /ft/scripts/ingest-fixture.py --kind cursor-blocking --corpus /ft/fixtures/cursor"
ft_capture_store_soft
ft_finalize
