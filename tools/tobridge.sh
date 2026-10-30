# boot +4D, hire crew, accept, begin, open Engineering status
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='x64sc.exe'\" | Where-Object { \$_.CommandLine -like '*remotemonitor*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
timeout 280 python p4d.py boot
for i in 1 2 3 4 5; do python p4d.py mon "> cf00 0d" "> 0062 01" >/dev/null; sleep 4; python p4d.py mon "> cf00 57" "> 0062 01" >/dev/null; sleep 6; done
python p4d.py mon "> cf00 0d" "> 0062 01" "warp on" >/dev/null; sleep 30; python p4d.py mon "warp off" >/dev/null
python p4d.py keys 0d; sleep 2; python p4d.py keys 45; sleep 2; python p4d.py keys 53; sleep 2
