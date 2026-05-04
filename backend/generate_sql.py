from database.connection import Base, engine
from database.models import *
from sqlalchemy.schema import CreateTable

for table in Base.metadata.sorted_tables:
    print(CreateTable(table).compile(engine))
    print(";")
