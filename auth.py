# auth.py (Versão de Diagnóstico)
import streamlit as st

# Tenta importar a biblioteca principal primeiro
try:
    import streamlit_firebase_auth
    st.success("SUCESSO: Biblioteca 'streamlit_firebase_auth' importada!")

    # --- INÍCIO DO DIAGNÓSTICO ---
    st.subheader("Diagnóstico do Módulo 'streamlit_firebase_auth':")
    try:
        st.text("Atributos disponíveis em 'streamlit_firebase_auth':")
        st.json(dir(streamlit_firebase_auth)) # Mostra todos os atributos do módulo principal

        if hasattr(streamlit_firebase_auth, 'Authenticator'):
            st.info("INFO: 'Authenticator' ENCONTRADO diretamente em 'streamlit_firebase_auth'.")
        else:
            st.warning("AVISO: 'Authenticator' NÃO ENCONTRADO diretamente em 'streamlit_firebase_auth'.")

        if hasattr(streamlit_firebase_auth, 'core'):
            st.text("Atributos disponíveis em 'streamlit_firebase_auth.core':")
            st.json(dir(streamlit_firebase_auth.core)) # Mostra atributos do submódulo .core
            if hasattr(streamlit_firebase_auth.core, 'Authenticator'):
                st.info("INFO: 'Authenticator' ENCONTRADO em 'streamlit_firebase_auth.core'.")
            else:
                st.warning("AVISO: 'Authenticator' NÃO ENCONTRADO em 'streamlit_firebase_auth.core'.")
        else:
            st.warning("AVISO: Submódulo 'core' NÃO ENCONTRADO em 'streamlit_firebase_auth'.")
    except Exception as e_diag:
        st.error(f"ERRO durante o diagnóstico: {e_diag}")
    # --- FIM DO DIAGNÓSTICO ---

except ImportError:
    st.error("ERRO CRÍTICO NA IMPORTAÇÃO: Não foi possível importar a biblioteca 'streamlit_firebase_auth'. Verifique se ela está no requirements.txt e se a versão está correta (ex: streamlit-firebase-auth==1.0.6).")
    st.stop() # Interrompe a execução se a biblioteca principal não puder ser importada
except Exception as e_import_geral:
    st.error(f"ERRO GERAL NA IMPORTAÇÃO da biblioteca 'streamlit_firebase_auth': {e_import_geral}")
    st.stop()

# Tentativa de definir a classe Authenticator para o restante do código
Authenticator = None
if hasattr(streamlit_firebase_auth, 'Authenticator'):
    Authenticator = streamlit_firebase_auth.Authenticator
elif hasattr(streamlit_firebase_auth, 'core') and hasattr(streamlit_firebase_auth.core, 'Authenticator'):
    Authenticator = streamlit_firebase_auth.core.Authenticator

if Authenticator is None:
    st.error("ERRO FINAL DE DIAGNÓSTICO: A classe 'Authenticator' não pôde ser carregada/definida. O aplicativo não pode prosseguir com a autenticação.")
    # Não vamos dar st.stop() aqui para que as mensagens de diagnóstico acima sejam visíveis.
    # Mas a autenticação não funcionará.
else:
    st.success("SUCESSO DE DIAGNÓSTICO: Classe 'Authenticator' carregada e pronta para uso!")


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
    if Authenticator is None:
        st.error("ERRO EM initialize_authenticator: Classe Authenticator não está disponível.")
        st.stop() # Não podemos prosseguir sem Authenticator
    try:
        firebase_config = load_firebase_config()
        cookie_name = st.secrets["cookie_name"]
        cookie_key = st.secrets["cookie_key"]
        cookie_expiry_days_str = st.secrets.get("cookie_expiry_days", "30")

        # Aviso sobre cookie_key já está no código de diagnóstico da classe Authenticator
        auth = Authenticator(
            config=firebase_config,
            cookie_name=cookie_name,
            cookie_key=cookie_key,
            cookie_expiry_days=int(cookie_expiry_days_str)
        )
        return auth
    except KeyError as e:
        st.error(f"ERRO: Configuração de cookie '{e}' não encontrada nos Segredos.")
        st.stop()
    except ValueError:
        st.error("ERRO: 'cookie_expiry_days' deve ser um número inteiro nos Segredos.")
        st.stop()
    except Exception as e:
        st.error(f"ERRO CRÍTICO ao inicializar objeto Authenticator: {e}")
        st.stop()

def authentication_flow(auth_obj):
    """
    Gerencia o fluxo de login, registro e logout.
    Retorna True se o usuário estiver autenticado, False caso contrário.
    """
    if auth_obj is None:
        # Este erro já deve ter sido pego por initialize_authenticator se Authenticator não foi carregado
        st.error("Objeto de autenticação é None em authentication_flow.")
        return False

    try:
        name, authentication_status, username = auth_obj.login()
    except Exception as e:
        st.error(f"Erro durante auth_obj.login(): {e}")
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        return False

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
