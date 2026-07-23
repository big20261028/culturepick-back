from django.db import migrations


TRIGRAM_INDEXES = (
    ("community_post_title_trgm_gin", "community_posts", "title"),
    ("community_post_content_trgm_gin", "community_posts", "content"),
)


def create_postgres_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    # The performances migration normally creates the shared extension first.
    # Keeping this idempotent makes the community migration safe in isolation.
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
        ("community", "0002_post_category"),
        ("performances", "0006_postgres_trigram_search_indexes"),
    ]

    operations = [
        migrations.RunPython(
            create_postgres_trigram_indexes,
            drop_postgres_trigram_indexes,
        ),
    ]
