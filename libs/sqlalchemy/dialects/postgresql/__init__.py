from sqlalchemy.dialects.postgresql import base, psycopg2, pg8000, zxjdbc

base.dialect = psycopg2.dialect

from sqlalchemy.dialects.postgresql.base import \
    INTEGER, BIGINT, SMALLINT, VARCHAR, CHAR, TEXT, NUMERIC, FLOAT, REAL, INET, \
    CIDR, UUID, BIT, MACADDR, DOUBLE_PRECISION, TIMESTAMP, TIME,\
    DATE, BYTEA, BOOLEAN, INTERVAL

__all__ = (
'INTEGER', 'BIGINT', 'SMALLINT', 'VARCHAR', 'CHAR', 'TEXT', 'NUMERIC', 'FLOAT', 'REAL', 'INET', 
'CIDR', 'UUID', 'BIT', 'MACADDR', 'DOUBLE_PRECISION', 'TIMESTAMP', 'TIME',
'DATE', 'BYTEA', 'BOOLEAN', 'INTERVAL'
)