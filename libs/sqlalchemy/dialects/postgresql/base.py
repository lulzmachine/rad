# postgresql.py
# Copyright (C) 2005, 2006, 2007, 2008, 2009 Michael Bayer mike_mp@zzzcomputing.com
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Support for the PostgreSQL database.  

For information on connecting using specific drivers, see the documentation section
regarding that driver.

Sequences/SERIAL
----------------

PostgreSQL supports sequences, and SQLAlchemy uses these as the default means of creating
new primary key values for integer-based primary key columns.   When creating tables, 
SQLAlchemy will issue the ``SERIAL`` datatype for integer-based primary key columns, 
which generates a sequence corresponding to the column and associated with it based on
a naming convention.

To specify a specific named sequence to be used for primary key generation, use the
:func:`~sqlalchemy.schema.Sequence` construct::

    Table('sometable', metadata, 
            Column('id', Integer, Sequence('some_id_seq'), primary_key=True)
        )

Currently, when SQLAlchemy issues a single insert statement, to fulfill the contract of
having the "last insert identifier" available, the sequence is executed independently
beforehand and the new value is retrieved, to be used in the subsequent insert.  Note
that when an :func:`~sqlalchemy.sql.expression.insert()` construct is executed using 
"executemany" semantics, the sequence is not pre-executed and normal PG SERIAL behavior
is used.

PostgreSQL 8.2 supports an ``INSERT...RETURNING`` syntax which SQLAlchemy supports 
as well.  A future release of SQLA will use this feature by default in lieu of 
sequence pre-execution in order to retrieve new primary key values, when available.

INSERT/UPDATE...RETURNING
-------------------------

The dialect supports PG 8.2's ``INSERT..RETURNING``, ``UPDATE..RETURNING`` and ``DELETE..RETURNING`` syntaxes, 
but must be explicitly enabled on a per-statement basis::

    # INSERT..RETURNING
    result = table.insert().returning(table.c.col1, table.c.col2).\\
        values(name='foo')
    print result.fetchall()
    
    # UPDATE..RETURNING
    result = table.update().returning(table.c.col1, table.c.col2).\\
        where(table.c.name=='foo').values(name='bar')
    print result.fetchall()

    # DELETE..RETURNING
    result = table.delete().returning(table.c.col1, table.c.col2).\\
        where(table.c.name=='foo')
    print result.fetchall()

Indexes
-------

PostgreSQL supports partial indexes. To create them pass a postgresql_where
option to the Index constructor::

  Index('my_index', my_table.c.id, postgresql_where=tbl.c.value > 10)



