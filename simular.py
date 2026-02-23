import requests
import time
import random
from datetime import datetime

# URL do seu servidor local (ou do Render se estiver rodando online)
#URL_WEBHOOK = "http://127.0.0.1:5000/webhook" 
URL_WEBHOOK = "https://viegas-monitor-tcc.onrender.com/webhook"

INTERVALO = 180 # 3 minutos (conforme solicitado)

def gerar_h2s():
    # 85% das vezes gera valor baixo (estável), 15% gera valor alto (crítico)
    if random.random() > 0.85:
        return round(random.uniform(16.0, 40.0), 2)
    return round(random.uniform(0.1, 2.5), 2)

def simular():
    print(f"--- SIMULADOR MIKROTIK ATIVO (Intervalo: {INTERVALO}s) ---")
    print(f"Enviando para: {URL_WEBHOOK}")
    
    while True:
        valor = gerar_h2s()
        
        # Formato de payload que o seu app.py já entende
        payload = {
            "variable": "h2s",
            "value": valor,
            "device": "mikrotik_edge" # Deve ser igual ao ID_MIKROTIK do .env
        }
        
        try:
            response = requests.post(URL_WEBHOOK, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Dado enviado: {valor} PPM | Sucesso")
            else:
                print(f"Erro no servidor: {response.status_code}")
        except Exception as e:
            print(f"Erro de conexão (o Flask está rodando?): {e}")
        
        print(f"Próxima leitura em {INTERVALO} segundos...")
        time.sleep(INTERVALO)
        return round(random.uniform(0.1, 2.0), 2)

if __name__ == "__main__":
    simular()