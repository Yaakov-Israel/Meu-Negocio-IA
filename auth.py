# auth.py
import streamlit as st
# Tentativa de importar Authenticator diretamente do submódulo .core
try:
    from streamlit_firebase_auth.core import Authenticator
except ImportError:
    # Fallback para a tentativa anterior se a importação direta de .core falhar
    # Isso também ajuda a isolar se o problema é o 'Authenticator' em si ou o módulo 'core'
    try:
        import streamlit_firebase_auth
        if hasattr(streamlit_firebase_auth, 'Authenticator'):
            Authenticator = streamlit_firebase_auth.Authenticator
        else:
            st.error("ERRO CRÍTICO: Não foi possível encontrar a classe 'Authenticator' na biblioteca 'streamlit_firebase_auth', nem diretamente nem em '.core'. Verifique a instalação da biblioteca.")
            st.stop()
    except ImportError:
        st.error("ERRO CRÍTICO: Não foi possível importar a biblioteca 'streamlit_firebase_auth'. Verifique se ela está no requirements.txt.")
        st.stop()


def load_firebase_config():
    """Carrega as configurações do Firebase a partir dos Streamlit Secrets."""
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
        st.error(f"ERRO: Credencial Firebase '{e}' não encontrada nos Segredos.")
        st.info("Verifique suas chaves 'firebase_...' no Streamlit Cloud.")
        st.stop()
    except Exception as e:
        st.error(f"ERRO ao carregar configuração do Firebase: {e}")
        st.stop()

def initialize_authenticator():
    """Inicializa e retorna o objeto de autenticação do Firebase."""
    try:
        firebase_config = load_firebase_config()

        cookie_name = st.secrets["cookie_name"]
        cookie_key = st.secrets["cookie_key"]
        cookie_expiry_days_str = st.secrets.get("cookie_expiry_days", "30")

        weak_or_placeholder_keys = [
            "sua_chave_secreta_super_forte_e_aleatoria_aqui",
            "COLOQUE_AQUI_UMA_SENHA_BEM_FORTE_E_ALEATORIA_QUE_VOCE_CRIOU",
            "ChaimTovim",
            "Chaim5778ToViN5728erobmaloRU189154", # Sua chave atual
            "W#z&8FpQ!s9g$X2vR7*kL@cN5bV1jM3"  # Minha sugestão anterior
        ]
        if not cookie_key or cookie_key in weak_or_placeholder_keys:
             st.warning("ATENÇÃO: A 'cookie_key' nos seus segredos parece ser um placeholder ou uma chave que já usamos em exemplos. Para produção, por favor, defina uma chave secreta ÚNICA, longa e forte no Streamlit Cloud Secrets!")

        # Agora usamos a classe Authenticator que tentamos importar no início do arquivo
        auth = Authenticator(
            config=firebase_config,
            cookie_name=cookie_name,
            cookie_key=cookie_key,
            cookie_expiry_days=int(cookie_expiry_days_str)
        )
        return auth

    except NameError: 
        # Isso aconteceria se a classe Authenticator não foi definida por nenhuma das tentativas de import
        st.error("ERRO INTERNO: A classe Authenticator não foi carregada. Isso não deveria acontecer com as tentativas de import acima.")
        st.stop()
    except KeyError as e:
        st.error(f"ERRO: Configuração de cookie '{e}' não encontrada nos Segredos.")
        st.info("Verifique 'cookie_name', 'cookie_key', e 'cookie_expiry_days'.")
        st.stop()
    except ValueError:
        st.error("ERRO: 'cookie_expiry_days' deve ser um número inteiro nos Segredos.")
        st.stop()
    except Exception as e:
        st.error(f"ERRO CRÍTICO ao inicializar autenticação Firebase: {e}")
        st.stop()

def authentication_flow(auth_obj):
    """
    Gerencia o fluxo de login, registro e logout.
    Retorna True se o usuário estiver autenticado, False caso contrário.
    """
    if auth_obj is None:
        st.error("Objeto de autenticação não foi inicializado corretamente.")
        return False

    name, authentication_status, username = auth_obj.login()

    if authentication_status:
        st.session_state['user_authenticated'] = True
        st.session_state['user_info'] = {
            'name': name if name else username.split('@')[0] if username and '@' in username else username,
            'email': username,
            'uid': username 
        }
        return True
    elif authentication_status is False:
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        return False
    elif authentication_status is None: 
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        return False
    return False
