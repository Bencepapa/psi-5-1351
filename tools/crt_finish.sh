timeout 10 python p4d.py mon "> cf00 57" "> 0062 01" >/dev/null; sleep 4
for i in 1 2 3 4; do timeout 10 python p4d.py mon "> cf00 0d" "> 0062 01" >/dev/null; sleep 3; timeout 10 python p4d.py mon "> cf00 57" "> 0062 01" >/dev/null; sleep 4; done
timeout 10 python p4d.py mon "> cf00 0d" "> 0062 01" >/dev/null; sleep 12
timeout 10 python p4d.py keys 0d >/dev/null; sleep 2; timeout 10 python p4d.py keys 45 >/dev/null; sleep 2; timeout 10 python p4d.py keys 53 >/dev/null; sleep 2
