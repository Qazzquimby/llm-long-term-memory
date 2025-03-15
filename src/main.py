from src.db import get_sessionmaker, get_engine, Base


def main():
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = get_sessionmaker()

    with SessionLocal() as session:
        pass


if __name__ == "__main__":
    main()
