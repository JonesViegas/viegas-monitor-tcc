from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime, time, json, os, traceback

app = Flask(__name__)
app.secret_key = "viegas_security_key"

DATA_FILE = "dados_sensores.json"
MAX_HISTORY = 10

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

# ESTA ROTA ACEITA TANTO O MIKROTIK QUANTO A TAGO AGORA
@app.route('/webhook', methods=['POST'])
@app.route('/api/v1/webhook/tago', methods=['POST'])
def webhook():
    global monitoramento
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload: return jsonify({"status": "error", "msg": "sem payload"}), 400
        if isinstance(payload, dict): payload = [payload]

        timestamp_atual = time.time()
        time_str = datetime.datetime.fromtimestamp(timestamp_atual).strftime("%H:%M:%S")

        # Mapeamento estendido para aceitar TUDO
        variable_map = {
            "gas_ppm": "GAS", "gas": "GAS", "h2s": "GAS", "h2s_ppm": "GAS",
            "temperatura": "TEMP", "temperature": "TEMP", "temp": "TEMP", "0_v": "TEMP",
            "umidade": "UMID", "humidity": "UMID", "umid": "UMID", "1_v": "UMID"
        }

        for item in payload:
            # Extração que aceita "variable" ou "variável"
            var_raw = item.get("variable") or item.get("variável")
            if not var_raw: continue
            var_raw = str(var_raw).lower().strip()

            # Extração que aceita "value" ou "valor"
            val_raw = item.get("value") or item.get("valor")
            if val_raw is None: continue
            
            try:
                value = float(str(val_raw).replace(',', '.'))
            except: continue

            serial = str(item.get("device", "")).strip()
            gas_type = variable_map.get(var_raw)
            if not gas_type: continue

            # LÓGICA DE DESTINO
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

            elif serial == "mikrotik_edge" or not serial: # Se vier do MikroTik sem serial
                if gas_type == "GAS":
                    monitoramento['sim']['h2s'] = value
                    monitoramento['sim']['ts'] = timestamp_atual
                    monitoramento['sim']['risco'] = "CRÍTICO" if value > 15 else "ESTÁVEL"
                    monitoramento['sim']['history'].insert(0, {"time": time_str, "val": value, "risco": monitoramento['sim']['risco']})

        salvar_dados(monitoramento)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)