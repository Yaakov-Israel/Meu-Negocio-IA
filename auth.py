# auth.py (Diagnóstico Final Simplificado)
import streamlit as st

st.subheader("Iniciando Diagnóstico de 'streamlit_firebase_auth'")

try:
    import streamlit_firebase_auth
    st.success("Biblioteca 'streamlit_firebase_auth' importada com SUCESSO!")

    st.text("Atributos disponíveis DIRETAMENTE em 'streamlit_firebase_auth':")
    st.json(dir(streamlit_firebase_auth)) # Lista tudo dentro do módulo principal

    # Vamos verificar se o submódulo 'core' existe e listar seu conteúdo também
    if hasattr(streamlit_firebase_auth, 'core'):
        st.text("Atributos disponíveis em 'streamlit_firebase_auth.core':")
        st.json(dir(streamlit_firebase_auth.core))
        if hasattr(streamlit_firebase_auth.core, 'Authenticator'):
             st.info("BOA NOTÍCIA: 'Authenticator' ENCONTRADO em 'streamlit_firebase_auth.core'!")
        else:
             st.warning("AVISO: 'Authenticator' NÃO encontrado em 'streamlit_firebase_auth.core'.")
    else:
        st.warning("AVISO: Submódulo 'core' NÃO encontrado em 'streamlit_firebase_auth'.")

    # Verificação final se Authenticator está no nível superior, como esperado originalmente
    if hasattr(streamlit_firebase_auth, 'Authenticator'):
        st.info("BOA NOTÍCIA: 'Authenticator' ENCONTRADO diretamente em 'streamlit_firebase_auth'!")
    else:
        st.warning("AVISO: 'Authenticator' NÃO encontrado diretamente em 'streamlit_firebase_auth'.")

except ImportError:
    st.error("ERRO CRÍTICO NA IMPORTAÇÃO: Não foi possível importar a biblioteca 'streamlit_firebase_auth'. Verifique o 'requirements.txt'.")
except Exception as e:
    st.error(f"ERRO GERAL DURANTE O DIAGNÓSTICO: {e}")

st.info("Fim do script de diagnóstico 'auth.py'. O aplicativo principal (streamlit_app.py) tentará prosseguir, mas pode falhar se 'Authenticator' não foi encontrado.")
# Não vamos dar st.stop() aqui para garantir que todas as mensagens de diagnóstico sejam exibidas
# e para ver o erro subsequente no streamlit_app.py se Authenticator não for definido.

# Tentativa de definir Authenticator para o streamlit_app.py poder tentar usá-lo
# Esta parte pode falhar se as verificações acima não encontrarem Authenticator,
# mas o objetivo é deixar o streamlit_app.py tentar e falhar se necessário,
# depois de termos visto as mensagens de diagnóstico.
Authenticator = None 
try:
    if hasattr(streamlit_firebase_auth, 'Authenticator'):
        Authenticator = streamlit_firebase_auth.Authenticator
    elif hasattr(streamlit_firebase_auth, 'core') and hasattr(streamlit_firebase_auth.core, 'Authenticator'):
        Authenticator = streamlit_firebase_auth.core.Authenticator
except NameError: # Caso streamlit_firebase_auth não tenha sido importado
    pass # Authenticator permanecerá None
except Exception: # Outros erros inesperados ao tentar acessar atributos
    pass # Authenticator permanecerá None

# As funções abaixo não serão chamadas se o script parar antes ou se Authenticator for None
# e initialize_authenticator falhar.
def load_firebase_config():
    # Esta função só será usada se o initialize_authenticator for chamado
    return st.secrets # Simplificado, já que as chaves são acessadas diretamente

def initialize_authenticator():
    if Authenticator is None:
        # Esta mensagem de erro é a que você viu da última vez.
        # As mensagens de diagnóstico acima DELA são as mais importantes agora.
        st.error("ERRO EM initialize_authenticator: Classe Authenticator não está disponível (permaneceu None após diagnóstico).")
        st.stop()

    firebase_config = {
        "apiKey": st.secrets["firebase_apiKey"],
        "authDomain": st.secrets["firebase_authDomain"],
        "projectId": st.secrets["firebase_projectId"],
        "storageBucket": st.secrets["firebase_storageBucket"],
        "messagingSenderId": st.secrets["firebase_messagingSenderId"],
        "appId": st.secrets["firebase_appId"],
        "databaseURL": st.secrets["firebase_databaseURL"],
    }
    auth = Authenticator(
        config=firebase_config,
        cookie_name=st.secrets["cookie_name"],
        cookie_key=st.secrets["cookie_key"],
        cookie_expiry_days=int(st.secrets.get("cookie_expiry_days", "30"))
    )
    return auth

def authentication_flow(auth_obj):
    if auth_obj is None: return False
    name, authentication_status, username = auth_obj.login()
    if authentication_status:
        st.session_state['user_authenticated'] = True
        st.session_state['user_info'] = {'name': name, 'email': username, 'uid': username}
        return True
    st.session_state['user_authenticated'] = False
    st.session_state['user_info'] = None
    return False
