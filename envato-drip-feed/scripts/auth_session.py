import time

from browser import driver
from common import settings

s = settings()
d = driver(s["selenium_url"])
d.get("https://app.envato.com/sign-in")
print("Envato opened. Complete login through the SSH-forwarded noVNC page at http://127.0.0.1:7900")
try:
    while True:
        url = d.current_url
        if "sign-in" not in url and "envato.com" in url:
            print(f"authenticated page visible: {url}")
        time.sleep(10)
except KeyboardInterrupt:
    d.quit()
    print("browser profile saved")

