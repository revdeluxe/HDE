import json, os

ADMIN_USERS = {"Robin"}

admin_path = "admin_users.json"
if not os.path.exists(admin_path):
    with open(admin_path, 'w') as f:
        json.dump(["richard"], f)
        print(f"🔧 Created default {admin_path}")
with open(admin_path) as f:
    ADMIN_USERS = set(json.load(f))