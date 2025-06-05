import os
import streamlit as st
import base64
from PIL import Image
import time
import datetime
import json

# --- Firebase Imports ---
import pyrebase  # Para autenticação de usuários
import firebase_admin
from firebase_admin import credentials, firestore as firebase_admin_firestore # Alias para clareza

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
APP_KEY_SUFFIX = "maxia_app_v0.6" # Novo sufixo para esta versão
USER_COLLECTION = "users" # No Firestore
ACTIVATION_KEYS_COLLECTION = "activation_keys" # No Firestore

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- Função Auxiliar para Imagem em Base64 ---
def convert_image_to_base64(image_path):
    try:
        if not os.path.exists(image_path):
            print(f"DEBUG: Imagem não encontrada em convert_image_to_base64: {image_path}")
            return None
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        print(f"ERRO convert_image_to_base64: {e}")
        return None

# --- Funções de Teste e Sistema de Ativação ---
def firestore_test_connectivity(db_client, test_user_uid="test_connectivity_user_main"):
    """Função simples para testar leitura/escrita básica no Firestore."""
    if not db_client:
        st.sidebar.error("❌ TESTE Firestore: Cliente DB é None.")
        return False
    try:
        test_collection_name = f"{APP_KEY_SUFFIX}_connectivity_tests_main"
        test_doc_ref = db_client.collection(test_collection_name).document(test_user_uid)
        test_data = {
            "timestamp": firebase_admin_firestore.SERVER_TIMESTAMP, 
            "status": "ok_from_streamlit_main_test", 
            "test_run_id": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        test_doc_ref.set(test_data, merge=True)
        time.sleep(0.3) # Pequeno delay para propagação
        doc_snapshot = test_doc_ref.get()

        if doc_snapshot.exists and doc_snapshot.to_dict().get("status") == "ok_from_streamlit_main_test":
            st.sidebar.success(f"✅ TESTE Firestore: Conexão Leitura/Escrita OK!")
            return True
        else:
            details = f"Doc existe: {doc_snapshot.exists}."
            if doc_snapshot.exists: details += f" Conteúdo: {doc_snapshot.to_dict()}"
            st.sidebar.error(f"❌ TESTE Firestore: Falha na verificação R/W. {details}")
            return False
    except Exception as e:
        st.sidebar.error(f"❌ TESTE Firestore: Exceção - {type(e).__name__}: {e}")
        print(f"DEBUG: Exceção no teste de conectividade Firestore: {type(e).__name__} - {e}")
        return False

def check_user_activation_status_firestore(user_uid, db_firestore_instance):
    if not db_firestore_instance:
        print("CRITICAL_ERROR: db_firestore_instance é None em check_user_activation_status_firestore.")
        raise ValueError("Conexão com banco de dados (Firestore) não estabelecida para verificar ativação.")
    try:
        user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)
        user_doc = user_ref.get()
        if user_doc.exists:
            return user_doc.to_dict().get("is_activated", False)
        return False
    except Exception as e:
        print(f"ERRO (check_user_activation_status_firestore) para UID {user_uid}: {type(e).__name__} - {e}")
        raise # Re-levanta a exceção para ser tratada pela função chamadora (ex: get_current_user_status)

