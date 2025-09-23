# dynamo_backup_restore.py
from __future__ import annotations
import json, time, importlib, argparse
from typing import Callable, Optional, Iterable, Dict, Any, List
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer

class DynamoBackupRestore:
    """
    Backup and restore DynamoDB tables using lossless DynamoDB JSON (via TypeSerializer/TypeDeserializer).

    - backup_table() writes one serialized item per line (JSONL) to a local file.
    - restore_table_from_backup() reads JSONL and writes back using batch_write with automatic retry.

    Optional transform: a callable(item: dict) -> dict to modify items during restore
    (e.g., to compute a new sort key name/value).
    """

    def __init__(self, profile: Optional[str] = None, region: Optional[str] = None):
        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile
        session = boto3.Session(**session_kwargs)
        self._dynamodb = session.resource("dynamodb", region_name=region)
        self._client = session.client("dynamodb", region_name=region)
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    # -------------------------
    # Helpers
    # -------------------------
    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        # Convert Python (incl. Decimal/sets) to DynamoDB JSON
        return {k: self._serializer.serialize(v) for k, v in item.items()}

    def _deserialize_item(self, ddb_json_item: Dict[str, Any]) -> Dict[str, Any]:
        # Convert DynamoDB JSON to Python
        return {k: self._deserializer.deserialize(v) for k, v in ddb_json_item.items()}

    def _yield_scan_items(self, table_name: str, limit: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        table = self._dynamodb.Table(table_name)
        last_evaluated_key = None
        seen = 0
        while True:
            kwargs = {"Limit": 1000}
            if last_evaluated_key:
                kwargs["ExclusiveStartKey"] = last_evaluated_key

            resp = table.scan(**kwargs)
            items = resp.get("Items", [])
            for it in items:
                yield it
                seen += 1
                if limit and seen >= limit:
                    return

            last_evaluated_key = resp.get("LastEvaluatedKey")
            if not last_evaluated_key:
                return

    def _batch_write(self, table_name: str, items: List[Dict[str, Any]]) -> None:
        """
        Write items using BatchWriteItem with exponential backoff for UnprocessedItems.
        Items should be Python-native types (NOT DynamoDB JSON).
        """
        # Convert to PutRequest in DynamoDB JSON
        put_requests = [{"PutRequest": {"Item": self._serialize_item(it)}} for it in items]
        request_items = {table_name: put_requests}

        backoff = 0.5
        max_backoff = 16
        while request_items.get(table_name):
            resp = self._client.batch_write_item(RequestItems=request_items)
            unprocessed = resp.get("UnprocessedItems", {}).get(table_name, [])
            if unprocessed:
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
                request_items = {table_name: unprocessed}
            else:
                break

    # -------------------------
    # Public: Backup
    # -------------------------
    def backup_table(self, table_name: str, out_path: str, limit: Optional[int] = None) -> int:
        """
        Scan the table and write each item as a single JSON line (DynamoDB JSON).
        Returns the number of items written.
        """
        count = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for item in self._yield_scan_items(table_name, limit=limit):
                ddb_json = self._serialize_item(item)
                f.write(json.dumps(ddb_json, separators=(",", ":"), ensure_ascii=False))
                f.write("\n")
                count += 1
                if count % 1000 == 0:
                    print(f"[backup] Wrote {count} items...")
        print(f"[backup] Done. Total items written: {count}")
        return count

    # -------------------------
    # Public: Restore
    # -------------------------
    def restore_table_from_backup(
        self,
        table_name: str,
        in_path: str,
        transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        batch_size: int = 25,
        dry_run: bool = False,
    ) -> int:
        """
        Read JSONL backup and write to target table, optionally applying a transform(item)->item.

        - transform can rename/add keys to match a new key schema (e.g., new sort key).
        - batch_size must be <= 25 (DynamoDB limit).
        - dry_run prints transformed items count without writing.

        Returns total items processed.
        """
        assert 1 <= batch_size <= 25, "batch_size must be between 1 and 25"
        total = 0
        batch: List[Dict[str, Any]] = []

        def flush():
            if not batch:
                return
            if not dry_run:
                self._batch_write(table_name, batch)
            batch.clear()

        with open(in_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                ddb_json = json.loads(line)
                item = self._deserialize_item(ddb_json)
                if transform:
                    item = transform(item)
                    if item is None:
                        # Allow transform to drop items by returning None
                        continue
                batch.append(item)
                total += 1

                if len(batch) >= batch_size:
                    flush()
                    if total % 1000 == 0:
                        print(f"[restore] Processed {total} items...")

        flush()
        print(f"[restore] Done. Total items {'(dry-run) ' if dry_run else ''}processed: {total}")
        return total

    # -------------------------
    # Utility: Load transform by "module:function" string
    # -------------------------
    @staticmethod
    def load_transform(transform_spec: Optional[str]) -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
        """
        Load a transform callable from a 'module:function' spec, or return None.
        The function signature must be: def fn(item: dict) -> dict
        """
        if not transform_spec:
            return None
        if ":" not in transform_spec:
            raise ValueError("transform must be 'module:function'")
        mod_name, fn_name = transform_spec.split(":", 1)
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        if not callable(fn):
            raise TypeError(f"{transform_spec} is not callable")
        return fn