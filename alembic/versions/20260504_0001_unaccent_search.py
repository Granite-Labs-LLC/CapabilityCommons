"""Make full-text search accent-insensitive.

Adds the `unaccent` extension, creates an `english_unaccent` text-search
configuration that runs tokens through `unaccent` before the English
stemmer, and rewrites `context_object_versions.search_tsv` to use it.

After this migration:
    websearch_to_tsquery('english_unaccent', 'cafe')
    @@ to_tsvector('english_unaccent', 'café')   -- matches

Revision ID: 20260504_0001
Revises: 20260402_0002
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

revision = "20260504_0001"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # Create english_unaccent only if it does not already exist. There's no
    # IF NOT EXISTS form for CREATE TEXT SEARCH CONFIGURATION, so guard it.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_ts_config WHERE cfgname = 'english_unaccent'
            ) THEN
                CREATE TEXT SEARCH CONFIGURATION english_unaccent (COPY = english);
                ALTER TEXT SEARCH CONFIGURATION english_unaccent
                    ALTER MAPPING FOR
                        hword, hword_part, word, asciiword, asciihword,
                        hword_asciipart
                    WITH unaccent, english_stem;
            END IF;
        END
        $$;
        """
    )

    # Drop and re-add the generated column so it uses the new config. The
    # GIN index on it is dropped by CASCADE and recreated below.
    op.execute("DROP INDEX IF EXISTS idx_cov_search_tsv")
    op.execute("ALTER TABLE context_object_versions DROP COLUMN IF EXISTS search_tsv")
    op.execute(
        """
        ALTER TABLE context_object_versions
        ADD COLUMN search_tsv TSVECTOR GENERATED ALWAYS AS (
            to_tsvector(
                'english_unaccent',
                coalesce(title, '') || ' ' ||
                coalesce(summary_short, '') || ' ' ||
                coalesce(summary_medium, '') || ' ' ||
                coalesce(plain_language, '') || ' ' ||
                coalesce(markdown_body, '')
            )
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX idx_cov_search_tsv "
        "ON context_object_versions USING GIN(search_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cov_search_tsv")
    op.execute("ALTER TABLE context_object_versions DROP COLUMN IF EXISTS search_tsv")
    op.execute(
        """
        ALTER TABLE context_object_versions
        ADD COLUMN search_tsv TSVECTOR GENERATED ALWAYS AS (
            to_tsvector(
                'english',
                coalesce(title, '') || ' ' ||
                coalesce(summary_short, '') || ' ' ||
                coalesce(summary_medium, '') || ' ' ||
                coalesce(plain_language, '') || ' ' ||
                coalesce(markdown_body, '')
            )
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX idx_cov_search_tsv "
        "ON context_object_versions USING GIN(search_tsv)"
    )
    # Leave english_unaccent and the unaccent extension in place; harmless
    # to keep and removing them could break other consumers.
