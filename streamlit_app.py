import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image 

# --- Configuração da Página Streamlit ---
# Título da aba do navegador e favicon podem ser ajustados aqui:
st.set_page_config(
    page_title="Assistente PME Pro", 
    layout="wide", 
    initial_sidebar_state="expanded",
    # page_icon="🚀"  # Exemplo de favicon com emoji, ou você pode usar uma URL para uma imagem .ico ou .png
)

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm_model_instance = None 

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Adicione sua GOOGLE_API_KEY aos Segredos do seu app no painel do Streamlit Community Cloud.")
    st.stop()
except FileNotFoundError: 
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") 
    if not GOOGLE_API_KEY:
        st.error("🚨 ERRO: Chave API não encontrada nos Segredos do Streamlit nem como variável de ambiente.")
        st.info("Configure GOOGLE_API_KEY nos Segredos do Streamlit Cloud ou defina como variável de ambiente local.")
        st.stop()

if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
    st.error("🚨 ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
    st.stop()
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                     temperature=0.75, 
                                     google_api_key=GOOGLE_API_KEY,
                                     convert_system_message_to_human=True)
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique sua chave API, se a 'Generative Language API' está ativa no Google Cloud e suas cotas.")
        st.stop()

# --- Classe do Agente (AssistentePMEPro) ---
class AssistentePMEPro:
    def __init__(self, llm_passed_model): 
        if llm_passed_model is None:
            st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
            st.stop()
        self.llm = llm_passed_model 
        
        self.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)
        self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True)

    def _criar_cadeia_simples(self, system_message_content, human_message_content_template="{solicitacao_usuario}"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            HumanMessagePromptTemplate.from_template(human_message_content_template)
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, verbose=False)

    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name=memory_key_placeholder), 
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital com IA (Guia Prático)")
        st.markdown("Bem-vindo! Preencha os campos abaixo para criarmos juntos uma estratégia de marketing digital eficaz usando IA.")
        with st.form(key='marketing_form_guiado_v9'): # Nova key
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar?", key="mdg_publico_v9")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?", key="mdg_produto_v9")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing?", ["", "Aumentar vendas online", "Gerar mais contatos (leads)", "Fortalecer o reconhecimento da marca", "Aumentar o engajamento"], key="mdg_objetivo_v9")
            st.markdown("---")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer comunicar?", key="mdg_mensagem_v9")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial?", key="mdg_diferencial_v9")
            st.markdown("---")
            descricao_imagem = st.text_input("6. Ideia para imagem (opcional):", key="mdg_img_v9")
            descricao_video = st.text_input("7. Ideia para vídeo (opcional):", key="mdg_video_v9")
            orcamento_ideia = st.text_input("8. Ideia de orçamento para esta ação (opcional):", key="mdg_orcamento_v9")
            redes_opcoes = { "Não tenho certeza, preciso de sugestão": "Sugestão da IA", "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok", "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp", "E-mail Marketing": "E-mail Marketing", "Google Ads/Meu Negócio": "Google", "Integrada": "Integrada"}
            rede_social_alvo_label = st.selectbox("9. Canal digital principal ou pedir sugestão?", options=list(redes_opcoes.keys()), key="mdg_canal_v9")
            rede_social_alvo = redes_opcoes[rede_social_alvo_label]
            submit_button = st.form_submit_button(label='Gerar Meu Guia de Marketing com IA 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial]):
                st.warning("Por favor, preencha os campos sobre Público, Produto/Serviço, Objetivo, Mensagem e Diferencial.")
            else:
                system_message_marketing = "Você é o \"Assistente PME Pro\", um consultor especialista em Marketing Digital com IA para pequenas empresas. Seu objetivo é guiar o usuário a criar uma estratégia de marketing digital eficaz, baseado nos melhores princípios de marketing (como os de Kotler) e nas capacidades da IA."
                prompt_llm_marketing = f"Um dono de pequena empresa preencheu o seguinte formulário para obter um guia prático para Marketing Digital com IA:\n- Público-Alvo: {publico_alvo}\n- Produto/Serviço Principal: {produto_servico}\n- Principal Diferencial: {diferencial}\n- Objetivo Principal com Marketing Digital: {objetivo_campanha}\n- Mensagem Chave: {mensagem_principal}\n- Ideia para Imagem (se houver): {descricao_imagem or 'Não especificado'}\n- Ideia para Vídeo (se houver): {descricao_video or 'Não especificado'}\n- Orçamento Estimado (se houver): {orcamento_ideia or 'Não especificado'}\n- Canal Digital em Mente ou Pedido de Sugestão: {rede_social_alvo}\n\nCom base nisso, forneça um GUIA ESTRATÉGICO E PRÁTICO, incluindo:\n1. Diagnóstico Rápido e Oportunidade com IA.\n2. Canal(is) Prioritário(s) (com justificativa se pedi sugestão, ou como otimizar o escolhido com IA).\n3. Estratégias de Conteúdo Inteligente: Tipos de conteúdo, como IA pode ajudar (ideias, rascunhos), 2 exemplos de TÍTULOS/POSTS para meu negócio.\n4. Ferramenta de IA Recomendada (Gratuita/Baixo Custo): UMA ferramenta e como ajudaria.\n5. Primeiros 3 Passos Acionáveis para usar IA no marketing.\n6. Métrica Chave de Sucesso Inicial.\nTom: Mentor experiente, prático, encorajador. Linguagem clara. Foco em plano inicial acionável."
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing... 💡"):
                    cadeia_mkt = self._criar_cadeia_simples(system_message_marketing)
                    resposta_llm = cadeia_mkt.run(solicitacao_usuario=prompt_llm_marketing)
                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios especialista em IA. Sua tarefa é ajudar um empreendedor a ESBOÇAR e depois DETALHAR um PLANO DE NEGÓCIOS. Você faz perguntas UMA DE CADA VEZ para coletar informações. Use linguagem clara e seja encorajador.\n\n**FLUXO DA CONVERSA:**\n\n**INÍCIO DA CONVERSA / PEDIDO INICIAL:**\nSe o usuário indicar que quer criar um plano de negócios (ex: \"Crie meu plano de negócios\", \"Quero ajuda com meu plano\", \"sim\" para um botão de iniciar plano), SUA PRIMEIRA PERGUNTA DEVE SER: \"Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?\"\n\n**COLETA PARA O ESBOÇO:**\nApós saber o ramo, continue fazendo UMA PERGUNTA POR VEZ para obter informações para as seguintes seções (não precisa ser exatamente nesta ordem, mas cubra-as):\n1.  Nome da Empresa\n2.  Missão da Empresa\n3.  Visão da Empresa\n4.  Principais Objetivos\n5.  Produtos/Serviços Principais\n6.  Público-Alvo Principal\n7.  Principal Diferencial\n8.  Ideias Iniciais de Marketing e Vendas\n9.  Ideias Iniciais de Operações\n10. Estimativas Financeiras Muito Básicas\n\n**GERAÇÃO DO ESBOÇO:**\nQuando você sentir que coletou informações suficientes para estas 10 áreas, VOCÊ DEVE PERGUNTAR:\n\"Com as informações que reunimos até agora, você gostaria que eu montasse um primeiro ESBOÇO do seu plano de negócios? Ele terá as seções principais que discutimos.\"\n\nSe o usuário disser \"sim\":\n    - Gere um ESBOÇO do plano de negócios com as seções: Sumário Executivo, Descrição da Empresa, Produtos e Serviços, Público-Alvo e Diferenciais, Estratégias Iniciais de Marketing e Vendas, Operações Iniciais, Panorama Financeiro Inicial.\n    - No final do esboço, ADICIONE: \"Este é um esboço inicial para organizar suas ideias. Ele pode ser muito mais detalhado e aprofundado.\"\n    - ENTÃO, PERGUNTE: \"Este esboço inicial te ajuda a visualizar melhor? Gostaria de DETALHAR este plano de negócios agora? Podemos aprofundar cada seção, e você poderá me fornecer mais informações (e no futuro, até mesmo subir documentos).\"\n\n**DETALHAMENTO DO PLANO (SE O USUÁRIO ACEITAR):**\nSe o usuário disser \"sim\" para detalhar:\n    - Responda com entusiasmo: \"Ótimo! Para detalharmos, vamos focar em cada seção do plano. Aplicaremos princípios de administração e marketing (como os de Chiavenato e Kotler) para enriquecer a análise.\"\n    - ENTÃO, PERGUNTE: \"Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? Por exemplo, 'Análise de Mercado', 'Estratégias de Marketing Detalhadas', ou 'Projeções Financeiras'?\"\n    - A partir da escolha, faça perguntas específicas para aquela seção."
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        system_message_precos = f"""
        Você é o "Assistente PME Pro", especialista em precificação com IA.
        Sua tarefa é ajudar o usuário a definir o preço de venda de um produto ou serviço, atuando como um consultor que busca as informações necessárias.
        Você faz perguntas UMA DE CADA VEZ e guia o usuário.
        {(f"Contexto da imagem que o usuário enviou: '{descricao_imagem_contexto}'. Considere esta informação ao falar sobre o produto.") if descricao_imagem_contexto else ""}

        **FLUXO DA CONVERSA PARA PRECIFICAR:**

        **1. PERGUNTA INICIAL (SEMPRE FAÇA ESTA PRIMEIRO QUANDO O USUÁRIO ENTRAR NESTA FUNCIONALIDADE):**
           "Olá! Sou o Assistente PME Pro, pronto para te ajudar com a precificação. Para começar, o produto ou serviço que você quer precificar é algo que você COMPRA E REVENDE, ou é algo que sua empresa MESMA PRODUZ/CRIA?"

        **2. SE O USUÁRIO ESCOLHER "COMPRA E REVENDE":**
           a. PERGUNTE: "Entendido, é para revenda. Qual é o nome ou tipo específico do produto que você revende?" (Ex: SSD Interno 1TB Western Digital Blue, Camiseta XYZ)
           b. PERGUNTE: "Qual o seu CUSTO DE AQUISIÇÃO por unidade deste produto? (Quanto você paga ao seu fornecedor por cada um)."
           c. PERGUNTE: "Em qual CIDADE e ESTADO (Ex: Juiz de Fora - MG) sua loja ou negócio principal opera? Isso nos ajudará a considerar o mercado."
           d. APÓS OBTER ESSAS INFORMAÇÕES, DIGA:
              "Ok, tenho as informações básicas: produto '[NOME DO PRODUTO INFORMADO PELO USUÁRIO]', seu custo de R$[VALOR DO CUSTO INFORMADO] em [CIDADE/ESTADO INFORMADO].
              Agora, o passo CRUCIAL é entendermos o preço de mercado. **Vou te ajudar a analisar os preços praticados para produtos similares na sua região.** (No futuro, este app poderá fazer buscas automáticas na web, mas por enquanto, vamos analisar juntos com base no seu conhecimento e no que eu posso inferir).
              Para termos um ponto de partida, qual MARGEM DE LUCRO (em porcentagem, ex: 20%, 50%, 100%) você gostaria de ter sobre o seu custo de R$[VALOR DO CUSTO INFORMADO]? Ou você já tem um PREÇO DE VENDA ALVO em mente?"
           e. QUANDO O USUÁRIO RESPONDER A MARGEM/PREÇO ALVO:
              - Calcule o preço de venda sugerido (Custo / (1 - %MargemDesejada/100)) ou (Custo * (1 + %MarkupDesejado/100)). Explique o cálculo de forma simples.
              - APRESENTE O PREÇO CALCULADO e diga: "Com base no seu custo e na margem desejada, o preço de venda sugerido seria R$ X.XX.
                Para validar este preço, sugiro que você pesquise em pelo menos 3-5 concorrentes online e locais. Compare este preço calculado com os preços praticados. Se estiver muito diferente, precisaremos ajustar a margem ou reanalisar os custos e a estratégia de precificação."
              - PERGUNTE: "Este preço inicial faz sentido? Quer simular com outra margem?"

        **3. SE O USUÁRIO ESCOLHER "PRODUZ/CRIA":**
           a. PERGUNTE: "Excelente! Para precificar seu produto/serviço próprio, vamos detalhar os custos. Qual o nome do produto ou tipo de serviço que você cria/oferece?"
           # ... (restante da lógica para PRODUZ/CRIA como antes) ...
           b. PERGUNTE sobre CUSTOS DIRETOS DE MATERIAL/INSUMOS: "Quais são os custos diretos de material ou insumos que você gasta para produzir UMA unidade do produto ou para realizar UMA vez o serviço? Por favor, liste os principais itens e seus custos."
           c. PERGUNTE sobre MÃO DE OBRA DIRETA: "Quanto tempo de trabalho (seu ou de funcionários) é gasto diretamente na produção de UMA unidade ou na prestação de UMA vez o serviço? E qual o custo estimado dessa mão de obra por unidade/serviço?"
           d. PERGUNTE sobre CUSTOS FIXOS MENSAIS TOTAIS: "Quais são seus custos fixOS mensais totais (aluguel, luz, internet, salários administrativos, etc.) que precisam ser cobertos?"
           e. PERGUNTE sobre VOLUME DE PRODUÇÃO/VENDAS MENSAL ESPERADO: "Quantas unidades desse produto você espera vender por mês, ou quantos serviços espera prestar? Isso nos ajudará a ratear os custos fixos por unidade."
           f. APÓS OBTER ESSAS INFORMAÇÕES, explique: "Com esses dados, podemos calcular o Custo Total Unitário. Depois, adicionaremos sua margem de lucro desejada. Existem métodos como Markup ou Margem de Contribuição que podemos usar."
           g. PERGUNTE: "Qual MARGEM DE LUCRO (em porcentagem) você gostaria de adicionar sobre o custo total de produção para definirmos o preço de venda?"
           h. QUANDO O USUÁRIO RESPONDER A MARGEM:
              - Calcule o preço de venda sugerido.
              - APRESENTE O PREÇO CALCULADO e diga: "Com base nos seus custos e na margem desejada, o preço de venda sugerido seria R$ X.XX."
              - PERGUNTE: "Este preço cobre todos os seus custos e te dá a lucratividade esperada? Como ele se compara ao que você imagina que o mercado pagaria?"

        **FINALIZAÇÃO DA INTERAÇÃO (PARA AMBOS OS CASOS):**
        - Após uma sugestão de preço, sempre ofereça: "Podemos refinar este cálculo, simular outros cenários ou discutir estratégias de precificação com base nos princípios de marketing de Kotler?"

        Mantenha a conversa fluida e profissional, mas acessível. O objetivo é entregar o 'bolo pronto com a velinha', ou seja, uma análise e sugestão de preço fundamentada.
        """
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        system_message_ideias = f"""
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA, com foco em INOVAÇÃO e SOLUÇÃO DE PROBLEMAS.
        Sua tarefa é ajudar empreendedores a gerar ideias criativas e práticas para seus negócios, seja para resolver dores, encontrar novas oportunidades ou inovar.
        Você faz perguntas UMA DE CADA VEZ para entender o contexto do usuário.
        {(f"INFORMAÇÃO ADICIONAL FORNECIDA PELO USUÁRIO (pode ser de arquivos que ele carregou): '{contexto_arquivos}'. Por favor, CONSIDERE esta informação ao interagir e gerar ideias. Se for um arquivo de texto, use o conteúdo. Se for uma imagem, peça ao usuário para descrever como ela se relaciona com o desafio dele.") if contexto_arquivos else ""}

        **FLUXO DA CONVERSA:**

        **INÍCIO DA CONVERSA / PEDIDO INICIAL:**
        - Se o usuário indicar que quer ideias (ex: "Preciso de ideias para aumentar vendas", "Estou com dificuldade em X", "Como posso inovar meu serviço Y?") ou simplesmente iniciar a conversa nesta seção,
          SUA PRIMEIRA PERGUNTA DEVE SER (de forma empática e aberta): "Olá! Que bom que você quer explorar novas ideias. {('Recebi as informações dos arquivos que você carregou. ' if contexto_arquivos else 'Você também pode carregar arquivos de texto ou imagens se achar que ajudam a dar contexto. ')} Para que eu possa te ajudar da melhor forma, conte-me um pouco mais sobre o principal desafio que você está enfrentando, a dor que sente no seu negócio, ou a área específica em que você gostaria de inovar ou receber sugestões."

        **EXPLORAÇÃO DO PROBLEMA/OPORTUNIDADE (SE NECESSÁRIO):**
        - Após a primeira descrição do usuário, se precisar de mais clareza (e considerando o contexto de arquivos, se houver), faça UMA ou DUAS perguntas abertas para aprofundar, como:
            - "Interessante. Para eu entender melhor a dimensão disso, [faça uma pergunta específica sobre o que ele disse ou o contexto do arquivo]?"
            - "Quais são os principais obstáculos ou dificuldades que você enfrenta atualmente em relação a isso?"
        - Após o usuário responder, ou se ele já deu um bom contexto (especialmente se forneceu arquivos), diga:
          "Entendido. Com base no que você me contou sobre [resuma brevemente o problema/dor/objetivo do usuário, mencionando se informações de arquivos foram consideradas], vou gerar algumas ideias e sugestões para você, aplicando princípios de marketing e administração para encontrar soluções eficazes."
        - ENTÃO, gere de 3 a 5 ideias ou abordagens distintas e criativas. Para cada ideia:
            a. Dê um **Nome ou Título Curto e Chamativo**.
            b. **Descreva a Ideia:** Explique o conceito de forma clara e concisa (1-3 frases).
            c. **Benefício Principal:** Destaque o principal benefício ou solução que essa ideia traria.
            d. **Primeiro Passo Simples (Opcional, mas bom):** Se apropriado, sugira um primeiro passo muito pequeno e prático que o usuário poderia dar para começar a explorar essa ideia.

        **DISCUSSÃO E REFINAMENTO:**
        - Após apresentar as ideias, PERGUNTE: "O que você achou dessas primeiras sugestões? Alguma delas te inspira ou parece particularmente promissora para o seu caso? Gostaria de explorar alguma delas com mais detalhes, ou talvez refinar o foco para gerarmos mais alternativas?"
        """
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

# --- Funções Utilitárias de Chat ---
def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state:
        st.session_state[chat_display_key] = []
    
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
    
    if area_chave == "calculo_precos":
        st.session_state.last_uploaded_image_info_pricing = None
        st.session_state.processed_image_id_pricing = None
    elif area_chave == "gerador_ideias":
        st.session_state.uploaded_file_info_ideias_for_prompt = None 
        st.session_state.processed_file_id_ideias = None


def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state: 
        st.session_state[chat_display_key] = []

    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]):
            st.markdown(msg_info["content"])
    
    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v5") 

    if prompt_usuario:
        st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"):
            st.markdown(prompt_usuario)
        
        if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing = True
        elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias = True

        with st.spinner("Assistente PME Pro está processando... 🤔"):
            resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
        
        st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
        st.rerun()

