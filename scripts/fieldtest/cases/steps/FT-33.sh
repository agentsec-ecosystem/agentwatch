ft_up_recorder
ft_start_daemon
ft_assert_recorder "healthz-contract" "python3 -c \"import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:9100/healthz')); assert {'state','reason','store','export','redaction','hooks','gaps'} <= set(d)\""
ft_capture_store
ft_finalize
