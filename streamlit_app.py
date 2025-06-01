import streamlit as st
import json 
import pyrebase 
from PIL import Image 

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="centered", 
    initial_sidebar_state="expanded",
    page_icon="🔑" 
)

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
            if 'firebase_app_instance_base' not in st.session_state: 
                st.session_state.firebase_app_instance_base = pyrebase.initialize_app(plain_firebase_config_dict)
            firebase_app = st.session_state.firebase_app_instance_base
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_msg_base' not in st.session_state and not st.session_state.get('user_session_base_auth'):
                 if hasattr(st, 'sidebar'): # Garante que st.sidebar existe
                    st.sidebar.success("✅ Firebase SDK (Base) inicializado!")
                 st.session_state.firebase_init_msg_base = True
except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb_base: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb_base}"
    auth_exception_object = e_attr_fb_base
except Exception as e_general_fb_base: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb_base}"
    auth_exception_object = e_general_fb_base

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object: st.exception(auth_exception_object)
    st.stop()
if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

SESSION_KEY_USER = 'user_session_base_auth' 
if SESSION_KEY_USER not in st.session_state:
    st.session_state[SESSION_KEY_USER] = None

user_is_authenticated = False
if st.session_state[SESSION_KEY_USER] and 'idToken' in st.session_state[SESSION_KEY_USER]:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state[SESSION_KEY_USER]['idToken'])
        st.session_state[SESSION_KEY_USER]['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown_base', None) 
    except Exception as e_session_base: 
        error_message_session_check_base = "Sessão inválida ou expirada."
        try:
            error_details_str_base = e_session_base.args[0] if len(e_session_base.args) > 0 else "{}"
            error_data_base = json.loads(error_details_str_base.replace("'", "\"")) 
            api_error_message_base = error_data_base.get('error', {}).get('message', "ERRO_SESSAO_BASE")
            if "TOKEN_EXPIRED" in api_error_message_base or "INVALID_ID_TOKEN" in api_error_message_base:
                error_message_session_check_base = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check_base = f"Erro ({api_error_message_base}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check_base = f"Erro sessão (parsing). Detalhe: {str(e_session_base)}"
        st.session_state[SESSION_KEY_USER] = None 
        user_is_authenticated = False
        if 'auth_error_shown_base' not in st.session_state: 
            if hasattr(st, 'sidebar'): st.sidebar.warning(error_message_session_check_base)
            st.session_state.auth_error_shown_base = True
        
        rerun_flag_key_base = 'rerun_auth_fail_base_v1' 
        if not st.session_state.get(rerun_flag_key_base, False):
            st.session_state[rerun_flag_key_base] = True
            st.rerun()
        else:
            st.session_state.pop(rerun_flag_key_base, None)

if rerun_flag_key_check_base := st.session_state.get('rerun_auth_fail_base_v1'): 
    st.session_state.pop('rerun_auth_fail_base_v1', None)
import streamlit as st
import json 
import pyrebase 
from PIL import Image 

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="centered", 
    initial_sidebar_state="expanded",
    page_icon="🔑" 
)

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
            if 'firebase_app_instance_base' not in st.session_state: 
                st.session_state.firebase_app_instance_base = pyrebase.initialize_app(plain_firebase_config_dict)
            firebase_app = st.session_state.firebase_app_instance_base
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_msg_base' not in st.session_state and not st.session_state.get('user_session_base_auth'):
                 if hasattr(st, 'sidebar'): # Garante que st.sidebar existe
                    st.sidebar.success("✅ Firebase SDK (Base) inicializado!")
                 st.session_state.firebase_init_msg_base = True
except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb_base: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb_base}"
    auth_exception_object = e_attr_fb_base
except Exception as e_general_fb_base: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb_base}"
    auth_exception_object = e_general_fb_base

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object: st.exception(auth_exception_object)
    st.stop()
if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

SESSION_KEY_USER = 'user_session_base_auth' 
if SESSION_KEY_USER not in st.session_state:
    st.session_state[SESSION_KEY_USER] = None

