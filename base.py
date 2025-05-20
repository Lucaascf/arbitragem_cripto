from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import os
import sys
import traceback
import time
import threading

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# Variáveis globais para o cache
cache_data = None
last_update = None
cache_lock = threading.Lock()
crossings_30min = {} 
crossings_24h = {}    
crossings_lock = threading.Lock()

# Lista completa de moedas permitidas (com USDT)
MOEDAS_PERMITIDAS = {
    '1DOLLARUSDT', '1INCHUSDT', 'A8USDT', 'AAVEUSDT', 'ACAUSDT', 
    'ACEUSDT', 'ACHUSDT', 'ACSUSDT', 'ACTUSDT', 'ACXUSDT',
    'ADAUSDT', 'AERGOUSDT', 'AEROUSDT', 'AEVOUSDT', 'AGIUSDT',
    'AGIXTUSDT', 'AGLDUSDT', 'AGTUSDT', 'AIUSDT', 'AI16ZUSDT',
    'AICUSDT', 'AIOTUSDT', 'AIOZUSDT', 'AIXBTUSDT', 'AKTUSDT',
    'ALCHUSDT', 'ALCXUSDT', 'ALEOUSDT', 'ALGOUSDT', 'ALICEUSDT',
    'ALPACAUSDT', 'ALPHUSDT', 'ALPHAUSDT', 'ALPINEUSDT', 'ALUUSDT',
    'AMIUSDT', 'AMPUSDT', 'ANIMEUSDT', 'ANKRUSDT', 'ANONUSDT',
    'APEUSDT', 'APEXUSDT', 'API3USDT', 'APTUSDT', 'APXUSDT',
    'ARUSDT', 'ARBUSDT', 'ARCSOLUSDT', 'ARKUSDT', 'ARKMUSDT',
    'ARPAUSDT', 'ASRUSDT', 'ASTRUSDT', 'ATAUSDT', 'ATHUSDT',
    'ATOMUSDT', 'AUCTIONUSDT', 'AUDIOUSDT', 'AVAUSDT', 'AVAAIUSDT',
    'AVAILUSDT', 'AVAXUSDT', 'AVLUSDT', 'AXSUSDT', 'AZEROUSDT',
    'B2USDT', 'B3USDT', 'BABYUSDT', 'BADGERUSDT', 'BAKEUSDT',
    'BALUSDT', 'BANUSDT', 'BANANAUSDT', 'BANANAS31USDT', 'BANDUSDT',
    'BANKUSDT', 'BARUSDT', 'BATUSDT', 'BBUSDT', 'BCHUSDT',
    'BEAMXUSDT', 'BELUSDT', 'BERAUSDT', 'BERTUSDT', 'BFTOKENUSDT',
    'BGSCUSDT', 'BICOUSDT', 'BIDUSDT', 'BIGTIMEUSDT', 'BIOUSDT',
    'BLASTUSDT', 'BLURUSDT', 'BLZUSDT', 'BMTUSDT', 'BNBUSDT',
    'BNTUSDT', 'BOBAUSDT', 'BOMEUSDT', 'BOOPUSDT', 'BOTIFYUSDT',
    'BRUSDT', 'BRETTUSDT', 'BRISEUSDT', 'BRLUSDT', 'BROCCOLIUSDT',
    'BROCCOLIF2BUSDT', 'BROCCOLIF3BUSDT', 'BSVUSDT', 'BSWUSDT', 'BTCUSDT',
    'BUBBUSDT', 'BUTTHOLEUSDT', 'BUZZUSDT', 'C98USDT', 'CADUSDT',
    'CAKEUSDT', 'CAPTAINBNBUSDT', 'CARVUSDT', 'CATUSDT', 'CATIUSDT',
    'CATSUSDT', 'CBKUSDT', 'CELOUSDT', 'CELRUSDT', 'CETUSUSDT',
    'CFXUSDT', 'CGPTUSDT', 'CHEEMSUSDT', 'CHESSUSDT', 'CHILLGUYUSDT',
    'CHRUSDT', 'CHZUSDT', 'CITYUSDT', 'CKBUSDT', 'CLANKERUSDT',
    'CLOREUSDT', 'CLOUDUSDT', 'COLLATUSDT', 'COMPUSDT', 'COOKUSDT',
    'COOKIEUSDT', 'COREUSDT', 'COSUSDT', 'COTIUSDT', 'COWUSDT',
    'CPOOLUSDT', 'CROUSDT', 'CRVUSDT', 'CSPRUSDT', 'CTCUSDT',
    'CTKUSDT', 'CTSIUSDT', 'CVCUSDT', 'CVXUSDT', 'CYBERUSDT',
    'DUSDT', 'DADDYUSDT', 'DAGUSDT', 'DARKUSDT', 'DASHUSDT',
    'DATAUSDT', 'DBRUSDT', 'DCRUSDT', 'DEAIUSDT', 'DEEPUSDT',
    'DEGENUSDT', 'DEGOUSDT', 'DENTUSDT', 'DEVVEUSDT', 'DFUSDT',
    'DGBUSDT', 'DIAUSDT', 'DODOUSDT', 'DOGUSDT', 'DOGEUSDT',
    'DOGEGOVUSDT', 'DOGINMEUSDT', 'DOGSUSDT', 'DOLOUSDT', 'DONKEYUSDT',
    'DOODUSDT', 'DOTUSDT', 'DRBUSDT', 'DRIFTUSDT', 'DSYNCUSDT',
    'DUCKUSDT', 'DUPEUSDT', 'DUSKUSDT', 'DYDXUSDT', 'DYMUSDT',
    'EDGEUSDT', 'EDUUSDT', 'EGLDUSDT', 'EIGENUSDT', 'ELONUSDT',
    'ELXUSDT', 'ENAUSDT', 'ENJUSDT', 'ENSUSDT', 'EOSUSDT',
    'EPICUSDT', 'EPTUSDT', 'ETCUSDT', 'ETHUSDT', 'ETHFIUSDT',
    'ETHWUSDT', 'EURUSDT', 'FUSDT', 'FAIUSDT', 'FARMUSDT',
    'FARTBOYUSDT', 'FARTCOINUSDT', 'FBUSDT', 'FETUSDT', 'FHEUSDT',
    'FIDAUSDT', 'FIOUSDT', 'FISUSDT', 'FLMUSDT', 'FLOCKUSDT',
    'FLOKIUSDT', 'FLOWUSDT', 'FLRUSDT', 'FLUXUSDT', 'FORMUSDT',
    'FORTHUSDT', 'FOXYUSDT', 'FREDUSDT', 'FTNUSDT', 'FTTUSDT',
    'FUNUSDT', 'FWOGUSDT', 'FXSUSDT', 'GUSDT', 'G7USDT',
    'GALAUSDT', 'GEARUSDT', 'GFMUSDT', 'GHIBLIUSDT', 'GHSTUSDT',
    'GHXUSDT', 'GIGAUSDT', 'GLMUSDT', 'GLMRUSDT', 'GMTUSDT',
    'GMXUSDT', 'GNCUSDT', 'GNOUSDT', 'GOATUSDT', 'GODSUSDT',
    'GOMININGUSDT', 'GOONCUSDT', 'GORILLABSCUSDT', 'GORKUSDT', 'GPSUSDT',
    'GPUUSDT', 'GRASSUSDT', 'GRIFFAINUSDT', 'GROKUSDT', 'GRTUSDT',
    'GUNUSDT', 'HAEDALUSDT', 'HARRYUSDT', 'HASHAIUSDT', 'HBARUSDT',
    'HEIUSDT', 'HFTUSDT', 'HIFIUSDT', 'HIGHUSDT', 'HIPPOUSDT',
    'HIVEUSDT', 'HMSTRUSDT', 'HNTUSDT', 'HOLDUSDT', 'HOOKUSDT',
    'HOSICOUSDT', 'HOTUSDT', 'HOUSEUSDT', 'HYPEUSDT', 'HYPERUSDT',
    'ICEUSDT', 'ICPUSDT', 'ICXUSDT', 'IDUSDT', 'IDEXUSDT',
    'ILVUSDT', 'IMXUSDT', 'INITUSDT', 'INJUSDT', 'IOUSDT',
    'IOSTUSDT', 'IOTAUSDT', 'IOTXUSDT', 'IPUSDT', 'IQUSDT',
    'JUSDT', 'JAGERUSDT', 'JASMYUSDT', 'JELLYJELLYUSDT', 'JOEUSDT',
    'JSTUSDT', 'JTOUSDT', 'JUPUSDT', 'JUVUSDT', 'KUSDT',
    'KAIUSDT', 'KAITOUSDT', 'KASUSDT', 'KAVAUSDT', 'KDAUSDT',
    'KEKIUSUSDT', 'KERNELUSDT', 'KILOUSDT', 'KMDUSDT', 'KMNOUSDT',
    'KNCUSDT', 'KOMAUSDT', 'KSMUSDT', 'L3USDT', 'LAIUSDT',
    'LATUSDT', 'LAUNCHCOINUSDT', 'LAVAUSDT', 'LAYERUSDT', 'LAZIOUSDT',
    'LDOUSDT', 'LEVERUSDT', 'LINKUSDT', 'LISTAUSDT', 'LMWRUSDT',
    'LOKAUSDT', 'LOOKSUSDT', 'LOOMUSDT', 'LPTUSDT', 'LQTYUSDT',
    'LRCUSDT', 'LSKUSDT', 'LTCUSDT', 'LUCEUSDT', 'LUMIAUSDT',
    'LUNAIUSDT', 'LUNCUSDT', 'MAGICUSDT', 'MAJORUSDT', 'MANAUSDT',
    'MANEKIUSDT', 'MANTAUSDT', 'MASAUSDT', 'MASKUSDT', 'MAVUSDT',
    'MAVIAUSDT', 'MBLUSDT', 'MBOXUSDT', 'MDOGSUSDT', 'MDTUSDT',
    'MEUSDT', 'MELANIAUSDT', 'MEMEUSDT', 'MEMEFIUSDT', 'MERLUSDT',
    'METISUSDT', 'MEWUSDT', 'MICHIUSDT', 'MIGGLESUSDT', 'MILKUSDT',
    'MINAUSDT', 'MIRAIUSDT', 'MKRUSDT', 'MLNUSDT', 'MNTUSDT',
    'MOBILEUSDT', 'MOCAUSDT', 'MOODENGUSDT', 'MOONPIGUSDT', 'MORPHOUSDT',
    'MOVEUSDT', 'MOVRUSDT', 'MTLUSDT', 'MUBARAKUSDT', 'MUBARAKAHUSDT',
    'MUBIUSDT', 'MVLUSDT', 'MYRIAUSDT', 'MYROUSDT', 'MYXUSDT',
    'NAKAUSDT', 'NAVXUSDT', 'NCUSDT', 'NEARUSDT', 'NEIROCTOUSDT',
    'NEIROETHUSDT', 'NEOUSDT', 'NEXOUSDT', 'NFPUSDT', 'NFTUSDT',
    'NILUSDT', 'NKNUSDT', 'NMRUSDT', 'NOBODYUSDT', 'NOSUSDT',
    'NOTUSDT', 'NPCUSDT', 'NSUSDT', 'NTRNUSDT', 'NXPCUSDT',
    'OBOLUSDT', 'OBTUSDT', 'OGUSDT', 'OGNUSDT', 'OIKUSDT',
    'OLUSDT', 'OMUSDT', 'OMGUSDT', 'OMIUSDT', 'OMNIUSDT',
    'ONDOUSDT', 'ONEUSDT', 'ONGUSDT', 'ONTUSDT', 'OPUSDT',
    'ORAIUSDT', 'ORBSUSDT', 'ORCAUSDT', 'ORDERUSDT', 'ORDIUSDT',
    'OSMOUSDT', 'OXTUSDT', 'OZKUSDT', 'PAALUSDT', 'PAINUSDT',
    'PARTIUSDT', 'PAWSUSDT', 'PAXGUSDT', 'PEAQUSDT', 'PENDLEUSDT',
    'PENGUUSDT', 'PEOPLEUSDT', 'PEPEUSDT', 'PEPUUSDT', 'PERPUSDT',
    'PHAUSDT', 'PHBUSDT', 'PIUSDT', 'PINUSDT', 'PIPPINUSDT',
    'PIVXUSDT', 'PIXELUSDT', 'PLUMEUSDT', 'PNUTUSDT', 'POLUSDT',
    'POLSUSDT', 'POLYXUSDT', 'PONDUSDT', 'PONKEUSDT', 'POPCATUSDT',
    'POPEUSDT', 'PORT3USDT', 'PORTALUSDT', 'PORTOUSDT', 'POWRUSDT',
    'PRAIUSDT', 'PRCLUSDT', 'PRIMEUSDT', 'PROMUSDT', 'PROMPTUSDT',
    'PSGUSDT', 'PUFFERUSDT', 'PUMPUSDT', 'PUMPAIUSDT', 'PUNDIXUSDT',
    'PWEASEUSDT', 'PYRUSDT', 'PYTHUSDT', 'QNTUSDT', 'QTUMUSDT',
    'QUBICUSDT', 'QUICKUSDT', 'RACAUSDT', 'RADUSDT', 'RAREUSDT',
    'RATOUSDT', 'RAYUSDT', 'RBNTUSDT', 'RDACUSDT', 'RDNTUSDT',
    'REDUSDT', 'REIUSDT', 'RENDERUSDT', 'REQUSDT', 'REXUSDT',
    'REZUSDT', 'RFCUSDT', 'RIFUSDT', 'RIZUSDT', 'RLCUSDT',
    'ROAMUSDT', 'RONUSDT', 'ROSEUSDT', 'RPLUSDT', 'RSRUSDT',
    'RSS3USDT', 'RUNEUSDT', 'RVNUSDT', 'SUSDT', 'SAFEUSDT',
    'SAGAUSDT', 'SANDUSDT', 'SANTOSUSDT', 'SAROSUSDT', 'SATSUSDT',
    'SCUSDT', 'SCAUSDT', 'SCRUSDT', 'SCRTUSDT', 'SDUSDT',
    'SEEDUSDT', 'SEIUSDT', 'SENDUSDT', 'SERAPHUSDT', 'SFPUSDT',
    'SHELLUSDT', 'SHIBUSDT', 'SHMUSDT', 'SHXUSDT', 'SIGNUSDT',
    'SIRENUSDT', 'SKLUSDT', 'SKYAIUSDT', 'SLERFUSDT', 'SLFUSDT',
    'SLINGUSDT', 'SLPUSDT', 'SNEKUSDT', 'SNTUSDT', 'SNXUSDT',
    'SOLUSDT', 'SOLOUSDT', 'SOLVUSDT', 'SONICUSDT', 'SPAUSDT',
    'SPECUSDT', 'SPELLUSDT', 'SPXUSDT', 'SQDUSDT', 'SSVUSDT',
    'STARTUPUSDT', 'STEEMUSDT', 'STGUSDT', 'STNKUSDT', 'STOUSDT',
    'STONKSUSDT', 'STORJUSDT', 'STRAXUSDT', 'STRKUSDT', 'STXUSDT',
    'SUIUSDT', 'SUNUSDT', 'SUNDOGUSDT', 'SUPERUSDT', 'SUPRAUSDT',
    'SUSHIUSDT', 'SWANUSDT', 'SWARMSUSDT', 'SWEATUSDT', 'SWELLUSDT',
    'SWFTCUSDT', 'SXPUSDT', 'SXTUSDT', 'SYNUSDT', 'SYRUPUSDT',
    'SYSUSDT', 'SZNUSDT', 'TUSDT', 'TAIUSDT', 'TAIKOUSDT',
    'TAOUSDT', 'TELUSDT', 'TFUELUSDT', 'THEUSDT', 'THETAUSDT',
    'TIAUSDT', 'TIBBIRUSDT', 'TITCOINUSDT', 'TLMUSDT', 'TLOSUSDT',
    'TNSRUSDT', 'TOKENUSDT', 'TOMIUSDT', 'TORNUSDT', 'TOSHIUSDT',
    'TRBUSDT', 'TREATUSDT', 'TROLLSOLUSDT', 'TRUUSDT', 'TRUMPUSDT',
    'TRXUSDT', 'TURBOUSDT', 'TUTUSDT', 'TWTUSDT', 'UFDUSDT',
    'ULTIUSDT', 'ULTIMAUSDT', 'UMAUSDT', 'UNIUSDT', 'USAUSDT',
    'USDCUSDT', 'USELESSUSDT', 'USTCUSDT', 'USUALUSDT', 'UXLINKUSDT',
    'VANAUSDT', 'VANRYUSDT', 'VELOUSDT', 'VELODROMEUSDT', 'VETUSDT',
    'VICUSDT', 'VIDTUSDT', 'VINEUSDT', 'VIRTUALUSDT', 'VISTAUSDT',
    'VOXELUSDT', 'VRUSDT', 'VRAUSDT', 'VTHOUSDT', 'VVAIFUUSDT',
    'VVVUSDT', 'WUSDT', 'WALUSDT', 'WANUSDT', 'WAVESUSDT',
    'WAXPUSDT', 'WCTUSDT', 'WHITEUSDT', 'WIFUSDT', 'WILDUSDT',
    'WINUSDT', 'WIZZUSDT', 'WLDUSDT', 'WMTXUSDT', 'WOOUSDT',
    'XUSDT', 'XAIUSDT', 'XAUTUSDT', 'XCHUSDT', 'XCNUSDT',
    'XDCUSDT', 'XECUSDT', 'XEMUSDT', 'XIONUSDT', 'XLMUSDT',
    'XMRUSDT', 'XPRUSDT', 'XRDUSDT', 'XRPUSDT', 'XTZUSDT',
    'XVGUSDT', 'XVSUSDT', 'YFIUSDT', 'YGGUSDT', 'YZYSOLUSDT',
    'ZBCNUSDT', 'ZECUSDT', 'ZENUSDT', 'ZENTUSDT', 'ZEREBROUSDT',
    'ZEROUSDT', 'ZETAUSDT', 'ZEUSUSDT', 'ZIGUSDT', 'ZILUSDT',
    'ZKJUSDT', 'ZORAUSDT', 'ZRCUSDT', 'ZROUSDT', 'ZRXUSDT'
}


