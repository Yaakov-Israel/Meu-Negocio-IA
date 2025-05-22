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
    st.error("🚨 ERRO: Arquivo de Segredos (secrets.toml) não encontrado para desenvolvimento local.")
    st.info("Crie um arquivo .streamlit/secrets.toml ou configure nos Segredos do Streamlit Cloud.")
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

# --- Classe do Agente (Simplificada para este passo) ---
class AgentePlanoDeNegocios:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Seu objetivo é ajudar empreendedores a criar planos de negócios.
        Você fará perguntas UMA DE CADA VEZ para coletar as informações necessárias.
        Quando o usuário iniciar, sua primeira pergunta DEVE SER SEMPRE: "Perfeito! Qual é o seu ramo de atuação?"
        Se o usuário responder à pergunta sobre o ramo de atuação, sua próxima pergunta pode ser sobre o nome da empresa ou a ideia principal.
        Mantenha a conversa focada na coleta de dados para o plano de negócios.
        """
        # Inicializa a memória aqui, para que seja específica desta instância do agente.
        self.memory = ConversationBufferMemory(memory_key="historico_chat_plano_negocios", return_messages=True)


    def conversar_sobre_plano(self, input_usuario):
        # Se o histórico estiver vazio e for a primeira interação real (após o usuário talvez clicar num botão),
        # a IA deve fazer a pergunta inicial sobre o ramo de atuação.
        # Mas o prompt do sistema já instrui isso, então a cadeia deve lidar bem.

        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.system_message),
            MessagesPlaceholder(variable_name="historico_chat_plano_negocios"), # Deve corresponder ao memory_key
            HumanMessagePromptTemplate.from_template("{input_usuario_plano}")
        ])
        
        # Importante: A memória é passada para a cadeia AQUI.
        cadeia_conversacional = LLMChain(llm=self.llm, prompt=prompt_template, memory=self.memory, verbose=True)
        
        resposta_ai = cadeia_conversacional.predict(input_usuario_plano=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm:
    # Inicializa o agente para o plano de negócios
    # A memória agora está DENTRO da classe AgentePlanoDeNegocios
    # Para manter o estado da instância do agente entre reruns do Streamlit, usamos st.session_state
    if 'agente_plano_negocios' not in st.session_state:
        st.session_state.agente_plano_negocios = AgentePlanoDeNegocios(llm_model=llm)
    
    agente_pn = st.session_state.agente_plano_negocios

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100) 
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("Seu guia de IA para planejamento!") 
    st.sidebar.markdown("---")

    opcoes_menu = {
        "Página Inicial": None,
        "Criar meu Plano de Negócios": "funcao_plano_negocios" 
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    
    # Histórico de chat para a funcionalidade do plano de negócios
    if "chat_plano_negocios_display" not in st.session_state:
         st.session_state.chat_plano_negocios_display = []


    area_selecionada_sidebar = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v6', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_sidebar != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_sidebar
        # Se mudar de área, NÃO limpamos a memória do agente nem o histórico de display aqui,
        # pois o usuário pode querer voltar. A limpeza pode ser feita com um botão de "reset" se necessário.
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Pronto para transformar suas ideias em um plano de negócios sólido com a ajuda da Inteligência Artificial?")
        st.markdown("---")
        if st.button("🚀 Sim, quero Criar meu Plano de Negócios!", key="btn_iniciar_plano_v2"):
            st.session_state.area_selecionada = "Criar meu Plano de Negócios"
            # Limpa/Prepara o chat para uma nova sessão de plano de negócios
            st.session_state.chat_plano_negocios_display = []
            st.session_state.agente_plano_negocios.memory.clear() # Limpa a memória da cadeia Langchain
            st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Criar meu Plano de Negócios":
        st.header("📝 Assistente para Elaboração do seu Plano de Negócios")
        st.markdown("Responda às minhas perguntas para construirmos seu plano passo a passo.")

        # Exibir histórico da conversa do display
        for msg_info in st.session_state.chat_plano_negocios_display:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        
        prompt_usuario = st.chat_input("Sua resposta ou comando (ex: 'Crie meu plano de negócios'):")

        if prompt_usuario:
            # Adiciona mensagem do usuário ao histórico de display
            st.session_state.chat_plano_negocios_display.append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"):
                st.markdown(prompt_usuario)

            with st.spinner("Assistente PME Pro está pensando... 🤔"):
                # A memória da cadeia (dentro do agente_pn) já está sendo atualizada
                resposta_ai = agente_pn.conversar_sobre_plano(prompt_usuario)
            
            # Adiciona resposta da IA ao histórico de display
            st.session_state.chat_plano_negocios_display.append({"role": "assistant", "content": resposta_ai})
            with st.chat_message("assistant"):
                st.markdown(resposta_ai)
            # Não precisa de st.rerun() aqui, pois o Streamlit atualiza com os novos st.chat_message

        # Botão para reiniciar a conversa do plano de negócios, se necessário
        if st.button("Nova Sessão / Reiniciar Plano", key="btn_reset_plano_conversa"):
            st.session_state.chat_plano_negocios_display = []
            st.session_state.agente_plano_negocios.memory.clear()
            # Opcional: Adicionar uma mensagem inicial da IA após o reset
            st.session_state.chat_plano_negocios_display.append({"role": "assistant", "content": "Ok, vamos começar de novo! Qual é o seu ramo de atuação?"})
            st.session_state.agente_plano_negocios.memory.chat_memory.add_ai_message("Ok, vamos começar de novo! Qual é o seu ramo de atuação?")
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
