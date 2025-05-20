from datetime import datetime

def format_timestamp(timestamp):
    """Formata um timestamp para exibição amigável"""
    if isinstance(timestamp, str):
        return timestamp
    return timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'Nunca'

def calculate_percentage_difference(price1, price2):
    """Calcula a diferença percentual entre dois preços"""
    if not price1 or not price2 or price1 == 0:
        return 0
    return ((price2 - price1) / price1) * 100