def fetch_all_data():
    """Função para buscar dados de todas as APIs"""
    global crossings_24h, crossings_30min
    
    # Inicializa as variáveis se não existirem
    if 'crossings_24h' not in globals():
        crossings_24h = {}
    if 'crossings_30min' not in globals():
        crossings_30min = {}

    print("Atualizando cache de dados...")
    gateio = moedas_gateio()
    htx = moedas_htx()
    mexc_spot = moedas_mexc_spot()
    mexc_futuros = moedas_mexc_futuros()
    
    if not all([gateio, htx, mexc_spot, mexc_futuros]):
        raise Exception("Falha ao obter dados de uma ou mais APIs")
    
    simbolos_com_futuros = set(mexc_futuros.keys()).intersection(MOEDAS_PERMITIDAS)
    resultados = []
    now = datetime.now()
    
    with crossings_lock:
        # Limpa cruzamentos antigos
        crossings_30min = {k: v for k, v in crossings_30min.items() 
                          if (now - v['last_cross']).total_seconds() <= 1800}  # 30 minutos
        
        for simbolo in sorted(simbolos_com_futuros):
            precos_spot = {
                'GATEIO': gateio.get(simbolo, {}).get('last'),
                'HTX': htx.get(simbolo, {}).get('last'),
                'MEXC': mexc_spot.get(simbolo, {}).get('last')
            }
            
            volumes_spot = {
                'GATEIO': gateio.get(simbolo, {}).get('volume', 0),
                'HTX': htx.get(simbolo, {}).get('volume', 0),
                'MEXC': mexc_spot.get(simbolo, {}).get('volume', 0)
            }
            
            precos_validos = {k: v for k, v in precos_spot.items() if v is not None and v > 0}
            
            if not precos_validos:
                continue
                
            corretora_menor = min(precos_validos, key=precos_validos.get)
            menor_preco = precos_validos[corretora_menor]
            volume_spot = volumes_spot[corretora_menor]
            
            futuros_data = mexc_futuros.get(simbolo, {})
            preco_futuros = futuros_data.get('last')
            volume_futuros = futuros_data.get('volume', 0)
            
            if preco_futuros is None or preco_futuros <= 0:
                continue
                
            try:
                diferenca = ((preco_futuros - menor_preco) / menor_preco) * 100
            except ZeroDivisionError:
                continue
            
            # Verifica se houve cruzamento
            if abs(diferenca) < 0.1:  # Considera cruzamento quando diferença é menor que 0.1%
                if simbolo not in crossings_24h:
                    crossings_24h[simbolo] = {'count': 0, 'last_cross': now}
                
                crossings_24h[simbolo]['count'] += 1
                crossings_24h[simbolo]['last_cross'] = now
                
                if simbolo not in crossings_30min:
                    crossings_30min[simbolo] = {'count': 0, 'last_cross': now}
                
                crossings_30min[simbolo]['count'] += 1
                crossings_30min[simbolo]['last_cross'] = now
            
            resultados.append({
                'simbolo': simbolo,
                'preco_spot': menor_preco,
                'preco_futuros': preco_futuros,
                'corretora_spot': corretora_menor,
                'volume_spot': volume_spot,
                'volume_futuros': volume_futuros,
                'diferenca': diferenca,
                'crossings_24h': crossings_24h.get(simbolo, {'count': 0})['count'],
                'crossings_30min': crossings_30min.get(simbolo, {'count': 0})['count']
            })
    
    resultados.sort(key=lambda x: abs(x['diferenca']), reverse=True)
    return resultados

