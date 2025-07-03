import json

ADMIN_USERS = {"adminalice", "superadmin"}  # lowercase usernames

with open("admin_users.json") as f:
    ADMIN_USERS = set(json.load(f))  # e.g., ["richard", "alice"]
