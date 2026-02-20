import os
import json
import redis
import re
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, Response
from groq import Groq
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
api_key_groq = os.getenv("GROQ_API_KEY")
url_redis = os.getenv("REDIS_URL")
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")

# Verificação de segurança das chaves básicas
if not api_key_groq or not url_redis:
    raise ValueError("ERRO: Faltam chaves do Groq ou Redis no arquivo .env!")

client_groq = Groq(api_key=api_key_groq)

# Cliente do Twilio para Envio Ativo (Evita timeout de 15s)
if twilio_sid and twilio_token:
    client_twilio = Client(twilio_sid, twilio_token)
else:
    client_twilio = None
    print("AVISO: Chaves do Twilio não encontradas. O envio ativo pode falhar.")

# Conexão com Redis
try:
    db = redis.from_url(url_redis, decode_responses=True, ssl_cert_reqs=None)
    print("Redis ping:", db.ping())
    print("Conexão Redis e Groq estabelecida com sucesso.")
except Exception as e:
    print(f"Erro Crítico no Redis: {e}")

# --- CONFIGURAÇÃO DA PLANILHA (GOOGLE SHEETS) SEGURO PARA NUVEM ---
try:
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Busca o texto do JSON salvo nas variáveis do Railway
    google_creds_texto = os.getenv("GOOGLE_CREDENTIALS")
    
    if google_creds_texto:
        # Transforma o texto de volta em um dicionário (JSON)
        credenciais_dict = json.loads(google_creds_texto)
        credenciais = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, escopo)
        cliente_sheets = gspread.authorize(credenciais)
        
        # ATENÇÃO: Coloque aqui o nome EXATO da sua planilha no Google Drive
        planilha_pedidos = cliente_sheets.open("Planilha bot").sheet1
        print("✅ Conexão com Google Sheets estabelecida com sucesso.")
    else:
        planilha_pedidos = None
        print("AVISO: Variável GOOGLE_CREDENTIALS não encontrada no ambiente.")

except Exception as e:
    planilha_pedidos = None
    print("❌ Erro ao conectar com Google Sheets:", e)


cardapio_pizzaria = """
CARDÁPIO ATUALIZADO:
[Pizzas Salgadas - Média (6 fatias) / Grande (8 fatias)]
1. Calabresa (M: R$ 40,00 / G: R$ 55,00) - Molho, mussarela, calabresa e cebola.
2. Marguerita (M: R$ 42,00 / G: R$ 58,00) - Molho, mussarela, tomate e manjericão fresco.
3. Frango c/ Catupiry (M: R$ 45,00 / G: R$ 62,00) - Frango desfiado e catupiry original.
4. Portuguesa (M: R$ 45,00 / G: R$ 62,00) - Presunto, ovos, cebola, ervilha e mussarela.

[Pizzas Doces - Apenas Broto (4 fatias)]
5. Chocolate (R$ 35,00) - Chocolate ao leite e granulado.
6. Banana (R$ 30,00) - Banana, açúcar e canela.

[Bebidas]
- Coca-Cola 2L (R$ 15,00)
- Guaraná 2L (R$ 12,00)
- Suco Prats Laranja (R$ 18,00)
"""

