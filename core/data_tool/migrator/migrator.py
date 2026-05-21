import logging
import re

from holistiq_libs.operations.data_ops.migrate_db.utils import MigrateUtils
from sqlalchemy import Integer, MetaData, Table, create_engine, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.schema import Identity


class MigratorDB:
    def __init__(self, dry_run: bool = False):
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self._validate_migrate_params()
        self._create_engines()
        self.run_migrate()

    def _validate_migrate_params(self):
        source = str(getattr(self.env, f"{self.env.migrate.migrate.source}_conn"))
        target = str(getattr(self.env, f"{self.env.migrate.migrate.target}_conn"))

        if source.startswith("sqlite:///"):
            MigrateUtils.ensure_sqlite_dir(source.replace("sqlite:///", ""))
        if target.startswith("sqlite:///"):
            MigrateUtils.ensure_sqlite_dir(target.replace("sqlite:///", ""))

        self.schema_list = [None]
        self.filter_tables = None
        self.prefix = False
        self.batch_size = 1000

        if hasattr(self.env.migrate.migrate, "schemas"):
            self.schema_list = [
                s.strip() for s in self.env.migrate.migrate.schemas.split(",")
            ]
        if hasattr(self.env.migrate.migrate, "filter_table"):
            self.filter_tables = [
                t.strip() for t in self.env.migrate.migrate.filter_table.split(",")
            ]
        if hasattr(self.env.migrate.migrate, "prefix"):
            self.prefix = self.env.migrate.migrate.prefix
        if hasattr(self.env.migrate.migrate, "batch_size"):
            self.batch_size = self.env.migrate.migrate.batch_size

    def _create_engines(self):
        source = getattr(self.env, f"{self.env.migrate.migrate.source}_conn")
        target = getattr(self.env, f"{self.env.migrate.migrate.target}_conn")
        self.source_engine = create_engine(
            source if str(source).startswith("sqlite:///") else source.get_url()
        )
        self.target_engine = create_engine(
            target if str(target).startswith("sqlite:///") else target.get_url()
        )

    def run_migrate(self):
        for schema in self.schema_list:
            schema_name = schema or "default"
            self.logger.info(f"🔄 Migrating schema: {schema_name}")
            self._migrate_schema_tables(
                schema,
                self.source_engine,
                self.target_engine,
                self.filter_tables,
                self.prefix,  # type: ignore
                self.dry_run,
                self.batch_size,  # type: ignore
            )
        self.logger.info("🎉 Migration completed.")

    def _migrate_schema_tables(
        self,
        schema,
        source_engine,
        target_engine,
        filter_tables=None,
        prefix=True,
        dry_run=False,
        batch_size=1000,
    ):
        # Reflect source metadata
        src_meta = MetaData()
        dialect_src = source_engine.dialect.name
        dialect_tgt = target_engine.dialect.name
        use_schema = schema if MigrateUtils.supports_schemas(dialect_src) else None
        src_meta.reflect(bind=source_engine, schema=use_schema)

        tgt_meta = MetaData()
        # tgt_meta.reflect(bind=engine)
        tgt_inspector = inspect(target_engine)

        for full_table_name, src_table in src_meta.tables.items():
            # Table name handling
            if use_schema:
                raw_table_name = full_table_name.split(".")[-1]
                tgt_table_name = (
                    f"{schema}__{raw_table_name}" if prefix else raw_table_name
                )
            else:
                tgt_table_name = full_table_name

            if filter_tables and tgt_table_name not in filter_tables:
                continue

            # Check if table exists on target
            existing_tables = tgt_inspector.get_table_names(
                schema=schema if MigrateUtils.supports_schemas(dialect_tgt) else None
            )
            if tgt_table_name in existing_tables:
                self.logger.info(
                    f"⚠️ Table {tgt_table_name} already exists in target. Skipping creation."
                )
            else:
                # Create table on target DB
                try:
                    # Copy columns for target table definition
                    new_cols = [col.copy() for col in src_table.columns]
                    new_cols = self.sanitize_columns_for_sqlite(new_cols)
                    tgt_table = Table(
                        tgt_table_name,
                        tgt_meta,
                        *new_cols,
                        schema=(
                            schema
                            if MigrateUtils.supports_schemas(dialect_tgt)
                            else None
                        ),
                    )
                    create_stmt = str(
                        CreateTable(tgt_table).compile(dialect=target_engine.dialect)
                    )
                    if target_engine.dialect.name == "sqlite":
                        pattern = (
                            r"DEFAULT\s*\(?\s*nextval\('.*?_id_seq'::regclass\)\s*\)?"
                        )
                        replacement = "PRIMARY KEY AUTOINCREMENT"
                        create_stmt = re.sub(pattern, replacement, create_stmt)
                        # create_stmt = create_stmt.replace(f"DEFAULT (nextval('{src_table}_id_seq'::regclass))", "PRIMARY KEY AUTOINCREMENT")
                    if dry_run:
                        self.logger.info(
                            f"🧪 [Dry-run] Would create table: {tgt_table_name}"
                        )
                        self.logger.info(f"SQL: {create_stmt}")
                    else:
                        tgt_table.create(bind=target_engine)
                        self.logger.info(f"✅ Created table: {tgt_table_name}")
                except SQLAlchemyError as e:
                    self.logger.info(f"❌ Error creating table {tgt_table_name}: {e}")
                    self.logger.error(
                        f"Schema: {schema or 'default'}, Table: {tgt_table_name}, Error: {e}"
                    )
                    continue

            # Copy data
            try:
                if not dry_run:
                    with source_engine.connect() as src_conn:
                        rows = src_conn.execute(select(src_table)).fetchall()

                    if rows:
                        columns = [col.name for col in src_table.columns]
                        # placeholders = ", ".join([":{}".format(col) for col in columns])
                        # insert_sql = f"INSERT INTO {tgt_table_name} ({', '.join(columns)}) VALUES ({placeholders})"

                        self.logger.info(
                            f"📥 Copying {len(rows)} rows into {tgt_table_name}"
                        )

                        with target_engine.connect() as tgt_conn:
                            metadata = MetaData()
                            tgt_table = Table(
                                tgt_table_name, metadata, autoload_with=target_engine
                            )
                            trans = tgt_conn.begin()
                            try:
                                for chunk in MigrateUtils.batch(rows, batch_size):
                                    values_list = [
                                        dict(zip(columns, row)) for row in chunk
                                    ]
                                    tgt_conn.execute(tgt_table.insert(), values_list)
                                trans.commit()
                            except Exception:
                                trans.rollback()
                                raise
                        self.logger.info(
                            f"✅ Copied {len(rows)} rows into {tgt_table_name}"
                        )
                    else:
                        self.logger.info(f"⚠️ No data to copy for {tgt_table_name}")
            except SQLAlchemyError as e:
                self.logger.info(f"❌ Error copying data for {tgt_table_name}: {e}")
                self.logger.error(schema or "default", tgt_table_name, e)

    def sanitize_columns_for_sqlite(self, columns):
        patched = []
        for col in columns:
            new_col = col.copy()

            # Remove PG-style Identity objects
            if hasattr(new_col, "identity") and isinstance(new_col.identity, Identity):
                new_col.identity = None

            # Remove server_default if it's PG sequence-related
            if (
                hasattr(new_col, "server_default")
                and new_col.server_default is not None
            ):
                try:
                    # If it's text or expression-based
                    default_str = str(new_col.server_default.arg).lower()
                    if "nextval" in default_str and "::regclass" in default_str:
                        new_col.server_default = None
                except AttributeError:
                    # Handle case: 'Identity' object or others without .arg
                    new_col.server_default = None

            # Enable autoincrement if it's the PK and integer
            if new_col.primary_key and isinstance(new_col.type, Integer):
                new_col.autoincrement = True

            patched.append(new_col)
        return patched
