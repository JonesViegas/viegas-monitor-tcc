from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os, traceback
from dotenv import load_dotenv
import pytz

# Configuração de Fuso Horário
BR_TIMEZONE = pytz.timezone('America/Bahia')

load_dotenv()

app = Flask(__name__)

# CORREÇÃO DE SEGURANÇA: Chave secreta para sessões
app.secret_key = os.environ.get('SECRET_KEY', 'tcc-viegas-seguranca-2026-fallback-key')

# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback para SQLite local se não houver DATABASE_URL (para testes locais)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///tcc_viegas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Leitura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    variable = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

# ==========================================
# 2. CONFIGURAÇÕES E IDS (DATABASE_IDS)
# ==========================================
ID_RAK = "674665c3c948600008590f2e"
ID_NIT = "6567877910457c000a62e679"
ID_EDGE = "mikrotik_edge"

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
        # Senha padrão conforme seu projeto
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
# 4. API STATUS (CONSUMO DO DASHBOARD)
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
                dt_br = row.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE)
                return dt_br.timestamp()
            return 0

        data = {
            "rak": {
                "h2s": get_latest(ID_RAK, "H2S"),
                "co2": get_latest(ID_RAK, "CO2"),
                "ts": get_ts(ID_RAK)
            },
            "nit": {
                "umid": get_latest(ID_NIT, "UMID"),
                "temp": get_latest(ID_NIT, "TEMP"),
                "ts": get_ts(ID_NIT)
            },
            "sim": {
                "h2s": get_latest(ID_EDGE, "H2S"),
                "ts": get_ts(ID_EDGE),
                "risco": "CRÍTICO" if get_latest(ID_EDGE, "H2S") > 15 else "ESTÁVEL"
            }
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 5. WEBHOOK RECEPTOR (O ALVO DO ATAQUE)
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Pega o JSON mesmo se o Content-Type estiver errado
        payload = request.get_json(force=True, silent=True)
        print(f"DEBUG: Payload recebido: {payload}") # Aparecerá nos Logs do Render

        if not payload:
            return jsonify({"status": "error", "message": "Payload vazio"}), 400

        # Se vier um único objeto, transforma em lista
        if isinstance(payload, dict): payload = [payload]

        # Mapeamento expandido para aceitar dados do MikroTik e Tago
        variable_map = {
            "h2s": "H2S", "h2s_ppm": "H2S", "gas": "H2S",
            "co2": "CO2", "temp": "TEMP", "umid": "UMID"
        }

        for item in payload:
            # Identifica o dispositivo (ID do sensor ou nosso ID de simulação)
            dev_id = str(item.get("device") or item.get("device_id") or ID_EDGE).strip()
            
            # Identifica a variável e o valor
            var_raw = str(item.get("variable") or "").lower().strip()
            val_raw = item.get("value")
            
            if not var_raw or val_raw is None: continue

            # Converte valor para float
            try:
                value = float(str(val_raw).replace(',', '.'))
            except: continue

            # Traduz para o padrão do Banco
            gas_type = variable_map.get(var_raw, var_raw.upper())

            # SALVA NO BANCO DE DADOS
            nova_leitura = Leitura(device_id=dev_id, variable=gas_type, value=value)
            db.session.add(nova_leitura)
            print(f"SUCESSO: Gravado {gas_type}={value} para o device {dev_id}")

        db.session.commit()
        return jsonify({"status": "success"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"ERRO NO WEBHOOK: {traceback.format_exc()}")
        return jsonify({"status": "error"}), 500

# Rota para auditoria rápida (Ver todos os dados injetados)
@app.route('/audit')
def audit():
    leituras = Leitura.query.order_by(Leitura.id.desc()).limit(50).all()
    lista = [{"id": l.id, "device": l.device_id, "var": l.variable, "val": l.value, "time": l.timestamp} for l in leituras]
    return jsonify(lista)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)