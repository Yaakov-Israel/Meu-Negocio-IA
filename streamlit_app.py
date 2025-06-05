import os
import streamlit as st
import base64
from PIL import Image
import time
import datetime
import json

# --- Firebase Imports ---
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore as firebase_admin_firestore

# --- Langchain/Gemini Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import AIMessage

# --- Constantes ---
APP_KEY_SUFFIX = "maxia_app_v0.7"
USER_COLLECTION = "users"
ACTIVATION_KEYS_COLLECTION = "activation_keys"

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- Funções Auxiliares ---
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

# --- Funções do Sistema de Ativação ---
def check_user_activation_status_firestore(user_uid, db_client):
    if not db_client:
        raise ValueError("Firestore não conectado para verificar ativação.")
    try:
        user_ref = db_client.collection(USER_COLLECTION).document(user_uid)
        user_doc = user_ref.get()
        return user_doc.exists and user_doc.to_dict().get("is_activated", False)
    except Exception as e:
        print(f"ERRO (check_user_activation_status_firestore) para UID {user_uid}: {type(e).__name__} - {e}")
        raise

def process_activation_key_firestore(user_uid, key_code, db_client):
    if not db_client: return False, "Erro interno: Banco de dados indisponível."
    if not key_code: return False, "Por favor, insira uma chave de ativação."

    key_ref = db_client.collection(ACTIVATION_KEYS_COLLECTION).document(key_code)
    user_ref = db_client.collection(USER_COLLECTION).document(user_uid)

    @firebase_admin_firestore.transactional
    def claim_key_transaction(transaction, key_doc_ref, user_doc_ref):
        key_snapshot = key_doc_ref.get(transaction=transaction)
        if not key_snapshot.exists:
            return False, "Chave de ativação não encontrada ou inválida."
        
        key_data = key_snapshot.to_dict()
        if key_data.get("is_used", False):
            return False, "Chave de ativação já foi utilizada."
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        transaction.update(key_doc_ref, {"is_used": True, "used_by_uid": user_uid, "activation_date": now_utc})
        transaction.set(user_doc_ref, {"is_activated": True, "activated_at": now_utc}, merge=True)
        return True, "Chave ativada com sucesso! Bem-vindo ao Max IA."

    try:
        return claim_key_transaction(db_client.transaction(), key_ref, user_ref)
    except Exception as e:
        print(f"ERRO (process_activation_key_firestore): {type(e).__name__} - {e}")
        if "deadline exceeded" in str(e).lower() or "timeout" in str(e).lower():
            return False, "Tempo esgotado ao validar a chave. Tente mais tarde."
        return False, f"Ocorreu um erro ao processar sua chave. Tente novamente."

def display_activation_prompt_area(user_uid, db_client):
    st.subheader("🔑 Ativação do Max IA")
    st.info("Para utilizar esta funcionalidade, por favor, ative sua conta com uma chave válida.")
    
    with st.form(key=f"{APP_KEY_SUFFIX}_activation_form"):
        key_code_input = st.text_input("Sua Chave de Ativação", type="password")
        submit_button = st.form_submit_button("✅ Ativar Agora")
        if submit_button:
            with st.spinner("Validando sua chave..."):
                success, msg = process_activation_key_firestore(user_uid, key_code_input, db_client)
            if success:
                st.success(msg + " Atualizando seu acesso...")
                st.session_state.is_user_activated = True
                time.sleep(1.5)
                st.rerun()
            else: st.error(msg)
    st.caption("Não possui uma chave? Entre em contato com o suporte.")

# --- Configuração da Página Streamlit ---
try:
    page_icon_img_obj = Image.open("images/carinha-agente-max-ia.png") if os.path.exists("images/carinha-agente-max-ia.png") else "🤖"
except Exception: page_icon_img_obj = "🤖"
st.set_page_config(page_title="Max IA", page_icon=page_icon_img_obj, layout="wide", initial_sidebar_state="expanded")

