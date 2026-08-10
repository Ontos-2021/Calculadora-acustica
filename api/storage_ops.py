from __future__ import annotations

import argparse
import json

from .config import get_settings
from .database import init_db, session_scope
from .object_service import reconcile_assets, storage_metrics
from .storage import create_storage


def main() -> None:
    parser = argparse.ArgumentParser(description="Storage maintenance operations")
    parser.add_argument("command", choices=("reconcile", "metrics"))
    args = parser.parse_args()
    settings = get_settings()
    init_db()
    storage = create_storage(settings)
    with session_scope() as session:
        if args.command == "reconcile":
            result = reconcile_assets(
                session,
                storage,
                pending_max_age_seconds=settings.storage_pending_max_age_seconds,
            )
        else:
            result = storage_metrics(session)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
