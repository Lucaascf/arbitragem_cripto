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
        # Preços e volumes para COMPRA (spot + futuros)
        precos_compra = {}
        volumes_compra = {}
        
        # Adiciona preços SPOT
        if gateio_spot.get(symbol):
            data = gateio_spot[symbol]
            if data.get('last') and data['last'] > 0:
                precos_compra['GATEIO'] = data['last']
                volumes_compra['GATEIO'] = data.get('volume', 0)
        
        if htx.get(symbol):
            data = htx[symbol]
            if data.get('last') and data['last'] > 0:
                precos_compra['HTX'] = data['last']
                volumes_compra['HTX'] = data.get('volume', 0)
        
        if mexc_spot.get(symbol):
            data = mexc_spot[symbol]
            if data.get('last') and data['last'] > 0:
                precos_compra['MEXC'] = data['last']
                volumes_compra['MEXC'] = data.get('volume', 0)
        
        # Adiciona preços FUTUROS para compra também
        if gateio_futures and symbol in gateio_futures:
            data = gateio_futures[symbol]
            if data.get('last') and data['last'] > 0:
                precos_compra['GATEIO_FUTURES'] = data['last']
                volumes_compra['GATEIO_FUTURES'] = data.get('volume', 0)
        
        if mexc_futures and symbol in mexc_futures:
            data = mexc_futures[symbol]
            if data.get('last') and data['last'] > 0:
                precos_compra['MEXC_FUTURES'] = data['last']
                volumes_compra['MEXC_FUTURES'] = data.get('volume', 0)
        
        # Preços de futuros para SHORT (apenas futuros)
        precos_futuros = {}
        volumes_futuros = {}
        
        if gateio_futures and symbol in gateio_futures:
            data = gateio_futures[symbol]
            if data.get('last') and data['last'] > 0:
                precos_futuros['GATEIO'] = data['last']
                volumes_futuros['GATEIO'] = data.get('volume', 0)
        
        if mexc_futures and symbol in mexc_futures:
            data = mexc_futures[symbol]
            if data.get('last') and data['last'] > 0:
                precos_futuros['MEXC'] = data['last']
                volumes_futuros['MEXC'] = data.get('volume', 0)
        
        # Validações
        if not precos_compra or not precos_futuros:
            return None
        
        # Encontra o MENOR preço para compra (pode ser spot ou futuros)
        corretora_compra = min(precos_compra, key=precos_compra.get)
        preco_compra = precos_compra[corretora_compra]
        volume_compra = volumes_compra[corretora_compra]
        
        # Encontra o MAIOR preço de futuros para short
        corretora_short = max(precos_futuros, key=precos_futuros.get)
        preco_short = precos_futuros[corretora_short]
        volume_short = volumes_futuros[corretora_short]
        
        try:
            # Calcula diferença percentual
            diferenca = ((preco_short - preco_compra) / preco_compra) * 100
        except ZeroDivisionError:
            return None
        
        # Verifica se houve cruzamento
        self._check_crossings(symbol, diferenca, now)
        
        return {
            'simbolo': symbol,
            'preco_spot': preco_compra,
            'preco_futuros': preco_short,
            'corretora_spot': corretora_compra.replace('_FUTURES', ''),
            'corretora_futuros': corretora_short,
            'tipo_compra': 'FUTUROS' if '_FUTURES' in corretora_compra else 'SPOT',
            'volume_spot': volume_compra,
            'volume_futuros': volume_short,
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