from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os, traceback, pytz, time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "viegas_security_2026")

# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"): 
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or "postgresql://postgres:senha123@localhost:5432/viegas_tcc"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
BR_TIMEZONE = pytz.timezone('America/Bahia')

# IDs do .env
ID_RAK = os.getenv("ID_RAK")
ID_NIT = os.getenv("ID_NIT")
ID_MIKROTIK = os.getenv("ID_MIKROTIK", "mikrotik_edge")

class Leitura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), nullable=False)
    variable = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

# ==========================================
# FUNÇÕES AUXILIARES (LOGICA DE NEGÓCIO)
# ==========================================
def get_latest(dev_id, var_list):
    row = Leitura.query.filter(Leitura.device_id == dev_id, Leitura.variable.in_(var_list)).order_by(Leitura.id.desc()).first()
    return row.value if row else 0.0

def get_history(dev_id, var_list, limit=5):
    rows = Leitura.query.filter(Leitura.device_id == dev_id, Leitura.variable.in_(var_list)).order_by(Leitura.id.desc()).limit(limit).all()
    return [{"time": r.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE).strftime("%H:%M:%S"), "val": round(r.value, 2)} for r in rows]

def get_last_ts(dev_id):
    row = Leitura.query.filter(Leitura.device_id == dev_id).order_by(Leitura.id.desc()).first()
    if row:
        dt_br = row.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE)
        return {"unix": dt_br.timestamp(), "str": dt_br.strftime("%H:%M:%S")}
    return {"unix": 0, "str": "--:--:--"}

# ==========================================
# API STATUS (ALIMENTA O DASHBOARD)
# ==========================================
@app.route('/api/status')
def get_status():
    try:
        ts_sim = get_last_ts(ID_MIKROTIK)
        
        data = {
            "rak": {
                "h2s": get_latest(ID_RAK, ["H2S", "GAS_PPM"]),
                "co2": get_latest(ID_RAK, ["CO2"]),
                "ch4": get_latest(ID_RAK, ["CH4"]),
                "temp": get_latest(ID_RAK, ["TEMP", "TEMPERATURE"]),
                "history": get_history(ID_RAK, ["H2S", "GAS_PPM"])
            },
            "nit": {
                "umid": get_latest(ID_NIT, ["UMID", "HUMIDITY"]),
                "temp": get_latest(ID_NIT, ["TEMP", "TEMPERATURE"]),
                "history": get_history(ID_NIT, ["UMID", "HUMIDITY"])
            },
            "sim": {
                "h2s": get_latest(ID_MIKROTIK, ["H2S"]),
                "ts_unix": ts_sim["unix"],
                "ts_str": ts_sim["str"],
                "history": get_history(ID_MIKROTIK, ["H2S"])
            }
        }
        return jsonify(data)
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# ==========================================
# WEBHOOK (RECEBE TAGO E MIKROTIK)
# ==========================================
@app.route('/webhook', methods=['POST'])
@app.route('/api/v1/webhook/tago', methods=['POST'])
def webhook():
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload: return jsonify({"status": "error"}), 400
        if isinstance(payload, dict): payload = [payload]

        # Mapeamento de variáveis do TagoIO para o Padrão do Painel
        mapa = {
            "gas_ppm": "H2S", "h2s": "H2S",
            "temperature": "TEMP", "temp": "TEMP", "temperatura": "TEMP",
            "humidity": "UMID", "umid": "UMID", "umidade": "UMID",
            "co2": "CO2", "ch4": "CH4"
        }

        for item in payload:
            var_raw = str(item.get("variable", "")).lower()
            val_raw = item.get("value")
            # Se não vier 'device' no JSON, assume que é o ataque do MikroTik
            dev_id = str(item.get("device", ID_MIKROTIK)) 

            if val_raw is not None:
                var_final = mapa.get(var_raw, var_raw).upper()
                nova_leitura = Leitura(device_id=dev_id, variable=var_final, value=float(val_raw))
                db.session.add(nova_leitura)
        
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except:
        db.session.rollback()
        return jsonify({"status": "error"}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "viegas2026":
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)