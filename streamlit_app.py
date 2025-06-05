import os
import streamlit as st
import base64
from PIL import Image # Para o logo na sidebar
import time # Para pequenos delays na UI
import datetime # Para registrar data/hora da ativação
import json # Para lidar com erros do Firebase

# --- Firebase Imports ---
import pyrebase # Para autenticação de usuários
import firebase_admin # Para interagir com Firestore de forma segura
from firebase_admin import credentials, firestore

# --- Langchain/Gemini Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import AIMessage

# --- Constantes ---
APP_KEY_SUFFIX = "maxia_app_v0.2" # Suffixo único para chaves de session_state
USER_COLLECTION = "users" # Coleção no Firestore para perfis de usuário
ACTIVATION_KEYS_COLLECTION = "activation_keys" # Coleção no Firestore para chaves de ativação

# Seta as variáveis de ambiente necessárias para evitar avisos ou erros
os.environ["TOKENIZERS_PARALLELISM"] = "false" # Evita avisos de paralelismo do tokenizer

# --- Função Auxiliar para Imagem em Base64 ---
def convert_image_to_base64(image_path):
    """Converte uma imagem local para uma string base64."""
    try:
        if not os.path.exists(image_path):
            st.warning(f"Arquivo de imagem não encontrado: {image_path}")
            return None
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return encoded_string
    except Exception as e:
        st.error(f"Erro ao converter imagem {image_path} para base64: {e}")
        return None

# --- Funções do Sistema de Ativação ---
def check_user_activation_status(user_uid, db_firestore_instance):
    """Verifica no Firestore se o usuário já está ativado."""
    try:
        user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)
        user_doc = user_ref.get()
        return user_doc.exists and user_doc.get("is_activated", False)
    except Exception as e:
        st.error(f"Erro ao verificar status de ativação: {e}")
        # Em caso de erro na leitura, é mais seguro assumir que não está ativado.
        return False

def process_activation_key(user_uid, key_code, db_firestore_instance):
    """Valida a chave e, se válida e disponível, a reivindica para o usuário."""
    if not key_code:
        return False, "Por favor, insira uma chave de ativação."

    try:
        key_ref = db_firestore_instance.collection(ACTIVATION_KEYS_COLLECTION).document(key_code)
        key_doc = key_ref.get()

        if key_doc.exists:
            if key_doc.get("is_used"):
                if key_doc.get("used_by_uid") == user_uid:
                    # Chave já reivindicada por este usuário, considera ativado
                    # (Atualiza o status de ativação do usuário se não estiver marcado)
                    user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)
                    user_ref.set({"is_activated": True, "last_activation_key": key_code, "last_login": datetime.datetime.now()}, merge=True)
                    return True, "Chave já utilizada por você. Acesso liberado!"
                else:
                    return False, "Chave de ativação inválida, já utilizada por outro usuário ou expirada."
            else:
                # Chave válida e disponível! Reivindicar.
                key_ref.update({
                    "is_used": True,
                    "used_by_uid": user_uid,
                    "activation_date": datetime.datetime.now()
                })
                # Marcar usuário como ativado
                user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)
                user_ref.set({"is_activated": True, "last_activation_key": key_code, "last_login": datetime.datetime.now()}, merge=True)
                return True, "Chave ativada com sucesso!"
        else:
            return False, "Chave de ativação não encontrada."
    except Exception as e:
        st.error(f"Erro ao validar a chave de ativação: {e}")
        return False, f"Erro ao processar a chave: {e}"

def show_activation_page(user_uid, db_firestore_instance):
    st.title("🔑 Ativação Necessária - Max IA")
    st.write("Bem-vindo ao Max IA! Para continuar, por favor, insira sua chave de ativação.")
    
    with st.form("activation_form"):
        key_input = st.text_input("Chave de Ativação", type="password", placeholder="Insira sua chave aqui")
        submit_activation = st.form_submit_button("Ativar Max IA")

        if submit_activation:
            if not key_input:
                st.warning("Por favor, insira uma chave de ativação.")
                return

            with st.spinner("Validando sua chave..."):
                success, message = process_activation_key(user_uid, key_input, db_firestore_instance)
                if success:
                    st.session_state.is_user_activated = True # Atualiza estado da sessão
                    st.success(message + " Redirecionando...")
                    time.sleep(1.5)
                    st.rerun() # Recarrega para exibir o app
                else:
                    st.error(message)
    st.caption("Não possui uma chave? Entre em contato com o suporte para obter acesso.")


# --- Configuração da Página Streamlit ---
PAGE_ICON_PATH = "images/carinha-agente-max-ia.png"

# Tenta carregar o ícone da página
try:
    if os.path.exists(PAGE_ICON_PATH):
        st.set_page_config(
            page_title="Max IA",
            page_icon=Image.open(PAGE_ICON_PATH),
            layout="wide"
        )
    else:
        st.warning(f"Arquivo do ícone da página não encontrado: {PAGE_ICON_PATH}. Usando fallback.")
        st.set_page_config(page_title="Max IA", layout="wide") # Fallback
except Exception as e:
    st.error(f"Erro ao configurar o page_config: {e}")
    st.set_page_config(page_title="Max IA", layout="wide") # Fallback

# --- Inicialização do Firebase ---
firebase_app = None
firestore_db = None
pb_auth_client = None
error_message_firebase_init = None
firebase_init_success_message_shown = st.session_state.get('firebase_init_success_message_shown', False)

if not firebase_init_success_message_shown:
    try:
        # Configuração Pyrebase4 (para Auth)
        firebase_config = st.secrets["firebase_config"]
        required_pyrebase_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_pyrebase_keys = [key for key in required_pyrebase_keys if key not in firebase_config or not firebase_config[key]]

        if not firebase_config or missing_pyrebase_keys:
            error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
            if missing_pyrebase_keys:
                error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_pyrebase_keys)}"
        else:
            firebase_app = pyrebase.initialize_app(firebase_config)
            pb_auth_client = firebase_app.auth()
            st.session_state['firebase_app_instance'] = firebase_app # Armazena para evitar re-inicializar
            st.session_state['pb_auth_client_instance'] = pb_auth_client
            
            # Configuração Firebase Admin SDK (para Firestore)
            # Tenta carregar o JSON diretamente dos secrets ou do arquivo
            service_account_info = None
            if "gcp_service_account" in st.secrets:
                service_account_info = st.secrets["gcp_service_account"]
            elif os.path.exists("max-ia-firebase-service-account.json"):
                with open("max-ia-firebase-service-account.json") as f:
                    service_account_info = json.load(f)
            else:
                error_message_firebase_init = "ERRO CRÍTICO: Credenciais da conta de serviço GCP/Firebase Admin não encontradas em st.secrets['gcp_service_account'] ou no arquivo 'max-ia-firebase-service-account.json'."

            if service_account_info:
                if not firebase_admin._apps: # Inicializa apenas se não estiver inicializado
                    cred = credentials.Certificate(service_account_info)
                    firebase_admin.initialize_app(cred)
                firestore_db = firestore.client()
                st.session_state['firestore_db_instance'] = firestore_db
                st.sidebar.success("✅ Firebase SDKs (Pyrebase4 e Admin) inicializados!")
                st.session_state['firebase_init_success_message_shown'] = True # Evita exibir a mensagem novamente
            else:
                st.error(error_message_firebase_init) # Exibe o erro de credenciais da conta de serviço
                
    except KeyError:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
    except AttributeError as ae:
        error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {ae}. Verifique seus segredos."
    except Exception as e:
        error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4 ou Firebase Admin: {e}"

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop() # Interrompe a execução do script se o Firebase não inicializar

# Usar instâncias de sessão caso já existam (para evitar re-inicializações)
if 'firebase_app_instance' in st.session_state:
    firebase_app = st.session_state.firebase_app_instance
if 'pb_auth_client_instance' in st.session_state:
    pb_auth_client = st.session_state.pb_auth_client_instance
if 'firestore_db_instance' in st.session_state:
    firestore_db = st.session_state.firestore_db_instance

# --- Lógica de Autenticação e Estado da Sessão ---
def check_authentication_status(pb_auth_client_instance, db_firestore_instance):
    user_is_authenticated = False
    error_message_session_check = None
    user_uid = None
    user_email = None

    if 'user_session_pyrebase' in st.session_state and st.session_state.user_session_pyrebase:
        try:
            # Valida o token (checa expiracão)
            user_session_info = st.session_state.user_session_pyrebase
            pyrebase_auth_token = user_session_info['idToken']
            
            # Use Pyrebase para validar o token diretamente
            pb_auth_client_instance.get_account_info(pyrebase_auth_token)
            
            user_is_authenticated = True
            user_uid = user_session_info['localId']
            user_email = user_session_info['email']

            # Verifica o status de ativação do usuário
            # Se não estiver definido na sessão ou não for True, verifica no Firestore
            if 'is_user_activated' not in st.session_state or not st.session_state.is_user_activated:
                st.session_state.is_user_activated = check_user_activation_status(user_uid, db_firestore_instance)
            
            # Atualiza o last_login no Firestore
            user_ref = db_firestore_instance.collection(USER_COLLECTION).document(user_uid)
            user_ref.set({"email": user_email, "last_login": datetime.datetime.now()}, merge=True)

        except Exception as e_session:
            st.session_state.user_session_pyrebase = None # Clear invalid session
            st.session_state.pop('is_user_activated', None) # Clear activation status

            # Tenta parsear o erro para uma mensagem mais amigável
            api_error_message = ""
            try:
                error_data = json.loads(str(e_session).replace("'", "\""))
                api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            except:
                pass # Não é um JSON, use a string bruta

            if "TOKEN_EXPIRED" in api_error_message:
                error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
            elif "INVALID_ID_TOKEN" in api_error_message:
                error_message_session_check = "Sessão inválida. Por favor, faça login novamente."
            elif api_error_message:
                error_message_session_check = f"Erro ao verificar sessão ({api_error_message}). Faça login."
            else:
                error_message_session_check = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session)}"
            
            if error_message_session_check:
                if 'auth_error_shown' not in st.session_state:
                    st.error(error_message_session_check)
                    st.session_state.auth_error_shown = True # Flag para exibir apenas uma vez
                time.sleep(1) # Pequeno delay antes de tentar rerun
                st.rerun() # Force rerun to show login or error message

    return user_is_authenticated, st.session_state.get('is_user_activated', False), user_uid, user_email, error_message_session_check

