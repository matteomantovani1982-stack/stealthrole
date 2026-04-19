#!/usr/bin/env python3
"""
One-shot script to deduplicate linkedin_messages rows.
Removes duplicate conversations that have different URN formats
(e.g., 'thread:ABC' vs 'urn:li:fsd_conversation:ABC') for the same conversation.

Usage:
    python scripts/dedup_conversations.py
"""

import os
import sys
from collections import defaultdict

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://careeros:careeros@localhost:5432/careeros",
)

# Convert asyncpg URL to psycopg2 format
dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

def normalize_urn(urn: str) -> str:
    """Strip all known prefixes to get the core conversation key."""
    key = urn
    key = key.replace("thread:", "")
    for prefix in [
        "urn:li:fsd_conversation:",
        "urn:li:fs_conversation:",
        "urn:li:msg_conversation:",
    ]:
        key = key.replace(prefix, "")
    key = key.strip("()")
    return key

def main():
    print(f"Connecting to DB...")
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Get all conversations
    cur.execute("""
        SELECT id, user_id, conversation_urn, message_count, last_message_at, contact_name
        FROM linkedin_messages
        ORDER BY user_id, conversation_urn
    """)
    rows = cur.fetchall()
    print(f"Total rows in linkedin_messages: {len(rows)}")

    # Group by (user_id, normalized_key)
    groups = defaultdict(list)
    for row in rows:
        rid, user_id, urn, msg_count, last_at, name = row
        key = (user_id, normalize_urn(urn))
        groups[key].append({
            "id": rid,
            "urn": urn,
            "msg_count": msg_count or 0,
            "last_at": last_at,
            "name": name,
        })

    # Find duplicates
    to_delete = []
    dup_count = 0
    for key, entries in groups.items():
        if len(entries) < 2:
            continue
        dup_count += 1
        # Sort: keep the best (most messages, then has name, then has timestamp)
        entries.sort(key=lambda r: (
            r["msg_count"],
            1 if r["name"] else 0,
            str(r["last_at"] or ""),
        ), reverse=True)
        keeper = entries[0]
        for e in entries[1:]:
            to_delete.append(e["id"])
            if dup_count <= 10:  # Show first 10 examples
                print(f"  DUP: keeping '{keeper['urn'][:60]}' (msgs={keeper['msg_count']}, name={keeper['name']})")
                print(f"       delete '{e['urn'][:60]}' (msgs={e['msg_count']}, name={e['name']})")

    print(f"\nDuplicate groups found: {dup_count}")
    print(f"Rows to delete: {len(to_delete)}")
    print(f"Rows remaining after cleanup: {len(rows) - len(to_delete)}")

    if not to_delete:
        print("Nothing to clean up!")
        conn.close()
        return

    confirm = input("\nProceed with deletion? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        conn.close()
        return

    # Delete in batches
    batch_size = 100
    deleted = 0
    for i in range(0, len(to_delete), batch_size):
        batch = to_delete[i:i + batch_size]
        cur.execute(
            "DELETE FROM linkedin_messages WHERE id = ANY(%s)",
            (batch,)
        )
        deleted += cur.rowcount
        print(f"  Deleted {deleted}/{len(to_delete)}...")

    conn.commit()
    print(f"\nDone! Removed {deleted} duplicate rows.")

    # Verify
    cur.execute("SELECT count(*) FROM linkedin_messages")
    remaining = cur.fetchone()[0]
    print(f"Remaining rows: {remaining}")

    conn.close()

if __name__ == "__main__":
    main()
