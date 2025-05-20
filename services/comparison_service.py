from datetime import datetime
import threading
from config import (
    MOEDAS_PERMITIDAS,
    CROSSING_THRESHOLD,
    CROSSING_WINDOW_30MIN
)
from services.api_services import (
    fetch_gateio_tickers,
    fetch_htx_tickers,
    fetch_mexc_spot_tickers,
    fetch_mexc_futures_tickers
)

class ComparisonService:
    def __init__(self):
        self.crossings_24h = {}
        self.crossings_30min = {}
        self.crossings_lock = threading.Lock()
        self.previous_crossed_state = {}
    
    def compare_prices(self):
        """Compara preços spot e futuros, identificando oportunidades"""
        # Busca dados de todas as APIs
        gateio = fetch_gateio_tickers()
        htx = fetch_htx_tickers()
        mexc_spot = fetch_mexc_spot_tickers()
        mexc_futures = fetch_mexc_futures_tickers()
        
        if not all([gateio, htx, mexc_spot, mexc_futures]):
            raise Exception("Falha ao obter dados de uma ou mais APIs")
        
        simbolos_com_futuros = set(mexc_futures.keys()).intersection(MOEDAS_PERMITIDAS)
        resultados = []
        now = datetime.now()
        
        with self.crossings_lock:
            # Limpa cruzamentos antigos
            self._clean_old_crossings(now)
            
            for simbolo in sorted(simbolos_com_futuros):
                try:
                    result = self._process_symbol(
                        simbolo, gateio, htx, mexc_spot, mexc_futures, now
                    )
                    if result:
                        resultados.append(result)
                except Exception as e:
                    print(f"Erro processando {simbolo}: {str(e)}")
                    continue
        
        resultados.sort(key=lambda x: abs(x['diferenca']), reverse=True)
        return resultados
    
    def _process_symbol(self, symbol, gateio, htx, mexc_spot, mexc_futures, now):
        """Processa um símbolo individual e retorna os dados comparativos"""
        precos_spot = {
            'GATEIO': gateio.get(symbol, {}).get('last'),
            'HTX': htx.get(symbol, {}).get('last'),
            'MEXC': mexc_spot.get(symbol, {}).get('last')
        }
        
        volumes_spot = {
            'GATEIO': gateio.get(symbol, {}).get('volume', 0),
            'HTX': htx.get(symbol, {}).get('volume', 0),
            'MEXC': mexc_spot.get(symbol, {}).get('volume', 0)
        }
        
        # Filtra preços válidos (maiores que 0 e não nulos)
        precos_validos = {k: v for k, v in precos_spot.items() if v is not None and v > 0}
        
        if not precos_validos:
            return None
            
        # Encontra o menor preço spot
        corretora_menor = min(precos_validos, key=precos_validos.get)
        menor_preco = precos_validos[corretora_menor]
        volume_spot = volumes_spot[corretora_menor]
        
        # Obtém dados de futuros
        futuros_data = mexc_futures.get(symbol, {})
        preco_futuros = futuros_data.get('last')
        volume_futuros = futuros_data.get('volume', 0)
        
        if preco_futuros is None or preco_futuros <= 0:
            return None
            
        try:
            # Calcula diferença percentual
            diferenca = ((preco_futuros - menor_preco) / menor_preco) * 100
        except ZeroDivisionError:
            return None
        
        # Verifica se houve cruzamento
        self._check_crossings(symbol, diferenca, now)
        
        return {
            'simbolo': symbol,
            'preco_spot': menor_preco,
            'preco_futuros': preco_futuros,
            'corretora_spot': corretora_menor,
            'volume_spot': volume_spot,
            'volume_futuros': volume_futuros,
            'diferenca': diferenca,
            'crossings_24h': self.crossings_24h.get(symbol, {'count': 0})['count'],
            'crossings_30min': self.crossings_30min.get(symbol, {'count': 0})['count']
        }
    
    def _check_crossings(self, symbol, difference, now):
        """
        Registra quando o preço spot e de futuros convergem para o mesmo valor.
        Um cruzamento é definido como quando a diferença percentual absoluta é menor que o threshold.
        """
        # Determina se os preços estão cruzados (próximos o suficiente)
        is_currently_crossed = abs(difference) < CROSSING_THRESHOLD
        
        # Verifica se este é um novo cruzamento
        is_new_crossing = False
        
        if symbol in self.previous_crossed_state:
            # Se antes não estava cruzado e agora está, temos um novo cruzamento
            if not self.previous_crossed_state[symbol] and is_currently_crossed:
                is_new_crossing = True
        elif is_currently_crossed:
            # Se é a primeira vez que verificamos este símbolo e já está cruzado
            is_new_crossing = True
        
        # Atualiza o estado para a próxima verificação
        self.previous_crossed_state[symbol] = is_currently_crossed
        
        # Se for um novo cruzamento, incrementa os contadores
        if is_new_crossing:
            # Atualiza contagem de 24h
            if symbol not in self.crossings_24h:
                self.crossings_24h[symbol] = {'count': 0, 'last_cross': now}
            
            self.crossings_24h[symbol]['count'] += 1
            self.crossings_24h[symbol]['last_cross'] = now
            
            # Atualiza contagem de 30min
            if symbol not in self.crossings_30min:
                self.crossings_30min[symbol] = {'count': 0, 'last_cross': now}
            
            self.crossings_30min[symbol]['count'] += 1
            self.crossings_30min[symbol]['last_cross'] = now
    
    def _clean_old_crossings(self, now):
        """Limpa cruzamentos antigos das janelas de 30min e 24h"""
        # Limpa cruzamentos com mais de 30 minutos
        self.crossings_30min = {
            k: v for k, v in self.crossings_30min.items()
            if (now - v['last_cross']).total_seconds() <= CROSSING_WINDOW_30MIN
        }
        
        # Limpa cruzamentos com mais de 24 horas (86400 segundos)
        self.crossings_24h = {
            k: v for k, v in self.crossings_24h.items()
            if (now - v['last_cross']).total_seconds() <= 86400
        }
    
    def get_crossings_counts(self):
        """Retorna contagens totais de cruzamentos"""
        with self.crossings_lock:
            return {
                'total_24h': sum(c['count'] for c in self.crossings_24h.values()),
                'total_30min': sum(c['count'] for c in self.crossings_30min.values())
            }