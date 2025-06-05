import streamlit as st
import os
import json
import pyrebase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import AIMessage
import google.generativeai as genai
from PIL import Image
import base64
import time
import datetime
import firebase_admin
from firebase_admin import credentials, firestore as firebase_admin_firestore

# --- Constantes ---
APP_KEY_SUFFIX = "maxia_app_v1.1_stable"
USER_COLLECTION = "users"
ACTIVATION_KEYS_COLLECTION = "activation_keys" # Mantido para referência futura
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- Funções Auxiliares e de Configuração ---
def convert_image_to_base64(image_path):
    try:
        if not os.path.exists(image_path):
            print(f"DEBUG: Imagem não encontrada: {image_path}")
            return None
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        print(f"ERRO convert_image_to_base64: {e}")
        return None

@st.cache_resource
def initialize_firebase_services():
    """Inicializa Pyrebase Auth e Firebase Admin SDK para Firestore."""
    init_errors = []
    pb_auth = None
    firestore_db = None
    try:
        conf = st.secrets["firebase_config"]
        pb_auth = pyrebase.initialize_app(dict(conf)).auth()
    except Exception as e:
        init_errors.append(f"ERRO Auth: {e}")
    try:
        sa_creds = st.secrets["gcp_service_account"]
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(sa_creds))
            firebase_admin.initialize_app(cred)
        firestore_db = firebase_admin_firestore.client()
    except Exception as e:
        init_errors.append(f"ERRO Firestore: {e}")
    return pb_auth, firestore_db, init_errors

# --- Configuração da Página e Inicialização dos Serviços ---
try:
    page_icon_img_obj = Image.open("images/carinha-agente-max-ia.png") if os.path.exists("images/carinha-agente-max-ia.png") else "🤖"
except Exception: page_icon_img_obj = "🤖"
st.set_page_config(page_title="Max IA", page_icon=page_icon_img_obj, layout="wide", initial_sidebar_state="expanded")

pb_auth_client, firestore_db, init_errors = initialize_firebase_services()

if f'{APP_KEY_SUFFIX}_init_msgs_shown' not in st.session_state:
    if pb_auth_client: st.sidebar.success("✅ Firebase Auth OK.")
    else: st.sidebar.error("❌ Firebase Auth FALHOU.")
    if firestore_db: st.sidebar.success("✅ Firestore DB OK.")
    else: st.sidebar.error("❌ Firestore DB FALHOU.")
    if init_errors:
        for err in init_errors: st.sidebar.error(f"Init Error: {err}")
    st.session_state[f'{APP_KEY_SUFFIX}_init_msgs_shown'] = True

if not pb_auth_client:
    st.error("ERRO CRÍTICO: Autenticação Firebase não inicializada.")
    st.stop()

# --- Lógica de Sessão e Autenticação (Simplificada) ---
def get_current_user_status(auth_client):
    user_auth, uid, email = False, None, None
    session_key = f'{APP_KEY_SUFFIX}_user_session_data'
    if session_key in st.session_state and st.session_state[session_key]:
        try:
            session_data = st.session_state[session_key]
            # Valida o token e obtém informações atualizadas
            account_info = auth_client.get_account_info(session_data['idToken'])
            user_auth = True
            user_info = account_info['users'][0]
            uid = user_info['localId']
            email = user_info.get('email')
            st.session_state[session_key].update({'localId': uid, 'email': email})
        except Exception:
            st.session_state.pop(session_key, None)
            user_auth = False
            if 'auth_error_shown' not in st.session_state:
                 st.sidebar.warning("Sessão inválida. Faça login novamente.")
                 st.session_state['auth_error_shown'] = True
            st.rerun()
            
    st.session_state.user_is_authenticated = user_auth
    st.session_state.user_uid = uid
    st.session_state.user_email = email
    return user_auth, uid, email

user_is_authenticated, user_uid, user_email = get_current_user_status(pb_auth_client)

# --- Inicialização do LLM ---
llm = None
if user_is_authenticated:
    llm_key = f'{APP_KEY_SUFFIX}_llm_instance'
    if llm_key not in st.session_state:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.session_state[llm_key] = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=api_key, temperature=0.7)
            if 'llm_msg_shown' not in st.session_state:
                st.sidebar.success("✅ LLM (Gemini) OK.")
                st.session_state['llm_msg_shown'] = True
        except Exception as e: st.error(f"Erro ao inicializar LLM: {e}")
    llm = st.session_state.get(llm_key)

