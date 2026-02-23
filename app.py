from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os, traceback, pytz
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

# IDs do .env — usados para mapear qual device é RAK e qual é NIT
ID_RAK      = os.getenv("ID_RAK")
ID_NIT      = os.getenv("ID_NIT")
ID_MIKROTIK = os.getenv("ID_MIKROTIK", "mikrotik_edge")

class Leitura(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), nullable=False)
    variable  = db.Column(db.String(50),  nullable=False)
    value     = db.Column(db.Float,        nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

# ==========================================
# MAPEAMENTO DE VARIÁVEIS TAGO → PADRÃO
# ==========================================
MAPA_VARS = {
    "gas_ppm":     "H2S",
    "h2s":         "H2S",
    "temperature": "TEMP",
    "temp":        "TEMP",
    "temperatura": "TEMP",
    "humidity":    "UMID",
    "umid":        "UMID",
    "umidade":     "UMID",
    "co2":         "CO2",
    "ch4":         "CH4",
}

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def get_latest(dev_id, var_list):
    if not dev_id:
        return 0.0
    row = (Leitura.query
           .filter(Leitura.device_id == dev_id, Leitura.variable.in_(var_list))
           .order_by(Leitura.id.desc())
           .first())
    return round(row.value, 4) if row else 0.0

def get_history(dev_id, var_list, limit=5):
    if not dev_id:
        return []
    rows = (Leitura.query
            .filter(Leitura.device_id == dev_id, Leitura.variable.in_(var_list))
            .order_by(Leitura.id.desc())
            .limit(limit)
            .all())
    return [
        {
            "time": r.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE).strftime("%H:%M:%S"),
            "val":  round(r.value, 2)
        }
        for r in rows
    ]

def get_last_ts(dev_id):
    if not dev_id:
        return {"unix": 0, "str": "--:--:--"}
    row = Leitura.query.filter(Leitura.device_id == dev_id).order_by(Leitura.id.desc()).first()
    if row:
        dt_br = row.timestamp.replace(tzinfo=pytz.utc).astimezone(BR_TIMEZONE)
        return {"unix": dt_br.timestamp(), "str": dt_br.strftime("%H:%M:%S")}
    return {"unix": 0, "str": "--:--:--"}


# ==========================================
# WEBHOOK — RECEBE TAGO E MIKROTIK
# ==========================================
def _process_payload(payload):
    if not payload:
        return 0

    if isinstance(payload, dict):
        payload = [payload]

    saved = 0
    for item in payload:
        # TagoIO usa 'variable', 'value' e 'origin' (ID do dispositivo)
        var_raw = str(item.get("variable", "")).strip().lower()
        val_raw = item.get("value")
        
        # TagoIO envia o ID do dispositivo no campo 'origin' ou 'device'
        device_raw = str(item.get("origin") or item.get("device") or "").strip()

        if val_raw is None or var_raw == "":
            continue

        # Lógica de Identificação do Dispositivo
        if not device_raw or device_raw.lower() == "mikrotik":
            dev_id = ID_MIKROTIK
        elif ID_RAK and device_raw == ID_RAK:
            dev_id = ID_RAK
        elif ID_NIT and device_raw == ID_NIT:
            dev_id = ID_NIT
        else:
            # Se não bater com os IDs fixos, salva o que vier (ajuda no debug)
            dev_id = device_raw

        # Normaliza o nome da variável (ex: gas_ppm -> H2S)
        var_final = MAPA_VARS.get(var_raw, var_raw).upper()

        try:
            nova = Leitura(
                device_id=dev_id, 
                variable=var_final, 
                value=float(val_raw),
                timestamp=datetime.now(timezone.utc)
            )
            db.session.add(nova)
            saved += 1
        except Exception as e:
            print(f"Erro ao processar item: {e}")

    db.session.commit()
    return saved

# No get_status, adicione um print para debug se os dados sumirem
@app.route('/api/status')
def get_status():
    try:
        ts_sim = get_last_ts(ID_MIKROTIK)
        data = {
            "rak": {
                "h2s":     get_latest(ID_RAK, ["H2S"]),
                "co2":     get_latest(ID_RAK, ["CO2"]),
                "ch4":     get_latest(ID_RAK, ["CH4"]),
                "temp":    get_latest(ID_RAK, ["TEMP"]),
                "history": get_history(ID_RAK, ["H2S"])
            },
            "nit": {
                "umid":    get_latest(ID_NIT, ["UMID"]),
                "temp":    get_latest(ID_NIT, ["TEMP"]),
                "history": get_history(ID_NIT, ["UMID"])
            },
            "sim": {
                "h2s":     get_latest(ID_MIKROTIK, ["H2S"]),
                "ts_unix": ts_sim["unix"],
                "ts_str":  ts_sim["str"],
                "history": get_history(ID_MIKROTIK, ["H2S"])
            }
        }
        return jsonify(data)
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Erro interno"}), 500


@app.route('/webhook', methods=['POST'])
@app.route('/api/v1/webhook/tago', methods=['POST'])
def webhook():
    try:
        payload = request.get_json(force=True, silent=True)
        if payload is None:
            return jsonify({"status": "error", "msg": "payload vazio ou JSON inválido"}), 400

        saved = _process_payload(payload)
        return jsonify({"status": "success", "saved": saved}), 200

    except Exception:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({"status": "error"}), 500


# ==========================================
# ROTA DE DEBUG — VER O QUE CHEGOU NO BANCO
# ==========================================
@app.route('/api/debug')
def debug():
    """
    Retorna as últimas 20 leituras brutas + os IDs configurados.
    Acesse /api/debug para diagnosticar problemas de ingestão.
    REMOVA ou proteja essa rota em produção!
    """
    rows = Leitura.query.order_by(Leitura.id.desc()).limit(20).all()
    return jsonify({
        "config": {
            "ID_RAK":      ID_RAK,
            "ID_NIT":      ID_NIT,
            "ID_MIKROTIK": ID_MIKROTIK,
        },
        "ultimas_leituras": [
            {
                "id":        r.id,
                "device_id": r.device_id,
                "variable":  r.variable,
                "value":     r.value,
                "timestamp": r.timestamp.isoformat()
            }
            for r in rows
        ]
    })


# ==========================================
# ROTA DE TESTE — INJETAR DADO MANUAL
# ==========================================
@app.route('/api/test-inject', methods=['GET'])
def test_inject():
    """
    Injeta dados fictícios para testar se o dashboard funciona.
    Acesse /api/test-inject no browser. Remova em produção!
    """
    from random import uniform
    itens = [
        {"device": ID_RAK,      "variable": "H2S",  "value": round(uniform(0.1, 5.0), 2)},
        {"device": ID_RAK,      "variable": "CO2",  "value": round(uniform(400, 800), 1)},
        {"device": ID_RAK,      "variable": "CH4",  "value": round(uniform(0.0, 2.0), 2)},
        {"device": ID_RAK,      "variable": "TEMP", "value": round(uniform(24, 32), 1)},
        {"device": ID_NIT,      "variable": "UMID", "value": round(uniform(55, 90), 1)},
        {"device": ID_NIT,      "variable": "TEMP", "value": round(uniform(22, 30), 1)},
        {"device": ID_MIKROTIK, "variable": "H2S",  "value": round(uniform(0.0, 20.0), 2)},
    ]
    for item in itens:
        if item["device"]:
            db.session.add(Leitura(
                device_id=item["device"],
                variable=item["variable"],
                value=item["value"]
            ))
    db.session.commit()
    return jsonify({"status": "injetado", "itens": itens})


# ==========================================
# AUTENTICAÇÃO
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "viegas2026":
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)