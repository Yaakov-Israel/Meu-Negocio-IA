import streamlit as st
import streamlit_authenticator as stauth # Importa mesmo que a inicialização possa falhar depois

st.set_page_config(page_title="Teste Autenticação v4 - Diagnóstico de Segredos", layout="wide")
st.title("Diagnóstico Detalhado dos Segredos para `streamlit-authenticator`")

st.subheader("Conteúdo Bruto de `st.secrets` (chaves de nível superior):")
st.write(f"Chaves em st.secrets: `{list(st.secrets.keys())}`") # Mostra todas as seções principais

credentials_section_debug = None
cookie_section_debug = None
validation_error_message_debug = "Nenhum erro de validação dos segredos detectado ainda."
initial_checks_passed = False

st.markdown("---")
st.subheader("Analisando `st.secrets['credentials']`:")
if "credentials" in st.secrets:
    st.success("✅ Seção [credentials] ENCONTRADA em st.secrets!")
    credentials_section_debug = st.secrets["credentials"]
    st.write(f"Tipo de `st.secrets['credentials']`: `{type(credentials_section_debug)}`")
    
    try:
        # Acessar st.secrets.credentials diretamente como um dict pode funcionar
        # ou st.secrets.credentials.to_dict() se for um TomlFileProvider
        credentials_dict_debug = {}
        if hasattr(credentials_section_debug, 'to_dict'):
            credentials_dict_debug = credentials_section_debug.to_dict()
            st.write("`st.secrets['credentials']` convertido para dict via `.to_dict()`")
        elif isinstance(credentials_section_debug, dict):
            credentials_dict_debug = credentials_section_debug
            st.write("`st.secrets['credentials']` já é um dict.")
        else:
            st.warning("`st.secrets['credentials']` não é um dict e não tem `.to_dict()`.")
            # Tenta iterar como se fosse um dict-like object (SecretsSection)
            credentials_dict_debug = {k: credentials_section_debug[k] for k in credentials_section_debug}


        st.write("Conteúdo de `credentials` (após tentativa de conversão para dict):")
        st.json(credentials_dict_debug) 
        
        if "usernames" in credentials_dict_debug:
            st.success("Chave 'usernames' ENCONTRADA dentro de `credentials`!")
            usernames_val_debug = credentials_dict_debug["usernames"]
            st.write(f"Tipo de `credentials['usernames']`: `{type(usernames_val_debug)}`")
            st.write("Conteúdo de `credentials['usernames']`:")
            st.json(usernames_val_debug) 
            
            if isinstance(usernames_val_debug, dict):
                st.success("✅ `credentials['usernames']` É um dicionário (dict)!")
                initial_checks_passed = True # Pelo menos a parte de credentials.usernames está OK
            else:
                st.error("❌ `credentials['usernames']` NÃO é um dicionário (dict). Este é o problema!")
                validation_error_message_debug = "O valor de 'credentials.usernames' não é um dicionário."
        else:
            st.error("❌ Chave 'usernames' NÃO encontrada dentro de `credentials`.")
            validation_error_message_debug = "A chave 'usernames' está faltando na seção [credentials]."
            
    except Exception as e_creds_debug:
        st.error(f"Erro ao inspecionar `st.secrets['credentials']` ou 'usernames': {type(e_creds_debug).__name__} - {e_creds_debug}")
        validation_error_message_debug = f"Exceção ao acessar credentials: {e_creds_debug}"
else:
    st.error("❌ Seção [credentials] NÃO encontrada em st.secrets!")
    validation_error_message_debug = "A seção [credentials] está faltando nos segredos."

