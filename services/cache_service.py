# services/cache_service.py
import threading
import time
from datetime import datetime
from services.comparison_service import ComparisonService
from config import UPDATE_INTERVAL  # Importa a variável de configuração

class CacheService:
    def __init__(self):
        self.cache_data = None
        self.last_update = None
        self.cache_lock = threading.Lock()
        self.update_interval = UPDATE_INTERVAL  # Usa a variável de configuração
        self.comparison = ComparisonService()
        
    def start_background_updates(self):
        """Inicia a thread de atualização periódica"""
        update_thread = threading.Thread(target=self._update_loop)
        update_thread.daemon = True
        update_thread.start()
        
    def _update_loop(self):
        while True:
            self.update_cache()
            time.sleep(self.update_interval)
            
    def update_cache(self):
        """Atualiza os dados em cache"""
        try:
            new_data = self.comparison.compare_prices()  # Usa o método da instância
            with self.cache_lock:
                self.cache_data = new_data
                self.last_update = datetime.now()
                print(f"Cache atualizado em {self.last_update}")
        except Exception as e:
            print(f"Erro ao atualizar cache: {str(e)}")

    def get_cache(self):
        """Retorna os dados em cache com segurança thread-safe"""
        with self.cache_lock:
            return {
                'data': self.cache_data,
                'last_update': self.last_update
            }