
import asyncio
import json
import sys
from unittest.mock import MagicMock

# Adjust path to include app
sys.path.append(".")

from app.services.redis_service import RedisService
from app.repositories.conversation_repository import ConversationRepository

async def verify_redis_integration():
    print("🚀 Verificando Integración de Redis...")
    
    # 1. Test Connection
    redis_svc = RedisService()
    await redis_svc.connect()
    
    # Check manual set/get
    await redis_svc.set("test_key", "hello_redis")
    val = await redis_svc.get("test_key")
    
    if val == "hello_redis":
        print("✅ Redis Connect & Set/Get: OK")
    else:
        print(f"❌ Redis Failed: Got {val}")
        return

    # 2. Test Repository Caching
    print("\n📦 Verificando Caching en Repositorio...")
    repo = ConversationRepository()
    
    # Mock DB response to avoid hitting real Supabase and ensure we test cache logic
    # We'll insert a real message to DB via save_message (which clears cache)
    # Then get_history twice. First time DB hit + Cache set. Second time Cache hit.
    
    phone = "51999999999"
    content = "Hola Redis"
    
    # A. Save Message -> Should Invalidate Cache
    print(f"   Writing message for {phone}...")
    # Mocking DB insert execution since we might not have real DB credentials in this env/context or want to isolate
    # For this verification, we assume valid credentials in .env. If not, this might fail on DB insert.
    # Let's try-except the DB part, focusing on Redis.
    
    # But wait, save_message calls db.insert().execute(). logic is coupled.
    # Let's mock the DB client inside repo for this test to focus on Redis.
    
    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.data = [{"role": "human", "content": content, "created_at": "2026-01-01T00:00:00"}]
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_execute
    
    # Mock insert
    mock_db.table.return_value.insert.return_value.execute.return_value = None
    
    repo.db = mock_db
    
    # 1. Save (Invalidate)
    await repo.save_message(phone, "human", content)
    
    # Verify delete called
    cached_after_save = await redis_svc.get(f"chat_history:{phone}")
    if cached_after_save is None:
        print("✅ Cache Invalidated after Save: OK")
    else:
        print("❌ Cache NOT Invalidated after Save")

    # 2. Get History (Miss -> Hit DB -> Set Cache)
    history = await repo.get_history(phone)
    print(f"   First fetch count: {len(history)}")
    
    # Verify cache is now set
    cached_history = await redis_svc.get(f"chat_history:{phone}")
    if cached_history:
        print("✅ Cache Populated after Read: OK")
        print(f"   Cached content: {cached_history[:50]}...")
    else:
        print("❌ Cache NOT Populated after Read")

    # 3. Get History Again (Hit Cache)
    # To verify it hits cache, we can change the mock DB return to be empty or different.
    # If it returns the old data, it must be from cache.
    
    # Change mock to return empty
    mock_execute.data = [] 
    
    history_cached = await repo.get_history(phone)
    print(f"   Second fetch count: {len(history_cached)}")
    
    if len(history_cached) > 0 and history_cached[0]["content"] == content:
        print("✅ Cache HIT verified (DB mock changed but data persisted): OK")
    else:
        print("❌ Cache MISS (Executed DB query instead of cache)")

    await redis_svc.close()

if __name__ == "__main__":
    asyncio.run(verify_redis_integration())
