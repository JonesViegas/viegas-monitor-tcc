# Viegas - Inovação e Monitoramento Ambiental
> **Projeto de TCC - Pós-Graduação em Redes de Computação Distribuídas**

Este repositório contém o sistema de monitoramento de riscos ambientais **Viegas**, desenvolvido como estudo de caso para análise de vulnerabilidades em gateways de borda (Edge Computing).

## 🏢 Sobre o Sistema
O sistema foi concebido para monitorar níveis críticos de gases tóxicos (**H2S**) e inflamáveis (**CH4/Metano**) em ambientes industriais distribuídos. A arquitetura utiliza um gateway **MikroTik CHR** para o processamento de borda e o **Render.com** como central de comando em nuvem.

## 🏗️ Arquitetura do Fluxo de Dados
1. **Sensoriamento:** Dispositivos IoT (Bahia) -> Protocolo LoRaWAN -> Tago.io.
2. **Tunelamento:** Tago.io -> Webhook -> ngrok (Túnel Reverso).
3. **Borda (Edge):** ngrok -> **MikroTik CHR** (Alvo da auditoria de segurança).
4. **Dashboard:** MikroTik -> Redirecionamento de Camada 4 (NAT) -> Dashboard Viegas (Render.com).

## 🛡️ Estudo de Caso: Segurança e Vulnerabilidades
O foco principal deste projeto é a realização de testes de penetração (Pentest) no nó de borda para identificar:
- **Interceptação de Dados:** Ausência de criptografia TLS no transporte entre a borda e a nuvem.
- **Negação de Serviço (DoS):** Impacto na disponibilidade do monitoramento real-time sob ataque de inundação (hping3).
- **Exposição de Serviços:** Auditoria de portas abertas via túneis reversos.

## 🛠️ Tecnologias Utilizadas
- **Backend:** Python / Flask
- **Frontend:** Tailwind CSS / HTML5 / JavaScript (Fetch API)
- **Servidor Web:** Gunicorn (Produção)
- **Persistência:** Flat-file JSON (Arquitetura sem Banco de Dados SQL)
- **Infraestrutura:** MikroTik RouterOS v7 / Docker (Containers)

## 🚀 Como Executar
1. Instale as dependências: `pip install -r requirements.txt`
2. Execute o servidor: `python app.py`
3. Acesse: `http://localhost:5000`

**Credenciais Padrão:**
- Usuário: `admin`
- Senha: `viegas2026`

---
*Desenvolvido por: [Seu Nome]*
*Orientador: Inteligência Artificial Assistiva*