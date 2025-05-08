from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "eventstatus" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(255) NOT NULL
);
CREATE TABLE IF NOT EXISTS "event" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "event" VARCHAR(255) NOT NULL,
    "source_ip" VARCHAR(255) NOT NULL,
    "payload" JSON NOT NULL,
    "timestamp" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status_id" INT NOT NULL REFERENCES "eventstatus" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "pendingdelivery" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "subscriptor" VARCHAR(255) NOT NULL,
    "event_id" INT NOT NULL REFERENCES "event" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
