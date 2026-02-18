from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime
import time

app = Flask(__name__)
app.secret_key = "viegas_security_key"

# Banco de dados em memória - Monitorando os dois sensores
monitoramento = {
    "h2s": 0.0,
    "ch4": 0.0,
    "temp": 0.0,
    "risco": "Estável",
    "cor_risco": "emerald",
    "last_update": 0
}

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
    time_str = datetime.datetime.fromtimestamp(monitoramento["last_update"]).strftime("%H:%M:%S") if monitoramento["last_update"] > 0 else "--:--:--"
    return jsonify({**monitoramento, "time_str": time_str, "ts": monitoramento["last_update"]})

@app.route('/webhook', methods=['POST'])
def webhook():
    global monitoramento
    try:
        data = request.get_json(force=True)
        payload = data if isinstance(data, list) else [data]
        
        for item in payload:
            var = item.get('variable')
            val = float(item.get('value'))
            
            # Lógica para H2S (AquaGuard)
            if var in ['h2s_ppm', 'gas_ppm']:
                monitoramento['h2s'] = val
                if val > 15: monitoramento['risco'], monitoramento['cor_risco'] = "CRÍTICO", "red"
                elif val > 5: monitoramento['risco'], monitoramento['cor_risco'] = "ALERTA", "orange"
                else: monitoramento['risco'], monitoramento['cor_risco'] = "ESTÁVEL", "emerald"
            
            # Lógica para Metano / CO2 (Segundo Dispositivo)
            elif var in ['ch4_ppm', 'gas_hpa', 'co2_ppm']:
                monitoramento['ch4'] = val
            
            elif var in ['temperature', 'temperatura']:
                monitoramento['temp'] = val

        monitoramento["last_update"] = time.time()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)