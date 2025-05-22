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
st.set_page_config(page_title="Assistente PME Pro", layout="wide", initial_sidebar_state="expanded")

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
                                     temperature=0.75, # Um pouco mais de criatividade para ideias
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
        self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True) # Nova memória

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
        # ... (código da função marketing_digital_guiado como na versão anterior - INALTERADO)
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Preencha os campos abaixo para criarmos juntos uma estratégia de marketing digital eficaz usando IA.")
        with st.form(key='marketing_form_guiado_v7'): # Mantendo keys únicas
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar?", key="mdg_publico_v7")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?", key="mdg_produto_v7")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing?", ["", "Aumentar vendas online", "Gerar mais contatos (leads)", "Fortalecer o reconhecimento da marca", "Aumentar o engajamento"], key="mdg_objetivo_v7")
            st.markdown("---")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer comunicar?", key="mdg_mensagem_v7")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial?", key="mdg_diferencial_v7")
            st.markdown("---")
            descricao_imagem = st.text_input("6. Ideia para imagem (opcional):", key="mdg_img_v7")
            descricao_video = st.text_input("7. Ideia para vídeo (opcional):", key="mdg_video_v7")
            orcamento_ideia = st.text_input("8. Ideia de orçamento para esta ação (opcional):", key="mdg_orcamento_v7")
            redes_opcoes = { "Não tenho certeza, preciso de sugestão": "Sugestão da IA", "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok", "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp", "E-mail Marketing": "E-mail Marketing", "Google Ads/Meu Negócio": "Google", "Integrada": "Integrada"}
            rede_social_alvo_label = st.selectbox("9. Canal digital principal ou pedir sugestão?", options=list(redes_opcoes.keys()), key="mdg_canal_v7")
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
        # ... (código da função conversar_plano_de_negocios como na versão anterior - INALTERADO)
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios especialista em IA. Sua tarefa é ajudar um empreendedor a ESBOÇAR e depois DETALHAR um PLANO DE NEGÓCIOS. Você faz perguntas UMA DE CADA VEZ para coletar informações. Use linguagem clara e seja encorajador.\n\n**FLUXO DA CONVERSA:**\n\n**INÍCIO DA CONVERSA / PEDIDO INICIAL:**\nSe o usuário indicar que quer criar um plano de negócios (ex: \"Crie meu plano de negócios\", \"Quero ajuda com meu plano\", \"sim\" para um botão de iniciar plano), SUA PRIMEIRA PERGUNTA DEVE SER: \"Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?\"\n\n**COLETA PARA O ESBOÇO:**\nApós saber o ramo, continue fazendo UMA PERGUNTA POR VEZ para obter informações para as seguintes seções (não precisa ser exatamente nesta ordem, mas cubra-as):\n1.  Nome da Empresa\n2.  Missão da Empresa\n3.  Visão da Empresa\n4.  Principais Objetivos\n5.  Produtos/Serviços Principais\n6.  Público-Alvo Principal\n7.  Principal Diferencial\n8.  Ideias Iniciais de Marketing e Vendas\n9.  Ideias Iniciais de Operações\n10. Estimativas Financeiras Muito Básicas\n\n**GERAÇÃO DO ESBOÇO:**\nQuando você sentir que coletou informações suficientes para estas 10 áreas, VOCÊ DEVE PERGUNTAR:\n\"Com as informações que reunimos até agora, você gostaria que eu montasse um primeiro ESBOÇO do seu plano de negócios? Ele terá as seções principais que discutimos.\"\n\nSe o usuário disser \"sim\":\n    - Gere um ESBOÇO do plano de negócios com as seções: Sumário Executivo, Descrição da Empresa, Produtos e Serviços, Público-Alvo e Diferenciais, Estratégias Iniciais de Marketing e Vendas, Operações Iniciais, Panorama Financeiro Inicial.\n    - No final do esboço, ADICIONE: \"Este é um esboço inicial para organizar suas ideias. Ele pode ser muito mais detalhado e aprofundado.\"\n    - ENTÃO, PERGUNTE: \"Este esboço inicial te ajuda a visualizar melhor? Gostaria de DETALHAR este plano de negócios agora? Podemos aprofundar cada seção, e você poderá me fornecer mais informações (e no futuro, até mesmo subir documentos).\"\n\n**DETALHAMENTO DO PLANO (SE O USUÁRIO ACEITAR):**\nSe o usuário disser \"sim\" para detalhar:\n    - Responda com entusiasmo: \"Ótimo! Para detalharmos, vamos focar em cada seção do plano. Aplicaremos princípios de administração e marketing (como os de Chiavenato e Kotler) para enriquecer a análise.\"\n    - ENTÃO, PERGUNTE: \"Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? Por exemplo, 'Análise de Mercado', 'Estratégias de Marketing Detalhadas', ou 'Projeções Financeiras'?\"\n    - A partir da escolha, faça perguntas específicas para aquela seção."
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        # ... (código da função calcular_precos_interativo como na versão anterior - INALTERADO)
        system_message_precos = f"Você é o \"Assistente PME Pro\", especialista em precificação com IA. Sua tarefa é ajudar o usuário a definir o preço de venda de um produto ou serviço, atuando como um consultor que busca as informações necessárias. Você faz perguntas UMA DE CADA VEZ e guia o usuário.\n{(f'Contexto da imagem que o usuário enviou: \'{descricao_imagem_contexto}\'. Use isso se for relevante para identificar o produto.') if descricao_imagem_contexto else ''}\n\n**FLUXO DA CONVERSA PARA PRECIFICAR:**\n\n**1. PERGUNTA INICIAL (SEMPRE FAÇA ESTA PRIMEIRO QUANDO O USUÁRIO ENTRAR NESTA FUNCIONALIDADE):**\n   \"Olá! Sou o Assistente PME Pro, pronto para te ajudar com a precificação. Para começar, o produto ou serviço que você quer precificar é algo que você COMPRA E REVENDE, ou é algo que sua empresa MESMA PRODUZ/CRIA?\"\n\n**2. SE O USUÁRIO ESCOLHER \"COMPRA E REVENDE\":**\n   a. PERGUNTE: \"Entendido, é para revenda. Qual é o nome ou tipo específico do produto que você revende?\" (Ex: SSD Interno 1TB Western Digital Blue, Camiseta XYZ)\n   b. PERGUNTE: \"Qual o seu CUSTO DE AQUISIÇÃO por unidade deste produto? (Quanto você paga ao seu fornecedor por cada um).\"\n   c. PERGUNTE: \"Em qual CIDADE e ESTADO (Ex: Juiz de Fora - MG) sua loja ou negócio principal opera? Isso nos ajudará a considerar o mercado.\"\n   d. APÓS OBTER ESSAS INFORMAÇÕES, DIGA (simulando a preparação para a busca):\n      \"Ok, tenho as informações básicas: produto '{{nome_do_produto_informado}}', seu custo de R${{custo_informado}} em {{cidade_estado_informado}}.\n      Agora, o passo CRUCIAL é entendermos o preço de mercado. **Estou preparando para fazer uma análise de preços praticados para produtos similares na sua região.** (No futuro, esta será uma busca real na web).\n      Enquanto eu 'analiso' o mercado (o que farei com base no meu conhecimento geral por enquanto), para adiantarmos: Qual MARGEM DE LUCRO (em porcentagem, ex: 20%, 50%, 100%) você gostaria de ter sobre o seu custo de R${{custo_informado}}? Ou você já tem um PREÇO DE VENDA ALVO em mente?\"\n   e. QUANDO O USUÁRIO RESPONDER A MARGEM/PREÇO ALVO:\n      - Calcule o preço de venda sugerido (Custo / (1 - %MargemDesejada)) ou (Custo + (Custo * %MarkupDesejado)). Explique o cálculo de forma simples.\n      - APRESENTE O PREÇO CALCULADO e diga: \"Com base no seu custo e na margem desejada, o preço de venda seria R$ X.XX.\n        Lembre-se: após você fazer sua pesquisa de mercado real (sugiro buscar em 3-5 concorrentes online e locais), compare este preço calculado com os preços praticados. Se estiver muito diferente, precisaremos ajustar a margem ou analisar os custos.\"\n      - PERGUNTE: \"Este preço inicial faz sentido? Quer simular com outra margem?\"\n\n**3. SE O USUÁRIO ESCOLHER \"PRODUZ/CRIA\":**\n   a. PERGUNTE: \"Excelente! Para precificar seu produto/serviço próprio, vamos detalhar os custos. Qual o nome do produto ou tipo de serviço que você cria/oferece?\"\n   b. PERGUNTE sobre CUSTOS DIRETOS DE MATERIAL/INSUMOS: \"Quais são os custos diretos de material ou insumos que você gasta para produzir UMA unidade do produto ou para realizar UMA vez o serviço? Por favor, liste os principais itens e seus custos.\"\n   c. PERGUNTE sobre MÃO DE OBRA DIRETA: \"Quanto tempo de trabalho (seu ou de funcionários) é gasto diretamente na produção de UMA unidade ou na prestação de UMA vez o serviço? E qual o custo estimado dessa mão de obra por unidade/serviço?\"\n   d. PERGUNTE sobre CUSTOS FIXOS MENSAIS TOTAIS: \"Quais são seus custos fixOS mensais totais (aluguel, luz, internet, salários administrativos, etc.) que precisam ser cobertos?\"\n   e. PERGUNTE sobre VOLUME DE PRODUÇÃO/VENDAS MENSAL ESPERADO: \"Quantas unidades desse produto você espera vender por mês, ou quantos serviços espera prestar? Isso nos ajudará a ratear os custos fixos por unidade.\"\n   f. APÓS OBTER ESSAS INFORMAÇÕES, explique: \"Com esses dados, podemos calcular o Custo Total Unitário. Depois, adicionaremos sua margem de lucro desejada. Existem métodos como Markup ou Margem de Contribuição que podemos usar.\"\n   g. PERGUNTE: \"Qual MARGEM DE LUCRO (em porcentagem) você gostaria de adicionar sobre o custo total de produção para definirmos o preço de venda?\"\n   h. QUANDO O USUÁRIO RESPONDER A MARGEM:\n      - Calcule o preço de venda sugerido.\n      - APRESENTE O PREÇO CALCULADO e diga: \"Com base nos seus custos e na margem desejada, o preço de venda sugerido seria R$ X.XX.\"\n      - PERGUNTE: \"Este preço cobre todos os seus custos e te dá a lucratividade esperada? Como ele se compara ao que você imagina que o mercado pagaria?\"\n\n**FINALIZAÇÃO DA INTERAÇÃO (PARA AMBOS OS CASOS):**\n- Após uma sugestão de preço, sempre ofereça: \"Podemos refinar este cálculo, simular outros cenários ou discutir estratégias de precificação?\"\n\nMantenha a conversa fluida e profissional, mas acessível. O objetivo é entregar o 'bolo pronto com a velinha', ou seja, uma análise e sugestão de preço fundamentada."
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    # NOVA FUNÇÃO PARA GERADOR DE IDEIAS
    def gerar_ideias_para_negocios(self, input_usuario):
        system_message_ideias = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA, com foco em INOVAÇÃO e SOLUÇÃO DE PROBLEMAS.
        Sua tarefa é ajudar empreendedores a gerar ideias criativas e práticas para seus negócios, seja para resolver dores, encontrar novas oportunidades ou inovar.
        Você faz perguntas UMA DE CADA VEZ para entender o contexto do usuário.

        **FLUXO DA CONVERSA:**

        **INÍCIO DA CONVERSA / PEDIDO INICIAL:**
        - Se o usuário indicar que quer ideias (ex: "Preciso de ideias", "Estou com um problema X", "Como posso inovar em Y?"),
          SUA PRIMEIRA PERGUNTA DEVE SER (de forma empática): "Entendo que você está buscando novas ideias ou soluções. Para que eu possa te ajudar da melhor forma, conte-me um pouco mais sobre o principal desafio, dor ou área do seu negócio para a qual você gostaria de gerar ideias."

        **EXPLORAÇÃO DO PROBLEMA/OPORTUNIDADE:**
        - Após a primeira resposta do usuário, faça perguntas abertas para aprofundar o entendimento:
            - "Poderia me dar mais detalhes sobre [aspecto que o usuário mencionou]?"
            - "Quais são os principais obstáculos que você enfrenta em relação a isso?"
            - "O que você já tentou fazer para resolver/abordar essa questão?"
            - "Qual seria o resultado ideal que você gostaria de alcançar?"
            - "Existe algum recurso (tempo, orçamento, equipe) que é uma limitação importante a ser considerada?"

        **GERAÇÃO DE IDEIAS:**
        - Quando você tiver um bom entendimento do contexto (geralmente após 2-4 perguntas exploratórias), informe ao usuário:
          "Obrigado pelas informações. Com base no que você me contou sobre [resumo do problema/dor/objetivo], vou gerar algumas ideias e sugestões para você."
        - Então, gere de 3 a 5 ideias ou abordagens distintas. Para cada ideia:
            a. Dê um nome ou título curto para a ideia.
            b. Descreva a ideia de forma concisa (1-3 frases).
            c. Explique brevemente o racional ou o benefício potencial dessa ideia.
            d. (Opcional) Sugira um primeiro passo muito simples para explorar essa ideia.
        - Tente trazer perspectivas variadas (ex: uma ideia focada em marketing, outra em produto/serviço, outra em otimização de processo, etc., conforme aplicável ao problema do usuário).
        - Use princípios de criatividade, inovação, e também fundamentos de marketing e administração (Kotler, Chiavenato) de forma conceitual.

        **DISCUSSÃO E REFINAMENTO:**
        - Após apresentar as ideias, PERGUNTE: "Alguma dessas ideias te chama mais a atenção ou parece mais promissora para o seu caso? Gostaria de explorar alguma delas com mais detalhes ou talvez gerar mais algumas alternativas com um foco diferente?"

        Mantenha um tom positivo, criativo e colaborativo. O objetivo é ser um parceiro de brainstorming para o usuário.
        """
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

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
        "Gerador de Ideias para Negócios": "gerador_ideias" # NOVA OPÇÃO
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    for key_area_op in opcoes_menu.values():
        if key_area_op and f"chat_display_{key_area_op}" not in st.session_state:
            st.session_state[f"chat_display_{key_area_op}"] = []
    
    if 'start_marketing_form' not in st.session_state:
        st.session_state.start_marketing_form = False
    if 'last_uploaded_image_info_pricing' not in st.session_state:
        st.session_state.last_uploaded_image_info_pricing = None
    if 'processed_image_id_pricing' not in st.session_state:
        st.session_state.processed_image_id_pricing = None


    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v14', # Nova key para o radio
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        current_section_key_temp = opcoes_menu.get(st.session_state.area_selecionada)
        
        if st.session_state.area_selecionada != "Cálculo de Preços Inteligente":
            st.session_state.last_uploaded_image_info_pricing = None
            st.session_state.processed_image_id_pricing = None

        # Lógica para mensagem inicial ao mudar para uma aba de CHAT
        chat_display_key_temp = f"chat_display_{current_section_key_temp}"
        if current_section_key_temp == "plano_negocios" and not st.session_state.get(chat_display_key_temp, []):
            initial_msg = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[chat_display_key_temp] = [{"role": "assistant", "content": initial_msg}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_msg)
        elif current_section_key_temp == "calculo_precos" and not st.session_state.get(chat_display_key_temp, []):
            initial_msg = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[chat_display_key_temp] = [{"role": "assistant", "content": initial_msg}]
            agente.memoria_calculo_precos.clear()
            agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_msg)
        elif current_section_key_temp == "gerador_ideias" and not st.session_state.get(chat_display_key_temp, []): # Para nova aba
            initial_msg = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
            st.session_state[chat_display_key_temp] = [{"role": "assistant", "content": initial_msg}]
            agente.memoria_gerador_ideias.clear()
            agente.memoria_gerador_ideias.chat_memory.add_ai_message(initial_msg)
        elif current_section_key_temp == "marketing_guiado":
             st.session_state.start_marketing_form = False
        st.rerun()

    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    # --- RENDERIZAÇÃO DA PÁGINA SELECIONADA ---
    if current_section_key == "pagina_inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        st.markdown("---")
        
        # Ajustando para criar botões dinamicamente para todas as opções do menu (exceto Página Inicial)
        num_cols = len(opcoes_menu) -1
        if num_cols > 0 :
            cols_buttons = st.columns(num_cols)
            btn_idx = 0
            for nome_menu_btn, chave_secao_btn in opcoes_menu.items():
                if chave_secao_btn != "pagina_inicial":
                    button_label = nome_menu_btn.split(" com IA")[0] if " com IA" in nome_menu_btn else nome_menu_btn
                    if cols_buttons[btn_idx % num_cols].button(button_label, key=f"btn_goto_{chave_secao_btn}_v5", use_container_width=True):
                        st.session_state.area_selecionada = nome_menu_btn
                        # Lógica de inicialização de chat/estado para a seção específica
                        if chave_secao_btn == "plano_negocios" and not st.session_state.get(f"chat_display_{chave_secao_btn}",[]):
                            initial_msg = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                            st.session_state[f"chat_display_{chave_secao_btn}"] = [{"role": "assistant", "content": initial_msg}]
                            agente.memoria_plano_negocios.clear()
                            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_msg)
                        elif chave_secao_btn == "calculo_precos" and not st.session_state.get(f"chat_display_{chave_secao_btn}",[]):
                            initial_msg = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
                            st.session_state[f"chat_display_{chave_secao_btn}"] = [{"role": "assistant", "content": initial_msg}]
                            agente.memoria_calculo_precos.clear()
                            agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_msg)
                        elif chave_secao_btn == "gerador_ideias" and not st.session_state.get(f"chat_display_{chave_secao_btn}",[]):
                            initial_msg = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
                            st.session_state[f"chat_display_{chave_secao_btn}"] = [{"role": "assistant", "content": initial_msg}]
                            agente.memoria_gerador_ideias.clear()
                            agente.memoria_gerador_ideias.chat_memory.add_ai_message(initial_msg)
                        elif chave_secao_btn == "marketing_guiado":
                            st.session_state.start_marketing_form = False
                        st.rerun()
                    btn_idx +=1
        st.balloons()

    elif current_section_key == "marketing_guiado":
        agente.marketing_digital_guiado()

    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")
        chat_display_key_pn = f"chat_display_{current_section_key}"
        if not st.session_state.get(chat_display_key_pn, []): # Garante msg inicial se não veio do botão
            initial_ai_message_pn = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[chat_display_key_pn] = [{"role": "assistant", "content": initial_ai_message_pn}]
            if not agente.memoria_plano_negocios.chat_memory.messages:
                agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message_pn)
        for msg_info_pn in st.session_state[chat_display_key_pn]:
            with st.chat_message(msg_info_pn["role"]): st.markdown(msg_info_pn["content"])
        prompt_usuario_pn = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")
        if prompt_usuario_pn:
            st.session_state[chat_display_key_pn].append({"role": "user", "content": prompt_usuario_pn})
            with st.chat_message("user"): st.markdown(prompt_usuario_pn)
            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai_pn = agente.conversar_plano_de_negocios(prompt_usuario_pn)
            st.session_state[chat_display_key_pn].append({"role": "assistant", "content": resposta_ai_pn})
            with st.chat_message("assistant"): st.markdown(resposta_ai_pn)
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v6"): # Key única
            initial_ai_message_pn_reset = "Ok, vamos recomeçar seu plano de negócios! Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[chat_display_key_pn] = [{"role": "assistant", "content": initial_ai_message_pn_reset}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message_pn_reset)
            st.rerun()

    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Vamos definir os melhores preços para seus produtos ou serviços!")
        chat_display_key_cp = f"chat_display_{current_section_key}"
        uploaded_image_pricing_cp = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v5")
        descricao_imagem_para_contexto_ia = None
        if uploaded_image_pricing_cp is not None:
            if st.session_state.get('processed_image_id_pricing') != uploaded_image_pricing_cp.id:
                try:
                    st.image(Image.open(uploaded_image_pricing_cp), caption=f"Imagem: {uploaded_image_pricing_cp.name}", width=150)
                    descricao_imagem_para_contexto_ia = f"O usuário carregou uma imagem chamada '{uploaded_image_pricing_cp.name}'. Se esta imagem for do produto a ser precificado, você pode pedir mais detalhes sobre ela."
                    st.session_state.last_uploaded_image_info_pricing = descricao_imagem_para_contexto_ia
                    st.session_state.processed_image_id_pricing = uploaded_image_pricing_cp.id 
                    st.info(f"Imagem '{uploaded_image_pricing_cp.name}' pronta para ser considerada no próximo diálogo.")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {e}")
                    st.session_state.last_uploaded_image_info_pricing = None
                    st.session_state.processed_image_id_pricing = None
        if not st.session_state.get(chat_display_key_cp, []):
            initial_ai_message_cp = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[chat_display_key_cp] = [{"role": "assistant", "content": initial_ai_message_cp}]
            if not agente.memoria_calculo_precos.chat_memory.messages:
                agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_ai_message_cp)
        for msg_info_cp in st.session_state[chat_display_key_cp]:
            with st.chat_message(msg_info_cp["role"]): st.markdown(msg_info_cp["content"])
        prompt_usuario_cp = st.chat_input("Sua resposta ou descreva o produto/serviço para precificar:")
        if prompt_usuario_cp:
            st.session_state[chat_display_key_cp].append({"role": "user", "content": prompt_usuario_cp})
            with st.chat_message("user"): st.markdown(prompt_usuario_cp)
            contexto_img_atual_cp = st.session_state.get('last_uploaded_image_info_pricing')
            with st.spinner("Assistente PME Pro está calculando... 📈"):
                resposta_ai_cp = agente.calcular_precos_interativo(prompt_usuario_cp, descricao_imagem_contexto=contexto_img_atual_cp)
            if contexto_img_atual_cp: st.session_state.last_uploaded_image_info_pricing = None
            st.session_state[chat_display_key_cp].append({"role": "assistant", "content": resposta_ai_cp})
            with st.chat_message("assistant"): st.markdown(resposta_ai_cp)
        if st.sidebar.button("Reiniciar Cálculo de Preços", key="btn_reset_precos_v5"):
            initial_ai_message_cp_reset = "Ok, vamos começar um novo cálculo de preços! Você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[chat_display_key_cp] = [{"role": "assistant", "content": initial_ai_message_cp_reset}]
            agente.memoria_calculo_precos.clear()
            agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_ai_message_cp_reset)
            st.session_state.last_uploaded_image_info_pricing = None
            st.session_state.processed_image_id_pricing = None
            st.rerun()

    elif current_section_key == "gerador_ideias": # NOVA SEÇÃO DE UI PARA GERADOR DE IDEIAS
        st.header("💡 Gerador de Ideias para seu Negócio com IA")
        st.caption("Descreva seus desafios ou áreas onde busca inovação, e vamos encontrar soluções juntos!")
        chat_display_key_gi = f"chat_display_{current_section_key}"

        if not st.session_state.get(chat_display_key_gi, []): # Garante msg inicial
            initial_ai_message_gi = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
            st.session_state[chat_display_key_gi] = [{"role": "assistant", "content": initial_ai_message_gi}]
            if not agente.memoria_gerador_ideias.chat_memory.messages: # Adiciona à memória apenas se estiver vazia
                agente.memoria_gerador_ideias.chat_memory.add_ai_message(initial_ai_message_gi)

        for msg_info_gi in st.session_state[chat_display_key_gi]:
            with st.chat_message(msg_info_gi["role"]):
                st.markdown(msg_info_gi["content"])
        
        prompt_usuario_gi = st.chat_input("Descreva seu desafio ou peça ideias:")
        if prompt_usuario_gi:
            st.session_state[chat_display_key_gi].append({"role": "user", "content": prompt_usuario_gi})
            with st.chat_message("user"): st.markdown(prompt_usuario_gi)
            with st.spinner("O Assistente PME Pro está buscando inspiração e ideias... ✨"):
                resposta_ai_gi = agente.gerar_ideias_para_negocios(prompt_usuario_gi)
            st.session_state[chat_display_key_gi].append({"role": "assistant", "content": resposta_ai_gi})
            with st.chat_message("assistant"): st.markdown(resposta_ai_gi)

        if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v1"):
            initial_ai_message_gi_reset = "Ok, vamos começar uma nova busca por ideias! Conte-me sobre um novo desafio, dor ou área para inovar."
            st.session_state[chat_display_key_gi] = [{"role": "assistant", "content": initial_ai_message_gi_reset}]
            agente.memoria_gerador_ideias.clear()
            agente.memoria_gerador_ideias.chat_memory.add_ai_message(initial_ai_message_gi_reset)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
