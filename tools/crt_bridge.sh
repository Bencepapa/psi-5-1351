# boot the bridge test cartridge (psi5_ef_bridge.crt, built with efbuild.py --bridge) in VICE, 1351 in port 2
CRT=${CRT:-/c/dev/c64/psi5/psi5_ef_bridge.crt}
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='x64sc.exe'\" | Where-Object { \$_.CommandLine -like '*remotemonitor*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
(/c/dev/c64/vice/win/bin/x64sc.exe -config "$(cygpath -w /c/dev/c64/psi5/tools/vicetest.ini)" -remotemonitor -remotemonitoraddress ip4://127.0.0.1:6511 -controlport2device 3 -cartcrt "$(cygpath -w $CRT)" >/dev/null 2>&1 &)
sleep 6
