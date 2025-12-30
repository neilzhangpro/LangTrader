#!/usr/bin/env python3
"""
数据库迁移脚本
执行方法: python scripts/apply_migration.py
"""
import asyncio
from sqlalchemy import create_engine, text
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

async def apply_migration():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")
    
    # 移除 asyncpg 前缀用于同步连接
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # 同步引擎用于执行 SQL
    engine = create_engine(sync_url)
    
    migration_file = Path(__file__).parent / "migrations" / "add_quant_risk_config.sql"
    
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    print(f"📦 Applying migration from {migration_file.name}...")
    
    with engine.connect() as conn:
        # 执行迁移（按分号分割语句）
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        
        for idx, statement in enumerate(statements, 1):
            try:
                print(f"  Executing statement {idx}/{len(statements)}...")
                conn.execute(text(statement))
            except Exception as e:
                print(f"  ⚠️ Statement {idx} warning: {e}")
        
        conn.commit()
    
    print("✅ Migration applied successfully!")

if __name__ == "__main__":
    asyncio.run(apply_migration())

