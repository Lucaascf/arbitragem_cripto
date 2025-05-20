import requests
from config import MOEDAS_PERMITIDAS

def fetch_gateio_tickers():
    """Busca tickers spot da Gate.io"""
    url = "https://api.gateio.ws/api/v4/spot/tickers"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        dados = response.json()
        return {
            par['currency_pair'].replace('_', '').upper(): {
                'last': float(par['last']),
                'volume': float(par['quote_volume'])
            } 
            for par in dados 
            if par['currency_pair'].replace('_', '').upper() in MOEDAS_PERMITIDAS
        }
    except Exception as e:
        print(f"Erro na API GateIO: {str(e)}")
        return {}

def fetch_htx_tickers():
    """Busca tickers spot da HTX"""
    url = "https://api.huobi.pro/market/tickers"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {
            par['symbol'].upper(): {
                'last': float(par['close']),
                'volume': float(par['amount']) * float(par['close'])
            } 
            for par in dados['data'] 
            if par['symbol'].upper() in MOEDAS_PERMITIDAS
        }
    except Exception as e:
        print(f"Erro na API HTX: {str(e)}")
        return {}

def fetch_mexc_spot_tickers():
    """Busca tickers spot da MEXC"""
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {
            par['symbol'].upper(): {
                'last': float(par['lastPrice']),
                'volume': float(par['quoteVolume'])
            } 
            for par in dados 
            if par['symbol'].upper() in MOEDAS_PERMITIDAS
        }
    except Exception as e:
        print(f"Erro na API MEXC Spot: {str(e)}")
        return {}

def fetch_mexc_futures_tickers():
    """Busca tickers de futuros da MEXC"""
    url = "https://contract.mexc.com/api/v1/contract/ticker"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {
            item['symbol'].replace('-', '').replace('_', '').upper(): {
                'last': float(item['lastPrice']),
                'volume': float(item['volume24'])
            } 
            for item in dados['data'] 
            if item['symbol'].replace('-', '').replace('_', '').upper() in MOEDAS_PERMITIDAS
        }
    except Exception as e:
        print(f"Erro na API MEXC Futuros: {str(e)}")
        return {}