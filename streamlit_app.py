import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Pro - Seu Plano de Negócios", layout="wide", initial_sidebar_state="expanded")

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

# --- Classe do Agente ---
class AgentePlanoDeNegocios:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Sua tarefa é ajudar um empreendedor a ESBOÇAR e DETALHAR um PLANO DE NEGÓCIOS.
        Você faz perguntas UMA DE CADA VEZ para coletar informações.

        ETAPA 1: ESBOÇO INICIAL
        - Quando o usuário iniciar (ex: "Crie meu plano de negócios"), sua PRIMEIRA pergunta DEVE SER: "Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
        - Continue fazendo perguntas para cobrir as seções básicas: Nome da empresa, Missão, Visão, Objetivos, Produtos/Serviços, Público-alvo, Diferencial, Marketing e Vendas (ideias iniciais), Operações (ideias iniciais), Finanças (estimativas bem básicas).
        - Após coletar informações suficientes para um ESBOÇO (geralmente após a pergunta sobre finanças básicas), PERGUNTE: "Com as informações que temos, gostaria que eu tentasse montar um primeiro ESBOÇO do seu plano de negócios com as seções principais?"
        - Se o usuário disser "sim", gere um ESBOÇO CLARO e CONCISO do plano de negócios com as informações coletadas, usando as seções: 1. Sumário Executivo, 2. Descrição da Empresa, 3. Produtos/Serviços, 4. Plano de Marketing e Vendas, 5. Plano Operacional, 6. Plano Financeiro (Estimativas Iniciais). Adicione uma nota de que é um esboço e pode ser detalhado.
        - APÓS apresentar o esboço, pergunte: "Este esboço inicial te ajuda? Gostaria de detalhar mais alguma seção ou criar um plano mais completo agora, onde poderemos incluir mais informações e análises (como as de Kotler e Chiavenato)?"

        ETAPA 2: PLANO DETALHADO (se o usuário aceitar)
        - Se o usuário disser "sim" para detalhar, responda: "Ótimo! Para detalharmos, vamos focar em cada seção. Você poderá me fornecer mais dados, e no futuro, até fazer upload de documentos. Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? (Ex: Análise de Mercado, Estratégias de Marketing Detalhadas, Projeções Financeiras, etc.)"
        - A partir daí, guie o usuário para fornecer informações mais específicas para cada seção, mencionando que os princípios de marketing (Kotler) e administração (Chiavenato) serão aplicados.
        - Quando o usuário fornecer detalhes para uma seção, incorpore-os.

        Mantenha a conversa fluindo naturalmente. Seja prático e encorajador.
        """
        self.memory = ConversationBufferMemory(memory_key="historico_chat_plano_negocios", return_messages=True)

    def conversar_sobre_plano(self, input_usuario):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.system_message),
            MessagesPlaceholder(variable_name="historico_chat_plano_negocios"),
            HumanMessagePromptTemplate.from_template("{input_usuario_plano}")
        ])
        cadeia_conversacional = LLMChain(llm=self.llm, prompt=prompt_template, memory=self.memory, verbose=False) # verbose=True para debug
        resposta_ai = cadeia_conversacional.predict(input_usuario_plano=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm:
    if 'agente_plano_negocios' not in st.session_state:
        st.session_state.agente_plano_negocios = AgentePlanoDeNegocios(llm_model=llm)
    agente_pn = st.session_state.agente_plano_negocios

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100) 
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("Seu guia de IA para planejamento!") 
    st.sidebar.markdown("---")

    # Mantendo o menu simplificado por enquanto, mas podemos adicionar Marketing de volta se desejar
    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Elaborar Plano de Negócios com IA": "plano_negocios" 
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    if "chat_display_plano_negocios" not in st.session_state:
         st.session_state.chat_display_plano_negocios = []

    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v8', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        # Resetar o chat do plano de negócios ao selecionar a área pela primeira vez ou re-selecionar
        if st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA":
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"}]
            agente_pn.memory.clear()
            agente_pn.memory.chat_memory.add_ai_message("Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?")
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Pronto para transformar suas ideias em um plano de negócios sólido e impulsionar sua empresa com Inteligência Artificial?")
        st.markdown("---")
        if st.button("🚀 Sim, quero Criar meu Plano de Negócios com IA!", key="btn_iniciar_plano_v3"):
            st.session_state.area_selecionada = "Elaborar Plano de Negócios com IA"
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"}]
            agente_pn.memory.clear()
            agente_pn.memory.chat_memory.add_ai_message("Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?")
            st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")

        # Se o chat está vazio e não é a primeira mensagem, adiciona a saudação inicial
        if not st.session_state.chat_display_plano_negocios:
             st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"}]
             # Adiciona também à memória da IA para ela saber que já se apresentou
             if not agente_pn.memory.chat_memory.messages: # Só adiciona se a memória estiver realmente vazia
                agente_pn.memory.chat_memory.add_ai_message("Olá! Sou seu Assistente PME Pro. Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?")


        for msg_info in st.session_state.chat_display_plano_negocios:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        
        prompt_usuario_plano = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")

        if prompt_usuario_plano:
            st.session_state.chat_display_plano_negocios.append({"role": "user", "content": prompt_usuario_plano})
            with st.chat_message("user"):
                st.markdown(prompt_usuario_plano)

            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai_plano = agente_pn.conversar_sobre_plano(prompt_usuario_plano) # Memória já está no agente

            st.session_state.chat_display_plano_negocios.append({"role": "assistant", "content": resposta_ai_plano})
            with st.chat_message("assistant"):
                st.markdown(resposta_ai_plano)
        
        if st.sidebar.button("Nova Sessão / Reiniciar Plano", key="btn_reset_plano_v3"):
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Ok, vamos recomeçar seu plano de negócios! Qual é o seu ramo de atuação principal?"}]
            agente_pn.memory.clear()
            agente_pn.memory.chat_memory.add_ai_message("Ok, vamos recomeçar seu plano de negócios! Qual é o seu ramo de atuação principal?")
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
