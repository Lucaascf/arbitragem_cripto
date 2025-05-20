from flask import Flask, jsonify, render_template
from flask_cors import CORS
from services.cache_service import CacheService
import threading

app = Flask(__name__)
CORS(app)
cache_service = CacheService()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculadora')
def calculadora():
    return render_template('calculadora.html')

@app.route('/api/comparacao')
def api_comparacao():
    try:
        cache = cache_service.get_cache()
        
        if cache['data'] is None:
            cache_service.update_cache()
            cache = cache_service.get_cache()
        
        return jsonify({
            'data': cache['data'],
            'last_update': cache['last_update'].isoformat() if cache['last_update'] else None,
            'total_crossings_24h': sum(c['count'] for c in cache_service.comparison.crossings_24h.values()),
            'total_crossings_30min': sum(c['count'] for c in cache_service.comparison.crossings_30min.values())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Inicia o serviço de cache em background
    cache_service.start_background_updates()
    
    # Configura o serviço de comparação no cache service
    from services.comparison_service import ComparisonService
    cache_service.comparison = ComparisonService()
    
    app.run(debug=True, use_reloader=False, port=5000)