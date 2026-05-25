from database.database import engine
from database.models import Base


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("DB tables ensured (create_all).")


if __name__ == "__main__":
    main()
