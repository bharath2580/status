import requests
from bs4 import BeautifulSoup
import json, re, os, sys
from datetime import datetime

BASE_URL   = "https://choose.illinois.edu"
LOGIN_URL  = f"{BASE_URL}/account/login"
STATUS_URL = f"{BASE_URL}/apply/status"

EMAIL    = os.environ["NOTIFY_EMAIL"]
PASSWORD = os.environ["PASSWORD"]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
})

# Step 1: GET login page → grab CSRF cookie
r1 = session.get(LOGIN_URL)
csrf_token = session.cookies.get("_hash")
print(f"CSRF: {csrf_token}")

# Step 2: POST login
session.post(LOGIN_URL, data={
    "email":    EMAIL,
    "password": PASSWORD,
    "_hash":    csrf_token,
}, headers={"Referer": LOGIN_URL, "Origin": BASE_URL}, allow_redirects=True)

assert session.cookies.get("_uid"), "Login failed — check credentials"

# Step 3: GET status page
r3 = session.get(STATUS_URL)
soup = BeautifulSoup(r3.text, "html.parser")

# Extract status from the exact HTML structure we confirmed
# Finds the <strong> tag whose text is "Status: " then gets the next sibling text
status = "Unknown"
for strong in soup.find_all("strong"):
    if "Status" in strong.get_text():
        # The status text is the next sibling of the <strong> tag's parent span
        parent_text = strong.parent.get_text(" ", strip=True)
        m = re.search(r'Status[:\s\xa0]+(.+?)(?:Reference|$)', parent_text)
        if m:
            status = m.group(1).strip()
            break

# Also extract reference and program for display
full_text = soup.get_text(" ", strip=True)
ref_m  = re.search(r'Reference #[:\s\xa0]+(\d+)', full_text)
prog_m = re.search(r'Program[:\s\xa0]+(.+?)(?:Application Fee|Awaiting|$)', full_text)

reference = ref_m.group(1).strip()  if ref_m  else "110452293"
program   = prog_m.group(1).strip() if prog_m else "Computer Science (Urbana campus)-MCS"

# Load previous status to detect change
previous_status = "Awaiting Decision"
if os.path.exists("status.json"):
    with open("status.json") as f:
        old = json.load(f)
        previous_status = old.get("status", "Awaiting Decision")

status_changed = status.lower() != previous_status.lower()

data = {
    "status":           status,
    "previous_status":  previous_status,
    "status_changed":   status_changed,
    "reference":        reference,
    "program":          program,
    "last_checked":     datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
}

with open("status.json", "w") as f:
    json.dump(data, f, indent=2)

print(json.dumps(data, indent=2))

if status_changed:
    print(f"🚨 STATUS CHANGED: '{previous_status}' → '{status}'")
    sys.exit(1)   # triggers GitHub Actions failure → email alert
else:
    print(f"✅ No change: still '{status}'")
