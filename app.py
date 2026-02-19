from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime, time, json, os

app = Flask(__name__)
app.secret_key = "viegas_security_key"

DATA_FILE = "dados_sensores.json"
MAX_HISTORY = 10

# IDs REAIS DOS SEUS SENSORES (BAHIA) - CONFIRME NO TAGO.IO
ID_RAK = "674665c3c948600008590f2e"
ID_NIT = "6567877910457c000a62e679"

def carregar_dados():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f: return json.load(f)
        except: pass
    return {
        "rak": {"temp": 0.0, "h2s": 0.0, "ts": 0, "history": []},
        "nit": {"temp": 0.0, "umid": 0.0, "ts": 0, "history": []},
        "sim": {"h2s": 0.0, "ts": 0, "risco": "Estável", "cor": "emerald", "history": []}
    }

def salvar_dados(dados):
    with open(DATA_FILE, 'w') as f: json.dump(dados, f)

monitoramento = carregar_dados()

@app.route('/')
def home():
    if 'logged_in' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "viegas2026":
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    return render_template('login.html')

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
    data = carregar_dados()
    for key in ['rak', 'nit', 'sim']:
        ts = data[key].get('ts', 0)
        data[key]['time_str'] = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts > 0 else "--:--:--"
    return jsonify(data)

@app.route('/webhook', methods=['POST'])
def webhook():
    global monitoramento
    try:
        data = request.get_json(force=True)
        payload = data if isinstance(data, list) else [data]
        timestamp_atual = time.time()
        time_str = datetime.datetime.fromtimestamp(timestamp_atual).strftime("%H:%M:%S")

        for item in payload:
            dev_id = str(item.get('device'))
            var = item.get('variable')
            try:
                val = float(item.get('value'))
            except:
                continue
            
            # --- LÓGICA RAK (Campo A) ---
            if dev_id == ID_RAK:
                if var in ['gas_ppm', 'gas', 'h2s']: 
                    monitoramento['rak']['h2s'] = val
                    monitoramento['rak']['history'].insert(0, {"time": time_str, "val": val})
                elif var in ['temperature', 'temp']:
                    monitoramento['rak']['temp'] = val
                monitoramento['rak']['ts'] = timestamp_atual

            # --- LÓGICA NIT (Campo B) ---
            elif dev_id == ID_NIT:
                if var in ['humidity', '1_v', 'umid']: 
                    monitoramento['nit']['umid'] = val
                    monitoramento['nit']['history'].insert(0, {"time": time_str, "val": val})
                elif var in ['temperature', '0_v', 'temp']:
                    monitoramento['nit']['temp'] = val
                monitoramento['nit']['ts'] = timestamp_atual

            # --- LÓGICA MIKROTIK (Auditoria) ---
            elif dev_id == "mikrotik_edge":
                if var == 'h2s_ppm':
                    monitoramento['sim']['h2s'] = val
                    monitoramento['sim']['ts'] = timestamp_atual
                    monitoramento['sim']['risco'] = "CRÍTICO" if val > 15 else "ESTÁVEL"
                    monitoramento['sim']['history'].insert(0, {"time": time_str, "val": val, "risco": monitoramento['sim']['risco']})

        # Limpa histórico antigo
        for key in ['rak', 'nit', 'sim']:
            monitoramento[key]['history'] = monitoramento[key]['history'][:MAX_HISTORY]

        salvar_dados(monitoramento)
        return "OK", 200
    except Exception as e:
        print(f"Erro: {e}")
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)