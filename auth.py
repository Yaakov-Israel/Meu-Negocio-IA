# auth.py (para streamlit-authenticator - Definitivo para TypeError)
import streamlit as st
import streamlit_authenticator as stauth

def initialize_authenticator():
    try:
        credentials_config = st.secrets.get("credentials")
        cookie_config = st.secrets.get("cookie")

        if not credentials_config or not hasattr(credentials_config, "get") or not credentials_config.get("usernames"):
            st.error("ERRO: Configuração de 'credentials.usernames' não encontrada, vazia ou malformada nos Segredos.")
            st.stop()
        
        credentials_dict = credentials_config.to_dict() if hasattr(credentials_config, 'to_dict') else dict(credentials_config)
        if not credentials_dict.get("usernames"):
             st.error("ERRO: 'usernames' não encontrado dentro de 'credentials' após conversão para dict.")
             st.stop()

        if not cookie_config or not hasattr(cookie_config, "get"):
            st.error("ERRO: Seção 'cookie' não encontrada ou malformada nos Segredos.")
            st.stop()

        cookie_name = cookie_config.get("name")
        cookie_key = cookie_config.get("key")
        cookie_expiry_days_str = cookie_config.get("expiry_days")

        if not cookie_name or not cookie_key or cookie_expiry_days_str is None:
            st.error("ERRO: Configurações de 'cookie' (name, key, expiry_days) incompletas nos Segredos.")
            st.stop()
        
        try:
            cookie_expiry_days_int = int(cookie_expiry_days_str)
        except ValueError:
            st.error(f"ERRO: 'cookie.expiry_days' ('{cookie_expiry_days_str}') não é um número inteiro válido.")
            st.stop()

        # Este aviso será movido para streamlit_app.py para aparecer na sidebar se logado.
        # placeholder_cookie_keys = [
        #     "some_signature_key", "NovaChaveSecretaSuperForteParaAuthenticatorV2", 
        #     "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA",
        #     "Chaim5778ToViN5728erobmaloRU189154", "wR#sVn8gP!zY2qXmK7@cJ3*bL1$fH9" 
        # ]
        # if cookie_key in placeholder_cookie_keys:
        #     st.warning("ATENÇÃO: A 'cookie.key' parece ser um placeholder...")

        authenticator = stauth.Authenticate(
            credentials_dict, 
            cookie_name,
            cookie_key,
            cookie_expiry_days_int 
        )
        return authenticator

    except Exception as e:
        st.error(f"Erro crítico ao inicializar o autenticador: {type(e).__name__} - {e}")
        if hasattr(e, '__traceback__'):
            st.exception(e.with_traceback(e.__traceback__))
        st.info("Verifique a estrutura dos Segredos (TOML) e o arquivo requirements.txt.")
        st.stop()

def authentication_flow_stauth(authenticator_obj):
    if authenticator_obj is None:
        st.error("Falha na inicialização do autenticador (objeto é None). O app não pode prosseguir.")
        st.session_state['authentication_status'] = False
        st.session_state['name'] = None
        st.session_state['username'] = None
        return # Não há mais nada a fazer aqui

    # O método login() renderiza o formulário e retorna (name, authentication_status, username)
    # ou None se o formulário está apenas sendo exibido (antes da primeira interação).
    login_result = authenticator_obj.login(location='main') 
    
    name_val, auth_status_val, username_val = (None, None, None) 

    if login_result is not None:
        try:
            name_val, auth_status_val, username_val = login_result
        except ValueError:
            st.error(f"Erro ao desempacotar resultado do login. Resultado: {login_result}")
            auth_status_val = False 
    
    st.session_state['name'] = name_val
    st.session_state['authentication_status'] = auth_status_val
    st.session_state['username'] = username_val
