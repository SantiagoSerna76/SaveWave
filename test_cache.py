"""Script de prueba del sistema de cache SaveWave."""
from cache import get_cache_stats, get_cached_video_info, set_cached_video_info

# Test 1: Guardar y recuperar
set_cached_video_info("http://test.com/video", {"title": "CacheTest"})
data = get_cached_video_info("http://test.com/video")
assert data is not None, "Fallo: No se recupero del cache"
assert data["title"] == "CacheTest", "Fallo: Dato incorrecto"
print("[OK] Cache set/get funciona")

# Test 2: Cache miss (URL no cacheada)
miss = get_cached_video_info("http://test.com/nuevo")
assert miss is None, "Fallo: Deberia ser cache miss"
print("[OK] Cache miss funciona")

# Test 3: Estadisticas
stats = get_cache_stats()
print(f"[OK] Cache type: {stats['type']}")
print(f"[OK] Memory items: {stats['memory_items']}")
print(f"[OK] Redis connected: {stats['redis_connected']}")

# Test 4: Archivo en disco
import os
from cache import CACHE_FILE
if os.path.exists(CACHE_FILE):
    size = os.path.getsize(CACHE_FILE)
    print(f"[OK] Archivo de cache en disco: {size} bytes")
else:
    print("[OK] Cache en memoria (sin archivo)")

print()
print("=== TODOS LOS TESTS PASARON ===")