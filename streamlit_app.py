import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

from auth import initialize_authenticator, authentication_flow_stauth

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

authenticator = initialize_authenticator()

if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
    
if not st.session_state.get('authentication_status'):
    authentication_flow_stauth(authenticator)

if st.session_state.get('authentication_status') is True: # Verifica explicitamente por True
    user_name_from_session = st.session_state.get('name', 'Usuário') 
    st.sidebar.success(f"Logado como: {user_name_from_session}")
    authenticator.logout("Logout", "sidebar", key="logout_button_stauth_v_final_final")

    cookie_config = st.secrets.get("cookie", {}).to_dict()
    cookie_key = cookie_config.get("key")
    placeholder_cookie_keys = [
        "some_signature_key", "NovaChaveSecretaSuperForteParaAuthenticatorV2", 
        "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA",
        "Chaim5778ToViN5728erobmaloRU189154", "wR#sVn8gP!zY2qXmK7@cJ3*bL1$fH9"
    ]
    if cookie_key in placeholder_cookie_keys:
        st.sidebar.warning("Aviso: cookie.key é um placeholder. Use uma chave FORTE!", icon="⚠️")

    GOOGLE_API_KEY = None
    llm_model_instance = None
    try:
        GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
        st.stop()

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
        st.stop()
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                 temperature=0.75,
                                                 google_api_key=GOOGLE_API_KEY,
                                                 convert_system_message_to_human=True)
        except Exception as e:
            st.error(f"ERRO AO INICIALIZAR O MODELO LLM: {e}")
            st.stop()
    
    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: 
                st.error("Erro: Modelo LLM não inicializado corretamente.")
                st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_v16stauth", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_v16stauth", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_v16stauth", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_v16stauth"):
            prompt_template = ChatPromptTemplate.from_messages([ 
                SystemMessagePromptTemplate.from_template(system_message_content), 
                MessagesPlaceholder(variable_name=memory_key_placeholder), 
                HumanMessagePromptTemplate.from_template("{input_usuario}")
            ])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            base_key_mkt = "mkt_v16_stauth" 
            # ... (código completo da função marketing_digital_guiado como na sua última versão funcional, garantindo chaves únicas)
            st.info("Seção de Marketing Digital em desenvolvimento.")


        def conversar_plano_de_negocios(self, input_usuario):
            system_message = "Assistente PME Pro: Consultor de Plano de Negócios."
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

        def calcular_precos_interativo(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Calculadora de Preços Inteligente."
            if kwargs.get('descricao_imagem_contexto'):
                system_message += f" Contexto da imagem: {kwargs['descricao_imagem_contexto']}"
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

        def gerar_ideias_para_negocios(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Gerador de Ideias para Negócios."
            if kwargs.get('contexto_arquivos'):
                system_message += f" Contexto dos arquivos: {kwargs['contexto_arquivos']}"
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        chat_display_key = f"chat_display_{area_chave}_v16stauth"
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia: 
            memoria_agente_instancia.clear()
            if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
            elif hasattr(memoria_agente_instancia.chat_memory, 'messages'):
                memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
        if area_chave == "calculo_precos": 
            st.session_state.pop(f'last_uploaded_image_info_pricing_v16stauth', None)
            st.session_state.pop(f'processed_image_id_pricing_v16stauth', None)
        elif area_chave == "gerador_ideias": 
            st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_v16stauth', None)
            st.session_state.pop(f'processed_file_id_ideias_v16stauth', None)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}_v16stauth"; chat_input_key = f"chat_input_{area_chave}_v16stauth"
        if chat_display_key not in st.session_state: 
            st.warning("Sessão de chat não iniciada."); return
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
        prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            with st.spinner("Processando..."): resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai}); st.rerun()

    if llm_model_instance:
        agente_key = "agente_pme_v16stauth"
        if agente_key not in st.session_state: 
            st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state[agente_key]
        URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
        st.sidebar.title("Menu Assistente PME Pro")
        st.sidebar.markdown("---")
        opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital": "marketing_guiado", "Plano de Negócios": "plano_negocios", "Cálculo de Preços": "calculo_precos", "Gerador de Ideias": "gerador_ideias"}
        current_area_key_main = "area_selecionada_v16stauth"
        if current_area_key_main not in st.session_state: 
            st.session_state[current_area_key_main] = "Página Inicial"
        for _, chave_secao_init_loop_main_v7 in opcoes_menu.items():
            if chave_secao_init_loop_main_v7 not in ["marketing_guiado", "pagina_inicial"]:
                chat_key_init_loop_main_v7 = f"chat_display_{chave_secao_init_loop_main_v7}_v16stauth"
                if chat_key_init_loop_main_v7 not in st.session_state:
                    st.session_state[chat_key_init_loop_main_v7] = []
        previous_area_key_main_nav_loop_main_v7 = "previous_area_selec_v16stauth_nav"
        if previous_area_key_main_nav_loop_main_v7 not in st.session_state: 
            st.session_state[previous_area_key_main_nav_loop_main_v7] = None
        area_selecionada_label = st.sidebar.radio("Navegação Principal:", options=list(opcoes_menu.keys()), key='sidebar_select_v16stauth', index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main]))
        if area_selecionada_label != st.session_state[current_area_key_main]:
            st.session_state[current_area_key_main] = area_selecionada_label; st.rerun()
        current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

        if current_section_key_val not in ["pagina_inicial", "marketing_guiado"]:
            if st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_main_nav_loop_main_v7):
                chat_display_key_nav = f"chat_display_{current_section_key_val}_v16stauth"
                msg_inicial_nav = ""; memoria_agente_nav = None
                if not st.session_state.get(chat_display_key_nav): 
                    if current_section_key_val == "plano_negocios": 
                        msg_inicial_nav = "Olá! Sou seu assistente para Planos de Negócios. Como posso ajudar?"
                        memoria_agente_nav = agente.memoria_plano_negocios
                    elif current_section_key_val == "calculo_precos": 
                        msg_inicial_nav = "Bem-vindo ao assistente de Cálculo de Preços. Qual produto ou serviço vamos precificar?"
                        memoria_agente_nav = agente.memoria_calculo_precos
                    elif current_section_key_val == "gerador_ideias": 
                        msg_inicial_nav = "Pronto para um brainstorm? Sobre o que você gostaria de gerar ideias?"
                        memoria_agente_nav = agente.memoria_gerador_ideias
                    if msg_inicial_nav and memoria_agente_nav is not None: 
                        inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
                st.session_state[previous_area_key_main_nav_loop_main_v7] = st.session_state[current_area_key_main]

        if current_section_key_val == "pagina_inicial":
            st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name_from_session}!</h1><img src='{URL_DO_SEU_LOGO}' width='150'></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p>Use o menu à esquerda para explorar as funcionalidades.</p></div>", unsafe_allow_html=True)
        elif current_section_key_val == "marketing_guiado":
            agente.marketing_digital_guiado()
        elif current_section_key_val == "plano_negocios":
            st.header("📝 Plano de Negócios com IA")
            exibir_chat_e_obter_input(current_section_key_val, "Descreva sua ideia ou faça perguntas sobre seu plano de negócios...", agente.conversar_plano_de_negocios)
            if st.sidebar.button("Reiniciar Plano", key="btn_reset_plano_v16stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Plano de negócios reiniciado. Como posso ajudar?", agente.memoria_plano_negocios); st.rerun()
        elif current_section_key_val == "calculo_precos":
            st.header("💲 Cálculo de Preços Inteligente")
            exibir_chat_e_obter_input(current_section_key_val, "Detalhes do produto/serviço para precificação...", agente.calcular_precos_interativo)
            if st.sidebar.button("Reiniciar Cálculo", key="btn_reset_precos_v16stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Novo cálculo de preços. Descreva o item.", agente.memoria_calculo_precos); st.rerun()
        elif current_section_key_val == "gerador_ideias":
            st.header("💡 Gerador de Ideias para Negócios")
            exibir_chat_e_obter_input(current_section_key_val, "Qual seu desafio ou área de interesse para novas ideias?", agente.gerar_ideias_para_negocios)
            if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v16stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Pronto para novas ideias! Qual o foco?", agente.memoria_gerador_ideias); st.rerun()
    else:
        # Se o modelo LLM não carregou, mas o usuário está autenticado, mostre uma mensagem de erro
        if st.session_state.get('authentication_status'):
            st.error("Modelo de Linguagem (LLM) não pôde ser carregado. Funcionalidades de IA limitadas.")
        # Se não está autenticado (False ou None), a lógica abaixo trata de exibir o formulário/mensagens de login
        
elif st.session_state['authentication_status'] is False:
    # O widget authenticator.login() (chamado via authentication_flow_stauth) já exibiu "Username/password is incorrect".
    # Adicionar st.error aqui pode ser redundante ou causar dupla mensagem.
    pass 
elif st.session_state['authentication_status'] is None:
    # O widget authenticator.login() já exibiu "Please enter your username and password" e o formulário.
    # Podemos adicionar um logo ou título geral da página aqui, que aparecerá com o formulário de login.
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    if URL_DO_SEU_LOGO_LOGIN: # Para evitar erro se a URL estiver vazia
        cols_login_header = st.columns([1,2,1]) 
        with cols_login_header[1]: 
            st.image(URL_DO_SEU_LOGO_LOGIN, width=200) 
    st.markdown("<h2 style='text-align: center;'>Assistente PME Pro</h2>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
