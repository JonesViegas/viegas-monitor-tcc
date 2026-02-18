import requests
import time
import random

TOKEN = "944fd390-3f1e-49bc-9727-7bf4089f21ed"
URL = "https://api.tago.io/data"

def enviar():
    # Gera dados aleatórios para simular o sensor real
    payload = [
        {"variable": "temperature", "value": round(random.uniform(25, 32), 2)},
        {"variable": "gas_ppm", "value": random.randint(300, 1200)},
        {"variable": "humidity", "value": random.randint(60, 80)}
    ]
    headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
    
    try:
        res = requests.post(URL, json=payload, headers=headers)
        print(f"[Simulador] Dados enviados: {res.status_code}")
    except:
        print("[Erro] Falha ao conectar com a Tago.io")

while True:
    enviar()
    time.sleep(30) # Envia a cada 30 segundos