def process_activation_key_firestore(user_uid, key_code, db_firestore_instance):
    if not db_firestore_instance:
        return False, "Erro interno: Conexão com banco de dados de chaves indisponível."
    if not key_code:
        return False, "Por favor, insira uma chave de ativação."

    key_ref = db_firestore_instance.collection(ACTIVATION_KEYS_COLLECTION).document(key_code)
    user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)

    @firebase_admin_firestore.transactional
    def claim_key_transaction_atomic(transaction, key_doc_ref_trans, user_doc_ref_trans):
        key_snapshot = key_doc_ref_trans.get(transaction=transaction)
        if not key_snapshot.exists:
            return False, "Chave de ativação não encontrada ou inválida."
        key_data = key_snapshot.to_dict()
        if key_data.get("is_used", False):
            return False, "Chave de ativação já utilizada." # Simplificado
        else: 
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            transaction.update(key_doc_ref_trans, {
                "is_used": True, "used_by_uid": user_uid, "activation_date": now_utc
            })
            transaction.set(user_doc_ref_trans, {
                "is_activated": True, "last_activation_key_used": key_code, "activated_at": now_utc
            }, merge=True)
            return True, "Chave ativada com sucesso! Bem-vindo ao Max IA."
    try:
        transaction_instance = db_firestore_instance.transaction()
        success, message = claim_key_transaction_atomic(transaction_instance, key_ref, user_ref)
        return success, message
    except Exception as e:
        print(f"ERRO (process_activation_key_firestore - transação) UID {user_uid}, Chave {key_code}: {type(e).__name__} - {e}")
        if "deadline exceeded" in str(e).lower() or "timeout" in str(e).lower():
            return False, "Tempo esgotado ao validar a chave. Verifique sua conexão ou tente mais tarde."
        return False, f"Ocorreu um erro ao processar sua chave ({type(e).__name__}). Tente novamente ou contate o suporte."

def display_activation_prompt_area(user_uid_for_activation, db_client_for_activation, key_suffix="main_prompt"):
    if not db_client_for_activation:
        st.error("Serviço de ativação indisponível (DB).")
        return
    st.subheader("🔑 Ativação Necessária")
    st.info("Para utilizar esta funcionalidade do Max IA, por favor, ative sua conta com uma chave válida.")
    
    form_key = f"{APP_KEY_SUFFIX}_activation_form_{key_suffix}"
    expander_state_key = f"{APP_KEY_SUFFIX}_activation_expander_state_{key_suffix}"

    if expander_state_key not in st.session_state:
        st.session_state[expander_state_key] = False

    if st.button("🔑 Inserir Chave de Ativação", key=f"{APP_KEY_SUFFIX}_toggle_activation_form_{key_suffix}"):
        st.session_state[expander_state_key] = not st.session_state[expander_state_key]

    if st.session_state[expander_state_key]:
        with st.form(key=form_key):
            key_code_input = st.text_input("Sua Chave de Ativação", type="password", key=f"{APP_KEY_SUFFIX}_key_code_input_{key_suffix}")
            submit_button = st.form_submit_button("✅ Ativar Agora")
            if submit_button:
                if not key_code_input:
                    st.warning("Por favor, insira a chave.")
                else:
                    with st.spinner("Validando sua chave..."):
                        success, msg = process_activation_key_firestore(user_uid_for_activation, key_code_input, db_client_for_activation)
                    if success:
                        st.success(msg + " Atualizando seu acesso...")
                        st.session_state[f'{APP_KEY_SUFFIX}_is_user_activated_{user_uid_for_activation}'] = True
                        st.session_state.is_user_activated = True # Atualiza estado global
                        st.session_state.pop(f'{APP_KEY_SUFFIX}_show_activation_prompt_area', None)
                        st.session_state[expander_state_key] = False # Fecha o expander
                        time.sleep(1.0) # Menor delay
                        st.rerun()
                    else:
                        st.error(msg)
    st.caption("Não possui uma chave ou precisa de ajuda? Entre em contato com o suporte.")

# --- Configuração da Página Streamlit ---
PAGE_ICON_PATH = "images/carinha-agente-max-ia.png"
try:
    page_icon_img_obj = Image.open(PAGE_ICON_PATH) if os.path.exists(PAGE_ICON_PATH) else "🤖"
except Exception: page_icon_img_obj = "🤖"
st.set_page_config(page_title="Max IA", page_icon=page_icon_img_obj, layout="wide", initial_sidebar_state="expanded")