# --- Interface Principal Streamlit ---
if llm_model_instance:
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
    agente = st.session_state.agente_pme

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100) 
    st.sidebar.title("Assistente PME Pro") 
    st.sidebar.markdown("IA para seu Negócio Decolar!")
    st.sidebar.markdown("---")

    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Marketing Digital com IA (Guia)": "marketing_guiado",
        "Elaborar Plano de Negócios com IA": "plano_negocios",
        "Cálculo de Preços Inteligente": "calculo_precos",
        "Gerador de Ideias para Negócios": "gerador_ideias" 
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    for nome_menu_init, chave_secao_init in opcoes_menu.items():
        if chave_secao_init and f"chat_display_{chave_secao_init}" not in st.session_state:
            st.session_state[f"chat_display_{chave_secao_init}"] = []
    
    if 'start_marketing_form' not in st.session_state: st.session_state.start_marketing_form = False
    if 'last_uploaded_image_info_pricing' not in st.session_state: st.session_state.last_uploaded_image_info_pricing = None
    if 'processed_image_id_pricing' not in st.session_state: st.session_state.processed_image_id_pricing = None
    if 'user_input_processed_pricing' not in st.session_state: st.session_state.user_input_processed_pricing = False
    
    if 'uploaded_file_info_ideias_for_prompt' not in st.session_state: st.session_state.uploaded_file_info_ideias_for_prompt = None 
    if 'processed_file_id_ideias' not in st.session_state: st.session_state.processed_file_id_ideias = None
    if 'user_input_processed_ideias' not in st.session_state: st.session_state.user_input_processed_ideias = False


    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v16', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        chave_secao_nav = opcoes_menu.get(st.session_state.area_selecionada)
        
        if st.session_state.area_selecionada != "Cálculo de Preços Inteligente":
            st.session_state.last_uploaded_image_info_pricing = None
            st.session_state.processed_image_id_pricing = None
        if st.session_state.area_selecionada != "Gerador de Ideias para Negócios": 
            st.session_state.uploaded_file_info_ideias_for_prompt = None
            st.session_state.processed_file_id_ideias = None
        
        if chave_secao_nav == "marketing_guiado":
            st.session_state.start_marketing_form = False
        elif chave_secao_nav and chave_secao_nav != "pagina_inicial": 
            chat_display_key_nav = f"chat_display_{chave_secao_nav}"
            if not st.session_state.get(chat_display_key_nav, []): 
                msg_inicial_nav = ""
                memoria_agente_nav = None # Inicializa como None
                if chave_secao_nav == "plano_negocios":
                    msg_inicial_nav = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                    memoria_agente_nav = agente.memoria_plano_negocios
                elif chave_secao_nav == "calculo_precos":
                    msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
                    memoria_agente_nav = agente.memoria_calculo_precos
                elif chave_secao_nav == "gerador_ideias":
                    msg_inicial_nav = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
                    memoria_agente_nav = agente.memoria_gerador_ideias
                
                if msg_inicial_nav and memoria_agente_nav: # Garante que memoria_agente_nav não é None
                    inicializar_ou_resetar_chat(chave_secao_nav, msg_inicial_nav, memoria_agente_nav)
        st.rerun()

    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    if current_section_key == "pagina_inicial":
        # >>>>> LINHA QUE VOCÊ PEDIU PARA ALTERAR <<<<<
        st.title("🚀 Bem-vindo ao seu Assistente PME Pro!") 
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        st.markdown("Use o menu à esquerda para explorar as ferramentas disponíveis.")
        st.markdown("---")
        
        num_botoes_funcionais = len(opcoes_menu) -1 
        if num_botoes_funcionais > 0 :
            num_cols_render = min(num_botoes_funcionais, 3) 
            cols_botoes_pg_inicial = st.columns(num_cols_render)
            
            btn_idx_pg_inicial = 0
            for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                if chave_secao_btn_pg != "pagina_inicial":
                    col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render] 
                    button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" para ")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" (Guia)","").replace(" (Criar Campanha)","")
                    if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v9", use_container_width=True): # Nova key
                        st.session_state.area_selecionada = nome_menu_btn_pg
                        if chave_secao_btn_pg == "marketing_guiado":
                            st.session_state.start_marketing_form = False
                        else: 
                            chat_display_key_btn_pg = f"chat_display_{chave_secao_btn_pg}"
                            if not st.session_state.get(chat_display_key_btn_pg,[]):
                                msg_inicial_btn_pg = ""
                                memoria_agente_btn_pg = None
                                if chave_secao_btn_pg == "plano_negocios": 
                                    msg_inicial_btn_pg = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                                    memoria_agente_btn_pg = agente.memoria_plano_negocios
                                elif chave_secao_btn_pg == "calculo_precos": 
                                    msg_inicial_btn_pg = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
                                    memoria_agente_btn_pg = agente.memoria_calculo_precos
                                elif chave_secao_btn_pg == "gerador_ideias": 
                                    msg_inicial_btn_pg = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
                                    memoria_agente_btn_pg = agente.memoria_gerador_ideias
                                if msg_inicial_btn_pg and memoria_agente_btn_pg:
                                    inicializar_ou_resetar_chat(chave_secao_btn_pg, msg_inicial_btn_pg, memoria_agente_btn_pg)
                        st.rerun()
                    btn_idx_pg_inicial +=1
            st.balloons()

    elif current_section_key == "marketing_guiado":
        agente.marketing_digital_guiado()

    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")
        if not st.session_state.get(f"chat_display_{current_section_key}", []):
            inicializar_ou_resetar_chat(current_section_key, "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!", agente.memoria_plano_negocios)
        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou diga 'Crie meu plano de negócios'", agente.conversar_plano_de_negocios)
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v7"): 
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar seu plano de negócios! Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!", agente.memoria_plano_negocios)
            st.rerun()

    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Vamos definir os melhores preços para seus produtos ou serviços!")
        if not st.session_state.get(f"chat_display_{current_section_key}", []):
            inicializar_ou_resetar_chat(current_section_key, "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?", agente.memoria_calculo_precos)
        
        uploaded_image = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v7")
        descricao_imagem_para_ia = None # Será preenchida se uma imagem for carregada
        if uploaded_image is not None:
            # Apenas processa a imagem e define a descrição se for uma nova imagem
            if st.session_state.get('processed_image_id_pricing') != uploaded_image.id:
                try:
                    st.image(Image.open(uploaded_image), caption=f"Imagem: {uploaded_image.name}", width=150)
                    # Prepara a descrição para ser usada no kwargs da função de chat
                    descricao_imagem_para_ia = f"O usuário carregou uma imagem chamada '{uploaded_image.name}'. Considere esta informação."
                    st.session_state.last_uploaded_image_info_pricing = descricao_imagem_para_ia
                    st.session_state.processed_image_id_pricing = uploaded_image.id 
                    st.info(f"Imagem '{uploaded_image.name}' pronta para ser considerada no próximo diálogo.")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {e}")
                    st.session_state.last_uploaded_image_info_pricing = None # Limpa em caso de erro
                    st.session_state.processed_image_id_pricing = None
        
        kwargs_preco_chat = {}
        # Usa a informação da imagem que acabou de ser processada ou a que estava no session_state
        contexto_imagem_ativo = descricao_imagem_para_ia or st.session_state.get('last_uploaded_image_info_pricing')
        if contexto_imagem_ativo:
             kwargs_preco_chat['descricao_imagem_contexto'] = contexto_imagem_ativo
        
        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou descreva o produto/serviço", agente.calcular_precos_interativo, **kwargs_preco_chat)
        
        # Se um input do usuário foi processado e havia informação de imagem, ela foi "consumida"
        if 'user_input_processed_pricing' in st.session_state and st.session_state.user_input_processed_pricing:
            if st.session_state.get('last_uploaded_image_info_pricing'): # Se a info da imagem foi usada
                 st.session_state.last_uploaded_image_info_pricing = None # Limpa para não usar no próximo input automaticamente
            st.session_state.user_input_processed_pricing = False 

        if st.sidebar.button("Reiniciar Cálculo de Preços", key="btn_reset_precos_v8"): # Nova key
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar um novo cálculo de preços! Você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?", agente.memoria_calculo_precos)
            st.rerun()

    elif current_section_key == "gerador_ideias": 
        st.header("💡 Gerador de Ideias para seu Negócio com IA")
        st.caption("Descreva seus desafios ou áreas onde busca inovação, e vamos encontrar soluções juntos!")
        
        if not st.session_state.get(f"chat_display_{current_section_key}", []): 
            inicializar_ou_resetar_chat(current_section_key, "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar.", agente.memoria_gerador_ideias)

        uploaded_files_ideias_ui = st.file_uploader(
            "Envie arquivos com informações (.txt, .png, .jpg):",
            type=["txt", "png", "jpg", "jpeg"], 
            accept_multiple_files=True, 
            key="ideias_file_uploader_v3" 
        )
        
        contexto_para_ia_ideias = None 
        if uploaded_files_ideias_ui:
            current_file_ids_ui = sorted([f.id for f in uploaded_files_ideias_ui])
            # Processa os arquivos somente se forem diferentes dos já processados ou se o contexto ainda não foi preparado para o prompt
            if st.session_state.get('processed_file_id_ideias') != current_file_ids_ui or not st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                text_contents_ui = []
                image_info_ui = []
                for uploaded_file_item in uploaded_files_ideias_ui:
                    try:
                        if uploaded_file_item.type == "text/plain":
                            file_content_ui = uploaded_file_item.read().decode("utf-8")
                            text_contents_ui.append(f"Conteúdo do arquivo de texto '{uploaded_file_item.name}':\n{file_content_ui[:1500]}...") 
                        elif uploaded_file_item.type in ["image/png", "image/jpeg"]:
                            st.image(Image.open(uploaded_file_item), caption=f"Imagem: {uploaded_file_item.name}", width=100)
                            image_info_ui.append(f"O usuário também carregou uma imagem chamada '{uploaded_file_item.name}'.")
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo '{uploaded_file_item.name}': {e}")
                
                full_context_ui = ""
                if text_contents_ui: full_context_ui += "\n\n--- CONTEÚDO DE ARQUIVOS DE TEXTO ---\n" + "\n\n".join(text_contents_ui)
                if image_info_ui: full_context_ui += "\n\n--- INFORMAÇÃO SOBRE IMAGENS CARREGADAS ---\n" + "\n".join(image_info_ui)
                
                if full_context_ui:
                    st.session_state.uploaded_file_info_ideias_for_prompt = full_context_ui.strip()
                    st.info("Arquivo(s) pronto(s) para serem considerados no próximo diálogo.")
                else: # Se nenhum arquivo foi processado com sucesso mas houve tentativa de upload
                    st.session_state.uploaded_file_info_ideias_for_prompt = None

                st.session_state.processed_file_id_ideias = current_file_ids_ui
        
        kwargs_ideias_chat_ui = {}
        # Passa o contexto dos arquivos se ele existir no session_state
        if st.session_state.get('uploaded_file_info_ideias_for_prompt'):
            kwargs_ideias_chat_ui['contexto_arquivos'] = st.session_state.uploaded_file_info_ideias_for_prompt
        
        exibir_chat_e_obter_input(current_section_key, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat_ui)
        
        # Limpa o contexto do arquivo APÓS ter sido potencialmente usado pela IA na chamada acima
        if 'user_input_processed_ideias' in st.session_state and st.session_state.user_input_processed_ideias:
            if st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                st.session_state.uploaded_file_info_ideias_for_prompt = None 
            st.session_state.user_input_processed_ideias = False
        
        if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v4"): 
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar uma nova busca por ideias! Conte-me sobre um novo desafio, dor ou área para inovar.", agente.memoria_gerador_ideias)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
# >>>>> LINHA QUE VOCÊ QUERIA ALTERAR (abaixo) <<<<<
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google") # TEXTO ALTERADO
