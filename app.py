
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os, time, traceback
from dotenv import load_dotenv
import pytz

BR_TIMEZONE = pytz.timezone('America/Bahia')

# Carrega o .env explicitamente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.secret_key = os.environ.get('SECRET_KEY', 'chave-secreta-para-o-tcc-viegas-2026')

# Pega a URL do banco do .env (local) ou do Render (nuvem)
DATABASE_URL = os.getenv("DATABASE_URL")

# Se for no Render, ele corrige automaticamente o protocolo
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL


# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS (POSTGRES)
# ==========================================
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://seu_usuario:senha@localhost/nome_do_banco')
if DATABASE_URL.startswith("postgres://"): 
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MODELO DE TABELA
class Leitura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    variable = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

# ==========================================
# 2. CONFIGURAÇÕES GERAIS E IDS
# ==========================================
DATA_FILE = "dados_sensores.json"
MAX_HISTORY = 10
ID_RAK = "674665c3c948600008590f2e"
ID_NIT = "6567877910457c000a62e679"

# ==========================================
# 3. ROTAS DE NAVEGAÇÃO
# ==========================================
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

# ==========================================
# 4. API STATUS (LENDO DO POSTGRES)
# ==========================================
@app.route('/api/status')
def get_status():
    try:
        def get_latest(dev_id, var):
            row = Leitura.query.filter_by(device_id=dev_id, variable=var).order_by(Leitura.id.desc()).first()
            return row.value if row else 0.0

        def get_ts(dev_id):
            row = Leitura.query.filter_by(device_id=dev_id).order_by(Leitura.id.desc()).first()
            if row:
                # Converte o tempo do banco (UTC) para o horário da Bahia
                dt_br = row.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE)
                return dt_br.timestamp()
            return 0

        def get_history(dev_id, var=None):
            query = Leitura.query.filter_by(device_id=dev_id)
            if var: query = query.filter_by(variable=var)
            rows = query.order_by(Leitura.id.desc()).limit(10).all()
            history = []
            for r in rows:
                dt_br = r.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE)
                history.append({"time": dt_br.strftime("%H:%M:%S"), "val": r.value})
            return history

        data = {
            "rak": {
                "h2s": get_latest(ID_RAK, "H2S"),
                "co2": get_latest(ID_RAK, "CO2"),
                "ch4": get_latest(ID_RAK, "CH4"),
                "temp": get_latest(ID_RAK, "TEMP"),
                "ts": get_ts(ID_RAK),
                "history": get_history(ID_RAK, "H2S")
            },
            "nit": {
                "umid": get_latest(ID_NIT, "UMID"),
                "temp": get_latest(ID_NIT, "TEMP"),
                "ts": get_ts(ID_NIT),
                "history": get_history(ID_NIT, "UMID")
            },
            "sim": {
                "h2s": get_latest("mikrotik_edge", "H2S"),
                "ts": get_ts("mikrotik_edge"),
                "risco": "CRÍTICO" if get_latest("mikrotik_edge", "H2S") > 15 else "ESTÁVEL",
                "history": get_history("mikrotik_edge", "H2S")
            }
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# 5. WEBHOOK (SALVANDO NO POSTGRES)
# ==========================================
@app.route('/webhook', methods=['POST'])
@app.route('/api/v1/webhook/tago', methods=['POST'])
def webhook():
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload: return jsonify({"status": "error"}), 400
        if isinstance(payload, dict): payload = [payload]

        variable_map = {
            "gas_ppm": "H2S", "h2s": "H2S", "h2s_ppm": "H2S",
            "co2": "CO2", "co2_ppm": "CO2",
            "metano": "CH4", "ch4": "CH4", "metano_ppm": "CH4",
            "temperature": "TEMP", "temp": "TEMP", "0_v": "TEMP",
            "humidity": "UMID", "umid": "UMID", "1_v": "UMID"
        }

        for item in payload:
            serial = str(item.get("device", "")).strip()
            # Se não houver serial, assumimos que é o MikroTik/Simulador
            if not serial or serial == "mikrotik_edge":
                serial = "mikrotik_edge"

            var_raw = str(item.get("variable") or item.get("variável") or "").lower().strip()
            val_raw = item.get("value") or item.get("valor")
            
            if not var_raw or val_raw is None: continue
            try:
                value = float(str(val_raw).replace(',', '.'))
            except: continue

            gas_type = variable_map.get(var_raw)
            if not gas_type: continue

            # --- SALVANDO NO BANCO DE DADOS ---
            nova_leitura = Leitura(device_id=serial, variable=gas_type, value=value)
            db.session.add(nova_leitura)

        db.session.commit()
        return jsonify({"status": "success"}), 200

    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)