# --- Inicialização Centralizada do Firebase ---
@st.cache_resource
def initialize_firebase_services_cached():
    loc_pb_auth_client, loc_firestore_db = None, None
    auth_initialized, firestore_initialized = False, False
    init_errors = []
    try:
        conf = st.secrets.get("firebase_config")
        if conf and all(conf.get(k) for k in ["apiKey", "authDomain", "projectId"]):
            loc_pb_auth_client = pyrebase.initialize_app(dict(conf)).auth()
            auth_initialized = True
        else: init_errors.append("ERRO: Config 'firebase_config' para Pyrebase Auth incompleta/ausente.")
    except Exception as e: init_errors.append(f"ERRO Pyrebase Auth: {e}")
    try:
        sa_creds = st.secrets.get("gcp_service_account")
        sa_path = "max-ia-firebase-service-account.json" # CONFIRME ESTE NOME DE ARQUIVO
        if not sa_creds and os.path.exists(sa_path):
            with open(sa_path) as f: sa_creds = json.load(f)
            print(f"AVISO: Usando credenciais de serviço do arquivo '{sa_path}'. Use st.secrets em produção.")
        if sa_creds:
            if not firebase_admin._apps: firebase_admin.initialize_app(credentials.Certificate(dict(sa_creds)))
            loc_firestore_db = firebase_admin_firestore.client()
            if loc_firestore_db: firestore_initialized = True
            else: init_errors.append("ERRO: firebase_admin_firestore.client() retornou None.")
        else: init_errors.append("ERRO: Credenciais 'gcp_service_account' não encontradas.")
    except Exception as e: init_errors.append(f"ERRO Firebase Admin/Firestore: {e}")
    return loc_pb_auth_client, loc_firestore_db, auth_initialized, firestore_initialized, init_errors

pb_auth_client, firestore_db, auth_init_ok, firestore_init_ok, init_errors = initialize_firebase_services_cached()

if f'{APP_KEY_SUFFIX}_init_msgs_shown' not in st.session_state:
    if auth_init_ok: st.sidebar.success("✅ Firebase Auth OK.")
    else: st.sidebar.error("❌ Firebase Auth FALHOU.")
    if firestore_init_ok: st.sidebar.success("✅ Firestore DB OK.")
    else: st.sidebar.error("❌ Firestore DB FALHOU.")
    if init_errors:
        for err in init_errors: st.sidebar.error(f"Init Error: {err}")
    st.session_state[f'{APP_KEY_SUFFIX}_init_msgs_shown'] = True