# --- Funções _marketing_handle_... e outras funções utilitárias ---
# (Aqui entram as funções que você já tinha, que são chamadas pelo MaxAgente)
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj{APP_KEY_SUFFIX}")
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{APP_KEY_SUFFIX}")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{APP_KEY_SUFFIX}")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{APP_KEY_SUFFIX}")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{APP_KEY_SUFFIX}")
    details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone{APP_KEY_SUFFIX}")
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{APP_KEY_SUFFIX}")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    try:
        st.download_button(
            label="📥 Baixar Conteúdo Gerado",
            data=generated_content.encode('utf-8'),
            file_name=f"{file_name_prefix}_{section_key}{APP_KEY_SUFFIX}.txt",
            mime="text/plain",
            key=f"download_{section_key}_{file_name_prefix}{APP_KEY_SUFFIX}"
        )
    except Exception as e_download:
        st.error(f"Erro ao tentar renderizar o botão de download: {e_download}")

def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_criar_post)
    pass

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_criar_campanha)
    pass

def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_criar_landing_page)
    pass

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_criar_site)
    pass

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_encontre_cliente)
    pass

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_conheca_concorrencia)
    pass

def _marketing_handle_detalhar_campanha(uploaded_files_info, plano_campanha_gerado, llm):
    # ... (cole aqui o corpo COMPLETO da sua função _marketing_handle_detalhar_campanha)
    pass

def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    # ... (cole aqui o corpo COMPLETO da sua função inicializar_ou_resetar_chat)
    pass

def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    # ... (cole aqui o corpo COMPLETO da sua função exibir_chat_e_obter_input)
    pass

def _sidebar_clear_button_max(label, memoria, section_key_prefix):
    # ... (cole aqui o corpo COMPLETO da sua função _sidebar_clear_button_max)
    pass

def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
    # ... (cole aqui o corpo COMPLETO da sua função _handle_chat_with_image)
    pass

def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
    # ... (cole aqui o corpo COMPLETO da sua função _handle_chat_with_files)
    pass
# --- Definição da Classe MaxAgente ---
class MaxAgente:
    def __init__(self, llm_instance, db_firestore_instance):
        self.llm = llm_instance
        self.db = db_firestore_instance
        if not self.llm: st.warning("MaxAgente: LLM não disponível.")
        if not self.db: st.warning("MaxAgente: Firestore não disponível.")

        # --- Bloco de inicialização de memória (Preservado do seu código) ---
        if f'memoria_max_bussola_plano{APP_KEY_SUFFIX}' not in st.session_state:
            st.session_state[f'memoria_max_bussola_plano{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_plano{APP_KEY_SUFFIX}", return_messages=True)
        if f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}' not in st.session_state:
            st.session_state[f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_ideias{APP_KEY_SUFFIX}", return_messages=True)
        if f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}' not in st.session_state:
            st.session_state[f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_financeiro_precos{APP_KEY_SUFFIX}", return_messages=True)

        self.memoria_max_bussola_plano = st.session_state[f'memoria_max_bussola_plano{APP_KEY_SUFFIX}']
        self.memoria_max_bussola_ideias = st.session_state[f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}']
        self.memoria_max_financeiro_precos = st.session_state[f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}']
        self.memoria_plano_negocios = self.memoria_max_bussola_plano
        self.memoria_calculo_precos = self.memoria_max_financeiro_precos
        self.memoria_gerador_ideias = self.memoria_max_bussola_ideias
    
    def _criar_cadeia_conversacional(self, system_message, memoria):
        if not self.llm: return None
        # ... (seu código original para _criar_cadeia_conversacional)
        actual_memory_key = memoria.memory_key
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=actual_memory_key),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria, verbose=False)

    # --- Métodos dos Agentes (Preservados do seu código original) ---
    def exibir_max_marketing_total(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_marketing_total)
        # O código de exemplo abaixo é apenas para estrutura.
        st.header("🚀 MaxMarketing Total")
        st.write("Conteúdo e ferramentas de marketing aqui...")
        # Lembrete: Se esta função precisar usar o Firestore, use `self.db`
        # Exemplo: doc_ref = self.db.collection("...").document(...)

    def exibir_max_financeiro(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_financeiro)
        st.header("💰 MaxFinanceiro")
        st.write("Conteúdo e ferramentas de finanças aqui...")
        
    def exibir_max_administrativo(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_administrativo)
        st.header("⚙️ MaxAdministrativo")
        st.write("Conteúdo e ferramentas de administração aqui...")
    
    def exibir_max_pesquisa_mercado(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_pesquisa_mercado)
        st.header("📈 MaxPesquisa de Mercado")
        st.write("Conteúdo e ferramentas de pesquisa de mercado aqui...")
    
    def exibir_max_bussola(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_bussola)
        st.header("🧭 MaxBússola Estratégica")
        st.write("Conteúdo e ferramentas de estratégia aqui...")
        
    def exibir_max_trainer(self):
        # ... (Cole aqui TODO o conteúdo original da sua função exibir_max_trainer)
        st.header("🎓 MaxTrainer IA")
        st.write("Conteúdo e ferramentas de treinamento aqui...")

