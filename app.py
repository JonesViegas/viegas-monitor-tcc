from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime
import time
import json
import os

app = Flask(__name__)
app.secret_key = "viegas_security_key"

DATA_FILE = "dados_sensores.json"

# Função para carregar dados do arquivo (Simulando o Banco de Dados)
def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "h2s": 0.0, "ch4": 0.0, "temp": 0.0, 
        "risco": "Estável", "cor_risco": "emerald", 
        "last_update": 0, "device_serial": "eui-ac1f09fffe090b22"
    }

# Função para salvar dados no arquivo
def salvar_dados(dados):
    with open(DATA_FILE, 'w') as f:
        json.dump(dados, f)

# Inicializa o monitoramento
monitoramento = carregar_dados()

USER_ADMIN = "admin"
PASS_ADMIN = "viegas2026"

@app.route('/')
def home():
    if 'logged_in' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == USER_ADMIN and request.form['password'] == PASS_ADMIN:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else: error = 'Credenciais Inválidas'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    if 'logged_in' not in session: return jsonify({"error": "unauthorized"}), 401
    current_data = carregar_dados()
    time_str = datetime.datetime.fromtimestamp(current_data["last_update"]).strftime("%H:%M:%S") if current_data["last_update"] > 0 else "--:--:--"
    return jsonify({**current_data, "time_str": time_str, "ts": current_data["last_update"]})

@app.route('/webhook', methods=['POST'])
def webhook():
    global monitoramento
    try:
        data = request.get_json(force=True)
        payload = data if isinstance(data, list) else [data]
        
        for item in payload:
            var = item.get('variable')
            val = float(item.get('value'))
            
            if var in ['h2s_ppm', 'gas_ppm']:
                monitoramento['h2s'] = val
                if val > 15: monitoramento['risco'], monitoramento['cor_risco'] = "CRÍTICO", "red"
                elif val > 5: monitoramento['risco'], monitoramento['cor_risco'] = "ALERTA", "orange"
                else: monitoramento['risco'], monitoramento['cor_risco'] = "ESTÁVEL", "emerald"
            elif var in ['ch4_ppm', 'gas_hpa', 'co2_ppm']:
                monitoramento['ch4'] = val
            elif var in ['temperature', 'temperatura']:
                monitoramento['temp'] = val

        monitoramento["last_update"] = time.time()
        salvar_dados(monitoramento) # Grava no arquivo JSON
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)