if not auth_init_ok:
    st.error("ERRO CRÍTICO: Autenticação Firebase não inicializada. App parado.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
def get_current_user_status(auth_client, db_client, is_auth_init_ok, is_firestore_init_ok):
    # (Esta função foi significativamente simplificada na minha resposta anterior, 
    #  mas o princípio é o mesmo: validar token, pegar UID/email, checar ativação)
    #  A versão abaixo é mais próxima da sua última estrutura funcional.
    user_is_auth, user_is_act, current_uid, current_email, sess_err_msg = False, False, None, None, None
    
    session_key = f'{APP_KEY_SUFFIX}_user_session_data' # Chave única para dados de sessão do usuário
    activation_cache_key_base = f'{APP_KEY_SUFFIX}_user_activated_status_'

    if is_auth_init_ok and session_key in st.session_state and st.session_state[session_key]:
        current_session_data = st.session_state[session_key]
        try:
            if not auth_client: raise ValueError("Cliente de autenticação não está disponível.")
            
            # Valida o token e obtém informações atualizadas do usuário
            user_account_info = auth_client.get_account_info(current_session_data['idToken'])
            user_is_auth = True
            user_info = user_account_info['users'][0]
            current_uid = user_info['localId']
            current_email = user_info.get('email', current_session_data.get('email')) # Prefere email atualizado

            # Atualiza a sessão com os dados mais recentes
            st.session_state[session_key]['localId'] = current_uid
            st.session_state[session_key]['email'] = current_email
            
            # Verifica o status de ativação se o Firestore estiver OK
            if is_firestore_init_ok and db_client and current_uid:
                user_specific_activation_key = f"{activation_cache_key_base}{current_uid}"
                if user_specific_activation_key not in st.session_state:
                    print(f"DEBUG: Firestore OK. Verificando ativação para UID: {current_uid}")
                    st.session_state[user_specific_activation_key] = check_user_activation_status_firestore(current_uid, db_client)
                user_is_act = st.session_state.get(user_specific_activation_key, False)

                # Tenta atualizar last_login (operação de escrita, não crítica para o status de auth/ativação)
                try:
                    user_profile_ref = db_client.collection(USER_COLLECTION).document(current_uid)
                    user_profile_ref.set(
                        {"last_login": firebase_admin_firestore.SERVER_TIMESTAMP, "email": current_email}, 
                        merge=True
                    )
                except Exception as e_upd_login:
                    print(f"AVISO: Falha ao atualizar last_login para {current_uid}: {e_upd_login}")
            else: # Firestore não está OK ou UID ausente
                if not is_firestore_init_ok: sess_err_msg = "Aviso: Firestore indisponível para checar ativação."
                elif not db_client: sess_err_msg = "Aviso: Cliente Firestore (db_client) é None em get_current_user_status."

            st.session_state.pop(f'{APP_KEY_SUFFIX}_auth_session_error_msg_displayed', None) # Limpa flag de erro anterior

        except Exception as e_session_validation:
            st.session_state.pop(session_key, None) # Limpa sessão inválida
            if current_uid: st.session_state.pop(f"{activation_cache_key_base}{current_uid}", None) # Limpa cache de ativação
            user_is_auth = False
            
            err_text = str(e_session_validation)
            # (Sua lógica de parsing de erro para tornar a mensagem mais amigável)
            # ...
            sess_err_msg = f"Sessão inválida ou expirada. Faça login. ({err_text[:100]})"
            if not st.session_state.get(f'{APP_KEY_SUFFIX}_auth_session_error_msg_displayed', False):
                 st.sidebar.warning(sess_err_msg)
                 st.session_state[f'{APP_KEY_SUFFIX}_auth_session_error_msg_displayed'] = True
            # Não fazer st.rerun() aqui, deixar o fluxo principal controlar.

    # Atualiza os estados globais da sessão para acesso fácil
    st.session_state.user_is_authenticated = user_is_auth
    st.session_state.is_user_activated = user_is_act if user_is_auth else False
    st.session_state.user_uid = current_uid
    st.session_state.user_email = current_email
    
    return user_is_auth, user_is_act, current_uid, current_email, sess_err_msg

user_is_authenticated, user_is_activated, user_uid, user_email, auth_error_message_runtime = \
    get_current_user_status(pb_auth_client, firestore_db, auth_init_ok, firestore_init_ok)

# --- Inicialização do LLM (somente se autenticado e se não já inicializado) ---
llm = None
if user_is_authenticated:
    llm_instance_key = f'{APP_KEY_SUFFIX}_llm_gemini_instance'
    if llm_instance_key not in st.session_state:
        try:
            google_api_key_from_secrets = st.secrets.get("GOOGLE_API_KEY")
            if google_api_key_from_secrets:
                st.session_state[llm_instance_key] = ChatGoogleGenerativeAI(
                    model="gemini-pro", # ou "gemini-1.5-flash"
                    google_api_key=google_api_key_from_secrets,
                    temperature=0.7
                )
                if not st.session_state.get(f'{APP_KEY_SUFFIX}_llm_success_msg_shown', False):
                    st.sidebar.success("✅ LLM (Gemini) Conectado.")
                    st.session_state[f'{APP_KEY_SUFFIX}_llm_success_msg_shown'] = True
            else:
                st.error("Chave GOOGLE_API_KEY não configurada nos segredos.")
        except Exception as e:
            st.error(f"Erro ao inicializar LLM: {e}")
    llm = st.session_state.get(llm_instance_key)

# --- Definição da Classe MaxAgente (ADAPTADA) ---
class MaxAgente:
    def __init__(self, llm_instance, db_firestore_instance):
        self.llm = llm_instance
        self.db = db_firestore_instance # ESSENCIAL: usa o cliente Firestore passado

        if not self.llm: st.warning("MaxAgente: LLM não disponível.")
        if not self.db: st.warning("MaxAgente: Firestore não disponível.")
        else: print(f"DEBUG: MaxAgente instanciado com Firestore client: {type(self.db)}")
        
        # (COLE AQUI A INICIALIZAÇÃO DAS MEMÓRIAS DA SUA CLASSE MaxAgente, usando APP_KEY_SUFFIX)
        # ...
        self.memoria_plano_negocios_key = f'{APP_KEY_SUFFIX}_mem_plano_negocios'
        if self.memoria_plano_negocios_key not in st.session_state:
            st.session_state[self.memoria_plano_negocios_key] = ConversationBufferMemory(memory_key=f"{APP_KEY_SUFFIX}_hist_plano", return_messages=True)
        self.memoria_plano_negocios = st.session_state[self.memoria_plano_negocios_key]
        # ... (e para outras memórias)


    def _criar_cadeia_conversacional(self, system_message, memoria):
        if not self.llm: return None
        # ... (seu código)
        pass

    def _check_activation_and_prompt(self, feature_name="esta funcionalidade", key_suffix="default_feat"):
        """Verifica ativação. Se não ativo, mostra prompt e retorna True para bloquear."""
        # Acessa o estado de ativação global da sessão
        if not st.session_state.get('is_user_activated', False):
            # Atualiza o estado 'show_activation_prompt_area' para True
            # Isso sinalizará à lógica principal para exibir o formulário de ativação
            st.session_state[f'{APP_KEY_SUFFIX}_show_activation_prompt_area'] = True
            # Mensagem mostrada pela função que renderiza o prompt de ativação
            # st.info(f"Ativação necessária para {feature_name}.") 
            return True # Sim, bloquear
        st.session_state.pop(f'{APP_KEY_SUFFIX}_show_activation_prompt_area', None) # Garante que está limpo se ativado
        return False # Não bloquear

    # !!! DEV MASTER PARA DIRETOR DO PROJETO !!!
    # EM CADA MÉTODO ABAIXO QUE REPRESENTA UMA FUNCIONALIDADE DO MAX IA:
    # 1. COMECE COM: if self._check_activation_and_prompt("Nome da Funcionalidade"): return
    # 2. SE PRECISAR DO FIRESTORE, USE: self.db.collection("nome_colecao").document("id_doc")...
    #    NUNCA USE firebase_app.firestore() AQUI DENTRO!

    def exibir_max_marketing_total(self):
        if self._check_activation_and_prompt("o MaxMarketing Total", key_suffix="mkt"): return
        if not self.llm: st.error("MaxMarketing indisponível: LLM não está pronto."); return
        st.header("🚀 MaxMarketing Total (Acesso Permitido)")
        st.write("Conteúdo do MaxMarketing aqui...")
        # Se precisar de Firestore:
        # if self.db:
        #     # Ex: Carregar preferências de marketing do usuário st.session_state.user_uid
        #     prefs_ref = self.db.collection("marketing_prefs").document(st.session_state.user_uid)
        #     # ...
        # else:
        #     st.warning("Banco de dados não disponível para preferências de marketing.")
        # ... (resto da sua lógica de marketing) ...

    def exibir_max_financeiro(self):
        if self._check_activation_and_prompt("o MaxFinanceiro", key_suffix="fin"): return
        if not self.llm: st.error("MaxFinanceiro indisponível: LLM não está pronto."); return
        st.header("💰 MaxFinanceiro (Acesso Permitido)")
        # ... (seu código, usando self.db para Firestore se necessário)

    # ... (defina os outros métodos: exibir_max_administrativo, etc. da mesma forma) ...
    def exibir_max_administrativo(self):
        if self._check_activation_and_prompt("o Max Administrativo", key_suffix="admin"): return
        st.header("⚙️ MaxAdministrativo (Acesso Permitido)")

    def exibir_max_pesquisa_mercado(self):
        if self._check_activation_and_prompt("o Max Pesquisa de Mercado", key_suffix="pesquisa"): return
        st.header("📈 MaxPesquisa de Mercado (Acesso Permitido)")

    def exibir_max_bussola(self):
        if self._check_activation_and_prompt("a MaxBússola Estratégica", key_suffix="bussola"): return
        if not self.llm: st.error("MaxBússola indisponível: LLM não está pronto."); return
        st.header("🧭 MaxBússola Estratégica (Acesso Permitido)")

    def exibir_max_trainer(self):
        # Este pode não precisar de ativação, ou um "nível free"
        # if self._check_activation_and_prompt("o MaxTrainer IA", key_suffix="trainer"): return
        st.header("🎓 MaxTrainer IA")
        st.info("Bem-vindo ao MaxTrainer! Conteúdo em breve.")


# (Suas funções utilitárias de chat como inicializar_ou_resetar_chat, etc. aqui)
# ... (Assegure-se que usam chaves de sessão com APP_KEY_SUFFIX)


# --- Instanciação do Agente ---
agente = None
if user_is_authenticated: # Só instancia se autenticado
    if llm and firestore_db and firestore_init_ok : # E se LLM e Firestore estiverem realmente OK
        agent_instance_key = f'{APP_KEY_SUFFIX}_max_agente_global_instance'
        if agent_instance_key not in st.session_state:
            print(f"DEBUG: Instanciando MaxAgente. LLM: {type(llm)}, Firestore: {type(firestore_db)}")
            st.session_state[agent_instance_key] = MaxAgente(llm_instance=llm, db_firestore_instance=firestore_db)
        agente = st.session_state[agent_instance_key]
    else: # Algo faltou para o agente
        if not llm and not st.session_state.get(f'{APP_KEY_SUFFIX}_llm_agent_warn_shown', False):
             st.sidebar.warning("⚠️ Agente Max: LLM não operacional.")
             st.session_state[f'{APP_KEY_SUFFIX}_llm_agent_warn_shown'] = True
        if not (firestore_db and firestore_init_ok) and not st.session_state.get(f'{APP_KEY_SUFFIX}_firestore_agent_warn_shown', False):
             st.sidebar.warning("⚠️ Agente Max: Firestore não operacional.")
             st.session_state[f'{APP_KEY_SUFFIX}_firestore_agent_warn_shown'] = True


# --- FLUXO PRINCIPAL DA INTERFACE ---
if user_is_authenticated:
    # TESTE DE CONECTIVIDADE (MOVIDO PARA DENTRO DO BLOCO user_is_authenticated)
    if firestore_init_ok and firestore_db:
        firestore_test_key = f'{APP_KEY_SUFFIX}_firestore_connectivity_test_status'
        if firestore_test_key not in st.session_state: # Executa apenas uma vez por sessão
            print(f"DEBUG: Executando teste de conectividade Firestore (UID: {user_uid})...")
            st.session_state[firestore_test_key] = firestore_test_connectivity(firestore_db, user_uid if user_uid else "default_test_uid")
    else: # Marca como falho se firestore não inicializou
        st.session_state[f'{APP_KEY_SUFFIX}_firestore_connectivity_test_status'] = False

    st.sidebar.markdown("---")
    st.sidebar.write(f"Logado como: {user_email if user_email else 'Usuário'}")
    if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_main_logout_btn_final"):
        for key_to_del in list(st.session_state.keys()): del st.session_state[key_to_del] # Limpa TUDO
        st.rerun()

    # NOVO FLUXO: Mostrar área de ativação se o flag for setado E usuário não ativado
    if st.session_state.get(f'{APP_KEY_SUFFIX}_show_activation_prompt_area', False) and \
       not st.session_state.get('is_user_activated', False):
        display_activation_prompt_area(user_uid, firestore_db) # Passa UID do usuário logado
    
    # Conteúdo principal do app (somente se o agente estiver pronto)
    elif agente: 
        # Lógica do menu da sidebar
        opcoes_menu_sidebar = {
            "👋 Boas-vindas": f"{APP_KEY_SUFFIX}_view_welcome",
            "🚀 MaxMarketing": f"{APP_KEY_SUFFIX}_view_marketing",
            "💰 MaxFinanceiro": f"{APP_KEY_SUFFIX}_view_finance",
            "⚙️ MaxAdministrativo": f"{APP_KEY_SUFFIX}_view_admin",
            "📈 MaxPesquisa de Mercado": f"{APP_KEY_SUFFIX}_view_research",
            "🧭 MaxBússola Estratégica": f"{APP_KEY_SUFFIX}_view_strategy",
            "🎓 MaxTrainer IA": f"{APP_KEY_SUFFIX}_view_trainer",
        }
        sidebar_nav_key = f'{APP_KEY_SUFFIX}_main_nav_selection'
        
        if sidebar_nav_key not in st.session_state:
            st.session_state[sidebar_nav_key] = list(opcoes_menu_sidebar.values())[0] # Default
        
        # Para mapear rótulos para chaves internas ao definir o radio
        labels_for_radio = list(opcoes_menu_sidebar.keys())
        keys_for_radio_map = list(opcoes_menu_sidebar.values())
        
        try:
            current_selected_internal_key = st.session_state[sidebar_nav_key]
            default_radio_idx = keys_for_radio_map.index(current_selected_internal_key)
        except ValueError: # Se a chave não estiver nos valores (raro, mas para segurança)
            default_radio_idx = 0
            st.session_state[sidebar_nav_key] = keys_for_radio_map[0]


        selected_label_from_radio = st.sidebar.radio(
            "Navegar Agentes Max IA:",
            options=labels_for_radio,
            index=default_radio_idx,
            key=f"{APP_KEY_SUFFIX}_sidebar_actual_radio_widget" # Chave do widget
        )
        
        # Atualiza a seleção no session_state se mudou
        chosen_internal_key = opcoes_menu_sidebar[selected_label_from_radio]
        if chosen_internal_key != st.session_state[sidebar_nav_key]:
            st.session_state[sidebar_nav_key] = chosen_internal_key
            # Limpar estados específicos de marketing se sair da seção
            if chosen_internal_key != f"{APP_KEY_SUFFIX}_view_marketing":
                mkt_keys_to_clear = [k for k in st.session_state if APP_KEY_SUFFIX in k and "generated_" in k]
                for k_mkt in mkt_keys_to_clear: st.session_state.pop(k_mkt, None)
            st.rerun()

        # Renderiza a view com base na chave selecionada
        active_view_key = st.session_state[sidebar_nav_key]
        if active_view_key == f"{APP_KEY_SUFFIX}_view_welcome":
            st.header(f"👋 Bem-vindo ao Max IA, {user_email if user_email else 'Empreendedor'}!")
            st.write("Use o menu à esquerda para explorar as funcionalidades do seu assistente de negócios IA.")
            if not st.session_state.get('is_user_activated', False):
                 # O prompt de ativação agora é mostrado dentro de cada feature pelo _check_activation_and_prompt
                 st.info("Sua conta ainda não está ativada. Algumas funcionalidades solicitarão ativação.")
            else:
                st.success("🎉 Sua conta Max IA está ativa! Explore todo o potencial.")
            # (Adicione os cards de navegação rápida aqui se desejar)

        elif active_view_key == f"{APP_KEY_SUFFIX}_view_marketing": agente.exibir_max_marketing_total()
        elif active_view_key == f"{APP_KEY_SUFFIX}_view_finance": agente.exibir_max_financeiro()
        elif active_view_key == f"{APP_KEY_SUFFIX}_view_admin": agente.exibir_max_administrativo()
        elif active_view_key == f"{APP_KEY_SUFFIX}_view_research": agente.exibir_max_pesquisa_mercado()
        elif active_view_key == f"{APP_KEY_SUFFIX}_view_strategy": agente.exibir_max_bussola()
        elif active_view_key == f"{APP_KEY_SUFFIX}_view_trainer": agente.exibir_max_trainer()
        
    else: # Usuário autenticado, mas 'agente' não pôde ser instanciado
        st.error("Max IA não está totalmente operacional.")
        if not llm: st.warning("O motor de inteligência (LLM) não pôde ser carregado.")
        if not (firestore_db and firestore_init_ok) : 
            st.warning("A conexão com o banco de dados (Firestore) não está funcional.")
        st.info("Verifique as mensagens na sidebar ou contate o suporte. Tente recarregar a página.")
        if st.button("Tentar Recarregar App"): st.rerun()

else: # Usuário NÃO autenticado
    st.session_state.pop(f'{APP_KEY_SUFFIX}_auth_error_shown', None)
    st.title("🔑 Bem-vindo ao Max IA")
    # ... (Seu código de login/registro como na última versão, usando APP_KEY_SUFFIX para as chaves dos widgets)
    # ... (E garantindo que pb_auth_client e firestore_db (para registro) sejam verificados)
    auth_action_choice_key_login = f"{APP_KEY_SUFFIX}_auth_choice_login_reg"
    if auth_action_choice_key_login not in st.session_state:
        st.session_state[auth_action_choice_key_login] = "Login"
    
    auth_action_selected_val = st.sidebar.radio("Acesso:", ("Login", "Registrar"), key=auth_action_choice_key_login)

    if auth_action_selected_val == "Login":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_login_form_instance_main"):
            email_login_main = st.text_input("Email", key=f"{APP_KEY_SUFFIX}_login_email_main")
            password_login_main = st.text_input("Senha", type="password", key=f"{APP_KEY_SUFFIX}_login_pass_main")
            login_submit_main = st.form_submit_button("Entrar")

            if login_submit_main:
                if email_login_main and password_login_main and pb_auth_client:
                    try:
                        user_creds_login = pb_auth_client.sign_in_with_email_and_password(email_login_main, password_login_main)
                        st.session_state[f'{APP_KEY_SUFFIX}_user_session_data'] = dict(user_creds_login) # Chave correta
                        st.session_state.pop(f'{APP_KEY_SUFFIX}_is_user_activated_{user_creds_login.get("localId")}', None)
                        st.session_state.pop(f'{APP_KEY_SUFFIX}_init_msgs_shown', None)
                        st.session_state.pop(f'{APP_KEY_SUFFIX}_llm_success_msg_shown', None)
                        st.session_state.pop(f'{APP_KEY_SUFFIX}_show_activation_prompt_area', None)
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Erro no login: Verifique credenciais. ({e})") # Mensagem genérica
                else: st.sidebar.warning("Preencha email e senha.")
    
    elif auth_action_selected_val == "Registrar":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_register_form_instance_main"):
            email_reg_main = st.text_input("Seu Email", key=f"{APP_KEY_SUFFIX}_reg_email_main")
            password_reg_main = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password", key=f"{APP_KEY_SUFFIX}_reg_pass_main")
            reg_submit_main = st.form_submit_button("Registrar Conta")

            if reg_submit_main:
                if email_reg_main and password_reg_main and len(password_reg_main) >= 6 and \
                   pb_auth_client and firestore_db and firestore_init_ok:
                    try:
                        new_user_reg_data = pb_auth_client.create_user_with_email_and_password(email_reg_main, password_reg_main)
                        uid_new_user_reg = new_user_reg_data['localId']
                        
                        user_doc_ref_reg = firestore_db.collection(USER_COLLECTION).document(uid_new_user_reg)
                        user_doc_ref_reg.set({
                            "email": email_reg_main,
                            "is_activated": False, 
                            "registration_date": firebase_admin_firestore.SERVER_TIMESTAMP,
                            "last_login": firebase_admin_firestore.SERVER_TIMESTAMP
                        }, merge=True)
                        st.sidebar.success(f"Conta para {email_reg_main} criada! Faça o login.")
                        try: 
                            pb_auth_client.send_email_verification(new_user_reg_data['idToken'])
                            st.sidebar.info("Email de verificação enviado.")
                        except Exception as e_verify_mail_reg:
                            st.sidebar.caption(f"Não foi possível enviar email de verificação: {e_verify_mail_reg}")
                    except Exception as e_register_main:
                        st.sidebar.error(f"Erro no registro: {e_register_main}") # Simplificado
                else:
                    if not (firestore_db and firestore_init_ok): st.sidebar.error("Serviço de registro indisponível (DB).")
                    elif len(password_reg_main) < 6: st.sidebar.warning("Senha deve ter no mínimo 6 caracteres.")
                    else: st.sidebar.warning("Preencha todos os campos corretamente.")

    logo_unauth_path = "images/max-ia-logo.png"
    logo_unauth_b64 = convert_image_to_base64(logo_unauth_path)
    if logo_unauth_b64:
        st.markdown(f"<div style='text-align: center; padding-top: 20px;'><img src='data:image/png;base64,{logo_unauth_b64}' width='150'></div>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info(f"Max IA (v{APP_KEY_SUFFIX})")
