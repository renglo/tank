# backup_table.py
import argparse
from dynamo_backup_restore import DynamoBackupRestore

def main():
    ap = argparse.ArgumentParser(description="Backup a DynamoDB table to JSONL (DynamoDB JSON).")
    ap.add_argument("--table", required=True, help="Source table name")
    ap.add_argument("--out", required=True, help="Output file path (e.g., backup.jsonl)")
    ap.add_argument("--profile", help="AWS profile name")
    ap.add_argument("--region", help="AWS region name")
    ap.add_argument("--limit", type=int, help="Optional limit for quick tests")
    args = ap.parse_args()

    tool = DynamoBackupRestore(profile=args.profile, region=args.region)
    tool.backup_table(args.table, args.out, limit=args.limit)

if __name__ == "__main__":
    main()