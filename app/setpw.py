import getpass, sys
from .auth import set_password

pw = sys.stdin.readline().rstrip("\n") if "--stdin" in sys.argv else getpass.getpass("New password: ")
if len(pw) < 8:
    sys.exit("password must be at least 8 characters")
set_password(pw)
print("password set")
