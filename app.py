from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime, time, json, os, traceback

app = Flask(__name__)
app.secret_key = "viegas_security_key"

DATA_FILE = "dados_sensores.json"
MAX_HISTORY = 10

# IDs REAIS (BAHIA)
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

# ==========================================
# WEBHOOK REESTRUTURADO (LÓGICA ECOGAS)
# ==========================================
@app.route('/api/v1/webhook/tago', methods=['POST']) # Rota que a Tago está usando
def webhook():
    global monitoramento
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload: return jsonify({"status": "error"}), 400
        if isinstance(payload, dict): payload = [payload]

        # Timestamp em UTC para sincronizar com o Dashboard
        timestamp_atual = datetime.datetime.now(datetime.timezone.utc).timestamp()
        time_str = datetime.datetime.fromtimestamp(timestamp_atual).strftime("%H:%M:%S")

        variable_map = {
            "gas_ppm": "GAS", "gas": "GAS", "h2s": "GAS", "h2s_ppm": "GAS",
            "temperature": "TEMP", "temp": "TEMP", "0_v": "TEMP",
            "humidity": "UMID", "umid": "UMID", "1_v": "UMID"
        }

        for item in payload:
            serial = str(item.get("device", "")).strip()
            var_raw = str(item.get("variable", "")).lower().strip()
            
            try:
                val_raw = item.get("value")
                value = float(str(val_raw).replace(',', '.'))
            except: continue

            gas_type = variable_map.get(var_raw)
            if not gas_type: continue

            if serial == ID_RAK:
                if gas_type == "GAS":
                    monitoramento['rak']['h2s'] = value
                    monitoramento['rak']['history'].insert(0, {"time": time_str, "val": value})
                elif gas_type == "TEMP":
                    monitoramento['rak']['temp'] = value
                monitoramento['rak']['ts'] = timestamp_atual

            elif serial == ID_NIT:
                if gas_type == "UMID":
                    monitoramento['nit']['umid'] = value
                    monitoramento['nit']['history'].insert(0, {"time": time_str, "val": value})
                elif gas_type == "TEMP":
                    monitoramento['nit']['temp'] = value
                monitoramento['nit']['ts'] = timestamp_atual

            elif serial == "mikrotik_edge":
                if gas_type == "GAS":
                    monitoramento['sim']['h2s'] = value
                    monitoramento['sim']['ts'] = timestamp_atual
                    monitoramento['sim']['risco'] = "CRÍTICO" if value > 15 else "ESTÁVEL"
                    monitoramento['sim']['history'].insert(0, {"time": time_str, "val": value, "risco": monitoramento['sim']['risco']})

        salvar_dados(monitoramento)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)