def update_cache():
    """Função para atualizar o cache periodicamente"""
    global cache_data, last_update
    
    while True:
        try:
            new_data = fetch_all_data()
            with cache_lock:
                cache_data = new_data
                last_update = datetime.now()
                print(f"Cache atualizado em {last_update}")
        except Exception as e:
            print(f"Erro ao atualizar cache: {str(e)}")
            traceback.print_exc()
        
        # Espera 30 segundos antes da próxima atualização
        time.sleep(10)

def moedas_gateio():
    url = "https://api.gateio.ws/api/v4/spot/tickers"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        dados = response.json()
        return {par['currency_pair'].replace('_', '').upper(): {
            'last': float(par['last']),
            'volume': float(par['quote_volume'])  # Volume em USDT
        } for par in dados}
    except Exception as e:
        print(f"Erro na API GateIO: {str(e)}")
        return {}

def moedas_htx():
    url = "https://api.huobi.pro/market/tickers"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {par['symbol'].upper(): {
            'last': float(par['close']),
            'volume': float(par['amount']) * float(par['close'])  # Calcula volume em USDT
        } for par in dados['data']}
    except Exception as e:
        print(f"Erro na API HTX: {str(e)}")
        return {}

def moedas_mexc_spot():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {par['symbol'].upper(): {
            'last': float(par['lastPrice']),
            'volume': float(par['quoteVolume'])  # Volume em USDT
        } for par in dados}
    except Exception as e:
        print(f"Erro na API MEXC Spot: {str(e)}")
        return {}

