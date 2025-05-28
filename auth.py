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

        # Verifica se as configurações essenciais foram carregadas
        if not credentials_config or not credentials_config.get("usernames"):
            st.error("ERRO: Configuração de 'credentials.usernames' não encontrada ou vazia nos Segredos.")
            st.info("Certifique-se de que as credenciais dos usuários estão configuradas corretamente.")
            st.stop()

        if not cookie_config.get("name") or not cookie_config.get("key") or not cookie_config.get("expiry_days"):
            st.error("ERRO: Configurações de 'cookie' (name, key, expiry_days) incompletas nos Segredos.")
            st.info("Verifique todas as chaves dentro da seção [cookie].")
            st.stop()

        # Aviso para a chave de cookie padrão ou fraca
        default_cookie_keys = [
            "some_signature_key", # Placeholder comum
            "NovaChaveSecretaSuperForteParaAuthenticatorV2", # Placeholder que usei no exemplo
            "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA", # Placeholder que usei no exemplo
            "Chaim5778ToViN5728erobmaloRU189154" # Sua chave antiga
        ]
        if cookie_config["key"] in default_cookie_keys:
            st.warning("ATENÇÃO: A 'cookie.key' nos seus segredos parece ser um placeholder ou uma chave de exemplo. Para produção, por favor, defina uma chave secreta ÚNICA, longa e forte no Streamlit Cloud Secrets!")

        authenticator = stauth.Authenticate(
            credentials_config, # st.secrets['credentials'] já é um dict-like acessível
            cookie_config["name"],
            cookie_config["key"],
            cookie_config["expiry_days"],
            # preauthorized # Pode ser usado no futuro para restringir e-mails de registro
        )
        return authenticator

    except Exception as e:
        st.error(f"Erro crítico ao inicializar o autenticador: {e}")
        st.long_text("Detalhes do Erro: " + str(e.with_traceback(e.__traceback__ if hasattr(e, '__traceback__') else None))) # Fornece mais detalhes do erro
        st.info("Verifique a estrutura das suas credenciais e configurações de cookie nos Segredos do Streamlit Cloud. Certifique-se de que o TOML está correto e todas as chaves necessárias (apiKey, authDomain, etc. para Firebase, e as seções [cookie] e [credentials] para streamlit-authenticator) estão presentes e corretas.")
        st.info("Exemplo de estrutura esperada para streamlit-authenticator nos Secrets:")
        st.code("""
[cookie]
expiry_days = 30
key = "SUA_CHAVE_SECRETA_FORTE_AQUI" 
name = "seu_nome_de_cookie_unico"

[credentials]
[credentials.usernames]
nomedousuario = {email = "email@exemplo.com", name = "Nome Completo", password = "HASH_DA_SENHA_AQUI"}
        """)
        st.stop()

def handle_authentication(authenticator):
    """
    Renderiza o widget de login e gerencia o estado da autenticação.
    Retorna True se autenticado, False caso contrário.
    Esta função deve ser chamada no corpo principal do seu app Streamlit,
    onde você quer que o formulário de login apareça se o usuário não estiver logado.
    """
    if authenticator is None:
        st.error("Falha na inicialização do autenticador.")
        return False

    # O widget de login é chamado. Ele retorna: name, authentication_status, username
    # O 'location' pode ser 'main' ou 'sidebar'. 'main' é o padrão se omitido.
    name, authentication_status, username = authenticator.login(location='main')

    # Atualiza o session_state com base no status retornado
    st.session_state['name'] = name
    st.session_state['authentication_status'] = authentication_status
    st.session_state['username'] = username

    if authentication_status is False:
        st.error('Nome de usuário/senha incorretos.')
        return False
    elif authentication_status is None:
        st.info('Por favor, insira seu nome de usuário e senha para continuar.')
        return False

    # Se chegou aqui, authentication_status é True
    return True
