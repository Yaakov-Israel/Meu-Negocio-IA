import streamlit as st
import os
import json # Mantido para o try-except do firebase_config, embora não estritamente necessário para este teste mínimo
import pyrebase 

# --- Configuração da Página ---
st.set_page_config(
    page_title="Teste Login PME Pro - Mínimo", # Título atualizado
    layout="centered",
    initial_sidebar_state="expanded",
    page_icon="🔑"
)

st.title("🔑 Teste de Inicialização Firebase (Pyrebase4)")
st.write("Tentando inicializar o Firebase...")

# --- Configuração do Firebase (dos Segredos) ---
firebase_app = None
pb_auth_client = None # Não vamos usar ainda, mas declaramos
error_message_firebase_init = None
firebase_initialized_successfully = False

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos do Streamlit."
        st.error(error_message_firebase_init)
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"] # "databaseURL" é opcional para auth apenas
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]

        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
            st.error(error_message_firebase_init)
        else:
            if not firebase_app: 
                firebase_app = pyrebase.initialize_app(plain_firebase_config_dict)
            
            pb_auth_client = firebase_app.auth() # Tentamos obter o cliente auth
            st.success("✅ Firebase (Pyrebase4) SDK inicializado com sucesso!")
            st.write("Objeto de autenticação (`pb_auth_client`): ", pb_auth_client)
            firebase_initialized_successfully = True

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
    st.error(error_message_firebase_init)
except AttributeError as e: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config'] (Possível problema de estrutura): {e}"
    st.error(error_message_firebase_init)
    st.exception(e)
except Exception as e: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e}"
    st.error(error_message_firebase_init)
    st.exception(e) # Mostra o traceback completo

if not firebase_initialized_successfully:
    st.warning("A inicialização do Firebase falhou. Verifique os erros acima.")

st.markdown("---")
st.markdown("Fim do script de teste mínimo.")
