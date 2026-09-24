"""Create or promote the local admin account.

Usage: python create_admin.py --email admin@example.com --password change-me --name Admin
"""
import argparse
from app.database import SessionLocal, User, init_db
from app.routers.auth import pwd_context

parser = argparse.ArgumentParser()
parser.add_argument("--email", required=True)
parser.add_argument("--password", required=True)
parser.add_argument("--name", default="Ripewise Admin")
args = parser.parse_args()
init_db(); db = SessionLocal()
user = db.query(User).filter(User.email == args.email.strip().lower()).first()
if user is None:
    user = User(name=args.name.strip(), email=args.email.strip().lower(), hashed_password=pwd_context.hash(args.password), role="admin")
    db.add(user)
else:
    user.role = "admin"
    user.hashed_password = pwd_context.hash(args.password)
db.commit(); print(f"Admin account ready: {user.email}"); db.close()