import unittest

from django.db import connection
from django.test import SimpleTestCase


EXPECTED_TRIGRAM_INDEXES = {
    "perf_title_trgm_gin",
    "perf_cast_trgm_gin",
    "perf_genre_trgm_gin",
    "venue_name_trgm_gin",
    "venue_sido_trgm_gin",
    "venue_gugun_trgm_gin",
    "venue_address_trgm_gin",
    "community_post_title_trgm_gin",
    "community_post_content_trgm_gin",
}


@unittest.skipUnless(
    connection.vendor == "postgresql",
    "PostgreSQL-specific pg_trgm index verification",
)
class PostgreSQLTrigramIndexTests(SimpleTestCase):
    databases = {"default"}

    def test_pg_trgm_extension_and_gin_expression_indexes_exist(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS("
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
                ")"
            )
            self.assertTrue(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND indexname = ANY(%s)
                """,
                [list(EXPECTED_TRIGRAM_INDEXES)],
            )
            definitions = dict(cursor.fetchall())

        self.assertEqual(set(definitions), EXPECTED_TRIGRAM_INDEXES)
        for definition in definitions.values():
            normalized = definition.lower()
            self.assertIn("using gin", normalized)
            self.assertIn("gin_trgm_ops", normalized)
            self.assertIn("upper(", normalized)

