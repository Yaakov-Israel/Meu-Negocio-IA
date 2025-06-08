import streamlit as st
import json
import os

# --- INÍCIO DA MÁGICA ---
# Pega o caminho absoluto do diretório onde este script (utils.py) está.
# __file__ é uma variável especial do Python que contém o caminho do arquivo atual.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Constrói o caminho completo e à prova de erros para os outros diretórios.
PROMPTS_DIR = os.path.join(SCRIPT_DIR, "prompts")
IMAGES_DIR = os.path.join(SCRIPT_DIR, "images")
FONTS_DIR = os.path.join(SCRIPT_DIR, "fonts")
# --- FIM DA MÁGICA ---

@st.cache_data
def carregar_prompts_config():
    """ Carrega o arquivo de configuração de prompts (prompts.json). """
    caminho_arquivo = os.path.join(PROMPTS_DIR, "prompts.json")
    if not os.path.exists(caminho_arquivo):
        st.error(f"FATAL: Arquivo de prompts não encontrado em '{caminho_arquivo}'.")
        return None
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"FATAL: Erro ao carregar ou decodificar '{caminho_arquivo}'. Erro: {e}")
        return None

# Função para carregar imagens de forma robusta
def get_image_path(image_name):
    return os.path.join(IMAGES_DIR, image_name)

# Função para carregar fontes de forma robusta
def get_font_path(font_name):
    return os.path.join(FONTS_DIR, font_name)
