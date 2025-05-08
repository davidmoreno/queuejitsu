from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "pendingdelivery" ADD "retry_count" INT NOT NULL DEFAULT 0;
        ALTER TABLE "pendingdelivery" ADD "last_attempt" TIMESTAMP;
        ALTER TABLE "pendingdelivery" ADD "retry_timeout" TIMESTAMP;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "pendingdelivery" DROP COLUMN "retry_count";
        ALTER TABLE "pendingdelivery" DROP COLUMN "last_attempt";
        ALTER TABLE "pendingdelivery" DROP COLUMN "retry_timeout";"""
