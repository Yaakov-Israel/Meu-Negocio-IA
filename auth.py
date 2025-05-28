# auth.py (para streamlit-authenticator)
import streamlit as st
import streamlit_authenticator as stauth

def initialize_authenticator():
    """
    Inicializa o objeto Authenticate do streamlit-authenticator
    usando as credenciais e configurações de cookie dos Streamlit Secrets.
    """
    try:
        credentials_config = st.secrets.get("credentials", {}).to_dict()
        cookie_config = st.secrets.get("cookie", {}).to_dict()

        if not credentials_config or not credentials_config.get("usernames"):
            st.error("ERRO: Configuração de 'credentials.usernames' não encontrada ou vazia nos Segredos.")
            st.stop()
        
        cookie_name = cookie_config.get("name")
        cookie_key = cookie_config.get("key")
        cookie_expiry_days_str = cookie_config.get("expiry_days") # Será convertido para int depois

        if not cookie_name or not cookie_key or cookie_expiry_days_str is None:
            st.error("ERRO: Configurações de 'cookie' (name, key, expiry_days) incompletas nos Segredos.")
            st.stop()
        
        # Chaves de cookie que disparam aviso de segurança
        placeholder_cookie_keys = [
            "some_signature_key", 
            "NovaChaveSecretaSuperForteParaAuthenticatorV2", 
            "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA",
            "Chaim5778ToViN5728erobmaloRU189154",
            "wR#sVn8gP!zY2qXmK7@cJ3*bL1$fH9" 
        ]
        if cookie_key in placeholder_cookie_keys:
            st.warning("ATENÇÃO: A 'cookie.key' nos seus segredos parece ser um placeholder ou uma chave de exemplo. Para produção, defina uma chave secreta ÚNICA, longa e forte!")

        authenticator = stauth.Authenticate(
            credentials_config, 
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

def authentication_flow_stauth(authenticator_obj): # Nome da função como esperado por streamlit_app.py
    """
    Renderiza o widget de login e gerencia o estado da autenticação.
    """
    if authenticator_obj is None:
        st.error("Falha na inicialização do autenticador.")
        st.session_state['authentication_status'] = False # Garante estado definido
        return

    name, authentication_status, username = authenticator_obj.login(location='main')

    st.session_state['name'] = name
    st.session_state['authentication_status'] = authentication_status
    st.session_state['username'] = username
    
    # Não é necessário retornar um valor booleano aqui, pois o status é gerenciado via session_state
    # e o widget de login/erro já é renderizado pelo authenticator_obj.login()
