from capability_commons.cli.worker import HANDLERS, OutboxWorker


def test_handler_registry():
    assert "version.published" in HANDLERS
    assert "version.reindexed" in HANDLERS


def test_worker_has_handlers():
    worker = OutboxWorker.__new__(OutboxWorker)
    for handler_name in HANDLERS.values():
        assert hasattr(worker, handler_name), f"Missing handler: {handler_name}"
