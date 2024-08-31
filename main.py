import requests
import re
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify

app = Flask(__name__)

# Función para descomponer el campo option
def decompose_option(option):
    match = re.match(r"([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})", option)
    if match:
        ticker = match.group(1)
        year = '20' + match.group(2)
        month = match.group(3)
        day = match.group(4)
        exp_date = f"{year}-{month}-{day}"
        call_put = 'Call' if match.group(5) == 'C' else 'Put'
        strike = int(match.group(6)) / 1000  # Ajustar el strike dividiendo por 1000
        return ticker, exp_date, strike, call_put
    return None, None, None, None

# Función para descargar y procesar datos de opciones de CBOE
def fetch_option_data(ticker):
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker.upper()}.json"
    response = requests.get(url)
    data = response.json()

    # Extraer la información relevante
    options_list = []
    for option_data in data['data']['options']:
        ticker, exp_date, strike, call_put = decompose_option(option_data['option'])
        gamma = option_data.get('gamma', None)
        if gamma != 0:  # Filtrar al inicio si gamma es distinto de 0
            option_info = {
                'ticker': ticker,
                'exp_date': exp_date,
                'strike': strike,
                'call_put': call_put,
                'gamma': gamma,
                'delta': option_data.get('delta', None),
                'oi': option_data.get('open_interest', None),
                'theta': option_data.get('theta', None),
                'vega': option_data.get('vega', None)
            }
            options_list.append(option_info)

    return options_list

# API endpoint para devolver los datos en formato JSON
@app.route('/data', methods=['GET'])
def get_data():
    tickers = ['_SPX', 'AAPL']
    all_options = []

    for ticker in tickers:
        options_data = fetch_option_data(ticker)
        all_options.extend(options_data)

    # Crear un DataFrame de pandas para visualizar los datos
    df = pd.DataFrame(all_options)

    # Convertir exp_date a formato datetime y filtrar registros mayores de 31 días
    df['exp_date'] = pd.to_datetime(df['exp_date'])
    today = datetime.now()
    df = df[df['exp_date'] <= today + timedelta(days=31)]
    df = df[df['strike'] == 200]  # Filtrar solo por strike 200 para validar

    # Reorganizar el DataFrame para tener columnas separadas para Call y Put
    df_call = df[df['call_put'] == 'Call'].rename(columns={
        'gamma': 'call_gamma',
        'delta': 'call_delta',
        'oi': 'call_oi',
        'theta': 'call_theta',
        'vega': 'call_vega'
    })

    df_put = df[df['call_put'] == 'Put'].rename(columns={
        'gamma': 'put_gamma',
        'delta': 'put_delta',
        'oi': 'put_oi',
        'theta': 'put_theta',
        'vega': 'put_vega'
    })

    # Merge de los DataFrames de Call y Put
    df_merged = pd.merge(df_call, df_put, on=['ticker', 'exp_date', 'strike'], how='outer')

    # Remover las columnas 'call_put_x' y 'call_put_y'
    df_merged = df_merged.drop(columns=['call_put_x', 'call_put_y'], errors='ignore')

    # Convertir el DataFrame a un formato JSON
    result = df_merged.to_dict(orient='records')
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
