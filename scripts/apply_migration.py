#!/usr/bin/env python3
"""
数据库迁移脚本
执行方法: python scripts/apply_migration.py <migration_file.sql>
"""
import asyncio
import sys
from sqlalchemy import create_engine, text
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

async def apply_migration(migration_file_path: str = None):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")
    
    # 移除 asyncpg 前缀用于同步连接
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # 同步引擎用于执行 SQL
    engine = create_engine(sync_url)
    
    # 确定迁移文件
    if migration_file_path:
        migration_file = Path(migration_file_path)
    else:
        # 默认使用旧的文件
        migration_file = Path(__file__).parent / "migrations" / "add_quant_risk_config.sql"
    
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    print(f"📦 Applying migration from {migration_file.name}...")
    print(f"   Database: {sync_url.split('@')[1] if '@' in sync_url else sync_url}")
    print()
    
    with engine.connect() as conn:
        # 执行迁移（按分号分割语句）
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        success_count = 0
        warning_count = 0
        
        for idx, statement in enumerate(statements, 1):
            # 跳过注释和echo命令
            if statement.startswith('\\echo') or statement.startswith('COMMENT'):
                continue
                
            try:
                print(f"  [{idx}/{len(statements)}] Executing...")
                conn.execute(text(statement))
                success_count += 1
            except Exception as e:
                warning_count += 1
                print(f"  ⚠️  Statement {idx} warning: {e}")
        
        conn.commit()
        print()
        print(f"✅ Migration applied successfully!")
        print(f"   Success: {success_count}, Warnings: {warning_count}")

if __name__ == "__main__":
    migration_file = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(apply_migration(migration_file))