# --- Inicialização Centralizada e Cacheada do Firebase ---
@st.cache_resource
def initialize_firebase_services():
    init_errors = []
    try:
        conf = st.secrets["firebase_config"]
        pb_auth = pyrebase.initialize_app(dict(conf)).auth()
    except Exception as e:
        pb_auth = None
        init_errors.append(f"ERRO Auth: {e}")
    try:
        sa_creds = st.secrets["gcp_service_account"]
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(sa_creds))
            firebase_admin.initialize_app(cred)
        firestore_db = firebase_admin_firestore.client()
    except Exception as e:
        firestore_db = None
        init_errors.append(f"ERRO Firestore: {e}")
    return pb_auth, firestore_db, init_errors

pb_auth_client, firestore_db, init_errors = initialize_firebase_services()

if f'{APP_KEY_SUFFIX}_init_msgs_shown' not in st.session_state:
    if pb_auth_client: st.sidebar.success("✅ Firebase Auth OK.")
    if firestore_db: st.sidebar.success("✅ Firestore DB OK.")
    if init_errors:
        for err in init_errors: st.sidebar.error(err)
    st.session_state[f'{APP_KEY_SUFFIX}_init_msgs_shown'] = True

if not pb_auth_client:
    st.error("ERRO CRÍTICO: Autenticação Firebase não inicializada.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
def get_current_user_status(auth_client, db_client):
    user_auth, user_act, uid, email = False, False, None, None
    session_key = f'{APP_KEY_SUFFIX}_user_session_data'
    if session_key in st.session_state and st.session_state[session_key]:
        try:
            session_data = st.session_state[session_key]
            account_info = auth_client.get_account_info(session_data['idToken'])
            user_auth = True
            user_info = account_info['users'][0]
            uid = user_info['localId']
            email = user_info.get('email')
            st.session_state[session_key].update({'localId': uid, 'email': email})
            if db_client and uid:
                user_act = check_user_activation_status_firestore(uid, db_client)
        except Exception as e:
            st.session_state.pop(session_key, None)
            user_auth = False
            if 'auth_error_shown' not in st.session_state:
                 st.sidebar.warning("Sessão inválida. Faça login novamente.")
                 st.session_state['auth_error_shown'] = True
            st.rerun()
            
    st.session_state.user_is_authenticated = user_auth
    st.session_state.is_user_activated = user_act
    st.session_state.user_uid = uid
    st.session_state.user_email = email
    return user_auth, user_act, uid, email

user_is_authenticated, user_is_activated, user_uid, user_email = get_current_user_status(pb_auth_client, firestore_db)

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
# --- Definição da Classe MaxAgente e Funções Utilitárias ---
class MaxAgente:
    def __init__(self, llm_instance, db_firestore_instance):
        self.llm = llm_instance
        self.db = db_firestore_instance
        if not self.llm: st.warning("MaxAgente: LLM não disponível.")
        if not self.db: st.warning("MaxAgente: Firestore não disponível.")
        # Adicione aqui a inicialização das suas memórias, usando APP_KEY_SUFFIX
        # Exemplo:
        self.memoria_plano_key = f'{APP_KEY_SUFFIX}_mem_plano'
        if self.memoria_plano_key not in st.session_state:
            st.session_state[self.memoria_plano_key] = ConversationBufferMemory(memory_key=f"{APP_KEY_SUFFIX}_hist_plano", return_messages=True)
        self.memoria_plano_negocios = st.session_state[self.memoria_plano_key]
        # ... e assim por diante para as outras memórias ...

    def _check_activation_and_prompt(self, feature_name="Esta funcionalidade"):
        """Verifica se o usuário está ativado. Se não, mostra o prompt e retorna True para bloquear."""
        if not st.session_state.get('is_user_activated', False):
            st.session_state[f'{APP_KEY_SUFFIX}_show_activation_prompt_area'] = True
            return True # Bloqueia
        st.session_state.pop(f'{APP_KEY_SUFFIX}_show_activation_prompt_area', None)
        return False # Não bloqueia

    # !!! DEV MASTER: Métodos do Agente para você preencher com a lógica !!!
    def exibir_painel_boas_vindas(self):
        st.header(f"👋 Bem-vindo ao Max IA, {st.session_state.user_email or 'Empreendedor'}!")
        st.write("Use o menu à esquerda para explorar as funcionalidades do seu assistente de negócios IA.")
        if not st.session_state.get('is_user_activated', False):
             st.info("Sua conta ainda não está ativada. Algumas funcionalidades solicitarão ativação com uma chave válida.")
        else:
            st.success("🎉 Sua conta Max IA está ativa! Explore todo o potencial.")

    def exibir_max_marketing_total(self):
        if self._check_activation_and_prompt("o MaxMarketing Total"): return
        if not self.llm: st.error("MaxMarketing indisponível: LLM não está pronto."); return
        st.header("🚀 MaxMarketing Total (Acesso Permitido)")
        st.write("O conteúdo e as ferramentas de Marketing do Max IA aparecerão aqui.")
        # Lembrete: Se esta função precisar usar o Firestore, use `self.db.collection(...)`

    def exibir_max_financeiro(self):
        if self._check_activation_and_prompt("o MaxFinanceiro"): return
        if not self.llm: st.error("MaxFinanceiro indisponível: LLM não está pronto."); return
        st.header("💰 MaxFinanceiro (Acesso Permitido)")
        st.write("O conteúdo e as ferramentas de Finanças do Max IA aparecerão aqui.")
    
    # Adicione os outros métodos de exibição aqui...
    # ...

# --- Instanciação do Agente ---
agente = None
if user_is_authenticated and llm and firestore_db:
    agent_key = f'{APP_KEY_SUFFIX}_agente_instancia'
    if agent_key not in st.session_state:
        st.session_state[agent_key] = MaxAgente(llm_instance=llm, db_firestore_instance=firestore_db)
    agente = st.session_state[agent_key]

# --- FLUXO PRINCIPAL DA INTERFACE ---
if not user_is_authenticated:
    st.title("🔑 Bem-vindo ao Max IA")
    # ... (código da tela de login/registro como na minha resposta anterior) ...
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
                        for k in list(st.session_state.keys()): # Limpa caches antigos ao logar
                            if '_init_msgs_shown' in k or '_is_user_activated_' in k:
                                del st.session_state[k]
                        st.rerun()
                    except Exception as e: st.sidebar.error(f"Erro no login: {e}")
                else: st.sidebar.warning("Preencha todos os campos.")
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
                        try: pb_auth_client.send_email_verification(new_user['idToken'])
                        except: pass
                    except Exception as e: st.sidebar.error(f"Erro no registro: {e}")
                else: st.sidebar.warning("Preencha os campos corretamente. Firestore deve estar conectado para registro.")
else: # Usuário está autenticado
    st.sidebar.write(f"Logado como: **{user_email}**")
    if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_logout_button"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    # TESTE DE CONECTIVIDADE
    if firestore_init_ok:
        test_key = f'{APP_KEY_SUFFIX}_firestore_test_completed'
        if test_key not in st.session_state:
            st.session_state[test_key] = firestore_test_connectivity(firestore_db, user_uid)

    # LÓGICA DE NAVEGAÇÃO E EXIBIÇÃO
    if st.session_state.get(f'{APP_KEY_SUFFIX}_show_activation_prompt_area'):
        display_activation_prompt_area(user_uid, firestore_db)
    elif agente:
        opcoes_menu = {"👋 Boas-vindas": "boas_vindas", "🚀 MaxMarketing": "marketing", "💰 MaxFinanceiro": "financeiro"}
        view_key = f'{APP_KEY_SUFFIX}_current_view'
        if view_key not in st.session_state: st.session_state[view_key] = "boas_vindas"
        
        try: current_idx = list(opcoes_menu.values()).index(st.session_state[view_key])
        except ValueError: current_idx = 0

        selected_label = st.sidebar.radio("Navegar Agentes:", list(opcoes_menu.keys()), index=current_idx, key=f"{APP_KEY_SUFFIX}_nav")
        st.session_state[view_key] = opcoes_menu[selected_label]
        
        # Renderiza a view selecionada
        if st.session_state[view_key] == "boas_vindas": agente.exibir_painel_boas_vindas()
        elif st.session_state[view_key] == "marketing": agente.exibir_max_marketing_total()
        elif st.session_state[view_key] == "financeiro": agente.exibir_max_financeiro()
        # Adicione elif para outras views...
    else:
        st.error("Agente Max IA não pôde ser carregado. Verifique os erros de inicialização.")

st.sidebar.markdown("---")
st.sidebar.info(f"Max IA v{APP_KEY_SUFFIX.split('_')[-1]} | Desenvolvido por Yaakov Israel com Gemini Pro")
