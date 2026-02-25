import re
from bot import obter_resposta_ia, db

numero_teste = "whatsapp:+5511999999999"

print("🍔 Teste Local do Chef Burger iniciado! (Digite 'sair' para encerrar ou '/reset' para limpar a memória)\n")

while True:
    mensagem = input("Você: ")
    
    if mensagem.lower() == 'sair':
        break
    
    if mensagem.lower() == '/reset':
        db.delete(f"chat:{numero_teste}")
        print("Bot: Memória apagada! Começando do zero.\n")
        continue

    # Pega a resposta da IA
    resposta = obter_resposta_ia(mensagem, numero_teste)
    
    # ✂️ TESOURA: Esconde o JSON do terminal igual fazemos no WhatsApp
    resposta_limpa = re.sub(r'\[JSON_PEDIDO\].*?\[/JSON_PEDIDO\]', '', resposta, flags=re.DOTALL).strip()
    
    print(f"\nBot: {resposta_limpa}\n")