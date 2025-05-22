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
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") # Para desenvolvimento local
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
        
        # Memória específica para o chat do plano de negócios
        if 'memoria_plano_negocios_agente' not in st.session_state:
            st.session_state.memoria_plano_negocios_agente = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_plano_negocios = st.session_state.memoria_plano_negocios_agente

    def _criar_cadeia_simples(self, system_message_content, human_message_content_template="{solicitacao_usuario}"):
        # Usada para interações que não precisam de memória de longo prazo ou são baseadas em formulário
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            HumanMessagePromptTemplate.from_template(human_message_content_template)
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, verbose=False)

    def _criar_cadeia_conversacional(self, system_message_content, memoria):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name="historico_chat_plano"), # Deve corresponder ao memory_key
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Preencha os campos abaixo para criarmos juntos uma estratégia de marketing digital eficaz usando IA.")

        # Não precisamos do botão "Sim, quero criar..." aqui, o formulário já é o guia.
        
        with st.form(key='marketing_form_guiado_v5'):
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar? (Descreva seu público-alvo):", key="mdg_publico_v5")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?:", key="mdg_produto_v5")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing digital?",
                                             ["", "Aumentar vendas online", "Gerar mais contatos (leads)",
                                              "Fortalecer o reconhecimento da minha marca", "Aumentar o engajamento com clientes"],
                                             key="mdg_objetivo_v5", help="Pense no resultado mais importante que você busca.")
            st.markdown("---")
            st.markdown("##### ✉️ Sua Mensagem e Diferencial")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer que seus clientes recebam sobre seu negócio?:", key="mdg_mensagem_v5")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial ou diferente da concorrência?:", key="mdg_diferencial_v5")
            st.markdown("---")
            st.markdown("##### 🖼️ Ideias para Conteúdo Visual (Opcional)")
            descricao_imagem = st.text_input("6. Se você imagina uma imagem, como ela seria? (ou cole uma URL de referência):", key="mdg_img_v5")
            descricao_video = st.text_input("7. E se fosse um vídeo, qual seria a ideia principal?:", key="mdg_video_v5")
            st.markdown("---")
            st.markdown("##### 💰 Outras Informações")
            orcamento_ideia = st.text_input("8. Você tem alguma ideia de orçamento para esta ação (Ex: baixo, até R$X, etc.)?:", key="mdg_orcamento_v5")
            redes_opcoes = { "Não tenho certeza, preciso de sugestão": "Sugestão da IA", "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok", "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp", "E-mail Marketing": "E-mail Marketing", "Google Ads/Meu Negócio": "Google", "Integrada": "Integrada"}
            rede_social_alvo_label = st.selectbox("9. Canal digital principal ou pedir sugestão?", options=list(redes_opcoes.keys()), key="mdg_canal_v5")
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
                1.  **Diagnóstico Rápido e Oportunidade com IA:** Uma frase curta sobre o potencial percebido.
                2.  **Sugestão de Canal(is) Prioritário(s):** Se pedi sugestão, qual(is) seria(m) o(s) melhor(es) para começar e por quê? Se já escolhi um, como a IA pode potencializá-lo?
                3.  **Estratégias de Conteúdo Inteligente:**
                    a.  Que tipos de conteúdo (posts, artigos, vídeos curtos) são mais indicados para meu público e canal?
                    b.  Como posso usar IA (conceitualmente) para me ajudar a criar esses conteúdos de forma mais eficiente ou criativa? (ex: gerar ideias, rascunhos, legendas, scripts).
                    c.  Dê 2 exemplos de TÍTULOS ou TEMAS de posts/conteúdos que eu poderia criar usando IA, adaptados ao meu negócio.
                4.  **Ferramenta de IA Recomendada (Foco no Gratuito/Baixo Custo):** Sugira UMA ferramenta de IA específica (existente no mercado) que seria útil para um dos aspectos da criação de conteúdo ou marketing que você mencionou, e explique brevemente como ela ajudaria.
                5.  **Seu Plano de Ação (Primeiros 3 Passos):** Quais os TRÊS primeiros passos práticos que devo tomar AGORA para começar a usar IA no meu marketing digital?
                6.  **Métrica de Sucesso Inicial:** Qual UMA métrica chave devo acompanhar para ver se estou no caminho certo?

                O tom deve ser de um mentor experiente, encorajador e super prático. Use linguagem clara e direta para um empreendedor ocupado.
                O objetivo é que o usuário saia daqui com um plano inicial acionável.
                """
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing... 💡"):
                    # Para esta função de formulário, não precisamos de memória de conversa complexa.
                    # Podemos usar uma chamada direta ou uma cadeia simples.
                    cadeia_mkt = self._criar_cadeia_simples(system_message_marketing)
                    resposta_llm = cadeia_mkt.run(solicitacao_usuario=prompt_llm_marketing) # Passando o prompt formatado

                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)

    def conversar_plano_de_negocios(self, input_usuario): # Memória agora é atributo da instância
        system_message_plano = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Sua tarefa é ajudar um empreendedor a ESBOÇAR e DETALHAR um PLANO DE NEGÓCIOS.
        Você faz perguntas UMA DE CADA VEZ para coletar informações.

        ETAPA 1: ESBOÇO INICIAL
        - Se a conversa está começando ou o usuário diz "Crie meu plano de negócios" (ou similar), sua PRIMEIRA pergunta DEVE SER: "Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
        - Continue fazendo perguntas para cobrir as seções básicas: Nome da empresa, Missão, Visão, Objetivos, Produtos/Serviços, Público-alvo, Diferencial, Marketing e Vendas (ideias iniciais), Operações (ideias iniciais), Finanças (estimativas bem básicas).
        - Após coletar informações suficientes para um ESBOÇO (geralmente após a pergunta sobre finanças básicas), PERGUNTE: "Com as informações que temos, gostaria que eu tentasse montar um primeiro ESBOÇO do seu plano de negócios com as seções principais?"
        - Se o usuário disser "sim", gere um ESBOÇO CLARO e CONCISO do plano de negócios com as informações coletadas, usando as seções: 1. Sumário Executivo, 2. Descrição da Empresa, 3. Produtos/Serviços, 4. Plano de Marketing e Vendas, 5. Plano Operacional, 6. Plano Financeiro (Estimativas Iniciais). Adicione uma nota de que é um esboço e pode ser detalhado.
        - APÓS apresentar o esboço, pergunte: "Este esboço inicial te ajuda? Gostaria de detalhar mais alguma seção ou criar um plano mais completo agora, onde poderemos incluir mais informações e análises (como as de Kotler e Chiavenato)?"

        ETAPA 2: PLANO DETALHADO (se o usuário aceitar)
        - Se o usuário disser "sim" para detalhar, responda: "Ótimo! Para detalharmos, vamos focar em cada seção. Você poderá me fornecer mais dados (e no futuro, até fazer upload de documentos). Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? (Ex: Análise de Mercado, Estratégias de Marketing Detalhadas, Projeções Financeiras, etc.)"
        - A partir daí, guie o usuário para fornecer informações mais específicas para cada seção, aplicando princípios de administração e marketing.
        """
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios)
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
        "Elaborar Plano de Negócios com IA": "plano_negocios"
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    if "chat_display_plano_negocios" not in st.session_state:
         st.session_state.chat_display_plano_negocios = []

    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v9', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        if st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA" and not st.session_state.chat_display_plano_negocios:
            # Prepara a primeira mensagem da IA para iniciar a conversa do plano de negócios
            initial_ai_message = "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
        elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
            st.session_state.start_marketing_form = False # Reseta para mostrar o botão de início
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Quero um Guia de Marketing Digital com IA!", key="btn_goto_marketing_v2"):
                st.session_state.area_selecionada = "Marketing Digital com IA (Guia)"
                st.session_state.start_marketing_form = False 
                st.rerun()
        with col2:
            if st.button("📝 Quero Esboçar meu Plano de Negócios com IA!", key="btn_goto_plano_v3"):
                st.session_state.area_selecionada = "Elaborar Plano de Negócios com IA"
                if not st.session_state.chat_display_plano_negocios: # Se o chat estiver vazio, inicia com a saudação
                     initial_ai_message = "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
                     st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
                     agente.memoria_plano_negocios.clear() # Limpa memória para nova sessão
                     agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
                st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
        agente.marketing_digital_guiado()

    elif st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")

        # Garante que a conversa comece se o histórico estiver vazio
        if not st.session_state.chat_display_plano_negocios:
             initial_ai_message = "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
             st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
             if not agente.memoria_plano_negocios.chat_memory.messages:
                agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
        
        for msg_info in st.session_state.chat_display_plano_negocios:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        
        prompt_usuario_plano = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")

        if prompt_usuario_plano:
            st.session_state.chat_display_plano_negocios.append({"role": "user", "content": prompt_usuario_plano})
            with st.chat_message("user"):
                st.markdown(prompt_usuario_plano)

            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai_plano = agente.conversar_plano_de_negocios(prompt_usuario_plano) 
            
            st.session_state.chat_display_plano_negocios.append({"role": "assistant", "content": resposta_ai_plano})
            with st.chat_message("assistant"):
                st.markdown(resposta_ai_plano)
        
        if st.sidebar.button("Nova Sessão / Reiniciar Plano", key="btn_reset_plano_v3"):
            initial_ai_message = "Ok, vamos recomeçar seu plano de negócios! Qual é o seu ramo de atuação principal?"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": initial_ai_message}]
            agente.memoria_plano_negocios.clear()
            agente.memoria_plano_negocios.chat_memory.add_ai_message(initial_ai_message)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
