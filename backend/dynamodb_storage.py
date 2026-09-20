"""DynamoDB-based storage for conversations (Phase 1).

Replaces the JSON file-based storage with Amazon DynamoDB.
The table schema uses:
  - Partition Key: PK (String) = "CONV#<conversation_id>"
  - Sort Key:      SK (String) = "META" for conversation metadata,
                                 "MSG#<index>" for messages

This single-table design is efficient for DynamoDB and supports
all existing query patterns.
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from decimal import Decimal

from .aws_config import get_dynamodb_resource, get_dynamodb_client, DYNAMODB_TABLE_NAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decimal_to_native(obj):
    """Convert DynamoDB Decimal types to Python int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _serialize_for_dynamo(obj):
    """Convert Python floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _serialize_for_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_dynamo(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Table Bootstrap
# ---------------------------------------------------------------------------

def ensure_table_exists():
    """Create the DynamoDB table if it doesn't exist yet."""
    client = get_dynamodb_client()
    existing = client.list_tables().get("TableNames", [])
    if DYNAMODB_TABLE_NAME in existing:
        return

    client.create_table(
        TableName=DYNAMODB_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",  # On-demand pricing – no capacity planning needed
    )

    # Wait for table to become ACTIVE
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=DYNAMODB_TABLE_NAME)
    print(f"[DynamoDB] Created table '{DYNAMODB_TABLE_NAME}'")


def _get_table():
    """Return the DynamoDB Table resource."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(DYNAMODB_TABLE_NAME)


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create a new conversation in DynamoDB."""
    ensure_table_exists()
    table = _get_table()

    now = datetime.now(timezone.utc).isoformat()

    conversation_meta = {
        "PK": f"CONV#{conversation_id}",
        "SK": "META",
        "id": conversation_id,
        "created_at": now,
        "title": "New Conversation",
        "message_count": 0,
        "entity_type": "conversation",
    }

    table.put_item(Item=conversation_meta)

    return {
        "id": conversation_id,
        "created_at": now,
        "title": "New Conversation",
        "messages": [],
    }


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation with all its messages from DynamoDB."""
    table = _get_table()

    # Query all items for this conversation (META + MSG#*)
    response = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"CONV#{conversation_id}"},
        ScanIndexForward=True,  # Sort ascending by SK
    )

    items = response.get("Items", [])
    if not items:
        return None

    # Separate metadata from messages
    meta = None
    messages = []

    for item in items:
        item = _decimal_to_native(item)
        if item["SK"] == "META":
            meta = item
        elif item["SK"].startswith("MSG#"):
            msg_data = json.loads(item["message_json"])
            messages.append(msg_data)

    if meta is None:
        return None

    return {
        "id": meta["id"],
        "created_at": meta["created_at"],
        "title": meta.get("title", "New Conversation"),
        "messages": messages,
    }


def save_message(conversation_id: str, message_index: int, message: Dict[str, Any]):
    """Save a single message to DynamoDB."""
    table = _get_table()

    # Store the message as a JSON string to avoid DynamoDB type limitations
    # with deeply nested structures
    msg_item = {
        "PK": f"CONV#{conversation_id}",
        "SK": f"MSG#{message_index:06d}",  # Zero-padded for correct sort order
        "message_json": json.dumps(message, default=str),
        "role": message.get("role", "unknown"),
        "entity_type": "message",
    }

    table.put_item(Item=_serialize_for_dynamo(msg_item))


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only) – scans META items."""
    ensure_table_exists()
    table = _get_table()

    # Scan for all META items
    response = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "META"},
        ProjectionExpression="id, created_at, title, message_count",
    )

    items = response.get("Items", [])

    # Handle pagination for large datasets
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="SK = :sk",
            ExpressionAttributeValues={":sk": "META"},
            ProjectionExpression="id, created_at, title, message_count",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    conversations = []
    for item in items:
        item = _decimal_to_native(item)
        conversations.append({
            "id": item["id"],
            "created_at": item["created_at"],
            "title": item.get("title", "New Conversation"),
            "message_count": item.get("message_count", 0),
        })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def add_user_message(conversation_id: str, content: str):
    """Add a user message to a conversation in DynamoDB."""
    table = _get_table()

    # Get current message count
    meta_response = table.get_item(
        Key={"PK": f"CONV#{conversation_id}", "SK": "META"}
    )
    meta = meta_response.get("Item")
    if meta is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    current_count = int(meta.get("message_count", 0))

    # Save the message
    message = {"role": "user", "content": content}
    save_message(conversation_id, current_count, message)

    # Update the message count
    table.update_item(
        Key={"PK": f"CONV#{conversation_id}", "SK": "META"},
        UpdateExpression="SET message_count = :count",
        ExpressionAttributeValues={":count": current_count + 1},
    )


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
):
    """Add a complete assistant message with all 3 stages."""
    table = _get_table()

    # Get current message count
    meta_response = table.get_item(
        Key={"PK": f"CONV#{conversation_id}", "SK": "META"}
    )
    meta = meta_response.get("Item")
    if meta is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    current_count = int(meta.get("message_count", 0))

    # Save the assistant message
    message = {
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
    }
    save_message(conversation_id, current_count, message)

    # Update the message count
    table.update_item(
        Key={"PK": f"CONV#{conversation_id}", "SK": "META"},
        UpdateExpression="SET message_count = :count",
        ExpressionAttributeValues={":count": current_count + 1},
    )


def update_conversation_title(conversation_id: str, title: str):
    """Update the title of a conversation."""
    table = _get_table()

    table.update_item(
        Key={"PK": f"CONV#{conversation_id}", "SK": "META"},
        UpdateExpression="SET title = :title",
        ExpressionAttributeValues={":title": title},
    )


def delete_conversation(conversation_id: str):
    """Delete an entire conversation and all its messages."""
    table = _get_table()

    # Query all items for this conversation
    response = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"CONV#{conversation_id}"},
        ProjectionExpression="PK, SK",
    )

    # Batch delete all items
    with table.batch_writer() as batch:
        for item in response.get("Items", []):
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
