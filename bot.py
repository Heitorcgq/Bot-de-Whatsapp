import os
import json
import redis
from flask import Flask, request, Response
from groq import Groq
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
api_key_groq = os.getenv("GROQ_API_KEY")
url_redis = os.getenv("REDIS_URL")

if not api_key_groq or not url_redis:
    raise ValueError("ERRO: Faltam chaves no arquivo .env!")

client = Groq(api_key=api_key_groq)

try:
    db = redis.from_url(url_redis, decode_responses=True, ssl_cert_reqs=None)
    print("Redis ping:", db.ping())
    print("GROQ:", api_key_groq)
    print("REDIS:", url_redis)

except Exception as e:
    print(f"Erro Crítico no Redis: {e}")


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

{cardapio_pizzaria}

📋 DADOS OPERACIONAIS (USE ESTES DADOS REAIS):
- Taxa de entrega: R$ 8,00 fixa.
- Horário: Terça a Domingo, 18h às 23h.
- Regra de Preço (Meia a Meia): Cobra-se pelo valor da sabor mais caro.
- Pizzas Doces: VENDEMOS APENAS NO TAMANHO BROTO.
- CHAVE PIX: CNPJ 12.345.678/0001-99 (Nome: Bella Napoli Ltda).

🛑 PROTOCOLO DE ATENDIMENTO (SIGA ESTA ORDEM RIGOROSAMENTE):

Fase 1: Saudação e Cardápio
- Primeira mensagem: Apresente-se e mande o cardápio (só nomes e preços).
- Pergunte: "Algum sabor te agradou ou quer uma sugestão?"

Fase 2: A Definição da Pizza
- Se o cliente pedir sabor salgado, PERGUNTE: "Vai querer ela **inteira** ou **meia a meia**?"
- Se for meia a meia: Pergunte o 2º sabor e o tamanho (Média/Grande).
- Se for inteira: Pergunte o tamanho.
- Pizza Doce: Só existe tamanho Broto.

Fase 3: Expansão do Pedido (Venda Adicional)
- Assim que a pizza for definida, você DEVE perguntar:
  "Deseja incluir MAIS UMA pizza 🍕 no pedido? Ou vamos para as bebidas?"
- Se o cliente quiser mais pizza: Volte para a Fase 2.
- Se o cliente quiser bebida: Ofereça Coca-Cola, Guaraná ou Suco.

Fase 4: Fechamento (Endereço e Pagamento)
- IMPORTANTE: Só avance para esta fase se o cliente disser que NÃO quer mais nada.
- 1º: Peça o ENDEREÇO COMPLETO (Rua, Número e Bairro). NÃO INVENTE ENDEREÇO. Se o cliente não der, peça de novo.
- 2º: Peça a Forma de Pagamento (Pix, Cartão ou Dinheiro).
  - Se for Pix: Envie a CHAVE PIX que está nos Dados Operacionais acima.
  - Se for Dinheiro: Pergunte do troco.

Fase 5: Resumo e Confirmação
- Só envie o resumo se você JÁ TIVER o endereço e a forma de pagamento definidos.
- Resumo:
  [Lista de Itens]
  Entrega: R$ 8,00
  TOTAL: R$ XX,XX
  Endereço de Entrega: [Insira o endereço que o cliente informou]
- Pergunte: "Tudo certo? Posso mandar preparar?"

⚠️ REGRAS DE OURO:
1. NUNCA invente endereços (como "Rua Exemplo"). Se não souber o endereço, pergunte ao cliente.
2. NUNCA invente códigos Pix aleatórios ou use placeholders como "[insira código]". Use a chave que está nos DADOS OPERACIONAIS.
3. Se o cliente falar só "Quero pizza", pergunte o sabor.
4. Nunca assuma o tamanho da pizza, sempre pergunte.
"""

def gerenciar_memoria(numero_telefone, nova_mensagem=None, papel="user"):
    """
    Função inteligente que cuida do Redis.
    Ela busca o histórico, atualiza e salva com validade de 1 hora.
    """
    # CHAVE ÚNICA: O número do telefone é a chave do cofre no Redis
    chave_redis = f"chat:{numero_telefone}"
    
    # 1. Tenta pegar o histórico antigo no Redis
    historico_json = db.get(chave_redis)
    
    if historico_json:
        # Se existe, transforma de Texto para Lista Python
        historico = json.loads(historico_json)
    else:
        # Se não existe (primeira vez), cria lista vazia
        historico = []

    # 2. Se tiver mensagem nova para adicionar
    if nova_mensagem:
        historico.append({"role": papel, "content": nova_mensagem})
        
        # 3. Salva de volta no Redis
        db.set(chave_redis, json.dumps(historico), ex=3600)
    
    return historico

def obter_resposta_ia(mensagem_usuario, numero_telefone):
    try:
        # 1. Adiciona msg do usuário na memória do Redis
        historico_atualizado = gerenciar_memoria(numero_telefone, mensagem_usuario, "user")

        # 2. Monta o pacote para a IA
        mensagens_para_enviar = [
            {"role": "system", "content": prompt_sistema}
        ] + historico_atualizado

        # 3. Chama a IA
        chat_completion = client.chat.completions.create(
            messages=mensagens_para_enviar,
            model="llama-3.1-8b-instant",
            temperature=0.5,
        )
        
        resposta_ia = chat_completion.choices[0].message.content
        
        # 4. Salva a resposta da IA na memória do Redis
        gerenciar_memoria(numero_telefone, resposta_ia, "assistant")
        
        return resposta_ia

    except Exception as e:
        print("ERRO GROQ:", e)
    return "Desculpe, tivemos um erro interno."
@app.route("/bot", methods=['POST'])
def bot():
    msg_recebida = request.values.get('Body', '').strip()
    numero_remetente = request.values.get('From', '')
    
    # Comando de Reset Manual
    if msg_recebida.lower() == "/reset":
        db.delete(f"chat:{numero_remetente}")
        resp = MessagingResponse()
        resp.message("Memória apagada! Começando do zero.")
        return str(resp)

    resposta = obter_resposta_ia(msg_recebida, numero_remetente)

    if not resposta:
        resposta = "Desculpe, estou com instabilidade agora. Pode repetir?"

    resp = MessagingResponse()
    print("Resposta enviada:", resposta)
    
    # Limita o tamanho para evitar erro de limite do WhatsApp (1600 caracteres)
    resp.message(resposta[:1500])

    # --- AQUI ESTÁ O PULO DO GATO ---
    # Forçamos o Flask a dizer: "Isso é um XML, Twilio!"
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)