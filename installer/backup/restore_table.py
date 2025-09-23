# restore_table.py
import argparse
from dynamo_backup_restore import DynamoBackupRestore

def main():
    ap = argparse.ArgumentParser(description="Restore items into a DynamoDB table from JSONL backup.")
    ap.add_argument("--table", required=True, help="Target table name (must already exist)")
    ap.add_argument("--in", dest="in_path", required=True, help="Input file path (backup.jsonl)")
    ap.add_argument("--profile", help="AWS profile name")
    ap.add_argument("--region", help="AWS region name")
    ap.add_argument("--transform", help="Optional 'module:function' to transform items before write")
    ap.add_argument("--batch-size", type=int, default=25, help="Batch write size (<=25)")
    ap.add_argument("--dry-run", action="store_true", help="Parse/transform only; do not write")
    args = ap.parse_args()

    tool = DynamoBackupRestore(profile=args.profile, region=args.region)
    transform_fn = DynamoBackupRestore.load_transform(args.transform)
    tool.restore_table_from_backup(
        table_name=args.table,
        in_path=args.in_path,
        transform=transform_fn,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

if __name__ == "__main__":
    main()