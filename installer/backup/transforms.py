# transforms.py
def remap_sort_key(item: dict) -> dict:
    """
    Example: compute new sort key 'new_sk' from existing attributes and
    remove the old one. Adjust to your schema.
    """
    # Suppose new sort key = f"{item['type']}#{item['timestamp']}"
    # and the table expects keys: PK (unchanged) + new_sk
    if "type" not in item or "timestamp" not in item:
        # Decide how to handle; raise or skip:
        # return None   # <- skip this item
        raise ValueError(f"Cannot build new_sk for item: {item}")

    item["new_sk"] = f"{item['type']}#{item['timestamp']}"
    # If the old sort key exists and must be removed:
    item.pop("old_sk", None)
    return item