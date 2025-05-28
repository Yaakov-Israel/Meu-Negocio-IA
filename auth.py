# auth.py (para streamlit-authenticator - Tentativa de correção do TypeError)
import streamlit as st
import streamlit_authenticator as stauth

def initialize_authenticator():
    """
    Inicializa o objeto Authenticate do streamlit-authenticator
    usando as credenciais e configurações de cookie dos Streamlit Secrets.
    """
    try:
        credentials_config = st.secrets.get("credentials")
        cookie_config = st.secrets.get("cookie")

        if not credentials_config or not credentials_config.get("usernames"):
            st.error("ERRO: Configuração de 'credentials.usernames' não encontrada ou vazia nos Segredos.")
            st.stop()

        # Converte para dict se for SectionProxy (comportamento do st.secrets)
        credentials_dict = credentials_config.to_dict() if hasattr(credentials_config, 'to_dict') else credentials_config

        cookie_name = cookie_config.get("name")
        cookie_key = cookie_config.get("key")
        cookie_expiry_days_str = cookie_config.get("expiry_days")

        if not cookie_name or not cookie_key or cookie_expiry_days_str is None:
            st.error("ERRO: Configurações de 'cookie' (name, key, expiry_days) incompletas nos Segredos.")
            st.stop()

        placeholder_cookie_keys = [
            "some_signature_key", 
            "NovaChaveSecretaSuperForteParaAuthenticatorV2", 
            "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA",
            "Chaim5778ToViN5728erobmaloRU189154",
            "wR#sVn8gP!zY2qXmK7@cJ3*bL1$fH9" 
        ]
        if cookie_key in placeholder_cookie_keys:
            st.warning("ATENÇÃO: A 'cookie.key' parece ser um placeholder. Para produção, use uma chave ÚNICA e FORTE!")

        authenticator = stauth.Authenticate(
            credentials_dict, 
            cookie_name,
            cookie_key,
            int(cookie_expiry_days_str) 
        )
        return authenticator

    except Exception as e:
        st.error(f"Erro crítico ao inicializar o autenticador: {e}")
        if hasattr(e, '__traceback__'):
            st.exception(e.with_traceback(e.__traceback__))
        st.info("Verifique a estrutura dos Segredos e o requirements.txt.")
        st.stop()

def authentication_flow_stauth(authenticator_obj):
    if authenticator_obj is None:
        st.error("Falha na inicialização do autenticador.")
        st.session_state['authentication_status'] = False
        return

    # O método login retorna name, authentication_status, username
    # Ele também pode levantar exceções ou retornar None em alguns casos.
    login_result = authenticator_obj.login(location='main')

    if login_result is not None:
        name, authentication_status, username = login_result
        st.session_state['name'] = name
        st.session_state['authentication_status'] = authentication_status
        st.session_state['username'] = username
    else:
        # Se login_result for None, significa que o usuário ainda não interagiu
        # ou o formulário está sendo exibido. O status deve ser None.
        st.session_state['authentication_status'] = None
        st.session_state['name'] = None
        st.session_state['username'] = None

    # Feedback visual baseado no status
    if st.session_state['authentication_status'] is False:
        st.error('Nome de usuário/senha incorretos.')
    elif st.session_state['authentication_status'] is None:
        # A biblioteca já mostra "Please enter your username and password."
        # Podemos adicionar uma mensagem extra se quisermos.
        # st.info('Por favor, insira seu nome de usuário e senha para continuar.')
        pass
