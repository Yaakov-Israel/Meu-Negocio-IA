import streamlit as st
import streamlit_authenticator as stauth
# from yaml.loader import SafeLoader # Não estamos usando YAML diretamente com st.secrets

st.set_page_config(page_title="Teste Autenticação v2 - PME Pro", layout="wide")

# --- Carregar Configurações dos Segredos ---
credentials_config = None
cookie_config = None
try:
    if 'credentials' not in st.secrets or \
       'cookie' not in st.secrets or \
       'usernames' not in st.secrets['credentials']:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seções/chaves para 'streamlit-authenticator' ([credentials] com 'usernames', [cookie]) não encontradas nos Segredos.")
        st.stop()

    credentials_config = st.secrets['credentials'].to_dict() # Converte para dict
    cookie_config = st.secrets['cookie'].to_dict()
    
    # Validações internas (opcional, mas bom para depurar)
    if not isinstance(credentials_config.get('usernames'), dict):
        st.error("🚨 ERRO: 'credentials.usernames' não é um dicionário válido.")
        st.stop()
    if not all(isinstance(v, dict) and 'password' in v and 'name' in v and 'email' in v for v in credentials_config['usernames'].values()):
        st.error("🚨 ERRO: Estrutura interna de 'credentials.usernames' inválida.")
        st.stop()
    if not all(k_cookie in cookie_config for k_cookie in ['name', 'key', 'expiry_days']):
        st.error("🚨 ERRO: Faltam chaves em '[cookie]' (name, key, expiry_days).")
        st.stop()

except Exception as e_secrets:
    st.error(f"🚨 ERRO AO CARREGAR/VALIDAR SEGREDOS: {type(e_secrets).__name__} - {e_secrets}")
    st.exception(e_secrets) # Mostra o traceback completo
    st.stop()

# --- Inicializar o Autenticador ---
authenticator = None # Inicializa para ter a variável no escopo
try:
    authenticator = stauth.Authenticate(
        credentials_config,
        cookie_config['name'],
        cookie_config['key'],
        cookie_config['expiry_days'],
    )
except Exception as e_auth_init_diag: # Variável de exceção com nome único
    st.error(f"🚨 ERRO AO INICIALIZAR Authenticator: {type(e_auth_init_diag).__name__} - {e_auth_init_diag}")
    st.exception(e_auth_init_diag)
    st.stop()

if not authenticator:
    st.error("Falha crítica ao inicializar o Authenticator.")
    st.stop()

st.title("Teste de Login v2 com `streamlit-authenticator`")

# --- Processo de Login (Modificado para Diagnóstico) ---
login_form_return_value = None 
try:
    # A função login() renderiza o formulário e retorna os valores
    # O formulário é renderizado no corpo principal por padrão se 'location' não for especificado
    login_form_return_value = authenticator.login() 
    
    st.markdown("---")
    st.subheader("Diagnóstico do Retorno de `authenticator.login()`:")
    st.write(f"**Tipo do retorno:** `{type(login_form_return_value)}`")
    st.write(f"**Valor do retorno:** `{login_form_return_value}`")
    st.markdown("---")

    # Procede com a lógica de login somente se o retorno for uma tupla/lista de 3 elementos
    if login_form_return_value is not None and isinstance(login_form_return_value, (tuple, list)) and len(login_form_return_value) == 3:
        name_of_user, authentication_status, username = login_form_return_value

        if authentication_status:
            st.sidebar.success(f"Bem-vindo, *{name_of_user}*!")
            st.sidebar.write(f"Username: `{username}`")
            authenticator.logout("Logout", "sidebar", key='logout_button_v10_stauth_diag') # Chave única
            
            st.header("🎉 Login Bem-Sucedido!")
            st.write("O `streamlit-authenticator` parece estar funcionando!")
            
        elif authentication_status == False:
            st.error("Nome de usuário/senha incorreto.")
        elif authentication_status == None: 
            st.warning("Por favor, insira seu nome de usuário e senha e clique em Login.")
            # O formulário de login já deve estar visível acima.
    
    elif login_form_return_value is None:
         st.error("`authenticator.login()` retornou `None` diretamente. Isso é inesperado, especialmente antes da primeira submissão do formulário.")
         st.info("O formulário de login (campos de usuário e senha) deveria estar visível acima. Se não estiver, pode haver um problema na renderização do widget pela biblioteca.")
    else:
        st.error(f"Resultado inesperado de `authenticator.login()`: Não é uma tupla/lista de 3 elementos como esperado.")
        st.info("Isso pode indicar um problema com a versão da biblioteca ou uma configuração inesperada.")

except Exception as e_login_process: # Variável de exceção com nome único
    st.error(f"🚨 ERRO DURANTE O PROCESSO DE LOGIN DO WIDGET: {type(e_login_process).__name__} - {e_login_process}")
    st.exception(e_login_process)

st.markdown("---")
st.caption("Fim do teste minimalista v2 com streamlit-authenticator.")
