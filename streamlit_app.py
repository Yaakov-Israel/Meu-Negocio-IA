import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Pro - Plano de Negócios com IA", layout="wide", initial_sidebar_state="expanded")

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

# --- Definição do Super Agente ---
class SuperAgentePequenasEmpresas:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message_template_base = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Seu objetivo é ajudar empreendedores a criar e refinar planos de negócios sólidos,
        fazendo perguntas estratégicas e utilizando princípios de marketing e administração
        (inspirados em Kotler e Chiavenato) para guiar o usuário.
        Mantenha uma conversa, fazendo uma pergunta por vez para coletar informações.
        Quando tiver informações suficientes, ofereça-se para esboçar o plano.
        """

    def _criar_cadeia_conversacional(self, memoria_conversa, prompt_sistema_adicional=""):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.system_message_template_base + "\n" + prompt_sistema_adicional),
            MessagesPlaceholder(variable_name="historico_chat"),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_conversa, verbose=False)

    def iniciar_ou_continuar_plano_de_negocios(self, input_usuario, memoria_conversa):
        prompt_especifico = """
        Estou no processo de ajudar o usuário a elaborar um plano de negócios.
        Analise o histórico da nossa conversa.
        Se for o início ou se o usuário deu uma resposta vaga, faça uma pergunta chave para obter a próxima informação essencial para um plano de negócios (ex: Qual o nome e a ideia principal da sua empresa? Qual seu público-alvo principal? Qual seu produto/serviço chave? Qual seu maior diferencial?).
        Se o usuário já forneceu algumas informações, faça uma pergunta subsequente para aprofundar ou cobrir outra seção do plano de negócios.
        Faça apenas UMA pergunta por vez.
        Se o usuário pedir explicitamente para "gerar o plano" ou "esboçar o plano" e você sentir que tem informações mínimas (nome da empresa, produto/serviço, público-alvo), ofereça-se para criar um esboço inicial do plano de negócios com as seções principais.
        """
        cadeia = self._criar_cadeia_conversacional(memoria_conversa, prompt_especifico)
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm:
    # Inicializa o agente (mesmo que não usemos todas as suas funções antigas agora)
    # A lógica de conversação do plano de negócios será mais direta
    # agente = SuperAgentePequenasEmpresas(llm_model=llm) # Não vamos instanciar a classe inteira por enquanto

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100)
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("Seu guia de IA para planejamento e gestão!")
    st.sidebar.markdown("---")

    # Estado da Sessão para o Plano de Negócios
    if "plano_negocios_conversa" not in st.session_state:
        st.session_state.plano_negocios_conversa = [] # Lista de mensagens (HumanMessage, AIMessage)
    if "plano_negocios_memoria" not in st.session_state:
        # A memória precisa ser recriada se não existir, ou se quisermos resetar
        st.session_state.plano_negocios_memoria = ConversationBufferMemory(memory_key="historico_chat", return_messages=True)


    opcoes_menu = {
        "Página Inicial": None,
        "Elaborar Plano de Negócios com IA": "funcao_plano_negocios" # Usaremos um identificador
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"

    area_selecionada_sidebar = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v5',
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_sidebar != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_sidebar
        # Ao mudar de área, podemos resetar a conversa do plano de negócios se desejado
        # st.session_state.plano_negocios_conversa = []
        # st.session_state.plano_negocios_memoria.clear()
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("""
        Estou aqui para ser seu parceiro estratégico, utilizando Inteligência Artificial para
        ajudá-lo a construir e refinar os planos da sua pequena ou média empresa.

        Vamos começar a transformar suas ideias em um plano de negócios sólido?
        """)
        st.markdown("---")
        if st.button("🚀 Sim, quero elaborar meu Plano de Negócios com IA!", key="btn_iniciar_plano"):
            st.session_state.area_selecionada = "Elaborar Plano de Negócios com IA"
            # Prepara a primeira mensagem da IA para iniciar a conversa
            st.session_state.plano_negocios_conversa = [AIMessage(content="Olá! Que ótimo que você quer elaborar seu plano de negócios. Para começarmos, qual é o nome e a ideia principal da sua empresa?")]
            st.session_state.plano_negocios_memoria.chat_memory.messages = st.session_state.plano_negocios_conversa.copy()
            st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Elaborar Plano de Negócios com IA":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.markdown("Vamos construir seu plano passo a passo. Responda às minhas perguntas para que eu possa te ajudar.")

        # Instancia o agente aqui, pois só é usado nesta seção
        agente_pn = SuperAgentePequenasEmpresas(llm_model=llm)

        # Exibir histórico da conversa
        for msg in st.session_state.plano_negocios_conversa:
            if isinstance(msg, HumanMessage):
                with st.chat_message("user"):
                    st.markdown(msg.content)
            elif isinstance(msg, AIMessage):
                with st.chat_message("assistant"):
                    st.markdown(msg.content)
        
        prompt_usuario = st.chat_input("Sua resposta ou próxima informação:")

        if prompt_usuario:
            # Adiciona mensagem do usuário ao histórico e à memória
            st.session_state.plano_negocios_conversa.append(HumanMessage(content=prompt_usuario))
            # A memória é atualizada automaticamente pela LLMChain, mas podemos adicionar aqui para consistência da exibição
            # st.session_state.plano_negocios_memoria.chat_memory.add_user_message(prompt_usuario)


            with st.chat_message("user"):
                st.markdown(prompt_usuario)

            with st.spinner("O Assistente PME Pro está pensando... 🤔"):
                # Passa o input do usuário e a memória para a função do agente
                resposta_ai = agente_pn.iniciar_ou_continuar_plano_de_negocios(prompt_usuario, st.session_state.plano_negocios_memoria)
            
            # Adiciona resposta da IA ao histórico e à memória (a LLMChain já adiciona à memória)
            st.session_state.plano_negocios_conversa.append(AIMessage(content=resposta_ai))
            # st.session_state.plano_negocios_memoria.chat_memory.add_ai_message(resposta_ai) # Feito pela LLMChain

            with st.chat_message("assistant"):
                st.markdown(resposta_ai)
            # Não precisa de st.rerun() aqui, o Streamlit atualiza com o novo chat_message

        if st.sidebar.button("Reiniciar Conversa do Plano", key="btn_reset_plano"):
            st.session_state.plano_negocios_conversa = [AIMessage(content="Olá! Que ótimo que você quer elaborar seu plano de negócios. Para começarmos, qual é o nome e a ideia principal da sua empresa?")]
            st.session_state.plano_negocios_memoria.clear() # Limpa a memória da conversação
            st.session_state.plano_negocios_memoria.chat_memory.messages = st.session_state.plano_negocios_conversa.copy()
            st.rerun()

else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
