ft_up_recorder
ft_assert_recorder "alert-recipes" "python3 /ft/scripts/alert_recipes.py --webhook-sink"
ft_assert "alert-recipes-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_alert_recipes.py
ft_capture_store_soft
ft_finalize
