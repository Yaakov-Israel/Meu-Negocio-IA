import streamlit as st
import os 
import json 
import pyrebase 

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro", # Voltando ao título original
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="🚀" 
)

st.title("🚀 Assistente PME Pro")
# --- Inicialização do Firebase ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False

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
            # Usar session_state para armazenar a instância do app Firebase e evitar reinicializações desnecessárias
            if 'firebase_app_instance' not in st.session_state:
                st.session_state.firebase_app_instance = pyrebase.initialize_app(plain_firebase_config_dict)
            
            firebase_app = st.session_state.firebase_app_instance
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_success_message_shown' not in st.session_state:
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_success_message_shown = True # Marcar que a msg foi mostrada

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
except AttributeError as e: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e}"
except Exception as e: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e}"

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if 'st' in locals() or 'st' in globals(): # Verifica se st está definido antes de chamar st.exception
        st.exception(e if 'e' in locals() else Exception(error_message_firebase_init))
    st.stop()

if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()
# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None) # Limpar flag de erro ao autenticar com sucesso
    except Exception as e: 
        error_message_session = "Sessão inválida ou expirada."
        try:
            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\""))
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                error_message_session = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session = f"Erro ao verificar sessão: {api_error_message}. Faça login."
        except (json.JSONDecodeError, IndexError, TypeError):
            error_message_session = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e)}"
        
        st.session_state.user_session_pyrebase = None 
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state: 
            st.sidebar.warning(error_message_session)
            st.session_state.auth_error_shown = True
        # Forçar rerun para UI de login aparecer se o token se tornou inválido
        # Isso só acontece se a sessão foi invalidada NESTA execução.
        if not st.session_state.get('running_rerun_after_auth_fail', False):
            st.session_state.running_rerun_after_auth_fail = True
            st.rerun()
        else:
            st.session_state.pop('running_rerun_after_auth_fail', None)


if 'running_rerun_after_auth_fail' in st.session_state and st.session_state.running_rerun_after_auth_fail:
    st.session_state.pop('running_rerun_after_auth_fail', None)
    # Não renderizar o resto da página se estivermos no meio de um rerun forçado por falha de autenticação

# --- Interface do Usuário Condicional ---
if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    
    if st.sidebar.button("Logout", key="app_logout_button_v20_final_final"): # Nova chave
        st.session_state.user_session_pyrebase = None
        st.session_state.pop('firebase_init_success_message_shown', None) # Para mostrar msg de init de novo se deslogar
        st.session_state.pop('firebase_app_instance', None) # Para garantir que app firebase seja reinicializado
        st.session_state.pop('firebase_app_initialized', None)
        st.rerun() 
    
    # --- AQUI ENTRARÁ O CÓDIGO DO SEU APLICATIVO PME PRO ---
    # Por enquanto, apenas uma mensagem de placeholder
    st.header("🎉 Assistente PME Pro - Autenticado! 🎉")
    st.write("Conteúdo principal do aplicativo aparecerá aqui em breve.")
    st.balloons()
    # Substitua esta seção pelo seu código da classe AssistentePMEPro e a lógica de navegação/UI

else:
    st.sidebar.subheader("Login / Registro")
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key="app_auth_action_choice_v20_final")

    if auth_action_choice == "Login":
        with st.sidebar.form("app_login_form_v20_final"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")

            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None)
                        st.rerun()
                    except Exception as e:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: 
                                error_message_login = f"Erro no login: {api_error_message}"
                        except: pass
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("app_register_form_v20_final"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")

            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: # Opcional: enviar email de verificação
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error:
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error}")
                    except Exception as e:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message:
                                error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except:
                             error_message_register = f"Erro no registro: {str(e)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Bem-vindo! Faça login ou registre-se para usar o Assistente PME Pro.")
        logo_url_login = "https://i.imgur.com/7IIYxq1.png" 
        st.image(logo_url_login, width=200)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro (vPyrebase)")
