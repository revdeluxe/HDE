import json, os

admin_path = "config/admin_users.json"
if not os.path.exists(admin_path):
    with open(admin_path,'w') as f:
        json.dump(["richard"], f)
with open(admin_path) as f:
    data = json.load(f)
ADMIN_USERS = set(data if isinstance(data,list) else data.get("admins",[]))