# --- O CÉREBRO DO LUIGI  ---
prompt_sistema = f"""
Você é o 'Luigi', o atendente virtual experiente da 'Pizzaria Bella Napoli' 🍕.
Sua missão é guiar o cliente desde a escolha até o pagamento de forma fluida.

🤖 TOM E COMPORTAMENTO OBRIGATÓRIOS:
- Aja como um humano no WhatsApp: respostas CURTAS, DIRETAS e amigáveis.
- NUNCA envie blocos de texto gigantes ou repita o cardápio inteiro sem necessidade.
- NUNCA dê explicações longas.
- NUNCA cite pedidos anteriores do cliente. Trate cada atendimento como o primeiro (sua memória é reiniciada a cada novo pedido).

{cardapio_pizzaria}

📋 DADOS OPERACIONAIS (USE ESTES DADOS REAIS):
- Taxa de entrega: R$ 8,00 fixa.
- Horário: Terça a Domingo, 18h às 23h.
- Regra do Meia a Meia: É UMA ÚNICA PIZZA com 2 sabores. O tamanho (M ou G) é um só para a pizza inteira. Cobra-se pelo valor do sabor mais caro.
- Pizzas Doces: VENDEMOS APENAS NO TAMANHO BROTO.
- CHAVE PIX: CNPJ 12.345.678/0001-99 (Nome: Bella Napoli Ltda).

🛑 PROTOCOLO DE ATENDIMENTO (SIGA ESTA ORDEM RIGOROSAMENTE):

Fase 1: Saudação e Cardápio
- Primeira mensagem: Apresente-se de forma breve e mande o cardápio.
- Pergunte: "Algum sabor te agradou ou quer uma sugestão?"

Fase 2: A Definição da Pizza
- Se o cliente pedir sabor salgado, PERGUNTE: "Vai querer ela **inteira** ou **meia a meia**?"
- Se for meia a meia: Pergunte o 2º sabor e o tamanho da pizza (Média/Grande). Lembre-se: é apenas UMA pizza, não pergunte o tamanho do segundo sabor separadamente.
- Se for inteira: Pergunte o tamanho.
- Pizza Doce: Só existe tamanho Broto.

Fase 3: Expansão do Pedido (Venda Adicional)
- Assim que a pizza for definida, você DEVE perguntar:
  "Deseja incluir MAIS UMA pizza 🍕 no pedido? Ou vamos para as bebidas?"
- Se o cliente quiser mais pizza: Volte para a Fase 2.
- Se o cliente quiser bebida: Ofereça Coca-Cola, Guaraná ou Suco.

Fase 4: Fechamento (Endereço e Pagamento)
- IMPORTANTE: Só avance para esta fase se o cliente disser que NÃO quer mais nada.
- 1º: Peça o ENDEREÇO COMPLETO (Rua, Número e Bairro). ACEITE QUALQUER ENDEREÇO que o cliente digitar, não tente verificar se o bairro ou a rua existem de verdade.
- 2º: Peça a Forma de Pagamento (Pix, Cartão ou Dinheiro).
  - Se for Pix: Envie a CHAVE PIX.
  - Se for Dinheiro: Pergunte do troco.

Fase 5: Resumo e Aguardar Confirmação
- Só envie o resumo se tiver endereço e pagamento definidos.
- Resumo: Itens, Entrega, TOTAL, Endereço e Pagamento.
- Pergunte EXATAMENTE: "Tudo certo? Posso mandar preparar?"
- 🛑 REGRA CRÍTICA: NESTA FASE É ESTRITAMENTE PROIBIDO GERAR O BLOCO [JSON_PEDIDO]. APENAS ESPERE O CLIENTE RESPONDER "SIM".

Fase 6: Fechamento Final e JSON (A Cozinha)
- APENAS QUANDO o cliente confirmar o resumo da Fase 5 (ex: "sim", "pode mandar"), você agradece de forma BEM CURTA e encerra o atendimento.
- 🛑 REGRA ABSOLUTA DE SIGILO: NUNCA diga as palavras "JSON", "código" ou "formato". O cliente não pode saber que você está enviando dados para a cozinha.
- É EXCLUSIVAMENTE NO FINAL DESTA MENSAGEM DE DESPEDIDA que você deve adicionar o bloco de texto exato abaixo:

[JSON_PEDIDO]
{{
  "pedido": "Resumo detalhado (Ex: 1x Meia Calabresa / Meia Marguerita G, 1x Coca-Cola 2L)",
  "endereco": "Rua X, Bairro Y",
  "pagamento": "Pix/Cartão/Dinheiro",
  "total": "R$ 00,00"
}}
[/JSON_PEDIDO]

⚠️ REGRAS DE OURO FINAIS:
1. NUNCA invente endereços. Se não souber o endereço, pergunte ao cliente.
2. NUNCA invente códigos Pix aleatórios. Use a chave dos DADOS OPERACIONAIS.
3. Nunca assuma o tamanho da pizza, sempre pergunte.
"""

def gerenciar_memoria(numero_telefone, nova_mensagem=None, papel="user"):
    chave_redis = f"chat:{numero_telefone}"
    historico_json = db.get(chave_redis)
    
    if historico_json:
        historico = json.loads(historico_json)
    else:
        historico = []

    if nova_mensagem:
        historico.append({"role": papel, "content": nova_mensagem})
        db.set(chave_redis, json.dumps(historico), ex=3600)
    
    return historico

