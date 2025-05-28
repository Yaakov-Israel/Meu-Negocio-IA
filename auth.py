# auth.py
import streamlit as st
import streamlit_firebase_auth # Importa a biblioteca

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

def initialize_auth_object():
    """Inicializa e retorna o objeto de autenticação do Firebase."""
    try:
        firebase_config = load_firebase_config()

        # Tenta obter o objeto de autenticação da forma padrão da biblioteca
        # A biblioteca pode inicializar o objeto internamente ao ser importada
        # ou pode ter uma função específica para isso.
        # Se a biblioteca for a de "thiagomartins", ela usa um construtor
        # que é um pouco diferente e requer as credenciais do cookie no construtor.

        # Vamos usar a forma como a biblioteca de "thiagomartins" funciona,
        # pois é a que usa "Authenticator" (que estava no erro anterior)
        # e é comum para Streamlit.

        cookie_name = st.secrets["cookie_name"]
        cookie_key = st.secrets["cookie_key"]
        cookie_expiry_days_str = st.secrets.get("cookie_expiry_days", "30")

        if not cookie_key or cookie_key in ["sua_chave_secreta_super_forte_e_aleatoria_aqui", "COLOQUE_AQUI_UMA_SENHA_BEM_FORTE_E_ALEATORIA_QUE_VOCE_CRIOU", "ChaimTovim", "Chaim5778ToViN5728erobmaloRU189154"]: # Adicionadas as suas chaves de exemplo para o aviso
             st.warning("ATENÇÃO: A 'cookie_key' nos seus segredos parece ser a padrão, um placeholder ou uma chave fraca. Por favor, defina uma chave secreta forte e única para segurança!")

        auth = streamlit_firebase_auth.Authenticator( # Acessando Authenticator diretamente do módulo
            config=firebase_config,
            cookie_name=cookie_name,
            cookie_key=cookie_key,
            cookie_expiry_days=int(cookie_expiry_days_str)
        )
        return auth

    except AttributeError:
         st.error("ERRO: A biblioteca 'streamlit_firebase_auth' não parece ter o atributo 'Authenticator'. Verifique a instalação e o nome da biblioteca em requirements.txt.")
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

def handle_auth_flow(auth_obj):
    """
    Gerencia o fluxo de login, registro e logout.
    Retorna True se o usuário estiver autenticado, False caso contrário.
    """
    if auth_obj is None:
        st.error("Objeto de autenticação não foi inicializado.")
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
        # A mensagem de erro já é exibida pelo componente 'login'
        # st.error(f"Falha na autenticação. Mensagem: {username}") 
        return False
    elif authentication_status is None: # Nenhum evento de login ainda
        st.session_state['user_authenticated'] = False
        st.session_state['user_info'] = None
        return False
    return False
