from scripts.run_sql_migrations import checksum_matches_applied


def test_checksum_matches_when_equal() -> None:
    checksum = "abc123"
    assert checksum_matches_applied("20260423_0001_document_entity_preflight", checksum, checksum)


def test_checksum_matches_known_alias() -> None:
    assert checksum_matches_applied(
        "20260422_0002_task_product_id_backfill",
        "32d6052aeea27b96e4053d5bab32c3fa6b2adc6fdbb21b31e0660fb05a89d118",  # pragma: allowlist secret
        "e044fd9a6539f98e1663a37eb60dd7c2fe5d61976d1e1bcd275a34dad535f6d6",  # pragma: allowlist secret
    )


def test_checksum_rejects_unknown_alias() -> None:
    assert not checksum_matches_applied(
        "20260422_0002_task_product_id_backfill",
        "deadbeef",
        "e044fd9a6539f98e1663a37eb60dd7c2fe5d61976d1e1bcd275a34dad535f6d6",  # pragma: allowlist secret
    )
