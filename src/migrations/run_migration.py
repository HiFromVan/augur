"""
运行数据库迁移脚本
"""
import asyncio
import asyncpg
import os
import sys

DATABASE_URL = "postgresql://augur:augur@localhost:5432/augur"

async def run_migration(migration_file: str):
    conn = await asyncpg.connect(DATABASE_URL)

    with open(migration_file, 'r') as f:
        sql = f.read()

    try:
        await conn.execute(sql)
        print(f"✓ Migration {migration_file} executed successfully")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "src/migrations/004_add_prediction_accuracy.sql"

    asyncio.run(run_migration(migration_file))
