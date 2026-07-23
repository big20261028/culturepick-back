from django.db import migrations


TRIGRAM_INDEXES = (
    ("perf_title_trgm_gin", "performances", "title"),
    ("perf_cast_trgm_gin", "performances", "cast"),
    ("perf_genre_trgm_gin", "performances", "genre"),
    ("venue_name_trgm_gin", "venues", "name"),
    ("venue_sido_trgm_gin", "venues", "sido"),
    ("venue_gugun_trgm_gin", "venues", "gugun"),
    ("venue_address_trgm_gin", "venues", "address"),
)


def create_postgres_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in TRIGRAM_INDEXES:
        schema_editor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" USING gin '
            f'(UPPER("{column_name}") gin_trgm_ops)'
        )


def drop_postgres_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    for index_name, _, _ in reversed(TRIGRAM_INDEXES):
        schema_editor.execute(
            f'DROP INDEX CONCURRENTLY IF EXISTS "{index_name}"'
        )


class Migration(migrations.Migration):
    # CREATE/DROP INDEX CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [
        ("performances", "0005_performanceprice"),
    ]

    operations = [
        migrations.RunPython(
            create_postgres_trigram_indexes,
            drop_postgres_trigram_indexes,
        ),
    ]