def obter_resposta_ia(mensagem_usuario, numero_telefone):
    try:
        historico_atualizado = gerenciar_memoria(numero_telefone, mensagem_usuario, "user")
        
        # TRUQUE NOVO: Se o usuário confirmou, injetamos uma ordem de sistema
        mensagens_para_enviar = [{"role": "system", "content": prompt_sistema}] + historico_atualizado
        
        # Verifica se é uma confirmação de pedido para forçar o JSON
        palavras_confirmacao = ["sim", "pode", "tá bom", "ok", "pode mandar", "tudo certo", "confirmo"]
        if any(p in mensagem_usuario.lower() for p in palavras_confirmacao):
            # Adiciona uma mensagem de sistema "falsa" no final para obrigar o bot a gerar o JSON
            mensagens_para_enviar.append({
                "role": "system", 
                "content": "O cliente confirmou o pedido. FINALIZE AGORA. Agradeça e GERE O BLOCO [JSON_PEDIDO] OBRIGATORIAMENTE."
            })

        chat_completion = client_groq.chat.completions.create(
            messages=mensagens_para_enviar,
            model="llama-3.1-8b-instant", # Modelo rápido
            temperature=0.3, # Baixei a temperatura para ele ser mais "robô" e obedecer regras
        )
        
        resposta_ia = chat_completion.choices[0].message.content
        gerenciar_memoria(numero_telefone, resposta_ia, "assistant")
        
        return resposta_ia

    except Exception as e:
        print("ERRO GROQ:", e)
    return "Desculpe, tivemos um erro interno."

@app.route("/bot", methods=['POST'])
def bot():
    msg_recebida = request.values.get('Body', '').strip()
    numero_remetente = request.values.get('From', '') # Cliente
    numero_bot = request.values.get('To', '')         # Twilio/Pizzaria
    
    # Comando de Reset Manual
    if msg_recebida.lower() == "/reset":
        db.delete(f"chat:{numero_remetente}")
        if client_twilio:
            client_twilio.messages.create(body="Memória apagada! Começando do zero.", from_=numero_bot, to=numero_remetente)
        return Response(str(MessagingResponse()), mimetype="application/xml")

    # 1. Pega a resposta da IA
    resposta = obter_resposta_ia(msg_recebida, numero_remetente)

    if not resposta:
        resposta = "Desculpe, estou com instabilidade agora. Pode repetir?"

    # 2. Verifica se a IA gerou o JSON de Fechamento de Pedido
    if "[JSON_PEDIDO]" in resposta:
        try:
            # Extrai o JSON do meio do texto
            texto_json = re.search(r'\[JSON_PEDIDO\](.*?)\[/JSON_PEDIDO\]', resposta, re.DOTALL).group(1)
            dados_pedido = json.loads(texto_json.strip())
            
            # Se a planilha estiver conectada, salva os dados
            if planilha_pedidos:
                agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                nova_linha = [
                    agora, 
                    numero_remetente.replace("whatsapp:", ""), 
                    dados_pedido.get("pedido", ""), 
                    dados_pedido.get("endereco", ""), 
                    dados_pedido.get("pagamento", ""), 
                    dados_pedido.get("total", "")
                ]
                planilha_pedidos.append_row(nova_linha)
                print("✅ Sucesso: Pedido salvo na planilha do Google Sheets!")

                db.delete(f"chat:{numero_remetente}")
                print("🧹 Memória do cliente limpa para o próximo pedido futuro.")

            # Limpa o bloco JSON da resposta para o cliente não ver
            resposta = re.sub(r'\[JSON_PEDIDO\].*?\[/JSON_PEDIDO\]', '', resposta, flags=re.DOTALL).strip()

            # Limpa o bloco JSON da resposta para o cliente não ver
            resposta = re.sub(r'\[JSON_PEDIDO\].*?\[/JSON_PEDIDO\]', '', resposta, flags=re.DOTALL).strip()

        except Exception as e:
            print("❌ Erro ao tentar ler o JSON ou salvar na planilha:", e)

    print("Resposta enviada:", resposta)

    # 3. ENVIO ATIVO (Evita o Timeout do Twilio caso o Google Sheets demore)
    if client_twilio:
        try:
            client_twilio.messages.create(
                body=resposta[:1500],
                from_=numero_bot,
                to=numero_remetente
            )
        except Exception as e:
            print(f"ERRO API TWILIO: {e}")
    else:
        # Fallback de segurança se as chaves do Twilio não estiverem configuradas
        resp = MessagingResponse()
        resp.message(resposta[:1500])
        return Response(str(resp), mimetype="application/xml")

    # Retorna XML vazio instantaneamente para fechar a conexão do Webhook
    return Response(str(MessagingResponse()), mimetype="application/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)