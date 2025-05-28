# auth.py (Diagnóstico Final - Versão Focada em Mostrar Informações na Tela)
import streamlit as st

# Este bloco tenta imprimir informações de diagnóstico na tela do app
# Essas mensagens podem não aparecer no arquivo de log baixado.
# É importante observar a tela do aplicativo diretamente.

st.title("Página de Diagnóstico - auth.py")
st.markdown("---")
st.subheader("Iniciando Diagnóstico do módulo 'streamlit_firebase_auth'")
st.markdown("Por favor, copie TODAS as mensagens desta página e envie.")
st.markdown("---")

try:
    import streamlit_firebase_auth
    st.success("SUCESSO NA IMPORTAÇÃO: A biblioteca 'streamlit_firebase_auth' foi importada!")
    
    st.subheader("Conteúdo de `streamlit_firebase_auth`:")
    try:
        st.text("Atributos disponíveis (saída de dir()):")
        st.json(dir(streamlit_firebase_auth)) # ESSA É A INFORMAÇÃO MAIS IMPORTANTE!
    except Exception as e_dir:
        st.error(f"Erro ao tentar listar atributos com dir(): {e_dir}")

    st.markdown("---")
    st.subheader("Verificando por 'Authenticator' e 'core':")

    if hasattr(streamlit_firebase_auth, 'Authenticator'):
        st.info("INFO: 'Authenticator' FOI ENCONTRADO diretamente em 'streamlit_firebase_auth'.")
        Authenticator_class_ref = streamlit_firebase_auth.Authenticator
    else:
        st.warning("AVISO: 'Authenticator' NÃO FOI ENCONTRADO diretamente em 'streamlit_firebase_auth'.")
        Authenticator_class_ref = None

    if hasattr(streamlit_firebase_auth, 'core'):
        st.info("INFO: Submódulo 'core' FOI ENCONTRADO em 'streamlit_firebase_auth'.")
        try:
            st.text("Atributos disponíveis em 'streamlit_firebase_auth.core':")
            st.json(dir(streamlit_firebase_auth.core))
            if hasattr(streamlit_firebase_auth.core, 'Authenticator'):
                st.info("INFO: 'Authenticator' FOI ENCONTRADO em 'streamlit_firebase_auth.core'.")
                if Authenticator_class_ref is None: # Usa este se não encontrou no nível superior
                     Authenticator_class_ref = streamlit_firebase_auth.core.Authenticator
            else:
                st.warning("AVISO: 'Authenticator' NÃO FOI ENCONTRADO em 'streamlit_firebase_auth.core'.")
        except Exception as e_core_dir:
            st.error(f"Erro ao tentar listar atributos de '.core': {e_core_dir}")
    else:
        st.warning("AVISO: Submódulo 'core' NÃO FOI ENCONTRADO em 'streamlit_firebase_auth'.")
    
    st.markdown("---")
    if Authenticator_class_ref is not None:
        st.success("CONCLUSÃO DO DIAGNÓSTICO: A classe 'Authenticator' parece ter sido encontrada e carregada!")
    else:
        st.error("CONCLUSÃO DO DIAGNÓSTICO: A classe 'Authenticator' NÃO FOI encontrada. A autenticação falhará.")
        st.warning("Verifique a saída de 'dir(streamlit_firebase_auth)' acima para entender o que está disponível.")
        st.stop() # Interrompe aqui se Authenticator não foi encontrado, para focar no diagnóstico.

except ImportError:
    st.error("ERRO CRÍTICO NA IMPORTAÇÃO: Não foi possível importar a biblioteca 'streamlit_firebase_auth'.")
    st.info("Verifique se 'streamlit-firebase-auth==1.0.6' está no seu arquivo 'requirements.txt' e se o app foi reiniciado após a mudança.")
    st.stop()
except Exception as e_geral:
    st.error(f"ERRO GERAL INESPERADO durante o diagnóstico: {e_geral}")
    st.stop()

# As funções abaixo só serão definidas se o script não parar antes
def load_firebase_config():
    try:
        return {
            "apiKey": st.secrets["firebase_apiKey"],
            "authDomain": st.secrets["firebase_authDomain"],
            "projectId": st.secrets["firebase_projectId"],
            "storageBucket": st.secrets["firebase_storageBucket"],
            "messagingSenderId": st.secrets["firebase_messagingSenderId"],
            "appId": st.secrets["firebase_appId"],
            "databaseURL": st.secrets["firebase_databaseURL"],
        }
    except KeyError as e:
        st.error(f"ERRO ao carregar config do Firebase (Secrets): Chave '{e}' não encontrada.")
        st.stop()

def initialize_authenticator():
    if Authenticator_class_ref is None: # Verifica a referência que tentamos carregar
        st.error("ERRO FATAL em initialize_authenticator: Referência para Authenticator é None.")
        st.stop()
    
    firebase_config = load_firebase_config()
    auth = Authenticator_class_ref(
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