user_is_authenticated, user_is_activated, user_uid, user_email, auth_error_message = check_authentication_status(pb_auth_client, firestore_db)

# --- LLM e Google Generative AI Initialization ---
llm_model_instance = None
llm_init_exception = None
sidebar_llm_success_shown = st.session_state.get('llm_init_success_sidebar_shown_main_app', False)

if user_is_authenticated and not sidebar_llm_success_shown:
    try:
        # Pega a API Key do Google Gemini dos secrets do Streamlit
        google_api_key = st.secrets["GOOGLE_API_KEY"]
        if not google_api_key:
            llm_init_exception = "🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada ou vazia nos Segredos do Streamlit."
            if "GOOGLE_API_KEY" in os.environ and os.environ["GOOGLE_API_KEY"]:
                google_api_key = os.environ["GOOGLE_API_KEY"]
                st.warning("Usando GOOGLE_API_KEY das variáveis de ambiente. Considere adicioná-la aos segredos do Streamlit.")
            else:
                st.error(llm_init_exception)
                # Não para o app aqui, apenas relata o erro. Deixa o usuário ver a mensagem.
        
        if google_api_key:
            llm_model_instance = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=google_api_key,
                temperature=0.7 # Ajuste a temperatura conforme a criatividade desejada
            )
            st.sidebar.success("✅ Max IA (Gemini) inicializado!")
            st.session_state['llm_init_success_sidebar_shown_main_app'] = True
            
    except Exception as e:
        llm_init_exception = f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}"
        st.sidebar.error(llm_init_exception)

