# Atendente Virtual com IA para WhatsApp

Um sistema completo de automação de atendimento e vendas para pizzarias, lanchonetes e delivery, operando 100% via WhatsApp. Diferente de chatbots tradicionais de "árvore de decisão", este bot utiliza Inteligência Artificial Generativa para conduzir uma conversa fluida, natural e inteligente com o cliente.

## 🚀 O Problema Resolvido
Donos de delivery perdem muito tempo (e pedidos) com o atendimento manual no WhatsApp, especialmente em horários de pico. Este MVP (Produto Mínimo Viável) automatiza todo o funil de vendas:
1. Recebe o cliente e envia o cardápio.
2. Entende pedidos complexos em linguagem natural (ex: "Quero uma meia calabresa e meia marguerita grande sem cebola").
3. Calcula os valores totais, incluindo taxas de entrega e lógicas de preço (cobra pelo sabor mais caro).
4. Coleta endereço e forma de pagamento.
5. **Salva o pedido finalizado automaticamente em uma planilha do Google Sheets** para a cozinha preparar.

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python & Flask
* **Inteligência Artificial:** Groq API (Modelo Llama 3 8b)
* **Integração WhatsApp:** Twilio API (Webhooks)
* **Banco de Dados (Memória):** Redis (Gestão de contexto de sessão)
* **Integração de Planilhas:** Google Sheets API (`gspread` + `oauth2client`)
* **Deploy:** Railway (PaaS)

## ✨ Funcionalidades Principais

* **🤖 Conversa Humanizada:** A IA entende o contexto, gírias e intenções, permitindo que o cliente faça o pedido de forma orgânica.
* **🧠 Memória de Sessão (Redis):** O bot "lembra" do que o cliente pediu nas mensagens anteriores durante a mesma sessão.
* **🛒 Lógica de Vendas Avançada:** O sistema foi instruído a fazer *upsell* (oferecer bebidas ou mais pizzas) e calcular regras de negócio específicas (tamanho único para pizza meia a meia, regra do sabor mais caro).
* **📝 Integração Invisível (JSON):** Quando o pedido é fechado, a IA gera silenciosamente um payload JSON que o backend Python intercepta e injeta no Google Sheets da cozinha em tempo real.
* **🛡️ Blindagem Anti-Hacker (Prompt Injection):** Regras rigorosas de sistema impedem que usuários mal-intencionados façam a IA revelar seu código-fonte, prompt ou se comportar de forma indesejada.

## ⚙️ Como executar o projeto localmente

### 1. Pré-requisitos
- Python 3.9+
- Conta no [Twilio](https://www.twilio.com/) (WhatsApp Sandbox)
- Conta na [Groq Cloud](https://console.groq.com/) (Para a chave da API Llama 3)
- Banco de Dados Redis (Pode ser local ou cloud via Upstash/Railway)
- Conta de Serviço do Google Cloud (Arquivo JSON de credenciais)

### 2. Instalação

Clone o repositório:
```bash
git clone [https://github.com/Heitorcgq/Bot-de-Whatsapp.git](https://github.com/Heitorcgq/Bot-de-Whatsapp.git)
cd Bot-de-Whatsapp
```

Desenvolvido por Heitor - Bot de Whatsapp