"""

import re

from sqlalchemy import schema as sa_schema
from sqlalchemy import sql, schema, exc, util
from sqlalchemy.engine import base, default, reflection
from sqlalchemy.sql import compiler, expression
from sqlalchemy.sql import operators as sql_operators
from sqlalchemy import types as sqltypes

from sqlalchemy.types import INTEGER, BIGINT, SMALLINT, VARCHAR, \
        CHAR, TEXT, FLOAT, NUMERIC, \
        TIMESTAMP, TIME, DATE, BOOLEAN

class REAL(sqltypes.Float):
    __visit_name__ = "REAL"

class BYTEA(sqltypes.Binary):
    __visit_name__ = 'BYTEA'

class DOUBLE_PRECISION(sqltypes.Float):
    __visit_name__ = 'DOUBLE_PRECISION'
    
class INET(sqltypes.TypeEngine):
    __visit_name__ = "INET"
PGInet = INET

class CIDR(sqltypes.TypeEngine):
    __visit_name__ = "CIDR"
PGCidr = CIDR

class MACADDR(sqltypes.TypeEngine):
    __visit_name__ = "MACADDR"
PGMacAddr = MACADDR

class INTERVAL(sqltypes.TypeEngine):
    __visit_name__ = 'INTERVAL'
PGInterval = INTERVAL

class BIT(sqltypes.TypeEngine):
    __visit_name__ = 'BIT'
PGBit = BIT

class UUID(sqltypes.TypeEngine):
    __visit_name__ = 'UUID'
PGUuid = UUID

class ARRAY(sqltypes.MutableType, sqltypes.Concatenable, sqltypes.TypeEngine):
    __visit_name__ = 'ARRAY'
    
    def __init__(self, item_type, mutable=True):
        if isinstance(item_type, type):
            item_type = item_type()
        self.item_type = item_type
        self.mutable = mutable

    def copy_value(self, value):
        if value is None:
            return None
        elif self.mutable:
            return list(value)
        else:
            return value

    def compare_values(self, x, y):
        return x == y

    def is_mutable(self):
        return self.mutable

    def dialect_impl(self, dialect, **kwargs):
        impl = super(ARRAY, self).dialect_impl(dialect, **kwargs)
        if impl is self:
            impl = self.__class__.__new__(self.__class__)
            impl.__dict__.update(self.__dict__)
        impl.item_type = self.item_type.dialect_impl(dialect)
        return impl
    
    def adapt(self, impltype):
        return impltype(
            self.item_type,
            mutable=self.mutable
        )
        
    def bind_processor(self, dialect):
        item_proc = self.item_type.bind_processor(dialect)
        def process(value):
            if value is None:
                return value
            def convert_item(item):
                if isinstance(item, (list, tuple)):
                    return [convert_item(child) for child in item]
                else:
                    if item_proc:
                        return item_proc(item)
                    else:
                        return item
            return [convert_item(item) for item in value]
        return process

    def result_processor(self, dialect):
        item_proc = self.item_type.result_processor(dialect)
        def process(value):
            if value is None:
                return value
            def convert_item(item):
                if isinstance(item, list):
                    return [convert_item(child) for child in item]
                else:
                    if item_proc:
                        return item_proc(item)
                    else:
                        return item
            return [convert_item(item) for item in value]
        return process
PGArray = ARRAY

class ENUM(sqltypes.Enum):

    def create(self, bind=None, checkfirst=True):
        if not checkfirst or not bind.dialect.has_type(bind, self.name, schema=self.schema):
            bind.execute(CreateEnumType(self))

    def drop(self, bind=None, checkfirst=True):
        if not checkfirst or bind.dialect.has_type(bind, self.name, schema=self.schema):
            bind.execute(DropEnumType(self))
        
    def _on_table_create(self, event, target, bind, **kw):
        self.create(bind=bind, checkfirst=True)

    def _on_metadata_create(self, event, target, bind, **kw):
        if self.metadata is not None:
            self.create(bind=bind, checkfirst=True)

    def _on_metadata_drop(self, event, target, bind, **kw):
        self.drop(bind=bind, checkfirst=True)

colspecs = {
    sqltypes.Interval:INTERVAL,
    sqltypes.Enum:ENUM,
}

ischema_names = {
    'integer' : INTEGER,
    'bigint' : BIGINT,
    'smallint' : SMALLINT,
    'character varying' : VARCHAR,
    'character' : CHAR,
    '"char"' : sqltypes.String,
    'name' : sqltypes.String,
    'text' : TEXT,
    'numeric' : NUMERIC,
    'float' : FLOAT,
    'real' : REAL,
    'inet': INET,
    'cidr': CIDR,
    'uuid': UUID,
    'bit':BIT,
    'macaddr': MACADDR,
    'double precision' : DOUBLE_PRECISION,
    'timestamp' : TIMESTAMP,
    'timestamp with time zone' : TIMESTAMP,
    'timestamp without time zone' : TIMESTAMP,
    'time with time zone' : TIME,
    'time without time zone' : TIME,
    'date' : DATE,
    'time': TIME,
    'bytea' : BYTEA,
    'boolean' : BOOLEAN,
    'interval':INTERVAL,
}



class PGCompiler(compiler.SQLCompiler):
    
    def visit_match_op(self, binary, **kw):
        return "%s @@ to_tsquery(%s)" % (self.process(binary.left), self.process(binary.right))

    def visit_ilike_op(self, binary, **kw):
        escape = binary.modifiers.get("escape", None)
        return '%s ILIKE %s' % (self.process(binary.left), self.process(binary.right)) \
            + (escape and ' ESCAPE \'%s\'' % escape or '')

    def visit_notilike_op(self, binary, **kw):
        escape = binary.modifiers.get("escape", None)
        return '%s NOT ILIKE %s' % (self.process(binary.left), self.process(binary.right)) \
            + (escape and ' ESCAPE \'%s\'' % escape or '')

    def visit_sequence(self, seq):
        if seq.optional:
            return None
        else:
            return "nextval('%s')" % self.preparer.format_sequence(seq)

    def limit_clause(self, select):
        text = ""
        if select._limit is not None:
            text +=  " \n LIMIT " + str(select._limit)
        if select._offset is not None:
            if select._limit is None:
                text += " \n LIMIT ALL"
            text += " OFFSET " + str(select._offset)
        return text

    def get_select_precolumns(self, select):
        if select._distinct is not False:
            if select._distinct is True:
                return "DISTINCT "
            elif isinstance(select._distinct, (list, tuple)):
                return "DISTINCT ON (" + ', '.join(
                    [(isinstance(col, basestring) and col or self.process(col)) for col in select._distinct]
                )+ ") "
            else:
                return "DISTINCT ON (" + unicode(select._distinct) + ") "
        else:
            return ""

    def for_update_clause(self, select):
        if select.for_update == 'nowait':
            return " FOR UPDATE NOWAIT"
        else:
            return super(PGCompiler, self).for_update_clause(select)

    def returning_clause(self, stmt, returning_cols):
        
        columns = [
                self.process(
                    self.label_select_column(None, c, asfrom=False), 
                    within_columns_clause=True, 
                    result_map=self.result_map) 
                for c in expression._select_iterables(returning_cols)
            ]
            
        return 'RETURNING ' + ', '.join(columns)

    def visit_extract(self, extract, **kwargs):
        field = self.extract_map.get(extract.field, extract.field)
        return "EXTRACT(%s FROM %s::timestamp)" % (
            field, self.process(extract.expr))

class PGDDLCompiler(compiler.DDLCompiler):
    def get_column_specification(self, column, **kwargs):
        colspec = self.preparer.format_column(column)
        if column.primary_key and \
            len(column.foreign_keys)==0 and \
            column.autoincrement and \
            isinstance(column.type, sqltypes.Integer) and \
            not isinstance(column.type, sqltypes.SmallInteger) and \
            (column.default is None or (isinstance(column.default, schema.Sequence) and column.default.optional)):
            if isinstance(column.type, sqltypes.BigInteger):
                colspec += " BIGSERIAL"
            else:
                colspec += " SERIAL"
        else:
            colspec += " " + self.dialect.type_compiler.process(column.type)
            default = self.get_column_default_string(column)
            if default is not None:
                colspec += " DEFAULT " + default

        if not column.nullable:
            colspec += " NOT NULL"
        return colspec

    def visit_create_sequence(self, create):
        return "CREATE SEQUENCE %s" % self.preparer.format_sequence(create.element)
            
    def visit_drop_sequence(self, drop):
        return "DROP SEQUENCE %s" % self.preparer.format_sequence(drop.element)
        
    def visit_enum_constraint(self, constraint):
        if not constraint.type.native_enum:
            return super(PGDDLCompiler, self).visit_enum_constraint(constraint)
            
    def visit_create_enum_type(self, create):
        type_ = create.element
        
        return "CREATE TYPE %s AS ENUM (%s)" % (
            self.preparer.format_type(type_),
            ",".join("'%s'" % e for e in type_.enums)
        )

    def visit_drop_enum_type(self, drop):
        type_ = drop.element

        return "DROP TYPE %s" % (
            self.preparer.format_type(type_)
        )
        
    def visit_create_index(self, create):
        preparer = self.preparer
        index = create.element
        text = "CREATE "
        if index.unique:
            text += "UNIQUE "
        text += "INDEX %s ON %s (%s)" \
                    % (preparer.quote(self._validate_identifier(index.name, True), index.quote),
                       preparer.format_table(index.table),
                       ', '.join([preparer.format_column(c) for c in index.columns]))
        
        if "postgres_where" in index.kwargs:
            whereclause = index.kwargs['postgres_where']
            util.warn_deprecated("The 'postgres_where' argument has been renamed to 'postgresql_where'.")
        elif 'postgresql_where' in index.kwargs:
            whereclause = index.kwargs['postgresql_where']
        else:
            whereclause = None
            
        if whereclause is not None:
            compiler = self._compile(whereclause, None)
            # this might belong to the compiler class
            inlined_clause = str(compiler) % dict(
                [(key,bind.value) for key,bind in compiler.binds.iteritems()])
            text += " WHERE " + inlined_clause
        return text


class PGTypeCompiler(compiler.GenericTypeCompiler):
    def visit_INET(self, type_):
        return "INET"

    def visit_CIDR(self, type_):
        return "CIDR"

    def visit_MACADDR(self, type_):
        return "MACADDR"

    def visit_FLOAT(self, type_):
        if not type_.precision:
            return "FLOAT"
        else:
            return "FLOAT(%(precision)s)" % {'precision': type_.precision}
    
    def visit_DOUBLE_PRECISION(self, type_):
        return "DOUBLE PRECISION"
        
    def visit_BIGINT(self, type_):
        return "BIGINT"

    def visit_datetime(self, type_):
        return self.visit_TIMESTAMP(type_)
    
    def visit_enum(self, type_):
        if not type_.native_enum:
            return super(PGTypeCompiler, self).visit_enum(type_)
        else:
            return self.visit_ENUM(type_)
        
    def visit_ENUM(self, type_):
        return self.dialect.identifier_preparer.format_type(type_)
        
    def visit_TIMESTAMP(self, type_):
        return "TIMESTAMP " + (type_.timezone and "WITH" or "WITHOUT") + " TIME ZONE"

    def visit_TIME(self, type_):
        return "TIME " + (type_.timezone and "WITH" or "WITHOUT") + " TIME ZONE"

    def visit_INTERVAL(self, type_):
        return "INTERVAL"

    def visit_BIT(self, type_):
        return "BIT"

    def visit_UUID(self, type_):
        return "UUID"

    def visit_binary(self, type_):
        return self.visit_BYTEA(type_)
        
    def visit_BYTEA(self, type_):
        return "BYTEA"

    def visit_REAL(self, type_):
        return "REAL"

    def visit_ARRAY(self, type_):
        return self.process(type_.item_type) + '[]'


class PGIdentifierPreparer(compiler.IdentifierPreparer):
    def _unquote_identifier(self, value):
        if value[0] == self.initial_quote:
            value = value[1:-1].replace(self.escape_to_quote, self.escape_quote)
        return value

    def format_type(self, type_, use_schema=True):
        if not type_.name:
            raise exc.ArgumentError("Postgresql ENUM type requires a name.")
        
        name = self.quote(type_.name, type_.quote)
        if not self.omit_schema and use_schema and type_.schema is not None:
            name = self.quote_schema(type_.schema, type_.quote) + "." + name
        return name
        
class PGInspector(reflection.Inspector):

    def __init__(self, conn):
        reflection.Inspector.__init__(self, conn)

    def get_table_oid(self, table_name, schema=None):
        """Return the oid from `table_name` and `schema`."""

        return self.dialect.get_table_oid(self.conn, table_name, schema,
                                          info_cache=self.info_cache)

class CreateEnumType(schema._CreateDropBase):
  __visit_name__ = "create_enum_type"

class DropEnumType(schema._CreateDropBase):
  __visit_name__ = "drop_enum_type"

class PGExecutionContext(default.DefaultExecutionContext):
    def fire_sequence(self, seq):
        if not seq.optional:
            return self._execute_scalar(("select nextval('%s')" % \
                        self.dialect.identifier_preparer.format_sequence(seq)))
        else:
            return None

    def get_insert_default(self, column):
        if column.primary_key:
            if (isinstance(column.server_default, schema.DefaultClause) and
                column.server_default.arg is not None):

                # pre-execute passive defaults on primary key columns
                return self._execute_scalar("select %s" % column.server_default.arg)

            elif column is column.table._autoincrement_column \
                    and (column.default is None or (isinstance(column.default, schema.Sequence) and column.default.optional)):

                # execute the sequence associated with a SERIAL primary key column.  
                # for non-primary-key SERIAL, the ID just generates server side.
                sch = column.table.schema

                if sch is not None:
                    exc = "select nextval('\"%s\".\"%s_%s_seq\"')" % (sch, column.table.name, column.name)
                else:
                    exc = "select nextval('\"%s_%s_seq\"')" % (column.table.name, column.name)

                return self._execute_scalar(exc)

        return super(PGExecutionContext, self).get_insert_default(column)
    
class PGDialect(default.DefaultDialect):
    name = 'postgresql'
    supports_alter = True
    max_identifier_length = 63
    supports_sane_rowcount = True
    
    supports_sequences = True
    sequences_optional = True
    preexecute_autoincrement_sequences = True
    postfetch_lastrowid = False
    
    supports_default_values = True
    supports_empty_insert = False
    default_paramstyle = 'pyformat'
    ischema_names = ischema_names
    colspecs = colspecs
    
    statement_compiler = PGCompiler
    ddl_compiler = PGDDLCompiler
    type_compiler = PGTypeCompiler
    preparer = PGIdentifierPreparer
    execution_ctx_cls = PGExecutionContext
    inspector = PGInspector
    isolation_level = None

    def __init__(self, isolation_level=None, **kwargs):
        default.DefaultDialect.__init__(self, **kwargs)
        self.isolation_level = isolation_level

    def initialize(self, connection):
        super(PGDialect, self).initialize(connection)
        self.implicit_returning = self.server_version_info > (8, 2) and \
                                        self.__dict__.get('implicit_returning', True)
        
    def visit_pool(self, pool):
        if self.isolation_level is not None:
            class SetIsolationLevel(object):
                def __init__(self, isolation_level):
                    self.isolation_level = isolation_level

                def connect(self, conn, rec):
                    cursor = conn.cursor()
                    cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL %s"
                                   % self.isolation_level)
                    cursor.execute("COMMIT")
                    cursor.close()
            pool.add_listener(SetIsolationLevel(self.isolation_level))

    def do_begin_twophase(self, connection, xid):
        self.do_begin(connection.connection)

    def do_prepare_twophase(self, connection, xid):
        connection.execute("PREPARE TRANSACTION '%s'" % xid)

    def do_rollback_twophase(self, connection, xid, is_prepared=True, recover=False):
        if is_prepared:
            if recover:
                #FIXME: ugly hack to get out of transaction context when commiting recoverable transactions
                # Must find out a way how to make the dbapi not open a transaction.
                connection.execute("ROLLBACK")
            connection.execute("ROLLBACK PREPARED '%s'" % xid)
            connection.execute("BEGIN")
            self.do_rollback(connection.connection)
        else:
            self.do_rollback(connection.connection)

    def do_commit_twophase(self, connection, xid, is_prepared=True, recover=False):
        if is_prepared:
            if recover:
                connection.execute("ROLLBACK")
            connection.execute("COMMIT PREPARED '%s'" % xid)
            connection.execute("BEGIN")
            self.do_rollback(connection.connection)
        else:
            self.do_commit(connection.connection)

    def do_recover_twophase(self, connection):
        resultset = connection.execute(sql.text("SELECT gid FROM pg_prepared_xacts"))
        return [row[0] for row in resultset]

    def get_default_schema_name(self, connection):
        return connection.scalar("select current_schema()")

    def has_table(self, connection, table_name, schema=None):
        # seems like case gets folded in pg_class...
        if schema is None:
            cursor = connection.execute(
                sql.text("select relname from pg_class c join pg_namespace n on "
                    "n.oid=c.relnamespace where n.nspname=current_schema() and "
                    "lower(relname)=:name",
                    bindparams=[
                            sql.bindparam('name', unicode(table_name.lower()),
                            type_=sqltypes.Unicode)]
                )
            )
        else:
            cursor = connection.execute(
                sql.text("select relname from pg_class c join pg_namespace n on "
                        "n.oid=c.relnamespace where n.nspname=:schema and lower(relname)=:name",
                    bindparams=[
                        sql.bindparam('name', unicode(table_name.lower()), type_=sqltypes.Unicode),
                        sql.bindparam('schema', unicode(schema), type_=sqltypes.Unicode)] 
                )
            )
        return bool(cursor.first())

    def has_sequence(self, connection, sequence_name, schema=None):
        if schema is None:
            cursor = connection.execute(
                        sql.text("SELECT relname FROM pg_class c join pg_namespace n on "
                            "n.oid=c.relnamespace where relkind='S' and n.nspname=current_schema()"
                            " and lower(relname)=:name",
                            bindparams=[
                                sql.bindparam('name', unicode(sequence_name.lower()),
                                type_=sqltypes.Unicode)
                            ] 
                        )
                    )
        else:
            cursor = connection.execute(
                    sql.text("SELECT relname FROM pg_class c join pg_namespace n on "
                        "n.oid=c.relnamespace where relkind='S' and n.nspname=:schema and "
                        "lower(relname)=:name",
                        bindparams=[
                            sql.bindparam('name', unicode(sequence_name.lower()),
                             type_=sqltypes.Unicode),
                            sql.bindparam('schema', unicode(schema), type_=sqltypes.Unicode)
                        ]
                    )
                )

        return bool(cursor.first())

    def has_type(self, connection, type_name, schema=None):
        bindparams = [
            sql.bindparam('typname',
                unicode(type_name), type_=sqltypes.Unicode),
            sql.bindparam('nspname',
                unicode(schema), type_=sqltypes.Unicode),
            ]
        if schema is not None:
            query = """
            SELECT EXISTS (
                SELECT * FROM pg_catalog.pg_type t, pg_catalog.pg_namespace n
                WHERE t.typnamespace = n.oid
                AND t.typname = :typname
                AND n.nspname = :nspname
                )
                """
        else:
            query = """
            SELECT EXISTS (
                SELECT * FROM pg_catalog.pg_type t
                WHERE t.typname = :typname
                AND pg_type_is_visible(t.oid)
                )
                """
        cursor = connection.execute(sql.text(query, bindparams=bindparams))
        return bool(cursor.scalar())

    def table_names(self, connection, schema):
        result = connection.execute(
            sql.text(u"SELECT relname FROM pg_class c "
                "WHERE relkind = 'r' "
                "AND '%s' = (select nspname from pg_namespace n where n.oid = c.relnamespace) " %
                 schema,
                typemap = {'relname':sqltypes.Unicode}
            )
        )
        return [row[0] for row in result]

    def _get_server_version_info(self, connection):
        v = connection.execute("select version()").scalar()
        m = re.match('PostgreSQL (\d+)\.(\d+)\.(\d+)', v)
        if not m:
            raise AssertionError("Could not determine version from string '%s'" % v)
        return tuple([int(x) for x in m.group(1, 2, 3)])

    @reflection.cache
    def get_table_oid(self, connection, table_name, schema=None, **kw):
        """Fetch the oid for schema.table_name.

        Several reflection methods require the table oid.  The idea for using
        this method is that it can be fetched one time and cached for
        subsequent calls.

        """
        table_oid = None
        if schema is not None:
            schema_where_clause = "n.nspname = :schema"
        else:
            schema_where_clause = "pg_catalog.pg_table_is_visible(c.oid)"
        query = """
            SELECT c.oid
            FROM pg_catalog.pg_class c
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE (%s)
            AND c.relname = :table_name AND c.relkind in ('r','v')
        """ % schema_where_clause
        # Since we're binding to unicode, table_name and schema_name must be
        # unicode.
        table_name = unicode(table_name)
        if schema is not None:
            schema = unicode(schema)
        s = sql.text(query, bindparams=[
            sql.bindparam('table_name', type_=sqltypes.Unicode),
            sql.bindparam('schema', type_=sqltypes.Unicode)
            ],
            typemap={'oid':sqltypes.Integer}
        )
        c = connection.execute(s, table_name=table_name, schema=schema)
        table_oid = c.scalar()
        if table_oid is None:
            raise exc.NoSuchTableError(table_name)
        return table_oid

    @reflection.cache
    def get_schema_names(self, connection, **kw):
        s = """
        SELECT nspname
        FROM pg_namespace
        ORDER BY nspname
        """
        rp = connection.execute(s)
        # what about system tables?
        # Py3K
        #schema_names = [row[0] for row in rp \
        #                if not row[0].startswith('pg_')]
        # Py2K
        schema_names = [row[0].decode(self.encoding) for row in rp \
                        if not row[0].startswith('pg_')]
        # end Py2K
        return schema_names

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.get_default_schema_name(connection)
        table_names = self.table_names(connection, current_schema)
        return table_names

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.get_default_schema_name(connection)
        s = """
        SELECT relname
        FROM pg_class c
        WHERE relkind = 'v'
          AND '%(schema)s' = (select nspname from pg_namespace n where n.oid = c.relnamespace)
        """ % dict(schema=current_schema)
        # Py3K
        #view_names = [row[0] for row in connection.execute(s)]
        # Py2K
        view_names = [row[0].decode(self.encoding) for row in connection.execute(s)]
        # end Py2K
        return view_names

    @reflection.cache
    def get_view_definition(self, connection, view_name, schema=None, **kw):
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.get_default_schema_name(connection)
        s = """
        SELECT definition FROM pg_views
        WHERE schemaname = :schema
        AND viewname = :view_name
        """
        rp = connection.execute(sql.text(s),
                                view_name=view_name, schema=current_schema)
        if rp:
            # Py3K
            #view_def = rp.scalar()
            # Py2K
            view_def = rp.scalar().decode(self.encoding)
            # end Py2K
            return view_def

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):

        table_oid = self.get_table_oid(connection, table_name, schema,
                                       info_cache=kw.get('info_cache'))
        SQL_COLS = """
            SELECT a.attname,
              pg_catalog.format_type(a.atttypid, a.atttypmod),
              (SELECT substring(d.adsrc for 128) FROM pg_catalog.pg_attrdef d
               WHERE d.adrelid = a.attrelid AND d.adnum = a.attnum AND a.atthasdef)
              AS DEFAULT,
              a.attnotnull, a.attnum, a.attrelid as table_oid
            FROM pg_catalog.pg_attribute a
            WHERE a.attrelid = :table_oid
            AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """
        s = sql.text(SQL_COLS, 
            bindparams=[sql.bindparam('table_oid', type_=sqltypes.Integer)], 
            typemap={'attname':sqltypes.Unicode, 'default':sqltypes.Unicode}
        )
        c = connection.execute(s, table_oid=table_oid)
        rows = c.fetchall()
        domains = self._load_domains(connection)
        enums = self._load_enums(connection)
        
        # format columns
        columns = []
        for name, format_type, default, notnull, attnum, table_oid in rows:
            ## strip (30) from character varying(30)
            attype = re.search('([^\([]+)', format_type).group(1)
            nullable = not notnull
            is_array = format_type.endswith('[]')
            try:
                charlen = re.search('\(([\d,]+)\)', format_type).group(1)
            except:
                charlen = False
            numericprec = False
            numericscale = False
            if attype == 'numeric':
                if charlen is False:
                    numericprec, numericscale = (None, None)
                else:
                    numericprec, numericscale = charlen.split(',')
                charlen = False
            if attype == 'double precision':
                numericprec, numericscale = (53, False)
                charlen = False
            if attype == 'integer':
                numericprec, numericscale = (32, 0)
                charlen = False
            args = []
            for a in (charlen, numericprec, numericscale):
                if a is None:
                    args.append(None)
                elif a is not False:
                    args.append(int(a))
            kwargs = {}
            if attype == 'timestamp with time zone':
                kwargs['timezone'] = True
            elif attype == 'timestamp without time zone':
                kwargs['timezone'] = False
            if attype in self.ischema_names:
                coltype = self.ischema_names[attype]
            elif attype in enums:
                enum = enums[attype]
                coltype = ENUM
                if "." in attype:
                    kwargs['schema'], kwargs['name'] = attype.split('.')
                else:
                    kwargs['name'] = attype
                args = tuple(enum['labels'])
            elif attype in domains:
                domain = domains[attype]
                if domain['attype'] in self.ischema_names:
                    # A table can't override whether the domain is nullable.
                    nullable = domain['nullable']
                    if domain['default'] and not default:
                        # It can, however, override the default value, but can't set it to null.
                        default = domain['default']
                    coltype = self.ischema_names[domain['attype']]
            else:
                coltype = None
                
            if coltype:
                coltype = coltype(*args, **kwargs)
                if is_array:
                    coltype = PGArray(coltype)
            else:
                util.warn("Did not recognize type '%s' of column '%s'" %
                          (attype, name))
                coltype = sqltypes.NULLTYPE
            # adjust the default value
            autoincrement = False
            if default is not None:
                match = re.search(r"""(nextval\(')([^']+)('.*$)""", default)
                if match is not None:
                    autoincrement = True
                    # the default is related to a Sequence
                    sch = schema
                    if '.' not in match.group(2) and sch is not None:
                        # unconditionally quote the schema name.  this could
                        # later be enhanced to obey quoting rules / "quote schema"
                        default = match.group(1) + ('"%s"' % sch) + '.' + match.group(2) + match.group(3)

            column_info = dict(name=name, type=coltype, nullable=nullable,
                               default=default, autoincrement=autoincrement)
            columns.append(column_info)
        return columns

    @reflection.cache
    def get_primary_keys(self, connection, table_name, schema=None, **kw):
        table_oid = self.get_table_oid(connection, table_name, schema,
                                       info_cache=kw.get('info_cache'))
        PK_SQL = """
          SELECT attname FROM pg_attribute
          WHERE attrelid = (
             SELECT indexrelid FROM pg_index i
             WHERE i.indrelid = :table_oid
             AND i.indisprimary = 't')
          ORDER BY attnum
        """
        t = sql.text(PK_SQL, typemap={'attname':sqltypes.Unicode})
        c = connection.execute(t, table_oid=table_oid)
        primary_keys = [r[0] for r in c.fetchall()]
        return primary_keys

    @reflection.cache
    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        preparer = self.identifier_preparer
        table_oid = self.get_table_oid(connection, table_name, schema,
                                       info_cache=kw.get('info_cache'))
        FK_SQL = """
          SELECT conname, pg_catalog.pg_get_constraintdef(oid, true) as condef
          FROM  pg_catalog.pg_constraint r
          WHERE r.conrelid = :table AND r.contype = 'f'
          ORDER BY 1
        """

        t = sql.text(FK_SQL, typemap={'conname':sqltypes.Unicode, 'condef':sqltypes.Unicode})
        c = connection.execute(t, table=table_oid)
        fkeys = []
        for conname, condef in c.fetchall():
            m = re.search('FOREIGN KEY \((.*?)\) REFERENCES (?:(.*?)\.)?(.*?)\((.*?)\)', condef).groups()
            (constrained_columns, referred_schema, referred_table, referred_columns) = m
            constrained_columns = [preparer._unquote_identifier(x) for x in re.split(r'\s*,\s*', constrained_columns)]
            if referred_schema:
                referred_schema = preparer._unquote_identifier(referred_schema)
            elif schema is not None and schema == self.get_default_schema_name(connection):
                # no schema (i.e. its the default schema), and the table we're
                # reflecting has the default schema explicit, then use that.
                # i.e. try to use the user's conventions
                referred_schema = schema
            referred_table = preparer._unquote_identifier(referred_table)
            referred_columns = [preparer._unquote_identifier(x) for x in re.split(r'\s*,\s', referred_columns)]
            fkey_d = {
                'name' : conname,
                'constrained_columns' : constrained_columns,
                'referred_schema' : referred_schema,
                'referred_table' : referred_table,
                'referred_columns' : referred_columns
            }
            fkeys.append(fkey_d)
        return fkeys

    @reflection.cache
    def get_indexes(self, connection, table_name, schema, **kw):
        table_oid = self.get_table_oid(connection, table_name, schema,
                                       info_cache=kw.get('info_cache'))
        IDX_SQL = """
          SELECT c.relname, i.indisunique, i.indexprs, i.indpred,
            a.attname
          FROM pg_index i, pg_class c, pg_attribute a
          WHERE i.indrelid = :table_oid AND i.indexrelid = c.oid
            AND a.attrelid = i.indexrelid AND i.indisprimary = 'f'
          ORDER BY c.relname, a.attnum
        """
        t = sql.text(IDX_SQL, typemap={'attname':sqltypes.Unicode})
        c = connection.execute(t, table_oid=table_oid)
        index_names = {}
        indexes = []
        sv_idx_name = None
        for row in c.fetchall():
            idx_name, unique, expr, prd, col = row
            if expr:
                if idx_name != sv_idx_name:
                    util.warn(
                      "Skipped unsupported reflection of expression-based index %s"
                      % idx_name)
                sv_idx_name = idx_name
                continue
            if prd and not idx_name == sv_idx_name:
                util.warn(
                   "Predicate of partial index %s ignored during reflection"
                   % idx_name)
                sv_idx_name = idx_name
            if idx_name in index_names:
                index_d = index_names[idx_name]
            else:
                index_d = {'column_names':[]}
                indexes.append(index_d)
                index_names[idx_name] = index_d
            index_d['name'] = idx_name
            index_d['column_names'].append(col)
            index_d['unique'] = unique
        return indexes

    def _load_enums(self, connection):
        ## Load data types for enums:
        SQL_ENUMS = """
            SELECT t.typname as "name",
                   -- t.typdefault as "default", -- no enum defaults in 8.4 at least
                   pg_catalog.pg_type_is_visible(t.oid) as "visible",
                   n.nspname as "schema",
                   e.enumlabel as "label"
            FROM pg_catalog.pg_type t
                 LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                 LEFT JOIN pg_catalog.pg_constraint r ON t.oid = r.contypid
                 LEFT JOIN pg_catalog.pg_enum e ON t.oid = e.enumtypid
            WHERE t.typtype = 'e'
            ORDER BY "name", e.oid -- e.oid gives us label order
        """

        s = sql.text(SQL_ENUMS, typemap={'attname':sqltypes.Unicode, 'label':sqltypes.Unicode})
        c = connection.execute(s)

        enums = {}
        for enum in c.fetchall():
            if enum['visible']:
                # 'visible' just means whether or not the enum is in a
                # schema that's on the search path -- or not overriden by
                # a schema with higher presedence. If it's not visible,
                # it will be prefixed with the schema-name when it's used.
                name = enum['name']
            else:
                name = "%s.%s" % (enum['schema'], enum['name'])

            if name in enums:
                enums[name]['labels'].append(enum['label'])
            else:
                enums[name] = {
                        'labels': [enum['label']],
                        }

        return enums

    def _load_domains(self, connection):
        ## Load data types for domains:
        SQL_DOMAINS = """
            SELECT t.typname as "name",
                   pg_catalog.format_type(t.typbasetype, t.typtypmod) as "attype",
                   not t.typnotnull as "nullable",
                   t.typdefault as "default",
                   pg_catalog.pg_type_is_visible(t.oid) as "visible",
                   n.nspname as "schema"
            FROM pg_catalog.pg_type t
                 LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                 LEFT JOIN pg_catalog.pg_constraint r ON t.oid = r.contypid
            WHERE t.typtype = 'd'
        """

        s = sql.text(SQL_DOMAINS, typemap={'attname':sqltypes.Unicode})
        c = connection.execute(s)

        domains = {}
        for domain in c.fetchall():
            ## strip (30) from character varying(30)
            attype = re.search('([^\(]+)', domain['attype']).group(1)
            if domain['visible']:
                # 'visible' just means whether or not the domain is in a
                # schema that's on the search path -- or not overriden by
                # a schema with higher presedence. If it's not visible,
                # it will be prefixed with the schema-name when it's used.
                name = domain['name']
            else:
                name = "%s.%s" % (domain['schema'], domain['name'])

            domains[name] = {
                    'attype':attype, 
                    'nullable': domain['nullable'], 
                    'default': domain['default']
                }

        return domains

