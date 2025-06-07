import streamlit as st
import json
import os

@st.cache_data # Otimização CRÍTICA do Streamlit!
def carregar_prompts_config(caminho_arquivo="prompts/prompts.json"):
    """
    Carrega o arquivo de configuração de prompts (prompts.json).
    Usa o cache do Streamlit para ler o arquivo do disco apenas uma vez,
    tornando o aplicativo muito mais rápido após a primeira carga.
    """
    if not os.path.exists(caminho_arquivo):
        st.error(f"FATAL: Arquivo de configuração de prompts não encontrado em '{caminho_arquivo}'. O aplicativo não pode continuar.")
        return None
    
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        st.error(f"FATAL: Erro ao decodificar o arquivo JSON em '{caminho_arquivo}'. Verifique a sintaxe. Erro: {e}")
        return None
    except Exception as e:
        st.error(f"FATAL: Um erro inesperado ocorreu ao carregar '{caminho_arquivo}'. Erro: {e}")
        return None