user_is_authenticated = False
if st.session_state[SESSION_KEY_USER] and 'idToken' in st.session_state[SESSION_KEY_USER]:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state[SESSION_KEY_USER]['idToken'])
        st.session_state[SESSION_KEY_USER]['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown_base', None) 
    except Exception as e_session_base: 
        error_message_session_check_base = "Sessão inválida ou expirada."
        try:
            error_details_str_base = e_session_base.args[0] if len(e_session_base.args) > 0 else "{}"
            error_data_base = json.loads(error_details_str_base.replace("'", "\"")) 
            api_error_message_base = error_data_base.get('error', {}).get('message', "ERRO_SESSAO_BASE")
            if "TOKEN_EXPIRED" in api_error_message_base or "INVALID_ID_TOKEN" in api_error_message_base:
                error_message_session_check_base = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check_base = f"Erro ({api_error_message_base}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check_base = f"Erro sessão (parsing). Detalhe: {str(e_session_base)}"
        st.session_state[SESSION_KEY_USER] = None 
        user_is_authenticated = False
        if 'auth_error_shown_base' not in st.session_state: 
            if hasattr(st, 'sidebar'): st.sidebar.warning(error_message_session_check_base)
            st.session_state.auth_error_shown_base = True
        
        rerun_flag_key_base = 'rerun_auth_fail_base_v1' 
        if not st.session_state.get(rerun_flag_key_base, False):
            st.session_state[rerun_flag_key_base] = True
            st.rerun()
        else:
            st.session_state.pop(rerun_flag_key_base, None)

if rerun_flag_key_check_base := st.session_state.get('rerun_auth_fail_base_v1'): 
    st.session_state.pop('rerun_auth_fail_base_v1', None)
if user_is_authenticated:
    st.session_state.pop('auth_error_shown_base', None) 
    display_email = st.session_state[SESSION_KEY_USER].get('email', "Usuário Logado")
    
    LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png"
    FALLBACK_LOGO_URL_SIDEBAR = "https://i.imgur.com/7IIYxq1.png"
    try:
        st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
    except Exception:
        st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR, width=150, caption="Logo (Fallback)")

    st.sidebar.title("Assistente PME Pro")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    
    if st.sidebar.button("Logout", key="logout_button_base"): 
        st.session_state[SESSION_KEY_USER] = None
        st.session_state.pop('firebase_init_msg_base', None)
        st.session_state.pop('firebase_app_instance_base', None)
        st.session_state.pop('llm_init_success_main_app_v1', None) # Limpando se existir de antes
        # Limpar outras chaves de sessão específicas de agentes no futuro
        st.rerun() 
    
    st.sidebar.markdown("---")
    st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro") # Movido para o final da sidebar
    
    st.title("🚀 Assistente PME Pro")
    st.header("Você está autenticado!")
    st.success("A base de autenticação está funcionando corretamente.")
    st.markdown("---")
    st.markdown("**Próximo passo:** Começar a construção do Agente de Marketing Digital.")
    # st.balloons() # Removido para simplificar

else: 
    st.session_state.pop('auth_error_shown_base', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key = "auth_action_choice_base"
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key)

    if auth_action_choice == "Login":
        with st.sidebar.form("login_form_base"): 
            login_email = st.text_input("Email", key="login_email_base")
            login_password = st.text_input("Senha", type="password", key="login_pass_base")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state[SESSION_KEY_USER] = dict(user_session)
                        st.session_state.pop('firebase_init_msg_base', None)
                        st.rerun()
                    except Exception as e_login_base:
                        error_message_login_base = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_l_base = e_login_base.args[0] if len(e_login_base.args) > 0 else "{}"
                            error_data_l_base = json.loads(error_details_str_l_base.replace("'", "\""))
                            api_error_message_l_base = error_data_l_base.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_l_base or "EMAIL_NOT_FOUND" in api_error_message_l_base or "INVALID_PASSWORD" in api_error_message_l_base or "USER_DISABLED" in api_error_message_l_base or "INVALID_EMAIL" in api_error_message_l_base:
                                error_message_login_base = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_l_base: error_message_login_base = f"Erro no login: {api_error_message_l_base}"
                        except: pass 
                        st.sidebar.error(error_message_login_base)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("register_form_base"): 
            reg_email = st.text_input("Email para registro", key="reg_email_base")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key="reg_pass_base")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque spam).")
                        except Exception as verify_email_error_base: 
                           st.sidebar.caption(f"Nota: Envio de email de verificação falhou: {verify_email_error_base}")
                    except Exception as e_register_base:
                        error_message_register_base = "Erro no registro."
                        try:
                            error_details_str_reg_base = e_register_base.args[0] if len(e_register_base.args) > 0 else "{}"
                            error_data_reg_base = json.loads(error_details_str_reg_base.replace("'", "\""))
                            api_error_message_reg_base = error_data_reg_base.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_base:
                                error_message_register_base = "Este email já está registrado."
                            elif api_error_message_reg_base:
                                error_message_register_base = f"Erro no registro: {api_error_message_reg_base}"
                        except: 
                             error_message_register_base = f"Erro no registro: {str(e_register_base)}"
                        st.sidebar.error(error_message_register_base)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN_UNAUTH = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN_UNAUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN_UNAUTH, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN_UNAUTH, width=200, caption="Logo (Fallback)")

    st.sidebar.markdown("---")
    st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
