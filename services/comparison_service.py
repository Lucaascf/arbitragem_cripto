from datetime import datetime
import threading
from config import (
    MOEDAS_PERMITIDAS,
    CROSSING_THRESHOLD,
    CROSSING_WINDOW_30MIN
)
from services.api_services import (
    fetch_gateio_tickers,
    fetch_gateio_futures_tickers,
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
        try:
            # Busca dados de todas as APIs
            gateio_spot = fetch_gateio_tickers()
            gateio_futures = fetch_gateio_futures_tickers()
            htx = fetch_htx_tickers()
            mexc_spot = fetch_mexc_spot_tickers()
            mexc_futures = fetch_mexc_futures_tickers()
            
            if not all([gateio_spot, htx, mexc_spot]):
                raise Exception("Falha ao obter dados de uma ou mais APIs spot")
            
            # Combina dados de futuros de ambas as exchanges
            all_futures_symbols = set()
            if gateio_futures:
                all_futures_symbols.update(gateio_futures.keys())
            if mexc_futures:
                all_futures_symbols.update(mexc_futures.keys())
            
            simbolos_com_futuros = all_futures_symbols.intersection(MOEDAS_PERMITIDAS)
            resultados = []
            now = datetime.now()
            
            with self.crossings_lock:
                # Limpa cruzamentos antigos
                self._clean_old_crossings(now)
                
                for simbolo in sorted(simbolos_com_futuros):
                    try:
                        result = self._process_symbol(
                            simbolo, gateio_spot, gateio_futures, htx, mexc_spot, mexc_futures, now
                        )
                        if result:
                            resultados.append(result)
                    except Exception as e:
                        continue
            
            resultados.sort(key=lambda x: abs(x['diferenca']), reverse=True)
            return resultados
            
        except Exception as e:
            print(f"Erro no compare_prices: {str(e)}")
            return []
    
    def _process_symbol(self, symbol, gateio_spot, gateio_futures, htx, mexc_spot, mexc_futures, now):
        """Processa um símbolo individual e retorna os dados comparativos"""
        # Preços e volumes spot
        precos_spot = {
            'GATEIO': gateio_spot.get(symbol, {}).get('last'),
            'HTX': htx.get(symbol, {}).get('last'),
            'MEXC': mexc_spot.get(symbol, {}).get('last')
        }
        
        volumes_spot = {
            'GATEIO': gateio_spot.get(symbol, {}).get('volume', 0),
            'HTX': htx.get(symbol, {}).get('volume', 0),
            'MEXC': mexc_spot.get(symbol, {}).get('volume', 0)
        }
        
        # Filtra preços spot válidos (maiores que 0 e não nulos)
        precos_validos = {k: v for k, v in precos_spot.items() if v is not None and v > 0}
        
        if not precos_validos:
            return None
            
        # Encontra o menor preço spot
        corretora_menor = min(precos_validos, key=precos_validos.get)
        menor_preco = precos_validos[corretora_menor]
        volume_spot = volumes_spot[corretora_menor]
        
        # Compara preços de futuros entre Gate.io e MEXC
        precos_futuros = {}
        volumes_futuros = {}
        
        # Adiciona dados do Gate.io Futuros se disponível
        if gateio_futures and symbol in gateio_futures:
            gateio_fut_data = gateio_futures[symbol]
            if gateio_fut_data.get('last') and gateio_fut_data['last'] > 0:
                precos_futuros['GATEIO'] = gateio_fut_data['last']
                volumes_futuros['GATEIO'] = gateio_fut_data.get('volume', 0)
        
        # Adiciona dados do MEXC Futuros se disponível
        if mexc_futures and symbol in mexc_futures:
            mexc_fut_data = mexc_futures[symbol]
            if mexc_fut_data.get('last') and mexc_fut_data['last'] > 0:
                precos_futuros['MEXC'] = mexc_fut_data['last']
                volumes_futuros['MEXC'] = mexc_fut_data.get('volume', 0)
        
        # Precisa ter pelo menos um preço de futuros válido
        if not precos_futuros:
            return None
        
        # Encontra o MAIOR preço de futuros (melhor para short)
        corretora_futuros = max(precos_futuros, key=precos_futuros.get)
        preco_futuros = precos_futuros[corretora_futuros]
        volume_futuros = volumes_futuros[corretora_futuros]
        
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
            'corretora_futuros': corretora_futuros,  # Nova informação
            'volume_spot': volume_spot,
            'volume_futuros': volume_futuros,
            'diferenca': diferenca,
            'crossings_24h': self.crossings_24h.get(symbol, {'count': 0})['count'],
            'crossings_30min': self.crossings_30min.get(symbol, {'count': 0})['count']
        }
    
    def _check_crossings(self, symbol, difference, now):
        """Registra cruzamentos mantendo históricos temporais precisos."""
        try:
            is_currently_in_zone = abs(difference) <= CROSSING_THRESHOLD
            previous_state = self.previous_crossed_state.get(symbol, False)
            
            # Detecta transição de fora→dentro da zona
            is_new_crossing = False
            if not previous_state and is_currently_in_zone:
                is_new_crossing = True
            
            self.previous_crossed_state[symbol] = is_currently_in_zone
            
            if not is_new_crossing:
                return
            
            # Inicializa estruturas se for o primeiro cruzamento
            if symbol not in self.crossings_24h:
                self.crossings_24h[symbol] = {'timestamps': [], 'count': 0}
            if symbol not in self.crossings_30min:
                self.crossings_30min[symbol] = {'timestamps': [], 'count': 0}
            
            # Adiciona cruzamento e já filtra expirados
            self._add_crossing(symbol, now, '24h', 86400)
            self._add_crossing(symbol, now, '30min', CROSSING_WINDOW_30MIN)
            
        except Exception as e:
            pass

    def _add_crossing(self, symbol, timestamp, window, window_seconds):
        """Método auxiliar para adicionar cruzamento com limpeza automática"""
        try:
            if window == '24h':
                data = self.crossings_24h[symbol]
            else:
                data = self.crossings_30min[symbol]
            
            # Adiciona novo timestamp
            data['timestamps'].append(timestamp)
            
            # Filtra apenas os dentro da janela temporal
            valid_ts = [ts for ts in data['timestamps'] 
                    if (timestamp - ts).total_seconds() <= window_seconds]
            
            # Atualiza estrutura
            data['timestamps'] = valid_ts
            data['count'] = len(valid_ts)
            
        except Exception as e:
            pass

    def _clean_old_crossings(self, now):
        """Limpeza adicional para remover símbolos sem cruzamentos recentes"""
        try:
            # Otimização: usa dict comprehension para criar novos dicionários
            self.crossings_30min = {
                k: v for k, v in self.crossings_30min.items()
                if v.get('count', 0) > 0 and v.get('timestamps') and 
                (now - v['timestamps'][-1]).total_seconds() <= CROSSING_WINDOW_30MIN
            }
            
            self.crossings_24h = {
                k: v for k, v in self.crossings_24h.items()
                if v.get('count', 0) > 0 and v.get('timestamps') and 
                (now - v['timestamps'][-1]).total_seconds() <= 86400
            }
            
        except Exception as e:
            pass
    
    def get_crossings_counts(self):
        """Retorna contagens totais de cruzamentos"""
        try:
            with self.crossings_lock:
                total_24h = sum(c.get('count', 0) for c in self.crossings_24h.values())
                total_30min = sum(c.get('count', 0) for c in self.crossings_30min.values())
                
                return {
                    'total_24h': total_24h,
                    'total_30min': total_30min
                }
        except Exception as e:
            return {'total_24h': 0, 'total_30min': 0}