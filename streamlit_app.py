import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(page_title="Teste Autenticação v3 - PME Pro", layout="wide")

# --- Carregar Configurações dos Segredos ---
credentials_config = None
cookie_config = None
try:
    if 'credentials' not in st.secrets or \
       'cookie' not in st.secrets or \
       'usernames' not in st.secrets['credentials'] or \
       not isinstance(st.secrets['credentials'].get('usernames'), dict): # Checa se usernames é um dict
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Segredos para 'streamlit-authenticator' ([credentials] com 'usernames' como dict, [cookie]) ausentes ou malformatados.")
        st.stop()

    credentials_config = st.secrets['credentials'].to_dict() 
    cookie_config = st.secrets['cookie'].to_dict()
    
    # Validação mais robusta (opcional, mas útil)
    if not all(isinstance(v, dict) and 'password' in v and 'name' in v and 'email' in v for v in credentials_config.get('usernames', {}).values()):
        st.error("🚨 ERRO: Estrutura interna de 'credentials.usernames' inválida. Cada usuário deve ter 'email', 'name', e 'password'.")
        st.stop()
    if not all(k_cookie in cookie_config for k_cookie in ['name', 'key', 'expiry_days']):
        st.error("🚨 ERRO: Faltam chaves em '[cookie]' (name, key, expiry_days).")
        st.stop()

except Exception as e_secrets:
    st.error(f"🚨 ERRO AO CARREGAR/VALIDAR SEGREDOS: {type(e_secrets).__name__} - {e_secrets}")
    st.exception(e_secrets)
    st.stop()

# --- Inicializar o Autenticador ---
authenticator = None
try:
    authenticator = stauth.Authenticate(
        credentials_config, # Passando o dict diretamente
        cookie_config['name'],
        cookie_config['key'],
        cookie_config['expiry_days'],
    )
except Exception as e_auth_init:
    st.error(f"🚨 ERRO AO INICIALIZAR Authenticator: {type(e_auth_init).__name__} - {e_auth_init}")
    st.exception(e_auth_init)
    st.stop()

if not authenticator: # Checagem de segurança
    st.error("Falha crítica: Objeto Authenticator não foi inicializado.")
    st.stop()

st.title("Teste de Login v3 com `streamlit-authenticator`")

# --- Processo de Login ---
# O formulário é renderizado no corpo principal por padrão.
name_of_user, authentication_status, username = authenticator.login()

st.markdown("---")
st.subheader("Diagnóstico do Retorno de `authenticator.login()`:")
st.write(f"**Nome do Usuário (retornado):** `{name_of_user}`")
st.write(f"**Status da Autenticação (retornado):** `{authentication_status}`")
st.write(f"**Username (retornado):** `{username}`")
st.markdown("---")

# Lógica de acordo com o status da autenticação
if authentication_status: # True se logado com sucesso
    st.sidebar.success(f"Bem-vindo, *{name_of_user}*!")
    st.sidebar.write(f"Username Logado: `{username}`")
    authenticator.logout("Logout", "sidebar", key='logout_button_v11_stauth') 
    
    st.header("🎉 Login Bem-Sucedido!")
    st.write("Se você está vendo esta mensagem, o `streamlit-authenticator` PERMITIU O LOGIN.")
    st.write("Agora podemos prosseguir para integrar isso com sua lógica de app completa e, se necessário, validação adicional com Firebase.")
    
    # TODO: Aqui entraria a lógica do seu aplicativo principal (agente, seções, etc.)
    # Exemplo:
    # if 'agente_pme_completo' not in st.session_state and llm_model_global: # Supondo que llm_model_global já foi carregado
    # st.session_state.agente_pme_completo = AssistentePMEPro(llm_model_global)
    # agente_app_instancia = st.session_state.agente_pme_completo
    # # Chamar as funções do agente aqui...
    st.info("Conteúdo principal do aplicativo apareceria aqui.")


elif authentication_status == False: # False se a tentativa de login falhou (ex: senha errada)
    st.error("Nome de usuário ou senha incorreto. Tente novamente.")
    # O formulário de login já foi renderizado acima pela chamada authenticator.login()
    # e deve continuar visível para nova tentativa.

elif authentication_status == None: # None se o formulário foi renderizado mas o usuário ainda não submeteu
    st.warning("Por favor, insira seu nome de usuário e senha e clique em Login.")
    # O formulário de login já foi renderizado acima.
    
st.markdown("---")
st.caption("Fim do teste minimalista v3 com streamlit-authenticator.")
