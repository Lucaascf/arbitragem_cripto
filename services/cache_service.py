# services/cache_service.py
import threading
import time
from datetime import datetime
from services.comparison_service import ComparisonService
from config import UPDATE_INTERVAL

class CacheService:
    def __init__(self):
        self.cache_data = None
        self.last_update = None
        self.cache_lock = threading.Lock()
        self.update_interval = UPDATE_INTERVAL
        self.comparison = ComparisonService()
        
    def start_background_updates(self):
        """Inicia a thread de atualização periódica"""
        try:
            print("[CacheService] Iniciando thread de atualização de cache...")
            if hasattr(self, '_update_thread') and self._update_thread.is_alive():
                print("[CacheService] Thread já está em execução")
                return
                
            self._update_thread = threading.Thread(
                target=self._update_loop, 
                daemon=True,
                name="CacheUpdater"
            )
            self._update_thread.start()
            print(f"[CacheService] Thread iniciada. ID: {self._update_thread.ident}")
        except Exception as e:
            print(f"[CacheService] Erro ao iniciar thread: {str(e)}")
            
    def _update_loop(self):
        """Loop principal de atualização"""
        while True:
            try:
                self.update_cache()
                time.sleep(self.update_interval)
            except Exception as e:
                time.sleep(self.update_interval)
            
    def update_cache(self):
        """Atualiza os dados em cache"""
        try:
            new_data = self.comparison.compare_prices()
            with self.cache_lock:
                self.cache_data = new_data
                self.last_update = datetime.now()
        except Exception as e:
            pass

    def get_cache(self):
        """Retorna os dados em cache com informações de cruzamentos"""
        with self.cache_lock:
            crossings_info = self.comparison.get_crossings_counts()
            
            return {
                'data': self.cache_data,
                'last_update': self.last_update,
                'crossings_24h': crossings_info['total_24h'],
                'crossings_30min': crossings_info['total_30min']
            }