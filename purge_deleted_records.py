"""Hard-delete CareOS records that have been soft-deleted past the retention window.

Archive/restore/delete in CareOS is a soft-delete: the row stays in Supabase
with `lifecycle_status = 'deleted'` and the action is written to
`data_lifecycle_events` for auditability. That's the right default for
accountability, but rows should not sit soft-deleted forever - this script
is the other half of the story: it actually frees storage once a deleted
row has aged past the retention window, while leaving the audit trail intact.

Run manually:

    python purge_deleted_records.py
    python purge_deleted_records.py --older-than-days 60

Or schedule it (recommended for a real deployment, not required for the
demo): on Render, add a separate **Cron Job** service pointed at this
script with the same environment variables as the main web service, running
on whatever cadence fits (daily/weekly). Locally or on any other host, a
plain cron entry or scheduled task works the same way.
"""

import argparse

from backend.app.db import purge_expired_deleted_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=30,
        help="Purge records soft-deleted more than this many days ago (default: 30).",
    )
    args = parser.parse_args()

    purged = purge_expired_deleted_records(older_than_days=args.older_than_days)
    total = sum(purged.values())
    print(f"Purged {total} record(s) soft-deleted more than {args.older_than_days} day(s) ago:")
    for table, count in purged.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
