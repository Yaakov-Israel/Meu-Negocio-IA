# auth.py
import streamlit as st
import streamlit_firebase_auth as sfa # Biblioteca para autenticação Firebase

def get_firebase_config():
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
        st.error(f"ERRO: Credencial Firebase '{e}' não encontrada nos Segredos (secrets.toml).")
        st.info("Verifique se todas as chaves 'firebase_...' estão configuradas corretamente no seu arquivo .streamlit/secrets.toml ou nas configurações do Streamlit Cloud.")
        st.stop()
    except Exception as e:
        st.error(f"ERRO ao carregar configuração do Firebase: {e}")
        st.stop()

def initialize_authenticator():
    """Inicializa e retorna o objeto de autenticação do Firebase."""
    try:
        firebase_config = get_firebase_config()
        cookie_name = st.secrets["cookie_name"]
        cookie_key = st.secrets["cookie_key"]
        cookie_expiry_days_str = st.secrets.get("cookie_expiry_days", "30")

        if not cookie_key or cookie_key == "sua_chave_secreta_super_forte_e_aleatoria_aqui" or cookie_key == "COLOQUE_AQUI_UMA_SENHA_BEM_FORTE_E_ALEATORIA_QUE_VOCE_CRIOU":
             st.warning("ATENÇÃO: A 'cookie_key' nos seus segredos parece ser a padrão ou um placeholder. Por favor, defina uma chave secreta forte e única para segurança!")

        authenticator = sfa.Authenticator(
            config=firebase_config,
            cookie_name=cookie_name,
            cookie_key=cookie_key,
            cookie_expiry_days=int(cookie_expiry_days_str)
        )
        return authenticator
    except KeyError as e:
        st.error(f"ERRO: Configuração de cookie '{e}' não encontrada nos Segredos.")
        st.info("Verifique se 'cookie_name', 'cookie_key', e 'cookie_expiry_days' estão configurados.")
        st.stop()
    except ValueError:
        st.error("ERRO: 'cookie_expiry_days' deve ser um número inteiro nos Segredos.")
        st.stop()
    except Exception as e:
        st.error(f"ERRO ao inicializar autenticação Firebase: {e}")
        st.stop()

def authentication_flow(authenticator):
    """
    Gerencia o fluxo de login, registro e logout.
    Retorna True se o usuário estiver autenticado, False caso contrário.
    """
    name, authentication_status, username = authenticator.login()

    if authentication_status:
        st.session_state['user_authenticated'] = True
        st.session_state['user_info'] = {
            'name': name if name else username.split('@')[0],
            'email': username,
            'uid': username
        }
        return True
    elif authentication_status is False:
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        st.error(f"Falha na autenticação. Mensagem: {username}")
        return False
    elif authentication_status is None:
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        return False
    return False
