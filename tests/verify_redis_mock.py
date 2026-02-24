
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Adjust path to include app
sys.path.append(".")

from app.services.redis_service import RedisService
from app.repositories.conversation_repository import ConversationRepository

# Mock get_supabase_client BEFORE importing/init ConversationRepository if possible,
# or patch it. Since it's imported in the module, we can patch the module import.
@patch("app.repositories.conversation_repository.get_supabase_client")
async def verify_redis_logic_mock(mock_get_db):
    print("🚀 Verificando Lógica de Redis (MOCKED)...")
    mock_db_instance = MagicMock()
    mock_get_db.return_value = mock_db_instance
    
    # 1. Test RedisService Singleton & Connection
    print("\n📦 1. Test RedisService...")
    redis_svc = RedisService()
    
    # Mock redis.from_url
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        
        await redis_svc.connect()
        mock_from_url.assert_called_once()
        print("✅ RedisService.connect() llama a redis.from_url")
        
        # Test Set
        await redis_svc.set("key", "val")
        mock_client.set.assert_called_with("key", "val", ex=3600)
        print("✅ RedisService.set() llama al cliente correctamente")

    # 2. Test ConversationRepository Cache-Aside
    print("\n📦 2. Test Repository Cache-Aside...")
    
    # Mock RedisService inside Repository
    # Note: Since RedisService is a singleton, we need to be careful.
    # We can patch the 'redis' attribute of the repository instance.
    
    repo = ConversationRepository()
    mock_redis_svc = AsyncMock()
    repo.redis = mock_redis_svc
    
    # Mock DB
    mock_db = MagicMock()
    repo.db = mock_db
    
    phone = "51999999999"
    
    # Scenario A: Cache HIT
    print("   A. Scenario: Cache HIT")
    mock_redis_svc.get.return_value = json.dumps([{"role": "user", "content": "cached_msg"}])
    
    history = await repo.get_history(phone)
    
    mock_redis_svc.get.assert_called_with(f"chat_history:{phone}")
    assert len(history) == 1
    assert history[0]["content"] == "cached_msg"
    # Ensure DB was NOT called
    mock_db.table.assert_not_called()
    print("✅ Cache HIT retorna datos sin tocar DB")
    
    # Scenario B: Cache MISS -> DB Read -> Cache Write
    print("   B. Scenario: Cache MISS")
    mock_redis_svc.get.return_value = None  # Cache empty
    
    # Mock DB Response
    mock_execute = MagicMock()
    # Repository reverses the list, so we provide it in normal order (newest first usually in DB checks, but repo does .order(desc))
    # Repo logic: 
    #   result = db...order(desc).limit(N)
    #   messages = list(reversed(result.data))
    # So if DB returns [Newest, Older], Repo returns [Older, Newest]
    mock_execute.data = [{"role": "user", "content": "db_msg", "created_at": "2023-01-01"}]
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_execute
    
    mock_db.reset_mock()
    history = await repo.get_history(phone)
    
    # DB called?
    mock_db.table.assert_called()
    # Cache Set called?
    mock_redis_svc.set.assert_called()
    args = mock_redis_svc.set.call_args
    # args[0] is (key, value), kwargs has 'expire'
    print("✅ Cache MISS consulta DB y escribe en Cache")
    
    # Scenario C: Save Message -> Cache Invalidate
    print("   C. Scenario: Save Message")
    
    mock_db.reset_mock()
    mock_redis_svc.delete.reset_mock()
    
    await repo.save_message(phone, "human", "new_msg")
    
    mock_db.table.assert_called() # Insert
    mock_redis_svc.delete.assert_called_with(f"chat_history:{phone}")
    print("✅ Save Message invalida caché (delete)")

if __name__ == "__main__":
    asyncio.run(verify_redis_logic_mock())
