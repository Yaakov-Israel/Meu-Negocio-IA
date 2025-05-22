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
# (Esta seção parece estar funcionando bem, vou mantê-la como estava na última versão funcional)
GOOGLE_API_KEY = None
llm = None # Renomeado de llm_langchain para llm para consistência

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
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                     temperature=0.7,
                                     google_api_key=GOOGLE_API_KEY,
                                     convert_system_message_to_human=True)
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique sua chave API, se a 'Generative Language API' está ativa no Google Cloud e suas cotas.")
        st.stop()

# --- Classe do Agente (AssistentePMEPro) ---
class AssistentePMEPro:
    def __init__(self, llm_model): # llm_model é o nosso llm inicializado com LangChain
        if llm_model is None:
            st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
            st.stop()
        self.llm = llm_model # Usando self.llm consistentemente
        
        # Inicializa as memórias como atributos diretos da instância do agente
        # Cada funcionalidade terá sua própria memória para não misturar as conversas
        self.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_controle_financeiro = ConversationBufferMemory(memory_key="historico_chat_financeiro", return_messages=True)
        self.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)

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
        # A memória específica (ex: self.memoria_plano_negocios) é passada aqui
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    def marketing_digital_guiado(self):
        # ... (código da função marketing_digital_guiado como na versão anterior)
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Preencha os campos abaixo para criarmos juntos uma estratégia de marketing digital eficaz usando IA.")
        with st.form(key='marketing_form_guiado_v6'): # Mantendo keys únicas
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar?", key="mdg_publico_v6")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?", key="mdg_produto_v6")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing?", ["", "Aumentar vendas online", "Gerar mais contatos (leads)", "Fortalecer o reconhecimento da marca", "Aumentar o engajamento"], key="mdg_objetivo_v6")
            st.markdown("---")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer comunicar?", key="mdg_mensagem_v6")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial?", key="mdg_diferencial_v6")
            st.markdown("---")
            descricao_imagem = st.text_input("6. Ideia para imagem (opcional):", key="mdg_img_v6")
            descricao_video = st.text_input("7. Ideia para vídeo (opcional):", key="mdg_video_v6")
            orcamento_ideia = st.text_input("8. Ideia de orçamento para esta ação (opcional):", key="mdg_orcamento_v6")
            redes_opcoes = { "Não tenho certeza, preciso de sugestão": "Sugestão da IA", "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok", "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp", "E-mail Marketing": "E-mail Marketing", "Google Ads/Meu Negócio": "Google", "Integrada": "Integrada"}
            rede_social_alvo_label = st.selectbox("9. Canal digital principal ou pedir sugestão?", options=list(redes_opcoes.keys()), key="mdg_canal_v6")
            rede_social_alvo = redes_opcoes[rede_social_alvo_label]
            submit_button = st.form_submit_button(label='Gerar Meu Guia de Marketing com IA 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial]):
                st.warning("Por favor, preencha os campos sobre Público, Produto/Serviço, Objetivo, Mensagem e Diferencial.")
            else:
                system_message_marketing = "Você é o \"Assistente PME Pro\", um consultor especialista em Marketing Digital com IA para pequenas empresas. Seu objetivo é guiar o usuário a criar uma estratégia de marketing digital eficaz, baseado nos melhores princípios de marketing (como os de Kotler) e nas capacidades da IA."
                prompt_llm_marketing = f"Um dono de pequena empresa preencheu o seguinte formulário para obter um guia prático para Marketing Digital com IA:\n- Público-Alvo: {publico_alvo}\n- Produto/Serviço Principal: {produto_servico}\n- Principal Diferencial: {diferencial}\n- Objetivo Principal com Marketing Digital: {objetivo_campanha}\n- Mensagem Chave: {mensagem_principal}\n- Ideia para Imagem (se houver): {descricao_imagem or 'Não especificado'}\n- Ideia para Vídeo (se houver): {descricao_video or 'Não especificado'}\n- Orçamento Estimado (se houver): {orcamento_ideia or 'Não especificado'}\n- Canal Digital em Mente ou Pedido de Sugestão: {rede_social_alvo}\n\nCom base nisso, forneça um GUIA ESTRATÉGICO E PRÁTICO, incluindo:\n1. Diagnóstico Rápido e Oportunidade com IA.\n2. Canal(is) Prioritário(s) (com justificativa se pedi sugestão, ou como otimizar o escolhido com IA).\n3. Estratégias de Conteúdo Inteligente: Tipos de conteúdo, como IA pode ajudar (ideias, rascunhos), 2 exemplos de TÍTULOS/POSTS para meu negócio.\n4. Ferramenta de IA Recomendada (Gratuita/Baixo Custo): UMA ferramenta e como ajudaria.\n5. Primeiros 3 Passos Acionáveis para usar IA no marketing.\n6. Métrica Chave de Sucesso Inicial.\nTom: Mentor experiente, prático, encorajador. Linguagem clara. Foco em plano inicial acionável."
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing... 💡"):
                    cadeia_mkt = self._criar_cadeia_simples(system_message_marketing) # Cadeia simples, sem memória de chat para o formulário
                    resposta_llm = cadeia_mkt.run(solicitacao_usuario=prompt_llm_marketing)
                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)


    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios especialista em IA. Sua tarefa é ajudar um empreendedor a ESBOÇAR e depois DETALHAR um PLANO DE NEGÓCIOS. Você faz perguntas UMA DE CADA VEZ para coletar informações. Use linguagem clara e seja encorajador.\n\n**FLUXO DA CONVERSA:**\n\n**INÍCIO DA CONVERSA / PEDIDO INICIAL:**\nSe o usuário indicar que quer criar um plano de negócios (ex: \"Crie meu plano de negócios\", \"Quero ajuda com meu plano\", \"sim\" para um botão de iniciar plano), SUA PRIMEIRA PERGUNTA DEVE SER: \"Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?\"\n\n**COLETA PARA O ESBOÇO:**\nApós saber o ramo, continue fazendo UMA PERGUNTA POR VEZ para obter informações para as seguintes seções (não precisa ser exatamente nesta ordem, mas cubra-as):\n1.  Nome da Empresa\n2.  Missão da Empresa\n3.  Visão da Empresa\n4.  Principais Objetivos\n5.  Produtos/Serviços Principais\n6.  Público-Alvo Principal\n7.  Principal Diferencial\n8.  Ideias Iniciais de Marketing e Vendas\n9.  Ideias Iniciais de Operações\n10. Estimativas Financeiras Muito Básicas\n\n**GERAÇÃO DO ESBOÇO:**\nQuando você sentir que coletou informações suficientes para estas 10 áreas, VOCÊ DEVE PERGUNTAR:\n\"Com as informações que reunimos até agora, você gostaria que eu montasse um primeiro ESBOÇO do seu plano de negócios? Ele terá as seções principais que discutimos.\"\n\nSe o usuário disser \"sim\":\n    - Gere um ESBOÇO do plano de negócios com as seções: Sumário Executivo, Descrição da Empresa, Produtos e Serviços, Público-Alvo e Diferenciais, Estratégias Iniciais de Marketing e Vendas, Operações Iniciais, Panorama Financeiro Inicial.\n    - No final do esboço, ADICIONE: \"Este é um esboço inicial para organizar suas ideias. Ele pode ser muito mais detalhado e aprofundado.\"\n    - ENTÃO, PERGUNTE: \"Este esboço inicial te ajuda a visualizar melhor? Gostaria de DETALHAR este plano de negócios agora? Podemos aprofundar cada seção, e você poderá me fornecer mais informações (e no futuro, até mesmo subir documentos).\"\n\n**DETALHAMENTO DO PLANO (SE O USUÁRIO ACEITAR):**\nSe o usuário disser \"sim\" para detalhar:\n    - Responda com entusiasmo: \"Ótimo! Para detalharmos, vamos focar em cada seção do plano. Aplicaremos princípios de administração e marketing (como os de Chiavenato e Kotler) para enriquecer a análise.\"\n    - ENTÃO, PERGUNTE: \"Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? Por exemplo, 'Análise de Mercado', 'Estratégias de Marketing Detalhadas', ou 'Projeções Financeiras'?\"\n    - A partir da escolha, faça perguntas específicas para aquela seção."
        # A memória self.memoria_plano_negocios é usada aqui
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def conversar_controle_financeiro(self, input_usuario):
        system_message_financeiro = "Você é o \"Assistente PME Pro\", um consultor financeiro especialista em IA para pequenas empresas. Sua tarefa é ajudar o empreendedor a entender e iniciar um CONTROLE FINANCEIRO básico. Você faz perguntas UMA DE CADA VEZ.\n\n- Se a conversa está começando ou o usuário diz algo como \"Quero ajuda com controle financeiro\" ou \"sim\" para uma pergunta inicial sobre o tema, sua PRIMEIRA pergunta DEVE SER: \"Entendido! Para começarmos a organizar suas finanças, qual é o principal tipo de receita da sua empresa atualmente?\"\n- Continue com perguntas para entender: Outras fontes de receita, despesas fixas, despesas variáveis, se já utiliza alguma ferramenta de controle.\n- Após coletar informações básicas, PERGUNTE: \"Com base no que conversamos, gostaria que eu gerasse um resumo da sua situação financeira atual e sugestões de como estruturar uma planilha de controle de fluxo de caixa simples e uma de despesas?\"\n- Se o usuário disser \"sim\", forneça: a) Resumo textual. b) Estrutura para planilha de Fluxo de Caixa (colunas: Data, Descrição, Entrada, Saída, Saldo). c) Estrutura para Planilha de Despesas (Categorias, Valor Mensal Estimado). d) Dica sobre separar finanças pessoais das empresariais.\n- APÓS apresentar as sugestões, pergunte: \"Isso te dá um ponto de partida? Podemos detalhar alguma dessas planilhas ou discutir como analisar esses números e gerar alguns gráficos simples com base nos dados que você me fornecer?\""
        # A memória self.memoria_controle_financeiro é usada aqui
        cadeia = self._criar_cadeia_conversacional(system_message_financeiro, self.memoria_controle_financeiro, memory_key_placeholder="historico_chat_financeiro")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None): # Adicionado descricao_imagem_contexto
        system_message_precos = f"""
        Você é o "Assistente PME Pro", especialista em precificação com IA.
        Sua tarefa é ajudar o usuário a definir o preço de venda de um produto ou serviço.
        Você faz perguntas UMA DE CADA VEZ.
        {(f"Contexto adicional: O usuário carregou uma imagem descrita como: '{descricao_imagem_contexto}'. Use isso se relevante para suas perguntas sobre o produto.") if descricao_imagem_contexto else ""}

        **INÍCIO DA CONVERSA:**
        - Se o usuário acabou de entrar nesta seção ou diz algo como "quero calcular preços",
          SUA PRIMEIRA PERGUNTA DEVE SER: "Olá! Para te ajudar a calcular o preço, me diga primeiro:
          Você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
        
        **CENÁRIO 1: PRODUTO DE REVENDA**
        - Se o usuário indicar REVENDA:
            - Pergunte: "Qual o nome ou tipo do produto que você revende?"
            - Pergunte: "Em qual cidade/estado você atua principalmente?"
            - Pergunte: "Você tem o custo de aquisição deste produto por unidade?"
            - Explique: "Para produtos de revenda, é importante pesquisar o preço de mercado. Eu não consigo pesquisar na web em tempo real, mas posso te dar dicas de como você pode fazer essa pesquisa (ex: pesquisar em grandes varejistas online, marketplaces, ou concorrentes locais). Com base no seu custo e na pesquisa de mercado, definiremos uma margem de lucro."
            - Pergunte: "Qual margem de lucro você gostaria de aplicar sobre o custo (ex: 30%, 50%, 100%) ou qual preço de venda você tem em mente?"
            - Com base no custo e margem (ou preço alvo), calcule e sugira o preço.

        **CENÁRIO 2: PRODUTO/SERVIÇO DE PRODUÇÃO PRÓPRIA**
        - Se o usuário indicar PRODUÇÃO PRÓPRIA:
            - Pergunte: "Entendido! Para precificar seu produto/serviço próprio, vamos detalhar os custos. Qual o nome do produto ou tipo de serviço?"
            - Pergunte sobre CUSTOS DIRETOS: "Quais são os custos diretos de material ou insumos por unidade produzida/serviço prestado?" (Peça exemplos)
            - Pergunte sobre MÃO DE OBRA DIRETA: "Quanto tempo de trabalho é gasto para produzir uma unidade ou prestar o serviço, e qual o custo dessa mão de obra?"
            - Pergunte sobre CUSTOS INDIRETOS/FIXOS: "Você tem uma estimativa dos seus custos fixos mensais (aluguel, luz, etc.) que precisam ser cobertos? E quantas unidades você espera vender por mês (para ajudar a ratear esses custos)?"
            - Explique brevemente métodos de precificação (Markup, Margem de Contribuição).
            - Pergunte: "Qual margem de lucro você gostaria de adicionar sobre o custo total de produção?"
            - Com base nos custos e margem, calcule e sugira o preço.
        
        GERAL: Peça informações de forma clara. Após apresentar um cálculo, pergunte se faz sentido ou se quer simular com outros valores. Lembre de considerar valor percebido e concorrência.
        """
        # A memória self.memoria_calculo_precos é usada aqui
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm: # Verifica se o llm (para LangChain) foi inicializado
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_model=llm) # Passando o llm do LangChain
    agente = st.session_state.agente_pme

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100)
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("IA para seu Negócio Decolar!")
    st.sidebar.markdown("---")

    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Marketing Digital com IA (Guia)": "marketing_guiado",
        "Elaborar Plano de Negócios com IA": "plano_negocios",
        "Cálculo de Preços Inteligente": "calculo_precos"
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    # Inicializar todos os históricos de display no session_state
    for key_area in opcoes_menu.values():
        if key_area and f"chat_display_{key_area}" not in st.session_state:
            st.session_state[f"chat_display_{key_area}"] = []
    
    # Caso especial para marketing que não usa o chat_display da mesma forma
    if 'start_marketing_form' not in st.session_state:
        st.session_state.start_marketing_form = False


    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v12',
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        # Lógica para mensagem inicial ao mudar para uma aba de CHAT
        if st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA" and not st.session_state.get(f"chat_display_{opcoes_menu[st.session_state.area_selecionada]}", []):
            initial_ai_message = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[f"chat_display_{opcoes_menu[st.session_state.area_selecionada]}"] = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
        elif st.session_state.area_selecionada == "Cálculo de Preços Inteligente" and not st.session_state.get(f"chat_display_{opcoes_menu[st.session_state.area_selecionada]}", []):
            initial_ai_message = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[f"chat_display_{opcoes_menu[st.session_state.area_selecionada]}"] = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_calculo_precos.clear()
            agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_ai_message)
        elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
            st.session_state.start_marketing_form = False
        st.rerun()

    # --- Área de Conteúdo Principal ---
    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    if current_section_key == "pagina_inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        st.markdown("---")
        cols = st.columns(len(opcoes_menu)-1) # Menos 1 para não incluir "Página Inicial" nos botões
        
        # Botões dinâmicos para cada funcionalidade (exceto Página Inicial)
        button_idx = 0
        for nome_menu, chave_secao in opcoes_menu.items():
            if chave_secao != "pagina_inicial":
                if cols[button_idx].button(nome_menu.split(" com IA")[0], key=f"btn_goto_{chave_secao}"): # Nome mais curto para o botão
                    st.session_state.area_selecionada = nome_menu
                    # Lógica de inicialização de chat/estado para a seção específica
                    if nome_menu == "Elaborar Plano de Negócios com IA" and not st.session_state.get(f"chat_display_{chave_secao}",[]):
                        initial_msg = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                        st.session_state[f"chat_display_{chave_secao}"] = [{"role": "assistant", "content": initial_msg}]
                        agente.memoria_plano_negocios.clear()
                        agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_msg)
                    elif nome_menu == "Cálculo de Preços Inteligente" and not st.session_state.get(f"chat_display_{chave_secao}",[]):
                        initial_msg = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
                        st.session_state[f"chat_display_{chave_secao}"] = [{"role": "assistant", "content": initial_msg}]
                        agente.memoria_calculo_precos.clear()
                        agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_msg)
                    elif nome_menu == "Marketing Digital com IA (Guia)":
                        st.session_state.start_marketing_form = False
                    st.rerun()
                button_idx +=1
        st.balloons()

    elif current_section_key == "marketing_guiado":
        agente.marketing_digital_guiado()

    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")
        chat_display_key = f"chat_display_{current_section_key}"
        
        if not st.session_state.get(chat_display_key, []):
            initial_ai_message = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": initial_ai_message}]
            if not agente.memoria_plano_negocios.chat_memory.messages:
                agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
        
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        prompt_usuario = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai = agente.conversar_plano_de_negocios(prompt_usuario)
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
            with st.chat_message("assistant"): st.markdown(resposta_ai)
        
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v5"):
            initial_ai_message = "Ok, vamos recomeçar seu plano de negócios! Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
            st.rerun()

    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Vamos definir os melhores preços para seus produtos ou serviços!")
        chat_display_key = f"chat_display_{current_section_key}"
        
        uploaded_image_pricing = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v2")
        descricao_imagem_para_ia = None
        if uploaded_image_pricing is not None:
            try:
                # Para modelos Gemini que aceitam bytes de imagem diretamente com texto:
                # imagem_pil = Image.open(uploaded_image_pricing)
                # st.image(imagem_pil, caption="Imagem Carregada", width=150)
                # TODO: No futuro, se a LLMChain ou o modelo suportar input multimodal direto, passar os bytes da imagem.
                # Por agora, vamos apenas pegar o nome do arquivo como contexto textual.
                descricao_imagem_para_ia = f"O usuário carregou uma imagem chamada '{uploaded_image_pricing.name}'. Peça detalhes sobre ela se for relevante para a precificação."
                st.info(f"Imagem '{uploaded_image_pricing.name}' carregada. A IA será informada sobre ela.")
            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")

        if not st.session_state.get(chat_display_key, []):
            initial_ai_message = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": initial_ai_message}]
            if not agente.memoria_calculo_precos.chat_memory.messages:
                agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_ai_message)
        
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        
        prompt_usuario_preco = st.chat_input("Sua resposta ou descreva o produto/serviço para precificar:")
        if prompt_usuario_preco:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario_preco})
            with st.chat_message("user"): st.markdown(prompt_usuario_preco)
            
            input_completo_para_ia = prompt_usuario_preco
            if descricao_imagem_para_ia: # Adiciona o contexto da imagem se ela foi carregada nesta interação
                input_completo_para_ia = f"{prompt_usuario_preco}\n(Contexto da imagem: {descricao_imagem_para_ia})"

            with st.spinner("Assistente PME Pro está calculando... 📈"):
                resposta_ai_preco = agente.calcular_precos_interativo(input_completo_para_ia)
            
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai_preco})
            with st.chat_message("assistant"): st.markdown(resposta_ai_preco)

        if st.sidebar.button("Reiniciar Cálculo de Preços", key="btn_reset_precos_v2"):
            initial_ai_message = "Ok, vamos começar um novo cálculo de preços! Você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_calculo_precos.clear()
            agente.memoria_calculo_precos.chat_memory.add_ai_message(initial_ai_message)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