# --- Instanciação do Agente ---
agente = None
if user_is_authenticated and llm: # Só instancia se autenticado e com LLM
    agent_key = f'{APP_KEY_SUFFIX}_agente_instancia'
    if agent_key not in st.session_state:
        # Passa o cliente LLM e o cliente Firestore para o agente
        st.session_state[agent_key] = MaxAgente(llm_instance=llm, db_firestore_instance=firestore_db)
    agente = st.session_state[agent_key]

# --- Lógica Principal da Interface ---
if not user_is_authenticated:
    st.title("🔑 Bem-vindo ao Max IA")
    auth_action = st.sidebar.radio("Acesso:", ["Login", "Registrar"], key=f"{APP_KEY_SUFFIX}_auth_choice")
    if auth_action == "Login":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if email and password and pb_auth_client:
                    try:
                        user_creds = pb_auth_client.sign_in_with_email_and_password(email, password)
                        st.session_state[f'{APP_KEY_SUFFIX}_user_session_data'] = dict(user_creds)
                        # Limpa caches para forçar re-verificação no próximo carregamento
                        for k in list(st.session_state.keys()):
                            if '_init_msgs_shown' in k or '_is_user_activated_' in k:
                                del st.session_state[k]
                        st.rerun()
                    except Exception as e: st.sidebar.error(f"Erro no login: Verifique as credenciais.")
    else: # Registrar
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_register_form"):
            email = st.text_input("Seu Email")
            password = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
            if st.form_submit_button("Registrar Conta"):
                if email and password and len(password) >= 6 and pb_auth_client and firestore_db:
                    try:
                        new_user = pb_auth_client.create_user_with_email_and_password(email, password)
                        user_doc = firestore_db.collection(USER_COLLECTION).document(new_user['localId'])
                        user_doc.set({"email": email, "is_activated": False, "registration_date": firebase_admin_firestore.SERVER_TIMESTAMP}, merge=True)
                        st.sidebar.success(f"Conta criada! Faça o login.")
                    except Exception as e: st.sidebar.error(f"Erro no registro: {e}")
                else:
                    if not firestore_db: st.sidebar.error("Serviço de registro indisponível (DB).")
                    else: st.sidebar.warning("Preencha os campos corretamente.")
else: # Usuário está autenticado, exibe o app principal
    st.sidebar.write(f"Logado como: **{user_email}**")
    if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_logout_button"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    # Renderiza a interface principal do agente
    if agente:
        # --- (COLE AQUI O SEU CÓDIGO ORIGINAL DA SIDEBAR E LÓGICA DE NAVEGAÇÃO) ---
        # Exemplo simplificado de como ficaria:
        st.sidebar.markdown("---")
        st.sidebar.title("Max IA")
        opcoes_menu = {
            "👋 Boas-vindas": "boas_vindas", 
            "🚀 MaxMarketing": "marketing",
            "💰 MaxFinanceiro": "financeiro"
            # Adicione suas outras opções de agente aqui
        }
        view_key = f'{APP_KEY_SUFFIX}_current_view'
        if view_key not in st.session_state: st.session_state[view_key] = "boas_vindas"
        
        try: current_idx = list(opcoes_menu.values()).index(st.session_state[view_key])
        except ValueError: current_idx = 0

        selected_label = st.sidebar.radio("Navegar Agentes:", list(opcoes_menu.keys()), index=current_idx, key=f"{APP_KEY_SUFFIX}_nav")
        if opcoes_menu[selected_label] != st.session_state[view_key]:
            st.session_state[view_key] = opcoes_menu[selected_label]
            st.rerun()
        
        # Renderiza a view selecionada
        if st.session_state[view_key] == "boas_vindas": agente.exibir_painel_boas_vindas()
        elif st.session_state[view_key] == "marketing": agente.exibir_max_marketing_total()
        elif st.session_state[view_key] == "financeiro": agente.exibir_max_financeiro()
        # Adicione elif para outras views...
    else:
        st.error("Agente Max IA não pôde ser carregado. Verifique os erros de inicialização.")

st.sidebar.markdown("---")
st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini Pro")
