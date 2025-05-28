# auth.py (para streamlit-authenticator - Versão Robusta)
import streamlit as st
import streamlit_authenticator as stauth

def initialize_authenticator():
    try:
        credentials_config = st.secrets.get("credentials")
        cookie_config = st.secrets.get("cookie")

        if not credentials_config or not hasattr(credentials_config, "get") or not credentials_config.get("usernames"):
            st.error("ERRO DE CONFIGURAÇÃO: 'credentials.usernames' não encontrado ou malformado nos Segredos.")
            st.stop()
        
        credentials_dict = credentials_config.to_dict() if hasattr(credentials_config, 'to_dict') else dict(credentials_config)
        if not credentials_dict.get("usernames"):
             st.error("ERRO DE CONFIGURAÇÃO: 'usernames' não é uma chave válida dentro de 'credentials'.")
             st.stop()

        if not cookie_config or not hasattr(cookie_config, "get"):
            st.error("ERRO DE CONFIGURAÇÃO: Seção 'cookie' não encontrada ou malformada nos Segredos.")
            st.stop()

        cookie_name = cookie_config.get("name")
        cookie_key = cookie_config.get("key")
        cookie_expiry_days_str = cookie_config.get("expiry_days")

        if not cookie_name or not cookie_key or cookie_expiry_days_str is None:
            st.error("ERRO DE CONFIGURAÇÃO: 'cookie.name', 'cookie.key', ou 'cookie.expiry_days' não encontrado nos Segredos.")
            st.stop()
        
        try:
            cookie_expiry_days_int = int(cookie_expiry_days_str)
        except ValueError:
            st.error(f"ERRO DE CONFIGURAÇÃO: 'cookie.expiry_days' ('{cookie_expiry_days_str}') não é um número inteiro válido.")
            st.stop()

        authenticator = stauth.Authenticate(
            config=credentials_dict, 
            cookie_name=cookie_name,
            key=cookie_key, # Nome do parâmetro é 'key'
            cookie_expiry_days=cookie_expiry_days_int 
        )
        return authenticator

    except Exception as e:
        st.error(f"Erro crítico ao inicializar o autenticador: {type(e).__name__} - {str(e)}")
        if hasattr(e, '__traceback__'):
            st.exception(e.with_traceback(e.__traceback__))
        st.info("Verifique a estrutura dos Segredos (TOML) e o arquivo requirements.txt.")
        st.stop()

def authentication_flow_stauth(authenticator_obj):
    if authenticator_obj is None:
        st.session_state['authentication_status'] = False
        st.session_state['name'] = None
        st.session_state['username'] = None
        st.error("Falha crítica: Objeto autenticador não foi inicializado.")
        return

    # O método login() renderiza o formulário.
    # Ele retorna: name, authentication_status, username
    # authentication_status pode ser True (logado), False (falha), None (formulário exibido, sem submissão)
    name, authentication_status, username = authenticator_obj.login(location='main')
    
    st.session_state['name'] = name
    st.session_state['authentication_status'] = authentication_status
    st.session_state['username'] = username
