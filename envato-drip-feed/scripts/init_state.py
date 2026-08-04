from common import connect, settings

s = settings()
con = connect(s["state_db"])
con.close()
for path in (s["download_root"], s["state_db"].parent, s["download_root"].parent / "staging"):
    path.mkdir(parents=True, exist_ok=True)
print(f"initialized {s['state_db']}")