st.markdown("---")
st.subheader("Analisando `st.secrets['cookie']`:")
if "cookie" in st.secrets:
    st.success("✅ Seção [cookie] ENCONTRADA em st.secrets!")
    cookie_section_debug = st.secrets["cookie"]
    st.write(f"Tipo de `st.secrets['cookie']`: `{type(cookie_section_debug)}`")
    try:
        cookie_dict_debug = {}
        if hasattr(cookie_section_debug, 'to_dict'):
            cookie_dict_debug = cookie_section_debug.to_dict()
        elif isinstance(cookie_section_debug, dict):
            cookie_dict_debug = cookie_section_debug
        else:
            cookie_dict_debug = {k: cookie_section_debug[k] for k in cookie_section_debug}

        st.write("Conteúdo de `cookie` (após tentativa de conversão para dict):")
        st.json(cookie_dict_debug)
        
        if "name" in cookie_dict_debug and "key" in cookie_dict_debug and "expiry_days" in cookie_dict_debug:
            st.success("✅ Chaves 'name', 'key', 'expiry_days' ENCONTRADAS em `cookie`!")
            if initial_checks_passed: # Só considera o cookie OK se credentials também estiverem minimamente OK
                 pass # Não muda o initial_checks_passed aqui
            else: # Se credentials falhou, o check geral falha
                 initial_checks_passed = False
        else:
            st.error("❌ Uma ou mais chaves ('name', 'key', 'expiry_days') NÃO encontradas em `cookie`.")
            validation_error_message_debug = "Chaves faltando na seção [cookie]."
            initial_checks_passed = False
            
    except Exception as e_cookie_debug:
        st.error(f"Erro ao inspecionar `st.secrets['cookie']`: {e_cookie_debug}")
        validation_error_message_debug = f"Exceção ao acessar cookie: {e_cookie_debug}"
        initial_checks_passed = False
else:
    st.error("❌ Seção [cookie] NÃO encontrada em st.secrets!")
    validation_error_message_debug = "A seção [cookie] está faltando nos segredos."
    initial_checks_passed = False

st.markdown("---")

# Validação final antes de tentar o Authenticator
if initial_checks_passed:
    st.success("🎉 VALIDAÇÃO INICIAL DOS SEGREDOS PASSOU! Tentando inicializar o Authenticator...")
    
    # Tentativa de usar o Authenticator
    authenticator_final_diag = None
    try:
        # Re-obtém os dicts para garantir que estamos usando a forma correta
        final_credentials_config_dict = st.secrets['credentials'].to_dict() if hasattr(st.secrets['credentials'], 'to_dict') else dict(st.secrets['credentials'])
        final_cookie_config_dict = st.secrets['cookie'].to_dict() if hasattr(st.secrets['cookie'], 'to_dict') else dict(st.secrets['cookie'])

        authenticator_final_diag = stauth.Authenticate(
            final_credentials_config_dict,
            final_cookie_config_dict['name'],
            final_cookie_config_dict['key'],
            final_cookie_config_dict['expiry_days'],
        )
        st.success("✅ Authenticator INICIALIZADO com sucesso!")
        
        name_diag_final, status_diag_final, username_diag_final = authenticator_final_diag.login()
        st.write(f"Resultado do login: Nome='{name_diag_final}', Status='{status_diag_final}', Username='{username_diag_final}'")
        
        if status_diag_final:
            st.sidebar.success(f"Login OK: {name_diag_final}")
            authenticator_final_diag.logout("Logout", "sidebar", key="logout_diag_v9_final")
            st.header("🎉 Login Bem-Sucedido no Teste v4!")
        elif status_diag_final == False:
            st.error("Credenciais inválidas no formulário de login.")
        elif status_diag_final == None:
            st.info("Formulário de login renderizado. Por favor, tente logar.")

    except Exception as e_auth_final_diag:
        st.error(f"🚨 ERRO AO INICIALIZAR/USAR Authenticator (Diagnóstico v4): {type(e_auth_final_diag).__name__} - {e_auth_final_diag}")
        st.exception(e_auth_final_diag)
else:
    st.error(f"Validação inicial dos segredos FALHOU. Mensagem final: {validation_error_message_debug}")
    st.info("Verifique o output de diagnóstico acima para ver qual parte dos segredos não foi lida corretamente.")

st.markdown("---")
st.caption("Fim do teste de diagnóstico de segredos v4.")