def moedas_mexc_futuros():
    url = "https://contract.mexc.com/api/v1/contract/ticker"
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        return {item['symbol'].replace('-', '').replace('_', '').upper(): {
            'last': float(item['lastPrice']),
            'volume': float(item['volume24'])  # Volume em USDT
        } for item in dados['data']}
    except Exception as e:
        print(f"Erro na API MEXC Futuros: {str(e)}")
        return {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/comparacao')
def api_comparacao():
    global cache_data, last_update, crossings_24h, crossings_30min
    
    try:
        with cache_lock:
            if cache_data is None:
                # Garante que as variáveis de cruzamento existam
                if 'crossings_24h' not in globals():
                    crossings_24h = {}
                if 'crossings_30min' not in globals():
                    crossings_30min = {}
                
                cache_data = fetch_all_data()
                last_update = datetime.now()
                print("Cache inicial criado")
            
            current_cache = cache_data.copy()
            last_update_time = last_update
            
        return jsonify({
            'data': current_cache,
            'last_update': last_update_time.isoformat(),
            'total_crossings_24h': sum(c['count'] for c in crossings_24h.values()),
            'total_crossings_30min': sum(c['count'] for c in crossings_30min.values())
        })
    
    except Exception as e:
        print(f"Erro completo: {traceback.format_exc()}", file=sys.stderr)
        return jsonify({'error': f"Erro ao processar dados: {str(e)}"}), 500
    
if __name__ == '__main__':
    # Inicia a thread de atualização do cache em segundo plano
    update_thread = threading.Thread(target=update_cache)
    update_thread.daemon = True  # Permite que o programa termine mesmo com a thread rodando
    update_thread.start()
    
    app.run(debug=True, use_reloader=False, port=5000)  # Adicione use_reloader=False