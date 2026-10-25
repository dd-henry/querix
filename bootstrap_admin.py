import sys

from database.postgres import PostgresAdapter
from database.users import UserRepository


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python bootstrap_admin.py email@empresa.com")
    UserRepository(PostgresAdapter()).bootstrap_admin(sys.argv[1])
    print("Bootstrap concluído. O email informado é admin se ainda não existia outro admin.")