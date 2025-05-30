import streamlit as st
import streamlit_authenticator as stauth # Nova biblioteca
import yaml # streamlit-authenticator usa YAML para carregar config, mas aqui vamos direto dos segredos
from yaml.loader import SafeLoader # Para carregar o YAML de forma segura

st.set_page_config(page_title="Teste de Autenticação - PME Pro", layout="wide")

# Carregar configurações dos segredos do Streamlit
# streamlit-authenticator espera que 'credentials' seja um dict
# e 'cookie' também seja um dict.

try:
    # Verifica se as chaves essenciais para o authenticator existem nos segredos
    if 'credentials' not in st.secrets or \
       'cookie' not in st.secrets or \
       'usernames' not in st.secrets['credentials']:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seções/chaves essenciais para 'streamlit-authenticator' ([credentials] com 'usernames', [cookie]) não encontradas nos Segredos.")
        st.info("Verifique se os segredos estão formatados corretamente para 'streamlit-authenticator'.")
        st.stop()

    credentials_config = st.secrets['credentials'].to_dict() # Converte para dict se for TomlFileProvider
    cookie_config = st.secrets['cookie'].to_dict()
    
    # Validação interna mais detalhada (opcional, mas bom para depurar)
    if not isinstance(credentials_config.get('usernames'), dict):
        st.error("🚨 ERRO DE CONFIGURAÇÃO: 'credentials.usernames' não é um dicionário válido nos segredos.")
        st.stop()
    if not all(isinstance(v, dict) and 'password' in v and 'name' in v and 'email' in v for v in credentials_config['usernames'].values()):
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Estrutura interna de 'credentials.usernames' inválida. Cada usuário deve ter 'email', 'name', e 'password'.")
        st.stop()
    if not all(k in cookie_config for k in ['name', 'key', 'expiry_days']):
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Faltam chaves em '[cookie]' (name, key, expiry_days).")
        st.stop()

except Exception as e_secrets_load:
    st.error(f"🚨 ERRO AO CARREGAR OU VALIDAR SEGREDOS PARA streamlit-authenticator: {type(e_secrets_load).__name__} - {e_secrets_load}")
    st.exception(e_secrets_load)
    st.stop()


# Inicializar o autenticador
try:
    authenticator = stauth.Authenticate(
        credentials_config,                   # dict de credenciais (do st.secrets)
        cookie_config['name'],                # nome do cookie (do st.secrets)
        cookie_config['key'],                 # chave secreta para assinar o cookie (do st.secrets)
        cookie_config['expiry_days'],         # validade do cookie em dias (do st.secrets)
        # preauthorized_emails=[]             # Opcional: lista de emails pré-autorizados
    )
except Exception as e_auth_init:
    st.error(f"🚨 ERRO AO INICIALIZAR o Authenticator: {type(e_auth_init).__name__} - {e_auth_init}")
    st.exception(e_auth_init)
    st.stop()

st.title("Teste de Login com `streamlit-authenticator`")

# Renderizar o widget de login
# O método login() retorna: name, authentication_status, username
# name: Nome completo do usuário
# authentication_status: True se logado, False se falhou, None se ainda não tentou
# username: Nome de usuário
try:
    name_of_user, authentication_status, username = authenticator.login() # Removido 'main' para testar no corpo principal

    if authentication_status:
        st.sidebar.success(f"Bem-vindo, *{name_of_user}*!")
        st.sidebar.write(f"Username: `{username}`")
        authenticator.logout("Logout", "sidebar", key='logout_button_v10_stauth') # Chave única
        
        st.header("🎉 Login Bem-Sucedido!")
        st.write("Se você está vendo esta mensagem, o `streamlit-authenticator` está funcionando.")
        st.write("Agora podemos prosseguir para integrar isso com sua lógica de app e validação Firebase.")
        
        # Aqui você pode adicionar a lógica do seu app que só aparece após o login
        # Por exemplo, carregar o LLM, a classe AssistentePMEPro, etc.
        # Mas para este teste, vamos manter simples.

    elif authentication_status == False:
        st.error("Nome de usuário/senha incorreto.")
    elif authentication_status == None:
        st.warning("Por favor, insira seu nome de usuário e senha.")

except Exception as e_login_widget:
    st.error(f"🚨 ERRO AO RENDERIZAR O WIDGET DE LOGIN: {type(e_login_widget).__name__} - {e_login_widget}")
    st.exception(e_login_widget)

st.markdown("---")
st.caption("Fim do teste minimalista com streamlit-authenticator.")
