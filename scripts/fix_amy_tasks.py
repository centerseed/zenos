import asyncio
import os
from zenos.infrastructure.action import SqlTaskRepository
from zenos.infrastructure.sql_common import get_pool
from zenos.infrastructure.context import current_partner_id

async def fix_tasks():
    # Set context for repository (Barry's partner ID from previous tool outputs)
    current_partner_id.set("xXLk35f9sIGqUeewhj2w")
    
    pool = await get_pool()
    repo = SqlTaskRepository(pool)
    
    yayun_id = "1575f903b79b4051b891e9e439fb9c36"  # 雅云行銷公司 L1 entity

    # Task 1: GRACE ONE 寶雅陳列物
    t1 = await repo.get_by_id("02cb8e8ba2d844c3822a9b88c1c82910")
    if t1:
        t1.project = "yayun"
        t1.product_id = yayun_id
        t1.linked_entities = ["1311e7c6a7f3424e975609d5ce203824"]  # pragma: allowlist secret
        await repo.upsert(t1)
        print("Fixed Task 1 (GRACE ONE)")

    # Task 2: Banila Co IG v1
    t2 = await repo.get_by_id("049d5d374b3747ca989bfe7189f2b89b")
    if t2:
        t2.project = "yayun"
        t2.product_id = yayun_id
        t2.linked_entities = ["80ad76afa3a64d499db30e5c95c7dde8"]  # pragma: allowlist secret
        await repo.upsert(t2)
        print("Fixed Task 2 (Banila Co v1)")

    # Task 3: Banila Co IG v2
    t3 = await repo.get_by_id("39e4d04192ee447c98acd102b97010e2")
    if t3:
        t3.project = "yayun"
        t3.product_id = yayun_id
        t3.linked_entities = ["80ad76afa3a64d499db30e5c95c7dde8"]  # pragma: allowlist secret
        await repo.upsert(t3)
        print("Fixed Task 3 (Banila Co v2)")
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(fix_tasks())
