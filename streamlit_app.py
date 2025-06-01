import streamlit as st
import json 
import pyrebase 
from PIL import Image # Para o logo na sidebar

# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title="Assistente PME Pro - Login", # Título focado no login por enquanto
    layout="centered", # Layout centralizado para a tela de login/app simples
    initial_sidebar_state="expanded",
    page_icon="🔑" 
)

# --- Inicialização do Firebase ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False
auth_exception_object = None 

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]

        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
        else:
            if 'firebase_app_instance_skeleton' not in st.session_state: # Chave de instância única para o esqueleto
                st.session_state.firebase_app_instance_skeleton = pyrebase.initialize_app(plain_firebase_config_dict)
            
            firebase_app = st.session_state.firebase_app_instance_skeleton
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_success_msg_skel' not in st.session_state and not st.session_state.get('user_session_pyrebase_skel'): # Chaves únicas
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_success_msg_skel = True

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb_skel: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb_skel}"
    auth_exception_object = e_attr_fb_skel
except Exception as e_general_fb_skel: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb_skel}"
    auth_exception_object = e_general_fb_skel

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object and ('st' in locals() or 'st' in globals()):
        st.exception(auth_exception_object)
    st.stop()

if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão (para o esqueleto) ---
SESSION_KEY_USER_SKEL = 'user_session_pyrebase_skel' # Chave de sessão única

if SESSION_KEY_USER_SKEL not in st.session_state:
    st.session_state[SESSION_KEY_USER_SKEL] = None

user_is_authenticated_skel = False
if st.session_state[SESSION_KEY_USER_SKEL] and 'idToken' in st.session_state[SESSION_KEY_USER_SKEL]:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state[SESSION_KEY_USER_SKEL]['idToken'])
        st.session_state[SESSION_KEY_USER_SKEL]['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated_skel = True
        st.session_state.pop('auth_error_shown_skel', None) 
    except Exception as e_session_skel: 
        error_message_session_check_skel = "Sessão inválida ou expirada."
        try:
            error_details_str_skel = e_session_skel.args[0] if len(e_session_skel.args) > 0 else "{}"
            error_data_skel = json.loads(error_details_str_skel.replace("'", "\"")) 
            api_error_message_skel = error_data_skel.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            if "TOKEN_EXPIRED" in api_error_message_skel or "INVALID_ID_TOKEN" in api_error_message_skel:
                error_message_session_check_skel = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check_skel = f"Erro ao verificar sessão ({api_error_message_skel}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check_skel = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session_skel)}"
        
        st.session_state[SESSION_KEY_USER_SKEL] = None 
        user_is_authenticated_skel = False
        if 'auth_error_shown_skel' not in st.session_state: 
            st.sidebar.warning(error_message_session_check_skel)
            st.session_state.auth_error_shown_skel = True
        
        session_rerun_key_skel = 'running_rerun_after_auth_fail_skel_v1' 
        if not st.session_state.get(session_rerun_key_skel, False):
            st.session_state[session_rerun_key_skel] = True
            st.rerun()
        else:
            st.session_state.pop(session_rerun_key_skel, None)

session_rerun_key_check_skel = 'running_rerun_after_auth_fail_skel_v1'
if session_rerun_key_check_skel in st.session_state and st.session_state[session_rerun_key_check_skel]:
    st.session_state.pop(session_rerun_key_check_skel, None)
# --- Interface do Usuário ---
if user_is_authenticated_skel:
    st.session_state.pop('auth_error_shown_skel', None) 
    display_email_skel = st.session_state[SESSION_KEY_USER_SKEL].get('email', "Usuário Logado")
    
    # Logo da Sidebar
    LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png" # Caminho para seu logo local
    FALLBACK_LOGO_URL_SIDEBAR = "https://i.imgur.com/7IIYxq1.png" # URL de fallback
    try:
        st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
    except Exception:
        st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR, width=150, caption="Logo (Fallback)")

    st.sidebar.title("Assistente PME Pro")
    st.sidebar.write(f"Bem-vindo(a), {display_email_skel}!")
    
    if st.sidebar.button("Logout", key="logout_button_skel"): 
        st.session_state[SESSION_KEY_USER_SKEL] = None
        # Limpar flags de inicialização para que apareçam novamente se o usuário deslogar e logar
        st.session_state.pop('firebase_init_success_msg_skel', None)
        st.session_state.pop('firebase_app_instance_skeleton', None) # Força reinicialização do app Firebase na próxima vez
        st.session_state.pop('llm_init_success_sidebar_shown_main_app', None) # Se esta chave foi usada antes
        st.rerun() 
    
    st.sidebar.markdown("---")
    
    # Conteúdo principal após login
    st.title("🚀 Assistente PME Pro")
    st.header("Você está autenticado!")
    st.success("A base de autenticação está funcionando corretamente.")
    st.markdown("---")
    st.markdown("**Próximos passos:** Integrar as funcionalidades dos Agentes de IA.")
    st.balloons()

else: 
    st.session_state.pop('auth_error_shown_skel', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_skel_key = "auth_action_choice_skeleton"
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_skel_key)

    if auth_action_choice == "Login":
        with st.sidebar.form("login_form_skeleton"): 
            login_email = st.text_input("Email", key="login_email_skel")
            login_password = st.text_input("Senha", type="password", key="login_pass_skel")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state[SESSION_KEY_USER_SKEL] = dict(user_session)
                        st.session_state.pop('firebase_init_success_msg_skel', None)
                        st.rerun()
                    except Exception as e_login_skel:
                        error_message_login_skel = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_skel_l = e_login_skel.args[0] if len(e_login_skel.args) > 0 else "{}"
                            error_data_skel_l = json.loads(error_details_str_skel_l.replace("'", "\""))
                            api_error_message_skel_l = error_data_skel_l.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_skel_l or "EMAIL_NOT_FOUND" in api_error_message_skel_l or "INVALID_PASSWORD" in api_error_message_skel_l or "USER_DISABLED" in api_error_message_skel_l or "INVALID_EMAIL" in api_error_message_skel_l:
                                error_message_login_skel = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_skel_l: error_message_login_skel = f"Erro no login: {api_error_message_skel_l}"
                        except: pass 
                        st.sidebar.error(error_message_login_skel)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("register_form_skeleton"): 
            reg_email = st.text_input("Email para registro", key="reg_email_skel")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key="reg_pass_skel")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_skel: 
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_skel}")
                    except Exception as e_register_skel:
                        error_message_register_skel = "Erro no registro."
                        try:
                            error_details_str_reg_skel = e_register_skel.args[0] if len(e_register_skel.args) > 0 else "{}"
                            error_data_reg_skel = json.loads(error_details_str_reg_skel.replace("'", "\""))
                            api_error_message_reg_skel = error_data_reg_skel.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_skel:
                                error_message_register_skel = "Este email já está registrado. Tente fazer login."
                            elif api_error_message_reg_skel:
                                error_message_register_skel = f"Erro no registro: {api_error_message_reg_skel}"
                        except: 
                             error_message_register_skel = f"Erro no registro: {str(e_register_skel)}"
                        st.sidebar.error(error_message_register_skel)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
