import streamlit as st
import os
import json 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import pyrebase 

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

firebase_app = None
pb_auth_client = None
user_is_authenticated = False

try:
    firebase_config_from_secrets = st.secrets["firebase_config"]
    plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
    
    if plain_firebase_config_dict:
        firebase_app = pyrebase.initialize_app(plain_firebase_config_dict)
        pb_auth_client = firebase_app.auth()
    else:
        st.error("🚨 ERRO CRÍTICO: Configuração do Firebase vazia.")
        st.stop()
except KeyError:
    st.error("🚨 ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos.")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO ao inicializar Pyrebase4: {e}")
    st.exception(e) # Mostra o traceback completo para este erro específico
    st.stop()