# --- Interface do Usuário Condicional e Lógica Principal do App ---
if user_is_authenticated:
    if user_is_activated: # Usuário autenticado E ATIVADO
    
        db = firestore_db # Obtém a instância do Firestore
        
        # Funções para manipulação de marketing (mantidas como no código original)
        # Adaptadas para usar 'llm_model_instance' e 'firestore_db'
        
        def _marketing_display_output_options(generated_content, key_prefix, file_name_base):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            col_dl, col_copy = st.columns([1, 10])
            with col_dl:
                try:
                    st.download_button(label="📥 Baixar Conteúdo Gerado",
                                    data=generated_content.encode('utf-8'),
                                    file_name=f"{file_name_base}.txt",
                                    mime="text/plain",
                                    key=f"download_{key_prefix}_content")
                except Exception as e:
                    st.error(f"Erro ao tentar renderizar o botão de download: {e}")
            with col_copy:
                st.text_input("Copiar Conteúdo (Ctrl+C)", value=generated_content, key=f"copy_{key_prefix}_content", label_visibility="collapsed")

        def _marketing_get_objective_details(prefix_key, type_of_creation):
            details = {}
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{prefix_key}_objective")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{prefix_key}_target_audience")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{prefix_key}_product_service")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{prefix_key}_key_message")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{prefix_key}_usp")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{prefix_key}_style_tone")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{prefix_key}_extra_info")
            return details

        def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms, llm):
            # st.error("DEBUG: EXECUTANDO A VERSÃO CORRIGIDA DE _marketing_handle_criar_post v2") # DEBUG
            if not selected_platforms:
                st.warning("Por favor, selecione pelo menos uma plataforma.")
                st.session_state.pop(f'generated_post_content_new', None)
                return
            if not details_dict.get("objective") or not details_dict["objective"].strip():
                st.warning("Por favor, descreva o objetivo do post.")
                st.session_state.pop(f'generated_post_content_new', None)
                return

            with st.spinner("🤖 Max IA está criando seu post... Aguarde!"):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil. Sua tarefa é criar um post otimizado e engajador para as seguintes plataformas e objetivos.",
                    "Considere as informações de suporte se fornecidas. Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes.",
                    "Seja conciso e direto ao ponto, adaptando a linguagem para cada plataforma se necessário, mas mantendo a mensagem central.",
                    "Se multiplas plataformas forem selecionadas, gere uma versão base e sugira pequenas adaptações para cada uma se fizer sentido, ou indique que o post pode ser usado de forma similar.",
                    f"**Plataformas:** {', '.join(selected_platforms)}",
                    f"**Objetivo:** {details_dict.get('objective', '')}",
                    f"**Público-Alvo:** {details_dict.get('target_audience', '')}",
                    f"**Produto/Serviço:** {details_dict.get('product_service', '')}",
                    f"**Mensagem Chave:** {details_dict.get('key_message', '')}",
                    f"**Proposta Única de Valor (USP):** {details_dict.get('usp', '')}",
                    f"**Tom/Estilo:** {details_dict.get('style_tone', '')}",
                    f"**Informações Adicionais/CTA:** {details_dict.get('extra_info', '')}"
                ]

                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a IA está vazio. Por favor, preencha os campos necessários.")
                    st.session_state.pop(f'generated_post_content_new', None)
                    return

                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_post_content_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_post_content_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para o post: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_post_content_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR POST: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para o post: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_post_content_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR POST: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms, llm):
            if not selected_platforms:
                st.warning("Por favor, selecione pelo menos uma plataforma para a campanha.")
                st.session_state.pop(f'generated_campaign_content_new', None)
                return
            if not details_dict.get("objective") or not details_dict["objective"].strip():
                st.warning("Por favor, descreva o objetivo principal da campanha.")
                st.session_state.pop(f'generated_campaign_content_new', None)
                return
            if not campaign_specifics.get("name") or not campaign_specifics["name"].strip():
                st.warning("Por favor, dê um nome para a campanha.")
                st.session_state.pop(f'generated_campaign_content_new', None)
                return

            with st.spinner("🧠 Max IA está elaborando seu plano de campanha..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um estrategista de marketing digital experiente, focado em PMEs no Brasil. Desenvolva um plano de campanha de marketing conciso e acionável com base nas informações fornecidas. O plano deve incluir: 1. Conceito da Campanha (Tema Central). 2. Sugestões de Conteúdo Chave para cada plataforma selecionada. 3. Um cronograma geral sugerido (Ex: Semana 1 - Teaser, Semana 2 - Lançamento, etc.). 4. Métricas chave para acompanhar o sucesso. Considere as informações de suporte, se fornecidas.",
                    f"**Nome da Campanha:** {campaign_specifics.get('name', '')}",
                    f"**Plataformas:** {', '.join(selected_platforms)}",
                    f"**Objetivo da Campanha:** {details_dict.get('objective', '')}",
                    f"**Público-Alvo da Campanha:** {details_dict.get('target_audience', '')}",
                    f"**Produto/Serviço Principal da Campanha:** {details_dict.get('product_service', '')}",
                    f"**Mensagem Chave da Campanha:** {details_dict.get('key_message', '')}",
                    f"**USP do Produto/Serviço na Campanha:** {details_dict.get('usp', '')}",
                    f"**Tom/Estilo da Campanha:** {details_dict.get('style_tone', '')}",
                    f"**Duração Estimada:** {campaign_specifics.get('duration', 'Não especificada')}",
                    f"**Orçamento Aproximado (se informado):** {campaign_specifics.get('budget', 'Não informado')}",
                    f"**KPIs mais importantes:** {campaign_specifics.get('kpis', 'Não especificados')}",
                    f"**Informações Adicionais/CTA da Campanha:** {details_dict.get('extra_info', '')}"
                ]

                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a campanha está vazio.")
                    st.session_state.pop(f'generated_campaign_content_new', None)
                    return

                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_campaign_content_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_campaign_content_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a campanha: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_campaign_content_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR CAMPANHA: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a campanha: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_campaign_content_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR CAMPANHA: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details.get("purpose") or not lp_details["purpose"].strip():
                st.warning("Por favor, preencha o principal objetivo da landing page.")
                st.session_state.pop(f'generated_lp_content_new', None)
                return
            if not lp_details.get("main_offer") or not lp_details["main_offer"].strip():
                st.warning("Por favor, descreva a oferta principal da landing page.")
                st.session_state.pop(f'generated_lp_content_new', None)
                return
            if not lp_details.get("cta") or not lp_details["cta"].strip():
                st.warning("Por favor, defina a Chamada para Ação (CTA) principal da landing page.")
                st.session_state.pop(f'generated_lp_content_new', None)
                return

            with st.spinner("🎨 Max IA está desenhando a estrutura da sua landing page..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages de alta conversão, com foco em PMEs no Brasil. Baseado nos detalhes fornecidos, crie uma estrutura detalhada e sugestões de texto (copy) para cada seção de uma landing page. Inclua seções como: Cabeçalho (Headline, Sub-headline), Problema/Dor, Apresentação da Solução/Produto, Benefícios Chave, Prova Social (Depoimentos), Oferta Irresistível, Chamada para Ação (CTA) clara e forte, Garantia (se aplicável), FAQ. Considere as informações de suporte, se fornecidas.",
                    f"**Objetivo da Landing Page:** {lp_details.get('purpose', '')}",
                    f"**Público-Alvo (Persona):** {lp_details.get('target_audience', 'Não especificado')}",
                    f"**Oferta Principal:** {lp_details.get('main_offer', '')}",
                    f"**Principais Benefícios/Transformações da Oferta:** {lp_details.get('key_benefits', 'Não especificados')}",
                    f"**Chamada para Ação (CTA) Principal:** {lp_details.get('cta', '')}",
                    f"**Preferências Visuais/Referências (se houver):** {lp_details.get('visual_prefs', 'Nenhuma')}"
                ]
                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a landing page está vazio.")
                    st.session_state.pop(f'generated_lp_content_new', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_lp_content_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_lp_content_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a landing page: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_lp_content_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR LANDING PAGE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a landing page: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_lp_content_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR LANDING PAGE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details.get("business_type") or not site_details["business_type"].strip():
                st.warning("Por favor, informe o tipo do seu negócio/empresa para o site.")
                st.session_state.pop(f'generated_site_content_new', None)
                return
            if not site_details.get("main_purpose") or not site_details["main_purpose"].strip():
                st.warning("Por favor, descreva o principal objetivo do seu site.")
                st.session_state.pop(f'generated_site_content_new', None)
                return
            with st.spinner("🛠️ Max IA está arquitetando a estrutura do seu site..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um arquiteto de informação e web designer experiente, focado em criar sites eficazes para PMEs no Brasil. Desenvolva uma proposta de estrutura de site (mapa do site com principais páginas e seções dentro de cada página) e sugestões de conteúdo chave para cada seção. Considere as informações de suporte, se fornecidas.",
                    f"**Tipo de Negócio/Empresa:** {site_details.get('business_type', '')}",
                    f"**Principal Objetivo do Site:** {site_details.get('main_purpose', '')}",
                    f"**Público-Alvo Principal:** {site_details.get('target_audience', 'Não especificado')}",
                    f"**Páginas Essenciais Desejadas:** {site_details.get('essential_pages', 'Não especificadas')}",
                    f"**Principais Produtos/Serviços/Diferenciais a serem destacados:** {site_details.get('key_features', 'Não especificados')}",
                    f"**Personalidade da Marca:** {site_details.get('brand_personality', 'Não especificada')}",
                    f"**Preferências Visuais/Referências (se houver):** {site_details.get('visual_references', 'Nenhuma')}"
                ]
                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a estrutura do site está vazio.")
                    st.session_state.pop(f'generated_site_content_new', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_site_content_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_site_content_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a estrutura do site: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_site_content_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR SITE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a estrutura do site: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_site_content_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR SITE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details.get("product_campaign") or not client_details["product_campaign"].strip():
                st.warning("Por favor, descreva o produto/serviço ou campanha para o qual deseja encontrar o cliente ideal.")
                st.session_state.pop(f'generated_client_analysis_new', None)
                return
            with st.spinner("🕵️ Max IA está investigando seu público-alvo..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado para PMEs no Brasil. Sua tarefa é realizar uma análise completa do público-alvo com base nas informações fornecidas e gerar um relatório detalhado com os seguintes itens: 1. Persona Detalhada (Nome fictício, Idade, Profissão, Dores, Necessidades, Sonhos, Onde busca informação). 2. Sugestões de Canais de Marketing mais eficazes para alcançar essa persona. 3. Sugestões de Mensagens Chave e Ângulos de Comunicação que ressoem com essa persona. 4. Se 'Deep Research' estiver ativado, inclua insights adicionais sobre comportamento online, tendências e micro-segmentos. Considere as informações de suporte, se fornecidas.",
                    f"**Produto/Serviço ou Campanha para Análise:** {client_details.get('product_campaign', '')}",
                    f"**Localização Geográfica (Cidade(s), Região):** {client_details.get('location', 'Não especificada')}",
                    f"**Verba Aproximada para Ação/Campanha (se aplicável):** {client_details.get('budget', 'Não informada')}",
                    f"**Faixa Etária e Gênero Predominante (se souber):** {client_details.get('age_gender', 'Não especificados')}",
                    f"**Principais Interesses, Hobbies, Dores, Necessidades do Público Desejado:** {client_details.get('interests', 'Não especificados')}",
                    f"**Canais de Marketing que já utiliza ou considera:** {client_details.get('current_channels', 'Não especificados')}",
                    f"**Nível de Pesquisa:** {'Deep Research Ativado (análise mais aprofundada)' if client_details.get('deep_research', False) else 'Pesquisa Padrão'}"
                ]
                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a análise de cliente está vazio.")
                    st.session_state.pop(f'generated_client_analysis_new', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_client_analysis_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_client_analysis_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de cliente: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_client_analysis_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de cliente: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_client_analysis_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details.get("your_business") or not competitor_details["your_business"].strip():
                st.warning("Por favor, descreva seu próprio negócio/produto para comparação com a concorrência.")
                st.session_state.pop(f'generated_competitor_analysis_new', None)
                return
            if not competitor_details.get("competitors_list") or not competitor_details["competitors_list"].strip():
                st.warning("Por favor, liste seus principais concorrentes para análise.")
                st.session_state.pop(f'generated_competitor_analysis_new', None)
                return
            if not competitor_details.get("aspects_to_analyze"):
                st.warning("Por favor, selecione pelo menos um aspecto da concorrência para analisar.")
                st.session_state.pop(f'generated_competitor_analysis_new', None)
                return
            with st.spinner("🔬 Max IA está analisando a concorrência..."):
                aspects_str = ", ".join(competitor_details.get('aspects_to_analyze', []))
                prompt_parts = [
                    "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em análise de mercado para PMEs no Brasil. Com base nas informações do negócio do usuário e da lista de concorrentes, elabore um relatório breve e útil. Para cada concorrente listado (ou os principais, se a lista for longa), analise os 'Aspectos para Análise' selecionados. Destaque os pontos fortes e fracos de cada um em relação a esses aspectos e, ao final, sugira 2-3 oportunidades ou diferenciais que o negócio do usuário pode explorar. Considere as informações de suporte, se fornecidas.",
                    f"**Negócio do Usuário (para comparação):** {competitor_details.get('your_business', '')}",
                    f"**Concorrentes (nomes, sites, redes sociais, se possível):** {competitor_details.get('competitors_list', '')}",
                    f"**Aspectos para Análise:** {aspects_str if aspects_str else 'Não especificados'}"
                ]
                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(filter(None, prompt_parts))
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a análise de concorrência está vazio.")
                    st.session_state.pop(f'generated_competitor_analysis_new', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_competitor_analysis_new'] = ai_response.content
                    else:
                        st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_competitor_analysis_new'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de concorrência: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_competitor_analysis_new', None)
                    print(f"ValueError DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de concorrência: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_competitor_analysis_new', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_detalhar_campanha(uploaded_files_info, plano_campanha_gerado, llm):
            st.session_state.pop(f'generated_campaign_details_content', None) # Limpa o conteúdo detalhado anterior
            if not plano_campanha_gerado or not plano_campanha_gerado.strip():
                st.error("Não há um plano de campanha para detalhar. Por favor, gere um plano primeiro.")
                return
            with st.spinner("✍️ Max IA está detalhando o conteúdo da sua campanha... Isso pode levar um momento!"):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista sênior em marketing digital e criação de conteúdo para PMEs no Brasil.",
                    "A seguir está um plano de campanha que foi gerado anteriormente. Sua tarefa é EXPANDIR e DETALHAR cada peça de conteúdo sugerida neste plano.",
                    "Para cada plataforma e tipo de conteúdo mencionado no plano, forneça:",
                    "1. Textos/Scripts Completos: Gere o texto completo para posts, e-mails, legendas de vídeo, etc. Use placeholders como [Nome do Cliente] ou [Detalhe Específico do Produto] onde apropriado.",
                    "2. Sugestões de Roteiro para Vídeos: Para conteúdos em vídeo (TikTok, Kwai, YouTube), forneça um roteiro breve com cenas, falas principais e sugestões visuais.",
                    "3. Ideias para Visuais/Imagens: Descreva o tipo de imagem ou visual que acompanharia bem cada peça de texto (ex: 'imagem vibrante de equipe colaborando', 'gráfico mostrando aumento de X%', 'foto de produto em uso com cliente feliz'). Não gere a imagem, apenas descreva a ideia.",
                    "4. Conselhos de Otimização: Para cada peça, adicione 1-2 conselhos curtos para otimizar o engajamento ou conversão naquela plataforma específica (ex: 'melhor horário para postar no Instagram para este público', 'usar CTA X no e-mail').",
                    "Seja criativo, prático e focado em resultados para PMEs. Organize a resposta de forma clara, separando por plataforma e tipo de conteúdo do plano original.",
                    "\n--- PLANO DE CAMPANHA ORIGINAL PARA DETALHAR ---\n",
                    plano_campanha_gerado
                ]
                if uploaded_files_info: 
                    prompt_parts.append(f"\n--- INFORMAÇÕES DE ARQUIVOS DE SUPORTE ADICIONAIS (considere se aplicável ao detalhamento) ---\n{', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(filter(None, prompt_parts)) 
                if not final_prompt or not final_prompt.strip(): 
                    st.error("🚧 Max IA detectou que o prompt para detalhar a campanha está vazio.")
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_campaign_details_content'] = ai_response.content
                    else:
                        st.warning("Resposta da IA (detalhamento) não continha o atributo 'content' esperado. Usando a resposta como string.")
                        st.session_state[f'generated_campaign_details_content'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao detalhar a campanha: {ve}")
                    st.error(f"Detalhes do prompt (detalhamento - primeiros 500): {final_prompt[:500]}...")
                    print(f"ValueError DETALHADO em llm.invoke para DETALHAR CAMPANHA: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema com o modelo de IA ao detalhar a campanha: {e_invoke}")
                    st.error(f"Detalhes do prompt (detalhamento - primeiros 500): {final_prompt[:500]}...")
                    print(f"Erro GERAL DETALHADO em llm.invoke para DETALHAR CAMPANHA: {e_invoke}\nPrompt: {final_prompt}")
                    return

        class MaxAgente:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None:
                    st.error("❌ Erro crítico: MaxAgente tentou ser inicializado sem um modelo LLM.")
                    st.stop()
                self.llm = llm_passed_model
                if f'memoria_max_bussola_plano' not in st.session_state:
                    st.session_state[f'memoria_max_bussola_plano'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_plano", return_messages=True)
                if f'memoria_max_bussola_ideias' not in st.session_state:
                    st.session_state[f'memoria_max_bussola_ideias'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_ideias", return_messages=True)
                if f'memoria_max_financeiro_precos' not in st.session_state:
                    st.session_state[f'memoria_max_financeiro_precos'] = ConversationBufferMemory(memory_key=f"historico_chat_financeiro_precos", return_messages=True)

                self.memoria_max_bussola_plano = st.session_state[f'memoria_max_bussola_plano']
                self.memoria_max_bussola_ideias = st.session_state[f'memoria_max_bussola_ideias']
                self.memoria_max_financeiro_precos = st.session_state[f'memoria_max_financeiro_precos']
                self.memoria_plano_negocios = self.memoria_max_bussola_plano
                self.memoria_calculo_precos = self.memoria_max_financeiro_precos
                self.memoria_gerador_ideias = self.memoria_max_bussola_ideias

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
                actual_memory_key = memoria_especifica.memory_key
                prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(system_message_content),
                    MessagesPlaceholder(variable_name=actual_memory_key),
                    HumanMessagePromptTemplate.from_template("{input_usuario}") # Adicionei o placeholder para o input do usuário
                ])
                return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

            def exibir_max_marketing_total(self):
                st.header("🚀 MaxMarketing Total")
                st.caption("Seu copiloto Max IA para criar estratégias, posts, campanhas e mais!")
                st.markdown("---")
                marketing_files_info_for_prompt_local = []
                
                with st.sidebar:
                    st.subheader("📎 Suporte para MaxMarketing")
                    uploaded_marketing_files = st.file_uploader(
                        "Upload de arquivos de CONTEXTO para Marketing (opcional):",
                        accept_multiple_files=True,
                        type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'],
                        key=f"marketing_files_uploader_max"
                    )
                    if uploaded_marketing_files:
                        temp_marketing_files_info = []
                        for up_file in uploaded_marketing_files:
                            temp_marketing_files_info.append({"name": up_file.name, "type": up_file.type, "size": up_file.size})
                        if temp_marketing_files_info:
                            marketing_files_info_for_prompt_local = temp_marketing_files_info
                            st.success(f"{len(uploaded_marketing_files)} arquivo(s) de contexto carregado(s) para MaxMarketing!")
                        with st.expander("Ver arquivos de contexto de Marketing"):
                            for finfo in marketing_files_info_for_prompt_local:
                                st.write(f"- {finfo['name']} ({finfo['type']})")

                main_action_key = f"main_marketing_action_choice_max"
                opcoes_menu_marketing_dict = {
                    "Selecione uma opção...": 0,
                    "1 - Criar post para redes sociais ou e-mail": 1,
                    "2 - Criar campanha de marketing completa": 2,
                    "3 - Criar estrutura e conteúdo para landing page": 3,
                    "4 - Criar estrutura e conteúdo para site com IA": 4,
                    "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)": 5,
                    "6 - Conhecer a concorrência (Análise Competitiva)": 6
                }
                opcoes_radio_marketing = list(opcoes_menu_marketing_dict.keys())
                radio_index_key = f"{APP_KEY_SUFFIX}_marketing_radio_index" # Chave específica
                if radio_index_key not in st.session_state:
                    st.session_state[radio_index_key] = 0
                def update_marketing_radio_index_on_change():
                    # Evita erro se a chave não existir durante mudança de estado
                    if main_action_key in st.session_state:
                        st.session_state[radio_index_key] = opcoes_radio_marketing.index(st.session_state[main_action_key])
                main_action = st.radio(
                    "Olá! Sou o Max, seu agente de Marketing. O que vamos criar hoje?",
                    opcoes_radio_marketing,
                    index=st.session_state[radio_index_key],
                    key=main_action_key,
                    on_change=update_marketing_radio_index_on_change
                )
                st.markdown("---")
                platforms_config_options = {
                    "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp",
                    "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
                    "E-mail Marketing (lista própria)": "email_own",
                    "E-mail Marketing (Campanha Google Ads)": "email_google"
                }

                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com Max IA")
                    SESSION_KEY_POST_CONTENT = f'{APP_KEY_SUFFIX}_generated_post_content_new'
                    FORM_KEY_POST = f"{APP_KEY_SUFFIX}_post_creator_form_max"

                    if SESSION_KEY_POST_CONTENT in st.session_state and st.session_state[SESSION_KEY_POST_CONTENT]:
                        _marketing_display_output_options(st.session_state[SESSION_KEY_POST_CONTENT], f"post_output_max", "post_max_ia")
                        if st.button("✨ Criar Novo Post", key=f"{APP_KEY_SUFFIX}_clear_post_content_button"):
                            st.session_state.pop(SESSION_KEY_POST_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_POST):
                            st.subheader(" Plataformas Desejadas:")
                            key_select_all_post = f"{APP_KEY_SUFFIX}_post_select_all_max"
                            select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Abaixo", key=key_select_all_post)
                            cols_post = st.columns(2); selected_platforms_post_ui = []
                            for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                                col_index = i % 2
                                platform_key = f"{APP_KEY_SUFFIX}_post_platform_max_{platform_suffix}" # Chave específica
                                with cols_post[col_index]:
                                    if st.checkbox(platform_name, key=platform_key, value=select_all_post_checked):
                                        selected_platforms_post_ui.append(platform_name)
                                    if "E-mail Marketing" in platform_name and st.session_state.get(platform_key):
                                        st.caption("💡 Para e-mail marketing, considere segmentar sua lista e personalizar a saudação.")
                            post_details = _marketing_get_objective_details(f"{APP_KEY_SUFFIX}_post_max", "post")
                            submit_button_pressed_post = st.form_submit_button("💡 Gerar Post com Max IA!")

                            if submit_button_pressed_post:
                                _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, selected_platforms_post_ui, self.llm)
                                st.rerun()
                        
                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas de Marketing com Max IA")
                    SESSION_KEY_CAMPAIGN_PLAN = f'{APP_KEY_SUFFIX}_generated_campaign_content_new'
                    SESSION_KEY_CAMPAIGN_DETAILS = f'{APP_KEY_SUFFIX}_generated_campaign_details_content'
                    FORM_KEY_CAMPAIGN_PLAN = f"{APP_KEY_SUFFIX}_campaign_creator_form_max"

                    if SESSION_KEY_CAMPAIGN_DETAILS in st.session_state and st.session_state[SESSION_KEY_CAMPAIGN_DETAILS]:
                        st.subheader("📝 Conteúdo Detalhado da Campanha:")
                        st.markdown(st.session_state[SESSION_KEY_CAMPAIGN_DETAILS])
                        try:
                            st.download_button(label="📥 Baixar Conteúdo Detalhado da Campanha",
                                            data=st.session_state[SESSION_KEY_CAMPAIGN_DETAILS].encode('utf-8'),
                                            file_name=f"campanha_detalhada_max_ia.txt",
                                            mime="text/plain",
                                            key=f"{APP_KEY_SUFFIX}_download_campaign_details_btn_") # Chave mais única
                        except Exception as e_dl_details:
                            if "can't be used in an `st.form()`" in str(e_dl_details):
                                st.warning("O botão de download para o conteúdo detalhado está temporariamente indisponível aqui.")
                            else:
                                st.error(f"Erro ao renderizar botão de download dos detalhes da campanha: {e_dl_details}")
                        
                        if st.button("💡 Gerar Novo Plano de Campanha", key=f"{APP_KEY_SUFFIX}_clear_all_campaign_button"):
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_PLAN, None)
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_DETAILS, None)
                            st.rerun()
                        
                    elif SESSION_KEY_CAMPAIGN_PLAN in st.session_state and st.session_state[SESSION_KEY_CAMPAIGN_PLAN]:
                        st.subheader("📋 Plano da Campanha Gerado:")
                        _marketing_display_output_options(st.session_state[SESSION_KEY_CAMPAIGN_PLAN], f"campaign_plan_output_max", "plano_campanha_max_ia")
                        st.markdown("---")
                        if st.button("✍️ Detalhar Conteúdo da Campanha com Max IA", key=f"{APP_KEY_SUFFIX}_detail_campaign_button"):
                            plano_gerado = st.session_state[SESSION_KEY_CAMPAIGN_PLAN]
                            _marketing_handle_detalhar_campanha(marketing_files_info_for_prompt_local, plano_gerado, self.llm)
                            st.rerun() 
                        if st.button("💡 Gerar Novo Plano de Campanha", key=f"{APP_KEY_SUFFIX}_clear_campaign_plan_button"):
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_PLAN, None)
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_DETAILS, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_CAMPAIGN_PLAN):
                            campaign_name = st.text_input("Nome da Campanha:", key=f"{APP_KEY_SUFFIX}_campaign_name_max")
                            st.subheader(" Plataformas Desejadas:")
                            key_select_all_camp = f"{APP_KEY_SUFFIX}_campaign_select_all_max"
                            select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Abaixo", key=key_select_all_camp)
                            cols_camp = st.columns(2); selected_platforms_camp_ui = []
                            for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                                col_index = i % 2
                                platform_key = f"{APP_KEY_SUFFIX}_campaign_platform_max_{platform_suffix}" # Chave específica
                                with cols_camp[col_index]:
                                    if st.checkbox(platform_name, key=platform_key, value=select_all_camp_checked):
                                        selected_platforms_camp_ui.append(platform_name)
                            campaign_details_obj = _marketing_get_objective_details(f"{APP_KEY_SUFFIX}_campaign_max", "campanha")
                            campaign_duration = st.text_input("Duração Estimada:", key=f"{APP_KEY_SUFFIX}_campaign_duration_max")
                            campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key=f"{APP_KEY_SUFFIX}_campaign_budget_max")
                            specific_kpis = st.text_area("KPIs mais importantes:", key=f"{APP_KEY_SUFFIX}_campaign_kpis_max")
                            submit_button_pressed_camp_plan = st.form_submit_button("🚀 Gerar Plano de Campanha com Max IA!")

                            if submit_button_pressed_camp_plan:
                                campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration, "budget": campaign_budget_approx, "kpis": specific_kpis}
                                _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, selected_platforms_camp_ui, self.llm)
                                st.rerun()
                        
                elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                    st.subheader("📄 Gerador de Estrutura para Landing Pages com Max IA")
                    SESSION_KEY_LP_CONTENT = f'{APP_KEY_SUFFIX}_generated_lp_content_new'
                    FORM_KEY_LP = f"{APP_KEY_SUFFIX}_landing_page_form_max"

                    if SESSION_KEY_LP_CONTENT in st.session_state and st.session_state[SESSION_KEY_LP_CONTENT]:
                        st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                        st.markdown(st.session_state[SESSION_KEY_LP_CONTENT])
                        try:
                            st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state[SESSION_KEY_LP_CONTENT].encode('utf-8'), file_name=f"landing_page_sugestoes_max_ia.txt", mime="text/plain", key=f"{APP_KEY_SUFFIX}_download_lp_max_output")
                        except Exception as e_dl_lp:
                            st.error(f"Erro ao renderizar botão de download da LP: {e_dl_lp}")
                        if st.button("✨ Criar Nova Estrutura de LP", key=f"{APP_KEY_SUFFIX}_clear_lp_content_button"):
                            st.session_state.pop(SESSION_KEY_LP_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_LP):
                            lp_purpose = st.text_input("Principal objetivo da landing page:", key=f"{APP_KEY_SUFFIX}_lp_purpose_max")
                            lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key=f"{APP_KEY_SUFFIX}_lp_audience_max")
                            lp_main_offer = st.text_area("Oferta principal e irresistível:", key=f"{APP_KEY_SUFFIX}_lp_offer_max")
                            lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key=f"{APP_KEY_SUFFIX}_lp_benefits_max")
                            lp_cta = st.text_input("Chamada para ação (CTA) principal:", key=f"{APP_KEY_SUFFIX}_lp_cta_max")
                            lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key=f"{APP_KEY_SUFFIX}_lp_visual_max")
                            submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP com Max IA!")
                            if submitted_lp:
                                lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details_dict, self.llm)
                                st.rerun()
                        
                elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                    st.subheader("🏗️ Arquiteto de Sites com Max IA")
                    SESSION_KEY_SITE_CONTENT = f'{APP_KEY_SUFFIX}_generated_site_content_new'
                    FORM_KEY_SITE = f"{APP_KEY_SUFFIX}_site_creator_form_max"
                    if SESSION_KEY_SITE_CONTENT in st.session_state and st.session_state[SESSION_KEY_SITE_CONTENT]:
                        st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                        st.markdown(st.session_state[SESSION_KEY_SITE_CONTENT])
                        try:
                            st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state[SESSION_KEY_SITE_CONTENT].encode('utf-8'), file_name=f"site_sugestoes_max_ia.txt", mime="text/plain",key=f"{APP_KEY_SUFFIX}_download_site_max_output")
                        except Exception as e_dl_site:
                            st.error(f"Erro ao renderizar botão de download do Site: {e_dl_site}")
                        if st.button("✨ Criar Nova Estrutura de Site", key=f"{APP_KEY_SUFFIX}_clear_site_content_button"):
                            st.session_state.pop(SESSION_KEY_SITE_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_SITE):
                            site_business_type = st.text_input("Tipo do seu negócio/empresa:", key=f"{APP_KEY_SUFFIX}_site_biz_type_max")
                            site_main_purpose = st.text_area("Principal objetivo do seu site:", key=f"{APP_KEY_SUFFIX}_site_purpose_max")
                            site_target_audience = st.text_input("Público principal do site:", key=f"{APP_KEY_SUFFIX}_site_audience_max")
                            site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key=f"{APP_KEY_SUFFIX}_site_pages_max")
                            site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key=f"{APP_KEY_SUFFIX}_site_features_max")
                            site_brand_personality = st.text_input("Personalidade da sua marca:", key=f"{APP_KEY_SUFFIX}_site_brand_max")
                            site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key=f"{APP_KEY_SUFFIX}_site_visual_ref_max")
                            submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site com Max IA!")
                            if submitted_site:
                                site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                                _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details_dict, self.llm)
                                st.rerun()

                elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                    st.subheader("🎯 Decodificador de Clientes com Max IA")
                    SESSION_KEY_CLIENT_ANALYSIS = f'{APP_KEY_SUFFIX}_generated_client_analysis_new'
                    FORM_KEY_CLIENT = f"{APP_KEY_SUFFIX}_find_client_form_max"
                    if SESSION_KEY_CLIENT_ANALYSIS in st.session_state and st.session_state[SESSION_KEY_CLIENT_ANALYSIS]:
                        st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                        st.markdown(st.session_state[SESSION_KEY_CLIENT_ANALYSIS])
                        try:
                            st.download_button(label="📥 Baixar Análise de Público",data=st.session_state[SESSION_KEY_CLIENT_ANALYSIS].encode('utf-8'), file_name=f"analise_publico_alvo_max_ia.txt", mime="text/plain",key=f"{APP_KEY_SUFFIX}_download_client_analysis_max_output")
                        except Exception as e_dl_client:
                            st.error(f"Erro ao renderizar botão de download da Análise de Cliente: {e_dl_client}")
                        if st.button("✨ Nova Análise de Cliente", key=f"{APP_KEY_SUFFIX}_clear_client_analysis_button"):
                            st.session_state.pop(SESSION_KEY_CLIENT_ANALYSIS, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_CLIENT):
                            fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key=f"{APP_KEY_SUFFIX}_fc_campaign_max")
                            fc_location = st.text_input("Cidade(s) ou região de alcance:", key=f"{APP_KEY_SUFFIX}_fc_location_max")
                            fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key=f"{APP_KEY_SUFFIX}_fc_budget_max")
                            fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key=f"{APP_KEY_SUFFIX}_fc_age_gender_max")
                            fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key=f"{APP_KEY_SUFFIX}_fc_interests_max")
                            fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key=f"{APP_KEY_SUFFIX}_fc_channels_max")
                            fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key=f"{APP_KEY_SUFFIX}_fc_deep_max")
                            submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente com Max IA!")
                            if submitted_fc:
                                client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details_dict, self.llm)
                                st.rerun()

                elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                    st.subheader("🧐 Radar da Concorrência com Max IA")
                    SESSION_KEY_COMPETITOR_ANALYSIS = f'{APP_KEY_SUFFIX}_generated_competitor_analysis_new'
                    FORM_KEY_COMPETITOR = f"{APP_KEY_SUFFIX}_competitor_analysis_form_max"
                    if SESSION_KEY_COMPETITOR_ANALYSIS in st.session_state and st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS]:
                        st.subheader("📊 Análise da Concorrência e Insights:")
                        st.markdown(st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS])
                        try:
                            st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS].encode('utf-8'), file_name=f"analise_concorrencia_max_ia.txt",mime="text/plain",key=f"{APP_KEY_SUFFIX}_download_competitor_analysis_max_output")
                        except Exception as e_dl_comp:
                            st.error(f"Erro ao renderizar botão de download da Análise de Concorrência: {e_dl_comp}")
                        if st.button("✨ Nova Análise de Concorrência", key=f"{APP_KEY_SUFFIX}_clear_competitor_analysis_button"):
                            st.session_state.pop(SESSION_KEY_COMPETITOR_ANALYSIS, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_COMPETITOR):
                            ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key=f"{APP_KEY_SUFFIX}_ca_your_biz_max")
                            ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key=f"{APP_KEY_SUFFIX}_ca_competitors_max")
                            ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"{APP_KEY_SUFFIX}_ca_aspects_max")
                            submitted_ca = st.form_submit_button("📡 Analisar Concorrentes com Max IA!")
                            if submitted_ca:
                                competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details_dict, self.llm)
                                st.rerun()
                        
                elif main_action == "Selecione uma opção...":
                    st.info("👋 Bem-vindo ao MaxMarketing Total! Escolha uma das opções acima para começar.")
                    LOGO_PATH_MARKETING_WELCOME = "images/max-ia-logo.png"
                    try:
                        st.image(LOGO_PATH_MARKETING_WELCOME, width=200)
                    except Exception:
                        st.image("https://i.imgur.com/7IIYxq1.png", caption="Max IA (Fallback)", width=200)
                    
            def exibir_max_financeiro(self):
                st.header("💰 MaxFinanceiro")
                st.caption("Seu agente Max IA para inteligência financeira, cálculo de preços e mais.")
                st.subheader("💲 Cálculo de Preços Inteligente com Max IA")
                st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
                current_section_key_finance = f"{APP_KEY_SUFFIX}_max_financeiro_precos"
                memoria_financeiro = self.memoria_max_financeiro_precos
                uploaded_image_calc = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key=f"{APP_KEY_SUFFIX}_preco_img_max_financeiro")
                system_message_financeiro = "Você é Max IA, um especialista em finanças e precificação para PMEs. Ajude o usuário a calcular o preço de seus produtos ou serviços, considerando custos, margens, mercado e valor percebido. Seja claro e didático."
                chain_financeiro = self._criar_cadeia_conversacional(system_message_financeiro, memoria_financeiro)
                def conversar_max_financeiro_precos(input_usuario, descricao_imagem_contexto=None):
                    prompt_final_usuario = input_usuario
                    if descricao_imagem_contexto:
                        prompt_final_usuario = f"{descricao_imagem_contexto}\n\n{input_usuario}"
                    resposta_ai = chain_financeiro.invoke({"input_usuario": prompt_final_usuario})
                    return resposta_ai['text']
                _handle_chat_with_image(current_section_key_finance, "Descreva o produto/serviço, custos, etc.", conversar_max_financeiro_precos, uploaded_image_calc)
                _sidebar_clear_button_max("Preços (MaxFinanceiro)", memoria_financeiro, current_section_key_finance)

            def exibir_max_administrativo(self):
                st.header("⚙️ MaxAdministrativo")
                st.subheader("Olá! Sou o Max, seu agente para otimizar a gestão administrativa do seu negócio.")
                st.markdown("Escolha uma ferramenta abaixo para começarmos:")

                opcoes_administrativo = {
                    "Selecione uma ferramenta...": "admin_selecione",
                    "1) MaxFluxo de Caixa": "admin_fluxo_caixa",
                    "2) MaxPlanejamento Financeiro": "admin_planej_financeiro",
                    "3) MaxContábil": "admin_contabil",
                    "4) Controle de Estoque": "admin_controle_estoque",
                    "5) Gestão de Pessoas": "admin_gestao_pessoas",
                    "6) Planejamento Estratégico (Definição de Objetivos)": "admin_plan_estr_objetivos",
                    "7) Análise SWOT": "admin_analise_swot",
                    "8) Definição de Estratégias": "admin_def_estrategias",
                    "9) Análise de Risco": "admin_analise_risco",
                    "10) Planejamento de Riscos": "admin_plan_riscos"
                }

                escolha_admin_label = st.selectbox(
                    "Ferramentas Administrativas:",
                    options=list(opcoes_administrativo.keys()),
                    key=f"{APP_KEY_SUFFIX}_selectbox_admin_tool"
                )

                acao_selecionada = opcoes_administrativo.get(escolha_admin_label)
                st.markdown("---")

                if acao_selecionada == "admin_fluxo_caixa":
                    self._admin_render_fluxo_caixa()
                elif acao_selecionada == "admin_planej_financeiro":
                    self._admin_render_planejamento_financeiro()
                elif acao_selecionada == "admin_contabil":
                    self._admin_render_contabil()
                elif acao_selecionada == "admin_controle_estoque":
                    self._admin_render_controle_estoque()
                elif acao_selecionada == "admin_gestao_pessoas":
                    self._admin_render_gestao_pessoas()
                elif acao_selecionada == "admin_plan_estr_objetivos":
                    self._admin_render_planejamento_estrategico_objetivos()
                elif acao_selecionada == "admin_analise_swot":
                    self._admin_render_analise_swot()
                elif acao_selecionada == "admin_def_estrategias":
                    self._admin_render_definicao_estrategias()
                elif acao_selecionada == "admin_analise_risco":
                    self._admin_render_analise_risco()
                elif acao_selecionada == "admin_plan_riscos":
                    self._admin_render_planejamento_riscos()
                elif acao_selecionada == "admin_selecione":
                    st.info("Por favor, selecione uma ferramenta administrativa no menu acima para começar.")
                
            def _admin_render_fluxo_caixa(self):
                st.subheader("1) MaxFluxo de Caixa")
                st.write("Ferramenta para ajudar você a lançar e analisar as entradas e saídas, projetar saldos e tomar decisões financeiras mais assertivas para sua empresa.")
                st.info("Em desenvolvimento.")

            def _admin_render_planejamento_financeiro(self):
                st.subheader("2) MaxPlanejamento Financeiro")
                sub_opcao_plan_fin = st.radio(
                    "Escolha uma opção do Planejamento Financeiro:",
                    ("A) Elaborar orçamento", "B) Elaborar plano de negócios detalhado para definir metas e estratégias financeiras"),
                    key=f"{APP_KEY_SUFFIX}_radio_plan_fin"
                )
                if sub_opcao_plan_fin == "A) Elaborar orçamento":
                    st.write("Auxílio para criar um orçamento empresarial completo, definindo tetos de gastos, prevendo receitas e acompanhando o desempenho financeiro.")
                    st.info("Em desenvolvimento.")
                elif sub_opcao_plan_fin == "B) Elaborar plano de negócios detalhado para definir metas e estratégias financeiras":
                    st.write("Desenvolva um plano de negócios com foco nos aspectos financeiros, detalhando projeções de receita, custos, investimentos necessários e análise de viabilidade para suas metas e estratégias.")
                    st.info("Em desenvolvimento.")

            def _admin_render_contabil(self):
                st.subheader("3) MaxContábil")
                st.write("Oferecer agentes de IA para manter a contabilidade em dia e utilizar ferramentas de gestão financeira para controlar receitas, despesas e custos.")
                st.info("Em desenvolvimento.")

            def _admin_render_controle_estoque(self):
                st.subheader("4) Controle de Estoque")
                tab_planilhas, tab_previsao = st.tabs(["A) Planilhas, Gráficos e Relatórios", "B) Previsão de Demanda"])
                with tab_planilhas:
                    st.write("Gerar planilhas, gráficos e relatórios (o usuário escolhe) para controlar o estoque, monitorar níveis de produtos, identificar produtos com baixa rotatividade e evitar perdas por obsolescência.")
                    st.info("Em desenvolvimento.")
                with tab_previsao:
                    st.write("Estimar a demanda futura para evitar falta de produtos em estoque ou excesso de produtos.")
                    st.info("Em desenvolvimento.")

            def _admin_render_gestao_pessoas(self):
                st.subheader("5) Gestão de Pessoas")
                tab_rh, tab_comunicacao, tab_motivacao = st.tabs(["A) Recursos Humanos", "B) Comunicação Interna", "C) Motivação e Produtividade"])
                with tab_rh:
                    st.write("Planejar a contratação, desenvolvimento e retenção de talentos, definindo políticas de RH e treinamentos.")
                    st.info("Em desenvolvimento.")
                with tab_comunicacao:
                    st.write("Estabelecer canais de comunicação claros e eficientes para manter a equipe informada e motivada.")
                    st.info("Em desenvolvimento.")
                with tab_motivacao:
                    st.write("Criar um ambiente de trabalho positivo e incentivar a produtividade da equipe.")
                    st.info("Em desenvolvimento.")

            def _admin_render_planejamento_estrategico_objetivos(self):
                st.subheader("6) Planejamento Estratégico (Definição de Objetivos)")
                st.write("Estabelecer metas claras e mensuráveis para a empresa, definindo como a empresa se diferenciará da concorrência.")
                st.info("Em desenvolvimento.")

            def _admin_render_analise_swot(self):
                st.subheader("7) Análise SWOT")
                st.write("Avaliar as forças e fraquezas internas da empresa, bem como as oportunidades e ameaças externas.")
                st.info("Em desenvolvimento.")

            def _admin_render_definicao_estrategias(self):
                st.subheader("8) Definição de Estratégias")
                st.write("Elaborar um plano de ação para alcançar as metas definidas, incluindo estratégias de marketing, vendas e operações.")
                st.info("Em desenvolvimento.")

            def _admin_render_analise_risco(self):
                st.subheader("9) Análise de Risco")
                st.write("Avaliar os possíveis riscos que a empresa pode enfrentar, como riscos de mercado, financeiros ou operacionais.")
                st.info("Em desenvolvimento.")

            def _admin_render_planejamento_riscos(self):
                st.subheader("10) Planejamento de Riscos")
                st.write("Elaborar um plano de ação para mitigar ou evitar os riscos identificados.")
                st.info("Em desenvolvimento.")

            def exibir_max_pesquisa_mercado(self):
                st.header("📈 MaxPesquisa de Mercado")
                st.subheader("Olá! Sou o Max, seu agente para desvendar o mercado e seus clientes.")
                st.info("Esta área está em desenvolvimento. Em breve, você poderá realizar análises de público-alvo aprofundadas, entender a concorrência e descobrir novas tendências de mercado, tudo com a ajuda da IA.")
                st.caption("Por enquanto, algumas funcionalidades de análise de público e concorrência estão disponíveis no MaxMarketing Total.")

            def exibir_max_bussola(self):
                st.header("🧭 MaxBússola Estratégica")
                st.caption("Seu guia Max IA para planejamento estratégico, novas ideias e direção de negócios.")
                tab1_plano, tab2_ideias = st.tabs(["🗺️ Plano de Negócios com Max IA", "💡 Gerador de Ideias com Max IA"])
                with tab1_plano:
                    st.subheader("📝 Elaborando seu Plano de Negócios com Max IA")
                    st.caption("Converse com o Max para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
                    current_section_key_plano = f"{APP_KEY_SUFFIX}_max_bussola_plano"
                    memoria_plano = self.memoria_max_bussola_plano
                    system_message_plano = "Você é Max IA, um consultor de negócios experiente. Ajude o usuário a criar um rascunho de plano de negócios, seção por seção. Faça perguntas, ofereça sugestões e ajude a estruturar as ideias."
                    chain_plano = self._criar_cadeia_conversacional(system_message_plano, memoria_plano)
                    def conversar_max_bussola_plano(input_usuario):
                        resposta_ai = chain_plano.invoke({"input_usuario": input_usuario})
                        return resposta_ai['text']
                    exibir_chat_e_obter_input(current_section_key_plano, "Sua resposta ou próxima seção do plano...", conversar_max_bussola_plano)
                    _sidebar_clear_button_max("Plano (MaxBússola)", memoria_plano, current_section_key_plano)
                with tab2_ideias:
                    st.subheader("💡 Gerador de Ideias para seu Negócio com Max IA")
                    st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
                    current_section_key_ideias = f"{APP_KEY_SUFFIX}_max_bussola_ideias"
                    memoria_ideias = self.memoria_max_bussola_ideias
                    system_message_ideias = "Você é Max IA, um especialista em inovação e brainstorming. Ajude o usuário a gerar novas ideias para seus negócios, resolver problemas ou explorar novas oportunidades. Use o contexto de arquivos, se fornecido."
                    chain_ideias = self._criar_cadeia_conversacional(system_message_ideias, memoria_ideias)
                    def conversar_max_bussola_ideias(input_usuario, contexto_arquivos=None):
                        prompt_final_usuario = input_usuario
                        if contexto_arquivos:
                            prompt_final_usuario = f"Contexto dos arquivos:\n\n{contexto_arquivos}\n\nCom base nisso e na minha solicitação: {input_usuario}"
                        resposta_ai = chain_ideias.invoke({"input_usuario": prompt_final_usuario})
                        return resposta_ai['text']
                    uploaded_files_ideias_ui = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"{APP_KEY_SUFFIX}_ideias_file_uploader_max_bussola")
                    _handle_chat_with_files(current_section_key_ideias, "Descreva seu desafio ou peça ideias:", conversar_max_bussola_ideias, uploaded_files_ideias_ui)
                    _sidebar_clear_button_max("Ideias (MaxBússola)", memoria_ideias, current_section_key_ideias)

            def exibir_max_trainer(self):
                st.header("🎓 MaxTrainer IA")
                #st.image("images/max-ia-logo.png", width=150)
                st.subheader("Olá! Sou o Max, seu treinador pessoal de IA para negócios.")
                st.info("Esta área está em desenvolvimento. Em breve, o MaxTrainer trará tutoriais interativos, dicas personalizadas sobre como usar o Max IA ao máximo, e insights para você se tornar um mestre em aplicar IA no seu dia a dia empresarial.")
                st.write("Imagine aprender sobre:")
                st.markdown("""
                - Como criar os melhores prompts para cada agente Max IA.
                - Interpretando os resultados da IA e aplicando-os na prática.
                - Novas funcionalidades e como elas podem te ajudar.
                - Estudos de caso e exemplos de sucesso.
                """)
                st.balloons()

        # --- Funções Utilitárias Globais ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}" # Usar chave específica para a área
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                    memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
                    memoria_agente_instancia.chat_memory.messages.clear()
                    memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
            # Limpar estados relacionados a uploads de arquivos/imagens
            if area_chave == f"{APP_KEY_SUFFIX}_max_financeiro_precos":
                st.session_state.pop(f'{APP_KEY_SUFFIX}_last_uploaded_image_info_{area_chave}', None)
                st.session_state.pop(f'{APP_KEY_SUFFIX}_processed_image_id_{area_chave}', None)
                st.session_state.pop(f'{APP_KEY_SUFFIX}_user_input_processed_{area_chave}', None)
            elif area_chave == f"{APP_KEY_SUFFIX}_max_bussola_ideias":
                st.session_state.pop(f'{APP_KEY_SUFFIX}_uploaded_file_info_for_prompt_{area_chave}', None)
                st.session_state.pop(f'{APP_KEY_SUFFIX}_processed_file_id_{area_chave}', None)
                st.session_state.pop(f'{APP_KEY_SUFFIX}_user_input_processed_{area_chave}', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}"
            if chat_display_key not in st.session_state:
                st.session_state[chat_display_key] = []
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]):
                    st.markdown(msg_info["content"])
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"{APP_KEY_SUFFIX}_chat_input_{area_chave}")
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                
                # Flag para indicar que o input do usuário foi processado no contexto de arquivos/imagens
                if area_chave in [f"{APP_KEY_SUFFIX}_max_financeiro_precos", f"{APP_KEY_SUFFIX}_max_bussola_ideias"]:
                    st.session_state[f'{APP_KEY_SUFFIX}_user_input_processed_{area_chave}'] = True

                with st.spinner("Max IA está processando... 🤔"):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                    st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()

        def _sidebar_clear_button_max(label, memoria, section_key_prefix):
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"{APP_KEY_SUFFIX}_btn_reset_{section_key_prefix}_clear_max"):
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key_prefix == f"{APP_KEY_SUFFIX}_max_financeiro_precos":
                    msg_inicial = "Ok, vamos recomeçar o cálculo de preços com MaxFinanceiro! Descreva seu produto ou serviço."
                elif section_key_prefix == f"{APP_KEY_SUFFIX}_max_bussola_ideias":
                    msg_inicial = "Ok, vamos recomeçar a geração de ideias com MaxBússola! Qual o seu ponto de partida?"
                elif section_key_prefix == f"{APP_KEY_SUFFIX}_max_bussola_plano":
                    msg_inicial = "Olá! Sou Max IA com a MaxBússola. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia."
                inicializar_ou_resetar_chat(section_key_prefix, msg_inicial, memoria)
                st.experimental_rerun() # Use experimental_rerun para garantir recarregar o chat

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
            descricao_imagem_para_ia = None
            processed_image_id_key = f'{APP_KEY_SUFFIX}_processed_image_id_{area_chave}'
            last_uploaded_info_key = f'{APP_KEY_SUFFIX}_last_uploaded_image_info_{area_chave}'
            user_input_processed_key = f'{APP_KEY_SUFFIX}_user_input_processed_{area_chave}'

            if uploaded_image_obj is not None:
                if st.session_state.get(processed_image_id_key) != uploaded_image_obj.file_id:
                    try:
                        img_pil = Image.open(uploaded_image_obj); 
                        st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'. Considere o conteúdo desta imagem para a resposta."
                        st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                        st.session_state[processed_image_id_key] = uploaded_image_obj.file_id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo com Max IA.")
                        # Reseta o flag de processamento de input do usuário para forçar o contexto da imagem
                        st.session_state[user_input_processed_key] = False 
                    except Exception as e_img_proc:
                        st.error(f"Erro ao processar imagem: {e_img_proc}")
                        st.session_state[last_uploaded_info_key] = None; st.session_state[processed_image_id_key] = None
                else:
                    descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
            
            kwargs_chat = {}
            # Se a imagem foi carregada e o input do usuário ainda não foi processado com ela
            if descricao_imagem_para_ia and not st.session_state.get(user_input_processed_key, False):
                kwargs_chat['descricao_imagem_contexto'] = descricao_imagem_para_ia

            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
            
            # Após o chat, se o input do usuário foi processado e havia uma imagem, limpar o estado da imagem
            if st.session_state.get(user_input_processed_key, False):
                st.session_state.pop(last_uploaded_info_key, None)
                # Não remover processed_image_id_key para evitar re-upload ou re-exibição na reruns subsequentes
                st.session_state[user_input_processed_key] = False
            
        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
            contexto_para_ia_local = None
            processed_file_id_key = f'{APP_KEY_SUFFIX}_processed_file_id_{area_chave}'
            uploaded_info_key = f'{APP_KEY_SUFFIX}_uploaded_file_info_for_prompt_{area_chave}'
            user_input_processed_key = f'{APP_KEY_SUFFIX}_user_input_processed_{area_chave}'

            if uploaded_files_objs:
                current_file_signature = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id}" for f in uploaded_files_objs]))
                if st.session_state.get(processed_file_id_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                    text_contents, image_info = [], []
                    for f_item in uploaded_files_objs:
                        try:
                            if f_item.type == "text/plain": # Apenas arquivos de texto
                                text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...")
                            elif f_item.type.startswith("image/"): # Imagens
                                st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100)
                                image_info.append(f"Imagem '{f_item.name}'. Considere o conteúdo desta imagem para a resposta.")
                        except Exception as e_file_proc:
                            st.error(f"Erro ao processar '{f_item.name}': {e_file_proc}")
                    
                    full_ctx_str = ""
                    if text_contents:
                        full_ctx_str += "\n\n--- CONTEÚDO DOS ARQUIVOS DE TEXTO ---\n" + "\n\n".join(text_contents)
                    if image_info:
                        full_ctx_str += "\n\n--- INFORMAÇÕES DAS IMAGENS FORNECIDAS ---\n" + "\n".join(image_info)
                    
                    if full_ctx_str.strip():
                        st.session_state[uploaded_info_key] = full_ctx_str.strip()
                        contexto_para_ia_local = st.session_state[uploaded_info_key]
                        st.info("Arquivo(s) de contexto pronto(s) para Max IA.")
                        st.session_state[user_input_processed_key] = False # Reseta o flag
                    else:
                        st.session_state[uploaded_info_key] = None
                    st.session_state[processed_file_id_key] = current_file_signature
                else:
                    contexto_para_ia_local = st.session_state.get(uploaded_info_key)
            
            kwargs_chat = {}
            if contexto_para_ia_local and not st.session_state.get(user_input_processed_key, False):
                kwargs_chat['contexto_arquivos'] = contexto_para_ia_local

            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
            
            if st.session_state.get(user_input_processed_key, False):
                st.session_state.pop(uploaded_info_key, None)
                st.session_state[user_input_processed_key] = False

        # --- Instanciação do Agente ---
        # A instância do agente só é criada se o LLM estiver inicializado com sucesso
        if 'max_agente_instancia' not in st.session_state or \
            not isinstance(st.session_state.max_agente_instancia, MaxAgente) or \
            (hasattr(st.session_state.max_agente_instancia, 'llm') and st.session_state.max_agente_instancia.llm != llm_model_instance):
            
            if llm_model_instance:
                st.session_state.max_agente_instancia = MaxAgente(llm_passed_model=llm_model_instance)
            else:
                st.session_state.max_agente_instancia = None # Nao inicializa se o LLM falhou
            
        agente = None # Variável local para o agente
        if st.session_state.get('max_agente_instancia') and llm_model_instance:
            agente = st.session_state.max_agente_instancia

        # Bloco da interface principal (sidebar e conteúdo)
        if agente: # Só exibe se o LLM e o Agente foram inicializados
            st.sidebar.write(f"Logado como: {user_email}")
            if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_main_app_logout_max"):
                # Limpa todos os estados de sessão relacionados ao usuário e ao app
                st.session_state.user_session_pyrebase = None
                st.session_state.is_user_activated = False # Garante que a próxima sessão requeira ativação
                
                # Lista de chaves a serem limpas no logout
                keys_to_clear_on_logout = [k for k in st.session_state if APP_KEY_SUFFIX in k or k.startswith('memoria_') or k.startswith('chat_display_') or k.startswith('generated_') or k.startswith('post_') or k.startswith('campaign_') or k.startswith('processed_')]
                keys_to_clear_on_logout.extend([
                                                'max_agente_instancia', 'area_selecionada_max_ia',
                                                'firebase_init_success_message_shown',
                                                'llm_init_success_sidebar_shown_main_app',
                                                'auth_error_shown',
                                                'show_activation_screen'
                                                ])

                for key_to_clear in keys_to_clear_on_logout:
                    st.session_state.pop(key_to_clear, None)
                st.rerun()

            LOGO_PATH_SIDEBAR_APP = "images/max-ia-logo.png"
            try:
                st.sidebar.image(LOGO_PATH_SIDEBAR_APP, width=150)
            except Exception:
                st.sidebar.image("https://i.imgur.com/7IIYxq1.png", width=150, caption="Max IA (Fallback)")

            st.sidebar.title("Max IA")
            st.sidebar.markdown("Seu Agente IA para Maximizar Resultados!")
            st.sidebar.markdown("---")

            opcoes_menu_max_ia = {
                "👋 Bem-vindo ao Max IA": f"{APP_KEY_SUFFIX}_painel_max_ia",
                "🚀 MaxMarketing Total": f"{APP_KEY_SUFFIX}_max_marketing_total",
                "💰 MaxFinanceiro": f"{APP_KEY_SUFFIX}_max_financeiro",
                "⚙️ MaxAdministrativo": f"{APP_KEY_SUFFIX}_max_administrativo",
                "📈 MaxPesquisa de Mercado": f"{APP_KEY_SUFFIX}_max_pesquisa_mercado",
                "🧭 MaxBússola Estratégica": f"{APP_KEY_SUFFIX}_max_bussola",
                "🎓 MaxTrainer IA": f"{APP_KEY_SUFFIX}_max_trainer_ia"
            }
            radio_key_sidebar_main_max = f'{APP_KEY_SUFFIX}_sidebar_selection_max_ia'

            if 'area_selecionada_max_ia' not in st.session_state or st.session_state.area_selecionada_max_ia not in opcoes_menu_max_ia.values(): # Verifique values
                st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.values())[0]

            radio_index_key_nav_max = f'{APP_KEY_SUFFIX}_sidebar_selection_index'
            if radio_index_key_nav_max not in st.session_state:
                try:
                    current_selected_key = st.session_state.area_selecionada_max_ia
                    st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.values()).index(current_selected_key)
                except ValueError:
                    st.session_state[radio_index_key_nav_max] = 0
                    st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.values())[0]

            def update_main_radio_index_on_change_max_ia():
                # Atualiza a chave, não o rótulo
                selected_label = st.session_state[radio_key_sidebar_main_max]
                st.session_state.area_selecionada_max_ia = opcoes_menu_max_ia[selected_label]
                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(selected_label)

            area_selecionada_label_max_ia = st.sidebar.radio(
                "Max Agentes IA:",
                options=list(opcoes_menu_max_ia.keys()),
                key=radio_key_sidebar_main_max,
                index=st.session_state[radio_index_key_nav_max],
                on_change=update_main_radio_index_on_change_max_ia
            )

            # Só reruns se a seleção realmente mudou para evitar loops desnecessários
            new_selection_value = opcoes_menu_max_ia.get(area_selecionada_label_max_ia)
            if new_selection_value != st.session_state.area_selecionada_max_ia:
                st.session_state.area_selecionada_max_ia = new_selection_value
                # Limpa todos os conteúdos gerados de marketing se sair da seção MaxMarketing Total
                if new_selection_value != f"{APP_KEY_SUFFIX}_max_marketing_total":
                    keys_to_clear_on_nav = [
                        f'{APP_KEY_SUFFIX}_generated_post_content_new',
                        f'{APP_KEY_SUFFIX}_generated_campaign_content_new',
                        f'{APP_KEY_SUFFIX}_generated_campaign_details_content',
                        f'{APP_KEY_SUFFIX}_generated_lp_content_new',
                        f'{APP_KEY_SUFFIX}_generated_site_content_new',
                        f'{APP_KEY_SUFFIX}_generated_client_analysis_new',
                        f'{APP_KEY_SUFFIX}_generated_competitor_analysis_new'
                    ]
                    for key_to_clear in keys_to_clear_on_nav:
                        st.session_state.pop(key_to_clear, None)
                st.rerun()

            current_section_key_max_ia = st.session_state.area_selecionada_max_ia

            if current_section_key_max_ia == f"{APP_KEY_SUFFIX}_painel_max_ia":
                st.markdown("<div style='text-align: center;'><h1>👋 Bem-vindo ao Max IA!</h1></div>", unsafe_allow_html=True)
                logo_base64 = convert_image_to_base64('images/max-ia-logo.png')
                if logo_base64:
                    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{logo_base64}' width='200'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align: center;'><p>(Logo não pôde ser carregado)</p></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center;'><p style='font-size: 1.2em;'>Olá! Eu sou o <strong>Max</strong>, seu conjunto de agentes de IA dedicados a impulsionar o sucesso da sua Pequena ou Média Empresa.</p></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para selecionar um agente especializado e começar a transformar seu negócio hoje mesmo.</p></div>", unsafe_allow_html=True)
                st.markdown("---")
                st.subheader("Conheça seus Agentes Max IA:")
                cols_cards = st.columns(3)
                card_data_display = [ # Usar rótulos para exibição aqui
                    ("🚀 MaxMarketing Total", "Crie posts, campanhas, sites e muito mais!", f"{APP_KEY_SUFFIX}_max_marketing_total"),
                    ("💰 MaxFinanceiro", "Inteligência para preços, custos e finanças.", f"{APP_KEY_SUFFIX}_max_financeiro"),
                    ("⚙️ MaxAdministrativo", "Otimize sua gestão e rotinas.", f"{APP_KEY_SUFFIX}_max_administrativo"),
                    ("📈 MaxPesquisa de Mercado", "Desvende seu público e a concorrência (Em breve!).", f"{APP_KEY_SUFFIX}_max_pesquisa_mercado"),
                    ("🧭 MaxBússola Estratégica", "Planejamento, ideias e direção para o futuro.", f"{APP_KEY_SUFFIX}_max_bussola"),
                    ("🎓 MaxTrainer IA", "Aprenda a usar todo o poder da IA (Em breve!).", f"{APP_KEY_SUFFIX}_max_trainer_ia")
                ]
                for i, (title_display, caption, actual_key_id) in enumerate(card_data_display):
                    with cols_cards[i % 3]:
                        # Ações dos botões dos cards
                        card_button_key = f"{APP_KEY_SUFFIX}_btn_goto_card_{actual_key_id}"
                        if st.button(title_display, key=card_button_key, use_container_width=True, help=f"Ir para {title_display}"):
                            st.session_state.area_selecionada_max_ia = actual_key_id
                            # Atualizar o índice do radio button na sidebar (necessário para que a sidebar reflita a mudança)
                            matching_label = [label for label, key in opcoes_menu_max_ia.items() if key == actual_key_id]
                            if matching_label:
                                st.session_state[radio_key_sidebar_main_max] = matching_label[0]
                                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(matching_label[0])
                            st.rerun()

                        st.caption(caption)
                        st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
                st.balloons()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_marketing_total":
                agente.exibir_max_marketing_total()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_financeiro":
                agente.exibir_max_financeiro()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_administrativo":
                agente.exibir_max_administrativo()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_pesquisa_mercado":
                agente.exibir_max_pesquisa_mercado()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_bussola":
                agente.exibir_max_bussola()
            elif current_section_key_max_ia == f"{APP_KEY_SUFFIX}_max_trainer_ia":
                agente.exibir_max_trainer()
            else:
                st.error("🚨 O Max IA não pôde ser totalmente inicializado.")
                st.info("Isso pode ter ocorrido devido a um problema com a chave da API do Google ou ao contatar os serviços do Google Generative AI, ou o agente não pôde ser instanciado.")
                if llm_init_exception:
                    st.exception(llm_init_exception)

        else: # Se o agente não foi inicializado (provavelmente LLM falhou)
            st.error("🚨 O Max IA não pôde ser totalmente iniciado. Por favor, corrija os erros acima.")
            if llm_init_exception:
                st.exception(llm_init_exception)

    else: # Usuário autenticado, MAS NÃO ATIVADO - Mostra a tela de ativação
        # Limpa qualquer erro de autenticação anterior para não sobrepor
        st.session_state.pop('auth_error_shown', None)
        show_activation_page(user_uid, firestore_db)

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: # Usuário NÃO autenticado
    # Limpa qualquer erro de autenticação anterior
    st.session_state.pop('auth_error_shown', None)
    
    st.title("🔑 Bem-vindo ao Max IA")
    logo_base64_login = convert_image_to_base64('images/max-ia-logo.png')
    if logo_base64_login:
        st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{logo_base64_login}' width='150'></div>", unsafe_allow_html=True)
    
    st.info("Faça login ou registre-se na barra lateral para usar o Max IA.")
    
    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key = f"{APP_KEY_SUFFIX}_app_auth_choice_pyrebase_max"
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key)
    
    if auth_action_choice == "Login":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_app_login_form_pyrebase_max"):
            login_email = st.text_input("Email", key=f"{APP_KEY_SUFFIX}_login_email")
            login_password = st.text_input("Senha", type="password", key=f"{APP_KEY_SUFFIX}_login_password")
            login_button_clicked = st.form_submit_button("Login")
            
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        
                        # Garante que o status de ativação será re-verificado
                        st.session_state.pop('is_user_activated', None) 
                        st.session_state.pop('firebase_init_success_message_shown', None) # Force re-display of init success
                        st.session_state.pop('llm_init_success_sidebar_shown_main_app', None) # Force re-init llm message
                        st.session_state.pop('show_activation_screen', None) # Ensure activation screen is checked
                        st.rerun()
                    except Exception as e_login:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try:
                            error_details_str = e_login.args[0] if len(e_login.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: error_message_login = f"Erro no login: {api_error_message}"
                        except: pass # Se não for JSON, use a mensagem padrão
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
                
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_app_register_form_pyrebase_max"):
            reg_email = st.text_input("Email para registro", key=f"{APP_KEY_SUFFIX}_reg_email")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key=f"{APP_KEY_SUFFIX}_reg_password")
            submit_register = st.form_submit_button("Registrar")
            
            if submit_register:
                if reg_email and reg_password and pb_auth_client and firestore_db:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        user_uid = user['localId']
                        
                        # Criar/atualizar o documento do usuário no Firestore com status de ativação inicial
                        user_ref = firestore_db.collection(USER_COLLECTION).document(user_uid)
                        user_ref.set({
                            "email": reg_email,
                            "is_activated": False, # Novo usuário não está ativado por padrão
                            "registration_date": datetime.datetime.now()
                        }, merge=True)

                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        
                        try:
                            # Tentar enviar email de verificação de conta (opcional, Firebase lida com isso)
                            pb_auth_client.send_email_verification(user['idToken'])
                            st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_local:
                            st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_local}")
                            
                    except Exception as e_register:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e_register.args[0] if len(e_register.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message:
                                error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except: # Se não for JSON, use a mensagem padrão com a exceção completa
                            error_message_register = f"Erro no registro: {str(e_register)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                elif not firestore_db: st.sidebar.error("Firestore não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")

st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini Pro")
