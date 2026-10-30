# boot psi5_ef.crt in VICE (1351 in port 2), answer no to trainers, course 1, first crew, accept, begin, Eng status
CRT=${CRT:-/c/dev/c64/psi5/psi5_ef.crt}
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='x64sc.exe'\" | Where-Object { \$_.CommandLine -like '*remotemonitor*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
(/c/dev/c64/vice/win/bin/x64sc.exe -config "$(cygpath -w /c/dev/c64/psi5/tools/vicetest.ini)" -remotemonitor -remotemonitoraddress ip4://127.0.0.1:6511 -controlport2device 3 -cartcrt "$(cygpath -w $CRT)" >/dev/null 2>&1 &)
sleep 8
timeout 20 python p4d.py mon "> 0d2d ff" >/dev/null
sleep 25
timeout 10 python p4d.py mon "> cf00 31" "> 0062 01" >/dev/null; sleep 6
for i in 1 2 3 4 5; do timeout 10 python p4d.py mon "> cf00 0d" "> 0062 01" >/dev/null; sleep 3; timeout 10 python p4d.py mon "> cf00 57" "> 0062 01" >/dev/null; sleep 4; done
timeout 10 python p4d.py mon "> cf00 0d" "> 0062 01" >/dev/null; sleep 10
timeout 10 python p4d.py keys 0d >/dev/null; sleep 2; timeout 10 python p4d.py keys 45 >/dev/null; sleep 2; timeout 10 python p4d.py keys 53 >/dev/null; sleep 2
