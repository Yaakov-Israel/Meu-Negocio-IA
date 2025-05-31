import streamlit as st
import pyrebase
import json # Para tratar possíveis erros da API do Firebase

# --- Configuração da Página ---
st.set_page_config(
    page_title="Teste Login Mínimo",
    layout="centered",
    initial_sidebar_state="expanded",
    page_icon="🔑"
)

st.title("🔑 Teste de Autenticação Firebase (Pyrebase4)")

# --- Configuração do Firebase (dos Segredos) ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "🚨 ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos do Streamlit."
        st.error(error_message_firebase_init)
        st.stop()

    # Garantir que é um dicionário Python padrão
    plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
    
    # Verificar se as chaves essenciais estão presentes
    required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
    missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]
    if missing_keys:
        error_message_firebase_init = f"🚨 ERRO CRÍTICO: Chaves faltando em [firebase_config]: {', '.join(missing_keys)}"
        st.error(error_message_firebase_init)
        st.stop()

    if not firebase_app: # Evita reinicializar se já estiver ok (útil para desenvolvimento local com HMR)
        firebase_app = pyrebase.initialize_app(plain_firebase_config_dict)
    
    pb_auth_client = firebase_app.auth()
    st.sidebar.success("✅ Firebase (Pyrebase4) SDK inicializado com sucesso!")

except KeyError:
    error_message_firebase_init = "🚨 ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
    st.error(error_message_firebase_init)
    st.stop()
except AttributeError as e: # Captura caso st.secrets não seja um dicionário ou algo assim
    error_message_firebase_init = f"🚨 ERRO CRÍTICO ao acessar st.secrets['firebase_config'] (Possível problema de estrutura): {e}"
    st.error(error_message_firebase_init)
    st.exception(e)
    st.stop()
except Exception as e: # Outras exceções na inicialização
    error_message_firebase_init = f"🚨 ERRO GERAL ao inicializar Pyrebase4: {e}"
    st.error(error_message_firebase_init)
    st.exception(e)
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        # Tenta obter informações da conta para validar o token (Pyrebase pode usar refreshToken para obter um novo idToken)
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        # Se não deu erro, o token é considerado válido. Atualizar o email pode ser útil.
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
    except Exception as e: # Captura exceções de token inválido/expirado que não pôde ser atualizado
        st.session_state.user_session_pyrebase = None # Limpa a sessão inválida
        user_is_authenticated = False
        # st.sidebar.warning(f"Sessão expirada ou inválida. Faça login novamente. Erro: {e}") # Opcional: feedback ao usuário

if user_is_authenticated:
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    if st.sidebar.button("Logout", key="minimal_logout_button"):
        st.session_state.user_session_pyrebase = None
        st.experimental_rerun()
    
    st.header("🎉 Conteúdo Principal do Aplicativo 🎉")
    st.write("Você está autenticado!")
    # Aqui entraria o restante do seu aplicativo PME Pro

else:
    st.sidebar.subheader("Login / Registro")
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key="minimal_auth_action_choice")

    if auth_action_choice == "Login":
        with st.sidebar.form("minimal_login_form"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")

            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session) # Armazenar como dict
                        st.experimental_rerun()
                    except Exception as e:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: # Tenta extrair mensagem de erro mais amigável do Firebase
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            # Tentar normalizar aspas simples para duplas para json.loads
                            error_details_str_normalized = error_details_str.replace("'", "\"")
                            error_data = json.loads(error_details_str_normalized)
                            api_error_message = error_data.get('error', {}).get('message', '')
                            
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or \
                               "EMAIL_NOT_FOUND" in api_error_message or \
                               "INVALID_PASSWORD" in api_error_message or \
                               "INVALID_EMAIL" in api_error_message: # Adicionado INVALID_EMAIL
                                error_message_login = "Email ou senha inválidos."
                            elif api_error_message: # Se houver uma mensagem específica da API
                                error_message_login = f"Erro: {api_error_message}"
                            # Se não conseguir extrair uma mensagem específica, mantém a genérica.
                        except (json.JSONDecodeError, IndexError, TypeError) as parse_error:
                            st.sidebar.caption(f"Não foi possível parsear o erro detalhado: {parse_error}")
                            # Mantém a mensagem genérica se o parsing falhar
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("minimal_register_form"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")

            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                    except Exception as e:
                        error_message_register = f"Erro no registro."
                        try:
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_details_str_normalized = error_details_str.replace("'", "\"")
                            error_data = json.loads(error_details_str_normalized)
                            api_error_message = error_data.get('error', {}).get('message', '')

                            if api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except (json.JSONDecodeError, IndexError, TypeError) as parse_error:
                             st.sidebar.caption(f"Não foi possível parsear o erro detalhado: {parse_error}")
                             error_message_register = f"Erro no registro: {str(e)}" # fallback
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if error_message_firebase_init: # Se a inicialização do Firebase falhou, não mostrar esta info.
        pass
    else:
        st.info("Faça login ou registre-se para continuar.")

# Linha final para garantir que não há nada depois que possa causar problemas com o "corte"
st.sidebar.markdown("---")
st.sidebar.markdown("App Mínimo de Teste - v0.1")
