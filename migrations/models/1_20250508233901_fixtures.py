from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        INSERT INTO "eventstatus" ("id", "name") VALUES
        (10, 'Pending'),
        (20, 'Processing'),
        (30, 'Delivering'),
        (40, 'Delivered'),
        (50, 'Failed');
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
