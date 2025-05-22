import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Pro", layout="wide", initial_sidebar_state="expanded")

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm = None

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
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model
        
        if 'memoria_plano_negocios_agente' not in st.session_state:
            st.session_state.memoria_plano_negocios_agente = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_plano_negocios = st.session_state.memoria_plano_negocios_agente

        if 'memoria_controle_financeiro_agente' not in st.session_state:
            st.session_state.memoria_controle_financeiro_agente = ConversationBufferMemory(memory_key="historico_chat_financeiro", return_messages=True)
        self.memoria_controle_financeiro = st.session_state.memoria_controle_financeiro_agente

    def _criar_cadeia_simples(self, system_message_content, human_message_content_template="{solicitacao_usuario}"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            HumanMessagePromptTemplate.from_template(human_message_content_template)
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, verbose=False)

    def _criar_cadeia_conversacional(self, system_message_content, memoria, memory_key="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name=memory_key), 
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Preencha os campos abaixo para criarmos juntos uma estratégia de marketing digital eficaz usando IA.")
        
        with st.form(key='marketing_form_guiado_v6'):
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar?", key="mdg_publico_v6")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?", key="mdg_produto_v6")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing?",
                                             ["", "Aumentar vendas online", "Gerar mais contatos (leads)",
                                              "Fortalecer o reconhecimento da marca", "Aumentar o engajamento"],
                                             key="mdg_objetivo_v6")
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
                system_message_marketing = """
                Você é o "Assistente PME Pro", um consultor especialista em Marketing Digital com IA para pequenas empresas.
                Seu objetivo é guiar o usuário a criar uma estratégia de marketing digital eficaz,
                baseado nos melhores princípios de marketing (como os de Kotler) e nas capacidades da IA.
                """
                prompt_llm_marketing = f"""
                Um dono de pequena empresa preencheu o seguinte formulário para obter um guia prático para Marketing Digital com IA:
                - Público-Alvo: {publico_alvo}
                - Produto/Serviço Principal: {produto_servico}
                - Principal Diferencial: {diferencial}
                - Objetivo Principal com Marketing Digital: {objetivo_campanha}
                - Mensagem Chave: {mensagem_principal}
                - Ideia para Imagem (se houver): {descricao_imagem or "Não especificado"}
                - Ideia para Vídeo (se houver): {descricao_video or "Não especificado"}
                - Orçamento Estimado (se houver): {orcamento_ideia or "Não especificado"}
                - Canal Digital em Mente ou Pedido de Sugestão: {rede_social_alvo}

                Com base nisso, forneça um GUIA ESTRATÉGICO E PRÁTICO, incluindo:
                1. Diagnóstico Rápido e Oportunidade com IA.
                2. Canal(is) Prioritário(s) (com justificativa se pedi sugestão, ou como otimizar o escolhido com IA).
                3. Estratégias de Conteúdo Inteligente: Tipos de conteúdo, como IA pode ajudar (ideias, rascunhos), 2 exemplos de TÍTULOS/POSTS para meu negócio.
                4. Ferramenta de IA Recomendada (Gratuita/Baixo Custo): UMA ferramenta e como ajudaria.
                5. Primeiros 3 Passos Acionáveis para usar IA no marketing.
                6. Métrica Chave de Sucesso Inicial.
                Tom: Mentor experiente, prático, encorajador. Linguagem clara. Foco em plano inicial acionável.
                """
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing... 💡"):
                    cadeia_mkt = self._criar_cadeia_simples(system_message_marketing)
                    resposta_llm = cadeia_mkt.run(solicitacao_usuario=prompt_llm_marketing)

                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)

    def conversar_plano_de_negocios(self, input_usuario):
        # NOVO PROMPT DO SISTEMA PARA PLANO DE NEGÓCIOS
        system_message_plano = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Sua tarefa é ajudar um empreendedor a ESBOÇAR e depois DETALHAR um PLANO DE NEGÓCIOS.
        Você faz perguntas UMA DE CADA VEZ para coletar informações. Use linguagem clara e seja encorajador.

        **FLUXO DA CONVERSA:**

        **INÍCIO DA CONVERSA / PEDIDO INICIAL:**
        Se o usuário indicar que quer criar um plano de negócios (ex: "Crie meu plano de negócios", "Quero ajuda com meu plano", "sim" para um botão de iniciar plano),
        SUA PRIMEIRA PERGUNTA DEVE SER: "Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"

        **COLETA PARA O ESBOÇO:**
        Após saber o ramo, continue fazendo UMA PERGUNTA POR VEZ para obter informações para as seguintes seções (não precisa ser exatamente nesta ordem, mas cubra-as):
        1.  Nome da Empresa
        2.  Missão da Empresa (o propósito central, o que ela busca fazer)
        3.  Visão da Empresa (onde ela quer estar no futuro, ex: em 3-5 anos)
        4.  Principais Objetivos (metas claras, ex: atingir X de faturamento, abrir Y filiais)
        5.  Produtos/Serviços Principais (o que ela vende/oferece)
        6.  Público-Alvo Principal (para quem ela vende)
        7.  Principal Diferencial (o que a torna especial/melhor que a concorrência)
        8.  Ideias Iniciais de Marketing e Vendas (como ela pretende alcançar os clientes)
        9.  Ideias Iniciais de Operações (como o negócio vai funcionar no dia a dia)
        10. Estimativas Financeiras Muito Básicas (ideia de investimento inicial, principais custos fixos e variáveis, como espera gerar receita - não precisa de números exatos agora, apenas conceitos).

        **GERAÇÃO DO ESBOÇO:**
        Quando você sentir que coletou informações suficientes para estas 10 áreas (geralmente após a pergunta sobre finanças básicas), VOCÊ DEVE PERGUNTAR:
        "Com as informações que reunimos até agora, você gostaria que eu montasse um primeiro ESBOÇO do seu plano de negócios? Ele terá as seções principais que discutimos."

        Se o usuário disser "sim" (ou algo similar):
            - Gere um ESBOÇO do plano de negócios. Organize-o com os seguintes títulos de seção:
                1. Sumário Executivo (inclua nome, missão, visão, objetivos)
                2. Descrição da Empresa (ramo, o que faz)
                3. Produtos e Serviços
                4. Público-Alvo e Diferenciais
                5. Estratégias Iniciais de Marketing e Vendas
                6. Operações Iniciais
                7. Panorama Financeiro Inicial
            - No final do esboço, ADICIONE a seguinte frase: "Este é um esboço inicial para organizar suas ideias. Ele pode ser muito mais detalhado e aprofundado."
            - ENTÃO, IMEDIATAMENTE APÓS MOSTRAR O ESBOÇO, PERGUNTE: "Este esboço inicial te ajuda a visualizar melhor? Gostaria de DETALHAR este plano de negócios agora? Podemos aprofundar cada seção, e você poderá me fornecer mais informações e, no futuro, até mesmo subir documentos."

        **DETALHAMENTO DO PLANO (SE O USUÁRIO ACEITAR):**
        Se o usuário disser "sim" para detalhar (ou algo similar):
            - Responda com entusiasmo: "Ótimo! Para detalharmos, vamos focar em cada seção do plano. Aplicaremos princípios de administração e marketing (como os de Chiavenato e Kotler) para enriquecer a análise."
            - ENTÃO, PERGUNTE: "Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? Por exemplo, podemos começar com uma 'Análise de Mercado mais completa', detalhar suas 'Estratégias de Marketing e Vendas', ou elaborar 'Projeções Financeiras'?"
            - A partir da escolha do usuário, faça perguntas específicas para aquela seção, buscando mais detalhes, dados, e explicando brevemente a importância daquela informação para o plano.

        Lembre-se de manter o tom de um consultor parceiro e experiente.
        """
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key="historico_chat_plano")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

    def conversar_controle_financeiro(self, input_usuario):
        system_message_financeiro = """
        Você é o "Assistente PME Pro", um consultor financeiro especialista em IA para pequenas empresas.
        Sua tarefa é ajudar o empreendedor a entender e iniciar um CONTROLE FINANCEIRO básico.
        Você faz perguntas UMA DE CADA VEZ.

        - Se a conversa está começando ou o usuário diz algo como "Quero ajuda com controle financeiro" ou "sim" para uma pergunta inicial sobre o tema, sua PRIMEIRA pergunta DEVE SER: "Entendido! Para começarmos a organizar suas finanças, qual é o principal tipo de receita da sua empresa atualmente?"
        - Continue com perguntas para entender:
            - Outras fontes de receita (se houver).
            - Principais categorias de despesas fixas (aluguel, salários, pro-labore, etc.).
            - Principais categorias de despesas variáveis (matéria-prima, comissões, marketing, etc.).
            - Se já utiliza alguma ferramenta ou planilha de controle.
        - Após coletar algumas informações básicas, PERGUNTE: "Com base no que conversamos, gostaria que eu gerasse um resumo da sua situação financeira atual e sugestões de como estruturar uma planilha de controle de fluxo de caixa simples e uma de despesas?"
        - Se o usuário disser "sim", forneça:
            a) Um breve resumo textual das receitas e despesas identificadas.
            b) Uma sugestão de estrutura para uma planilha de Fluxo de Caixa Simples (colunas: Data, Descrição, Entrada, Saída, Saldo).
            c) Uma sugestão de estrutura para uma Planilha de Despesas Fixas e Variáveis (Categorias, Valor Mensal Estimado).
            d) Uma dica sobre a importância de separar finanças pessoais das empresariais.
        - APÓS apresentar as sugestões, pergunte: "Isso te dá um ponto de partida? Podemos detalhar alguma dessas planilhas ou discutir como analisar esses números e gerar alguns gráficos simples com base nos dados que você me fornecer?"
        """
        cadeia = self._criar_cadeia_conversacional(system_message_financeiro, self.memoria_controle_financeiro, memory_key="historico_chat_financeiro")
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm:
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_model=llm)
    agente = st.session_state.agente_pme

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100)
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("IA para seu Negócio Decolar!")
    st.sidebar.markdown("---")

    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Marketing Digital com IA (Guia)": "marketing_guiado",
        "Elaborar Plano de Negócios com IA": "plano_negocios",
        "Controle Financeiro Inteligente": "controle_financeiro"
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    # Históricos de chat para exibição na tela
    if "chat_display_plano_negocios" not in st.session_state:
         st.session_state.chat_display_plano_negocios = []
    if "chat_display_controle_financeiro" not in st.session_state:
         st.session_state.chat_display_controle_financeiro = []

    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v11', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        # Prepara a saudação inicial ao entrar nas abas de chat
        if st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA" and not st.session_state.chat_display_plano_negocios:
            initial_ai_message_plano = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message_plano}]
            agente.memoria_plano_negocios.clear() # Limpa a memória para uma nova sessão de plano
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message_plano)
        elif st.session_state.area_selecionada == "Controle Financeiro Inteligente" and not st.session_state.chat_display_controle_financeiro:
            initial_ai_message_fin = "Olá! Sou seu Assistente PME Pro. Quer organizar as finanças da sua empresa com a ajuda da IA? Se sim, me diga 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_controle_financeiro = [{"role": "assistant", "content": initial_ai_message_fin}]
            agente.memoria_controle_financeiro.clear() # Limpa a memória para uma nova sessão financeira
            agente.memoria_controle_financeiro.chat_memory.add_ai_message(initial_ai_message_fin)
        elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
             st.session_state.start_marketing_form = False 
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🚀 Guia de Marketing Digital", key="btn_goto_marketing_v3"):
                st.session_state.area_selecionada = "Marketing Digital com IA (Guia)"
                st.session_state.start_marketing_form = False 
                st.rerun()
        with col2:
            if st.button("📝 Esboçar Plano de Negócios", key="btn_goto_plano_v4"):
                st.session_state.area_selecionada = "Elaborar Plano de Negócios com IA"
                if not st.session_state.chat_display_plano_negocios:
                     initial_ai_message = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                     st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
                     agente.memoria_plano_negocios.clear()
                     agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
                st.rerun()
        with col3: 
            if st.button("💰 Organizar Controle Financeiro", key="btn_goto_financeiro_v2"):
                st.session_state.area_selecionada = "Controle Financeiro Inteligente"
                if not st.session_state.chat_display_controle_financeiro:
                     initial_ai_message = "Olá! Sou seu Assistente PME Pro. Quer organizar as finanças da sua empresa com a ajuda da IA? Se sim, me diga 'sim' ou 'vamos começar'!"
                     st.session_state.chat_display_controle_financeiro = [{"role": "assistant", "content": initial_ai_message}]
                     agente.memoria_controle_financeiro.clear()
                     agente.memoria_controle_financeiro.chat_memory.add_ai_message(initial_ai_message)
                st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
        agente.marketing_digital_guiado()

    elif st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")
        
        if not st.session_state.chat_display_plano_negocios: # Garante mensagem inicial se chegou aqui sem clicar no botão
            initial_ai_message = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
            if not agente.memoria_plano_negocios.chat_memory.messages: # Adiciona à memória apenas se estiver vazia
                agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)

        for msg_info in st.session_state.chat_display_plano_negocios:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        prompt_usuario_plano = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")
        if prompt_usuario_plano:
            st.session_state.chat_display_plano_negocios.append({"role": "user", "content": prompt_usuario_plano})
            with st.chat_message("user"): st.markdown(prompt_usuario_plano)
            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai_plano = agente.conversar_plano_de_negocios(prompt_usuario_plano)
            st.session_state.chat_display_plano_negocios.append({"role": "assistant", "content": resposta_ai_plano})
            with st.chat_message("assistant"): st.markdown(resposta_ai_plano)
        
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v4"):
            initial_ai_message = "Ok, vamos recomeçar seu plano de negócios! Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message) # Adiciona à memória da IA
            st.rerun()

    elif st.session_state.area_selecionada == "Controle Financeiro Inteligente":
        st.header("📊 Controle Financeiro Inteligente com IA")
        st.caption("Vamos organizar suas finanças e obter insights valiosos!")

        if not st.session_state.chat_display_controle_financeiro: # Garante mensagem inicial
            initial_ai_message = "Olá! Sou seu Assistente PME Pro. Quer organizar as finanças da sua empresa com a ajuda da IA? Se sim, me diga 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_controle_financeiro = [{"role": "assistant", "content": initial_ai_message}]
            if not agente.memoria_controle_financeiro.chat_memory.messages:
                agente.memoria_controle_financeiro.chat_memory.add_ai_message(initial_ai_message)

        for msg_info in st.session_state.chat_display_controle_financeiro:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        prompt_usuario_fin = st.chat_input("Sua resposta ou diga 'Quero ajuda com meu financeiro'")
        if prompt_usuario_fin:
            st.session_state.chat_display_controle_financeiro.append({"role": "user", "content": prompt_usuario_fin})
            with st.chat_message("user"): st.markdown(prompt_usuario_fin)
            with st.spinner("Assistente PME Pro está analisando suas finanças... 💹"):
                resposta_ai_fin = agente.conversar_controle_financeiro(prompt_usuario_fin)
            st.session_state.chat_display_controle_financeiro.append({"role": "assistant", "content": resposta_ai_fin})
            with st.chat_message("assistant"): st.markdown(resposta_ai_fin)
        
        if st.sidebar.button("Reiniciar Controle Financeiro", key="btn_reset_financeiro_v2"):
            initial_ai_message = "Certo! Vamos começar do zero com seu controle financeiro. Quer organizar as finanças da sua empresa com a ajuda da IA? Se sim, me diga 'sim' ou 'vamos começar'!"
            st.session_state.chat_display_controle_financeiro = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_controle_financeiro.clear()
            agente.memoria_controle_financeiro.chat_memory.add_ai_message(initial_ai_message)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
