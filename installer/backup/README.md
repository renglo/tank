# DynamoDB Backup & Restore (with Optional Transform)

Backup a DynamoDB table to a lossless JSONL file and restore it into a new table—optionally transforming items (e.g., rename/compute a new sort key) during the restore.

This repo contains:
	•	dynamo_backup_restore.py — reusable class DynamoBackupRestore
	•	backup_table.py — standalone backup script
	•	restore_table.py — standalone restore script
	•	transforms.py — example transform(s) you can customize

⸻

Why this exists

DynamoDB doesn’t allow changing key schemas (partition/sort keys) in-place. To change a sort key, you typically:
	1.	Backup the existing table
	2.	Create a new table with the desired key schema
	3.	Restore data into the new table (optionally remapping/deriving the new sort key)
	4.	Cut over your application, then retire the old table

This toolkit handles steps 1 and 3 safely, with lossless types using TypeSerializer/TypeDeserializer.

⸻

Features
	•	Lossless backup format: DynamoDB JSON (numbers as Decimal, sets, binary—preserved).
	•	Resumable restore: Uses BatchWriteItem with retry/backoff for UnprocessedItems.
	•	Transform hook: Optional transform(item) -> item | None lets you modify keys/values per item (e.g., compute new sort key; skip invalid items by returning None).
	•	Dry-run mode: Validate transforms before writing.
	•	Profiles & regions: Supports --profile and --region.

⸻

Prerequisites
	•	Python 3.9+
	•	boto3 and botocore
	•	AWS credentials available via one of:
	•	~/.aws/credentials (named profiles),
	•	environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.),
	•	an instance/profile role.




### Install dependencies
```
pip install boto3 botocore
```

### IAM Permissions

The identity running these scripts needs:

For backup
	•	dynamodb:Scan
	•	dynamodb:DescribeTable

For restore
	•	dynamodb:BatchWriteItem
	•	dynamodb:DescribeTable
	•	(Optional) dynamodb:DescribeContinuousBackups if you’re validating backup status, etc.

A minimal policy snippet (adjust resource ARNs/regions as needed):
```
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["dynamodb:DescribeTable","dynamodb:Scan"], "Resource": "arn:aws:dynamodb:*:*:table/OldTable" },
    { "Effect": "Allow", "Action": ["dynamodb:DescribeTable","dynamodb:BatchWriteItem"], "Resource": "arn:aws:dynamodb:*:*:table/NewTable" }
  ]
}
```

## USAGE

### Step 1: Backup

```
python backup_table.py \
  --table OldTable \
  --out backup.jsonl \
  --profile your-aws-profile \
  --region us-east-1
```

```
python backup_table.py \
  --table noma_chat \
  --out noma_chat_backup.json \
  --profile maker \
  --region us-east-1
```

Options:
	•	--limit N — optional, export only N items (for smoke tests).
	•	If you omit --profile/--region, your default session/region is used.

Output: backup.jsonl with one DynamoDB-JSON item per line.


### Step 2: Create the new table

Create it via Console, CloudFormation, CDK, or Terraform with the new key schema (partition & sort key names/types), plus any GSIs/LSIs you need.
Note: This toolkit does not create tables; it assumes the target exists.


### Step 3: Write a Transform (optional)

Example: Create a new_sk from existing attributes, drop old_sk

```
# transforms.py
def remap_sort_key(item: dict) -> dict | None:
    """
    Build 'new_sk' from existing fields and optionally drop 'old_sk'.
    Return None to skip an item you cannot fix.
    """
    # Example: new_sk = "{type}#{timestamp}"
    t = item.get("type")
    ts = item.get("timestamp")
    if not t or not ts:
        # Skip or raise; choose your strategy
        # return None
        raise ValueError(f"Cannot build new_sk for item: {item}")

    item["new_sk"] = f"{t}#{ts}"
    item.pop("old_sk", None)
    return item

```


### Step 4: Dry run your restore
Validate parsing & transforms without writing

```
python restore_table.py \
  --table NewTable \
  --in backup.jsonl \
  --profile your-aws-profile \
  --region us-east-1 \
  --transform transforms:remap_sort_key \
  --dry-run
```

```
python restore_table.py \
  --table NewTable \
  --in noma_chat_backup.jsonl \
  --profile maker \
  --region us-east-1 \
  --dry-run
```

You'll see progress logs but no writes occur.


### Step 5: Restore (write to the new table)

```
python restore_table.py \
  --table NewTable \
  --in backup.jsonl \
  --profile your-aws-profile \
  --region us-east-1 \
  --transform transforms:remap_sort_key \
  --batch-size 25
```

```
python restore_table.py \
  --table noma_chat2 \
  --in noma_chat_backup.jsonl \
  --profile maker \
  --region us-east-1 \
  --batch-size 25
```

Notes:
	•	--batch-size must be ≤ 25 (DynamoDB limit). Default is 25.
	•	The script automatically retries UnprocessedItems with exponential backoff.



### INDEX : Programmatic Use (import the class)

```
from dynamo_backup_restore import DynamoBackupRestore
from transforms import remap_sort_key

tool = DynamoBackupRestore(profile="your-aws-profile", region="us-east-1")

# Backup
tool.backup_table(table_name="OldTable", out_path="backup.jsonl")

# Restore (with transform)
tool.restore_table_from_backup(
    table_name="NewTable",
    in_path="backup.jsonl",
    transform=remap_sort_key,  # or None
    batch_size=25,
    dry_run=False,
)
```


### Format Details
	•	Backup format: one JSON object per line (JSONL).
	•	Each object is DynamoDB JSON (e.g., {"attr":{"S":"value"}}, {"n":{"N":"123"}}, including sets/binary).
	•	We use TypeSerializer/TypeDeserializer to avoid lossy conversions (e.g., float vs Decimal, set types, etc.).

⸻

### Operational Guidance
	•	Capacity/Throughput: Restores use BatchWriteItem. If your table is provisioned, ensure adequate WCU. If on-demand, AWS auto-scales but you may still see throttling (retries will handle it).
	•	Indexes: Create GSIs/LSIs on the target table before restoring if your app or transform depends on them.
	•	Item size/limits: DynamoDB item size limit is 400 KB. If your transform inflates item size beyond the limit, the write will fail.
	•	Idempotency: BatchWriteItem PUTs are upserts. If the same key already exists, it will be overwritten. If you need conditional writes, this toolkit would need extension (e.g., ConditionExpression on per-item put—BatchWriteItem does not support it).
	•	Validation: After restoring, compare counts and spot-check keys/attributes:
	•	DescribeTable → ItemCount is eventually consistent.
	•	For precise validation, scan both tables (with key-only projection) and diff the keys.





### Troubleshooting
	•	botocore.exceptions.NoCredentialsError
Ensure your AWS creds are configured or pass --profile. Test with aws sts get-caller-identity.
	•	Throttling / UnprocessedItems won’t drain
Lower --batch-size (e.g., 10), verify WCU/capacity, or temporarily increase provisioned capacity.
	•	ValidationException: One or more parameter values were invalid
Check that transformed items match the new key schema and attribute types. Also verify item size ≤ 400 KB.
	•	AccessDeniedException
Confirm IAM permissions for source/target tables.
	•	Transform errors
If your transform may skip bad items, return None to drop them. Otherwise raise to stop and fix the data or logic.

