import os
from cognee.infrastructure.databases.relational.create_relational_engine import create_relational_engine
from dotenv import load_dotenv


load_dotenv()


def get_sprounix_relational_engine():
    config =  {
        "db_path": None,
        "db_name": os.getenv("SPROUNIX_DB_DATABASE"),
        "db_host": os.getenv("SPROUNIX_DB_HOST"),
        "db_port": os.getenv("SPROUNIX_DB_PORT"),
        "db_username": os.getenv("SPROUNIX_DB_USERNAME"),
        "db_password": os.getenv("SPROUNIX_DB_PASSWORD"),
        "db_provider": "postgres",
    }
    return create_relational_engine(**config)
