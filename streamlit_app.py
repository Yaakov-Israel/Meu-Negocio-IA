import streamlit as st
import os
import json
import pyrebase # Para Firebase Auth
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import base64
import time
import datetime

# Importação para Firestore
from google.cloud import firestore # Garanta que 'google-cloud-firestore' está no requirements.txt

# --- Função Auxiliar para Imagem em Base64 ---
def convert_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Arquivo de imagem não encontrado: {image_path}")
        return None
    except Exception as e:
        st.error(f"Erro ao converter imagem {image_path}: {e}")
        return None

# --- Funções do Sistema de Ativação ---
# Estas funções esperam um cliente Firestore funcional (db)
def check_user_activation_status(uid, db):
    """Verifica no Firestore se o usuário já está ativado."""
    try:
        user_activation_ref = db.collection("user_activations").document(uid).get()
        if user_activation_ref.exists:
            return user_activation_ref.to_dict().get("activated", False)
    except Exception as e:
        st.error(f"Erro ao verificar status de ativação (check_user_activation_status): {e}")
    return False

def validate_and_claim_key(key_input, uid, db):
    """Valida a chave e, se válida e disponível, a reivindica para o usuário."""
    try:
        key_ref = db.collection("activation_keys").document(key_input)
        key_doc = key_ref.get()

        if key_doc.exists:
            key_data = key_doc.to_dict()
            if key_data.get("status") == "available":
                key_ref.update({
                    "status": "claimed",
                    "claimed_by_uid": uid,
                    "claimed_at": datetime.datetime.utcnow().isoformat() + "Z" 
                })
                db.collection("user_activations").document(uid).set({
                    "activated": True,
                    "activation_key_used": key_input,
                    "activated_at": datetime.datetime.utcnow().isoformat() + "Z"
                }, merge=True)
                return True, "Chave ativada com sucesso!"
            elif key_data.get("claimed_by_uid") == uid:
                user_activation_ref = db.collection("user_activations").document(uid)
                if not user_activation_ref.get().exists or not user_activation_ref.get().to_dict().get("activated"):
                    user_activation_ref.set({"activated": True, "activation_key_used": key_input}, merge=True)
                return True, "Chave já utilizada por você. Acesso liberado!"
            else:
                return False, "Chave de ativação inválida, já utilizada por outro usuário ou expirada."
        else:
            return False, "Chave de ativação não encontrada."
    except Exception as e:
        st.error(f"Erro ao validar a chave de ativação (validate_and_claim_key): {e}")
        return False, f"Erro ao processar a chave: {e}"

def display_activation_form(uid, db):
    st.image("images/max-ia-logo.png", width=150)
    st.title("🔑 Ativação Necessária - Max IA")
    st.write("Bem-vindo ao Max IA! Para continuar, por favor, insira sua chave de ativação.")
    
    with st.form("activation_form", clear_on_submit=False):
        key_input = st.text_input("Chave de Ativação", type="password", placeholder="Insira sua chave aqui")
        submit_activation = st.form_submit_button("Ativar Max IA")

    if submit_activation:
        if not key_input:
            st.warning("Por favor, insira uma chave de ativação.")
        else:
            with st.spinner("Validando sua chave..."):
                success, message = validate_and_claim_key(key_input, uid, db)
            if success:
                st.session_state.is_user_activated = True 
                st.success(message + " Redirecionando...")
                time.sleep(2)  
                st.rerun()
            else:
                st.error(message)
    st.markdown("---")
    st.caption("Não possui uma chave? Entre em contato com o suporte para obter acesso.")

# --- Configuração da Página Streamlit ---
PAGE_ICON_PATH = "images/carinha-agente-max-ia.png"
try:
    page_icon_img = Image.open(PAGE_ICON_PATH)
except FileNotFoundError:
    page_icon_img = "🤖"
    st.warning(f"Arquivo do ícone da página não encontrado: {PAGE_ICON_PATH}. Usando fallback.")

st.set_page_config(
    page_title="Max IA",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=page_icon_img
)

# --- Inicialização do Firebase e Firestore ---
firebase_app = None # Pyrebase app instance
pb_auth_client = None # Pyrebase auth client
firestore_db_client = None # google-cloud-firestore client instance
error_message_firebase_init = "" # Acumulador de mensagens de erro
firebase_initialized_successfully = False
firestore_initialized_successfully = False
auth_exception_object = None

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init += "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos.\n"
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]

        if missing_keys:
            error_message_firebase_init += f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}\n"
        else:
            # Inicializa Pyrebase para Autenticação
            try:
                if 'firebase_app_instance' not in st.session_state:
                    st.session_state.firebase_app_instance = pyrebase.initialize_app(plain_firebase_config_dict)
                firebase_app = st.session_state.firebase_app_instance
                pb_auth_client = firebase_app.auth()
                firebase_initialized_successfully = True
                if 'firebase_init_success_message_shown' not in st.session_state and not st.session_state.get('user_session_pyrebase'):
                    st.sidebar.success("✅ Firebase Auth (Pyrebase4) inicializado!")
                    st.session_state.firebase_init_success_message_shown = True
            except Exception as e_pyrebase:
                error_message_firebase_init += f"ERRO AO INICIALIZAR PYREBASE AUTH: {e_pyrebase}\n"
                firebase_initialized_successfully = False
            
            # Inicializa Cliente Firestore (google-cloud-firestore)
            try:
                project_id = plain_firebase_config_dict.get("projectId")
                if project_id:
                    if 'firestore_client_instance' not in st.session_state:
                         st.session_state.firestore_client_instance = firestore.Client(project=project_id)
                    firestore_db_client = st.session_state.firestore_client_instance
                    
                    if firestore_db_client: # Confirma que a instância não é None
                        firestore_initialized_successfully = True
                        if 'firestore_init_success_message_shown' not in st.session_state and not st.session_state.get('user_session_pyrebase'):
                             st.sidebar.success("✅ Firestore Client (google-cloud) inicializado!")
                             st.session_state.firestore_init_success_message_shown = True
                    else: # Caso firestore.Client() retorne None por algum motivo raro
                        error_message_firebase_init += "ERRO: Falha ao obter instância do cliente Firestore mesmo com projectId.\n"
                        firestore_initialized_successfully = False
                else:
                    error_message_firebase_init += "ERRO: projectId não encontrado em [firebase_config] para inicializar o Firestore.\n"
                    firestore_initialized_successfully = False
            
            except Exception as e_firestore:
                error_message_firebase_init += f"ERRO AO INICIALIZAR CLIENTE FIRESTORE (google-cloud): {e_firestore}\n"
                firestore_initialized_successfully = False

except KeyError: # Erro ao buscar 'firebase_config' nos secrets
    error_message_firebase_init += "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit.\n"
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb: # Erro se st.secrets não for como esperado
    error_message_firebase_init += f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb}\n"
    auth_exception_object = e_attr_fb
except Exception as e_general_fb: # Outros erros gerais na inicialização
    error_message_firebase_init += f"ERRO GERAL na inicialização do Firebase/Firestore: {e_general_fb}\n"
    auth_exception_object = e_general_fb

# Verifica se houve algum erro acumulado ou falha na inicialização de algum dos serviços
if error_message_firebase_init.strip() or not firebase_initialized_successfully or not firestore_initialized_successfully:
    if error_message_firebase_init.strip(): # Mostra erros acumulados se houver
      st.error(error_message_firebase_init)
    if not firebase_initialized_successfully:
        st.error("Falha crítica na inicialização do Firebase Auth. O app não pode continuar.")
    if not firestore_initialized_successfully:
        st.error("Falha crítica na inicialização do Firestore Client. Funcionalidades de ativação podem não funcionar.")
    
    if auth_exception_object: # Mostra o objeto da exceção se capturado
        st.exception(auth_exception_object)
    st.stop()


# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        st.session_state.user_session_pyrebase['localId'] = refreshed_user_info['users'][0].get('localId') 
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None)
    except Exception as e_session:
        error_message_session_check = "Sessão inválida ou expirada."
        
        # CORREÇÃO: Tratamento mais robusto da mensagem de erro da API
        api_error_details_text = ""
        if hasattr(e_session, 'args') and len(e_session.args) > 0:
            raw_error_content = e_session.args[0]
            if isinstance(raw_error_content, str):
                api_error_details_text = raw_error_content
                # Tenta parsear como JSON se for uma string e parecer um erro estruturado do Firebase
                if raw_error_content.strip().startswith("{") and "\"error\"" in raw_error_content.lower():
                    try:
                        # A substituição de aspas simples pode ser arriscada se o JSON for complexo.
                        # Idealmente, a API retornaria JSON válido.
                        error_data = json.loads(raw_error_content) 
                        parsed_message = error_data.get('error', {}).get('message', api_error_details_text)
                        if parsed_message: # Usa a mensagem parseada se disponível
                             api_error_details_text = parsed_message
                    except json.JSONDecodeError:
                        pass # Mantém api_error_details_text como a string original
            elif isinstance(raw_error_content, dict): # Se o erro já for um dict
                api_error_details_text = raw_error_content.get('error', {}).get('message', str(raw_error_content))
            else:
                api_error_details_text = str(raw_error_content) # Fallback
        else:
            api_error_details_text = str(e_session) # Fallback geral

        # Agora use api_error_details_text que é garantido ser uma string
        if "TOKEN_EXPIRED" in api_error_details_text or \
           "INVALID_ID_TOKEN" in api_error_details_text or \
           "ID_TOKEN_EXPIRED" in api_error_details_text: # Adicionado ID_TOKEN_EXPIRED
            error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
        elif api_error_details_text: # Se houver algum detalhe
             error_message_session_check = f"Erro ao verificar sessão ({api_error_details_text}). Faça login."
        # else: mantém a mensagem "Sessão inválida ou expirada."

        st.session_state.user_session_pyrebase = None
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state:
            st.sidebar.warning(error_message_session_check)
            st.session_state.auth_error_shown = True
        
        session_rerun_key = 'running_rerun_after_auth_fail_v3'
        if not st.session_state.get(session_rerun_key, False):
            st.session_state[session_rerun_key] = True
            st.rerun()
        else:
            st.session_state.pop(session_rerun_key, None)

session_rerun_key_check = 'running_rerun_after_auth_fail_v3'
if session_rerun_key_check in st.session_state:
    if user_is_authenticated or not st.session_state.user_session_pyrebase : # Limpa se autenticado ou se não há mais sessão
        st.session_state.pop(session_rerun_key_check, None)


# --- Interface do Usuário Condicional e Lógica Principal do App ---
APP_KEY_SUFFIX = "_v20_final" 

if user_is_authenticated:
    uid = st.session_state.user_session_pyrebase.get('localId')
    
    # ATENÇÃO: Use a instância correta do cliente Firestore
    db_firestore = firestore_db_client 

    # LINHA DE DEBUG (REMOVA APÓS VERIFICAR):
    # st.sidebar.info(f"DEBUG: Tipo de db_firestore: {type(db_firestore)}")

    if not db_firestore: 
        st.error("ERRO CRÍTICO: Cliente Firestore não está disponível (db_firestore é None). Funcionalidades de ativação estão desabilitadas.")
        st.warning("Isso pode ocorrer se o 'projectId' não estiver nos seus segredos do Firebase ou se houver um problema na inicialização do google-cloud-firestore.")
        st.stop() 

    # !! ALERTA IMPORTANTE !!
    # Verifique em TODO o restante do seu código (incluindo a classe MaxAgente e suas funções)
    # se existe alguma chamada como `firebase_app.firestore()` ou `alguma_variavel_pyrebase.firestore()`.
    # TODAS as interações com Firestore devem usar `db_firestore` (que é o cliente google-cloud-firestore).
    # O erro "AttributeError: 'Firebase' object has no attribute 'firestore'" que você viu
    # significa que uma chamada incorreta ainda existe em algum lugar.

    if 'is_user_activated' not in st.session_state:
        st.session_state.is_user_activated = check_user_activation_status(uid, db_firestore)

    if st.session_state.is_user_activated:
        # ----- USUÁRIO AUTENTICADO E ATIVADO - LÓGICA PRINCIPAL DO APP -----
        st.session_state.pop('auth_error_shown', None)
        display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")

        GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
        llm_model_instance = None
        llm_init_exception = None

        if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
            st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada ou vazia nos Segredos do Streamlit.")
            st.stop()
        else:
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                             temperature=0.75,
                                                             google_api_key=GOOGLE_API_KEY,
                                                             convert_system_message_to_human=True)
                if 'llm_init_success_sidebar_shown_main_app' not in st.session_state:
                    st.sidebar.success("✅ Max IA (Gemini) inicializado!")
                    st.session_state.llm_init_success_sidebar_shown_main_app = True
            except Exception as e_llm:
                llm_init_exception = e_llm
                st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm}")
        
        # --- Funções _marketing_handle_... e classe MaxAgente ---
        # (O restante do seu código da classe MaxAgente e funções de marketing aqui)
        # Lembre-se: se MaxAgente ou suas funções precisarem do Firestore, passe `db_firestore`.
        # Funções _marketing_handle_... (já corrigidas)
        def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj{APP_KEY_SUFFIX}")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{APP_KEY_SUFFIX}")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{APP_KEY_SUFFIX}")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{APP_KEY_SUFFIX}")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{APP_KEY_SUFFIX}")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone{APP_KEY_SUFFIX}")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{APP_KEY_SUFFIX}")
            return details

        def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            try:
                st.download_button(
                    label="📥 Baixar Conteúdo Gerado",
                    data=generated_content.encode('utf-8'),
                    file_name=f"{file_name_prefix}_{section_key}{APP_KEY_SUFFIX}.txt",
                    mime="text/plain",
                    key=f"download_{section_key}_{file_name_prefix}{APP_KEY_SUFFIX}" 
                )
            except Exception as e_download: 
                st.error(f"Erro ao tentar renderizar o botão de download: {e_download}")
                print(f"ERRO NO DOWNLOAD BUTTON ({section_key}): {e_download}")

        def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
            if not selected_platforms_list:
                st.warning("Por favor, selecione pelo menos uma plataforma.")
                st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                return
            if not details_dict.get("objective") or not details_dict["objective"].strip():
                st.warning("Por favor, descreva o objetivo do post.")
                st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                return
            with st.spinner("🤖 Max IA está criando seu post... Aguarde!"):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil. Sua tarefa é criar um post otimizado e engajador para as seguintes plataformas e objetivos.",
                    "Considere as informações de suporte se fornecidas. Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes.",
                    "Seja conciso e direto ao ponto, adaptando a linguagem para cada plataforma se necessário, mas mantendo a mensagem central.",
                    "Se multiplas plataformas forem selecionadas, gere uma versão base e sugira pequenas adaptações para cada uma se fizer sentido, ou indique que o post pode ser usado de forma similar.",
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                    f"**Produto/Serviço Principal:** {details_dict.get('product_service', '')}",
                    f"**Público-Alvo:** {details_dict.get('target_audience', '')}",
                    f"**Objetivo do Post:** {details_dict.get('objective', '')}",
                    f"**Mensagem Chave:** {details_dict.get('key_message', '')}",
                    f"**Proposta Única de Valor (USP):** {details_dict.get('usp', '')}",
                    f"**Tom/Estilo:** {details_dict.get('style_tone', '')}",
                    f"**Informações Adicionais/CTA:** {details_dict.get('extra_info', '')}"
                ]
                if uploaded_files_info:
                    prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a IA está vazio. Por favor, preencha os campos necessários.")
                    st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                    else: # Fallback para Langchain mais antigo ou diferentes tipos de resposta
                        st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para o post: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR POST: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para o post: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR POST: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
            if not selected_platforms_list:
                st.warning("Por favor, selecione pelo menos uma plataforma para a campanha.")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                return
            if not details_dict.get("objective") or not details_dict["objective"].strip():
                st.warning("Por favor, descreva o objetivo principal da campanha.")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                return
            if not campaign_specifics.get("name") or not campaign_specifics["name"].strip():
                st.warning("Por favor, dê um nome para a campanha.")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                return
            with st.spinner("🧠 Max IA está elaborando seu plano de campanha..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um estrategista de marketing digital experiente, focado em PMEs no Brasil. Desenvolva um plano de campanha de marketing conciso e acionável com base nas informações fornecidas. O plano deve incluir: 1. Conceito da Campanha (Tema Central). 2. Sugestões de Conteúdo Chave para cada plataforma selecionada. 3. Um cronograma geral sugerido (Ex: Semana 1 - Teaser, Semana 2 - Lançamento, etc.). 4. Métricas chave para acompanhar o sucesso. Considere as informações de suporte, se fornecidas.",
                    f"**Nome da Campanha:** {campaign_specifics.get('name', '')}",
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                    f"**Produto/Serviço Principal da Campanha:** {details_dict.get('product_service', '')}",
                    f"**Público-Alvo da Campanha:** {details_dict.get('target_audience', '')}",
                    f"**Objetivo Principal da Campanha:** {details_dict.get('objective', '')}",
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a campanha está vazio.")
                    st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                        st.session_state.pop(f'generated_campaign_details_content{APP_KEY_SUFFIX}', None) 
                    else:
                        st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'] = str(ai_response)
                        st.session_state.pop(f'generated_campaign_details_content{APP_KEY_SUFFIX}', None)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a campanha: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR CAMPANHA: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a campanha: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR CAMPANHA: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details.get("purpose") or not lp_details["purpose"].strip():
                st.warning("Por favor, preencha o principal objetivo da landing page.")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                return
            if not lp_details.get("main_offer") or not lp_details["main_offer"].strip():
                st.warning("Por favor, descreva a oferta principal da landing page.")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                return
            if not lp_details.get("cta") or not lp_details["cta"].strip():
                st.warning("Por favor, defina a Chamada para Ação (CTA) principal da landing page.")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a landing page está vazio.")
                    st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                    else:
                        st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a landing page: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR LANDING PAGE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a landing page: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR LANDING PAGE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details.get("business_type") or not site_details["business_type"].strip():
                st.warning("Por favor, informe o tipo do seu negócio/empresa para o site.")
                st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                return
            if not site_details.get("main_purpose") or not site_details["main_purpose"].strip():
                st.warning("Por favor, descreva o principal objetivo do seu site.")
                st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a estrutura do site está vazio.")
                    st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                    else:
                        st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a estrutura do site: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para CRIAR SITE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a estrutura do site: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR SITE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details.get("product_campaign") or not client_details["product_campaign"].strip():
                st.warning("Por favor, descreva o produto/serviço ou campanha para o qual deseja encontrar o cliente ideal.")
                st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a análise de cliente está vazio.")
                    st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content
                    else:
                        st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de cliente: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de cliente: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details.get("your_business") or not competitor_details["your_business"].strip():
                st.warning("Por favor, descreva seu próprio negócio/produto para comparação com a concorrência.")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                return
            if not competitor_details.get("competitors_list") or not competitor_details["competitors_list"].strip():
                st.warning("Por favor, liste seus principais concorrentes para análise.")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                return
            if not competitor_details.get("aspects_to_analyze"):
                st.warning("Por favor, selecione pelo menos um aspecto da concorrência para analisar.")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip():
                    st.error("🚧 Max IA detectou que o prompt final para a análise de concorrência está vazio.")
                    st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content
                    else:
                        st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = str(ai_response)
                except ValueError as ve:
                    st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de concorrência: {ve}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                    print(f"ValueError DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {ve}\nPrompt: {final_prompt}")
                    return
                except Exception as e_invoke:
                    st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de concorrência: {e_invoke}")
                    st.error(f"Detalhes do prompt (primeiros 500): {final_prompt[:500]}...")
                    st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                    print(f"Erro GERAL DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {e_invoke}\nPrompt: {final_prompt}")
                    return

        def _marketing_handle_detalhar_campanha(uploaded_files_info, plano_campanha_gerado, llm):
            st.session_state.pop(f'generated_campaign_details_content{APP_KEY_SUFFIX}', None) 
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
                final_prompt = "\n\n".join(prompt_parts)
                if not final_prompt or not final_prompt.strip(): 
                    st.error("🚧 Max IA detectou que o prompt para detalhar a campanha está vazio.")
                    return
                try:
                    ai_response = llm.invoke(final_prompt)
                    if hasattr(ai_response, 'content'):
                        st.session_state[f'generated_campaign_details_content{APP_KEY_SUFFIX}'] = ai_response.content
                    else:
                        st.session_state[f'generated_campaign_details_content{APP_KEY_SUFFIX}'] = str(ai_response)
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
                # Inicialização das memórias
                mem_keys = {
                    "plano": f'memoria_max_bussola_plano{APP_KEY_SUFFIX}',
                    "ideias": f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}',
                    "precos": f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}'
                }
                hist_keys = {
                    "plano": f"historico_chat_bussola_plano{APP_KEY_SUFFIX}",
                    "ideias": f"historico_chat_bussola_ideias{APP_KEY_SUFFIX}",
                    "precos": f"historico_chat_financeiro_precos{APP_KEY_SUFFIX}"
                }

                if mem_keys["plano"] not in st.session_state:
                    st.session_state[mem_keys["plano"]] = ConversationBufferMemory(memory_key=hist_keys["plano"], return_messages=True)
                if mem_keys["ideias"] not in st.session_state:
                    st.session_state[mem_keys["ideias"]] = ConversationBufferMemory(memory_key=hist_keys["ideias"], return_messages=True)
                if mem_keys["precos"] not in st.session_state:
                    st.session_state[mem_keys["precos"]] = ConversationBufferMemory(memory_key=hist_keys["precos"], return_messages=True)

                self.memoria_max_bussola_plano = st.session_state[mem_keys["plano"]]
                self.memoria_max_bussola_ideias = st.session_state[mem_keys["ideias"]]
                self.memoria_max_financeiro_precos = st.session_state[mem_keys["precos"]]
                
                # Aliases
                self.memoria_plano_negocios = self.memoria_max_bussola_plano
                self.memoria_calculo_precos = self.memoria_max_financeiro_precos
                self.memoria_gerador_ideias = self.memoria_max_bussola_ideias

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
                # Usa a memory_key da instância de memória fornecida
                actual_memory_key = memoria_especifica.memory_key 
                prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(system_message_content),
                    MessagesPlaceholder(variable_name=actual_memory_key), 
                    HumanMessagePromptTemplate.from_template("{input_usuario}")
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
                        key=f"marketing_files_uploader_max{APP_KEY_SUFFIX}"
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

                main_action_key = f"main_marketing_action_choice_max{APP_KEY_SUFFIX}"
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
                
                radio_index_key = f"{main_action_key}_index"
                if radio_index_key not in st.session_state:
                    st.session_state[radio_index_key] = 0 
                
                def update_marketing_radio_index_on_change():
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

                # Lógica para cada ação de marketing (Criar Post, Campanha, etc.)
                # ... (código das seções de marketing que você já tem)...
                # (Assegure-se que a lógica de "Selecionar Todas" e a leitura das plataformas
                # selecionadas no submit dos forms estejam corretas como nas minhas sugestões anteriores)
                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com Max IA")
                    SESSION_KEY_POST_CONTENT = f'generated_post_content_new{APP_KEY_SUFFIX}'
                    FORM_KEY_POST = f"post_creator_form_max{APP_KEY_SUFFIX}"

                    if SESSION_KEY_POST_CONTENT in st.session_state and st.session_state[SESSION_KEY_POST_CONTENT]:
                        _marketing_display_output_options(st.session_state[SESSION_KEY_POST_CONTENT], f"post_output_max{APP_KEY_SUFFIX}", "post_max_ia")
                        if st.button("✨ Criar Novo Post", key=f"clear_post_content_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_POST_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_POST):
                            st.subheader(" Plataformas Desejadas:")
                            key_select_all_post = f"post_select_all_max{APP_KEY_SUFFIX}"
                            
                            if key_select_all_post not in st.session_state: st.session_state[key_select_all_post] = False

                            def toggle_all_platforms_post_cb():
                                new_state = not st.session_state[key_select_all_post]
                                st.session_state[key_select_all_post] = new_state
                                for _, platform_suffix_iter in platforms_config_options.items():
                                    st.session_state[f"post_platform_max_{platform_suffix_iter}{APP_KEY_SUFFIX}"] = new_state
                            
                            st.checkbox("Selecionar Todas as Plataformas Abaixo", key=key_select_all_post, on_change=toggle_all_platforms_post_cb)
                            
                            cols_post = st.columns(2)
                            for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                                col_index = i % 2
                                platform_key = f"post_platform_max_{platform_suffix}{APP_KEY_SUFFIX}"
                                if platform_key not in st.session_state: # Inicializa se não existir
                                    st.session_state[platform_key] = st.session_state[key_select_all_post] 

                                with cols_post[col_index]:
                                    st.checkbox(platform_name, key=platform_key) # o on_change do "select all" já atualiza
                                    if "E-mail Marketing" in platform_name and st.session_state.get(platform_key):
                                        st.caption("💡 Para e-mail marketing...")
                            
                            post_details = _marketing_get_objective_details(f"post_max{APP_KEY_SUFFIX}", "post")
                            submit_button_pressed_post = st.form_submit_button("💡 Gerar Post com Max IA!")

                            if submit_button_pressed_post:
                                current_selected_platforms = [
                                    name for name, suffix in platforms_config_options.items() 
                                    if st.session_state.get(f"post_platform_max_{suffix}{APP_KEY_SUFFIX}")
                                ]
                                _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, current_selected_platforms, self.llm)
                                st.rerun()
                
                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas de Marketing com Max IA")
                    SESSION_KEY_CAMPAIGN_PLAN = f'generated_campaign_content_new{APP_KEY_SUFFIX}'
                    SESSION_KEY_CAMPAIGN_DETAILS = f'generated_campaign_details_content{APP_KEY_SUFFIX}'
                    FORM_KEY_CAMPAIGN_PLAN = f"campaign_creator_form_max{APP_KEY_SUFFIX}"

                    if SESSION_KEY_CAMPAIGN_DETAILS in st.session_state and st.session_state[SESSION_KEY_CAMPAIGN_DETAILS]:
                        st.subheader("📝 Conteúdo Detalhado da Campanha:")
                        st.markdown(st.session_state[SESSION_KEY_CAMPAIGN_DETAILS])
                        try:
                            st.download_button(label="📥 Baixar Conteúdo Detalhado",
                                                data=st.session_state[SESSION_KEY_CAMPAIGN_DETAILS].encode('utf-8'),
                                                file_name=f"campanha_detalhada_max_ia{APP_KEY_SUFFIX}.txt",
                                                mime="text/plain",
                                                key=f"download_campaign_details_btn_{APP_KEY_SUFFIX}") 
                        except Exception as e_dl_details:
                            st.error(f"Erro download detalhes campanha: {e_dl_details}")
                        
                        if st.button("💡 Gerar Novo Plano de Campanha", key=f"clear_all_campaign_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_PLAN, None)
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_DETAILS, None)
                            st.rerun()
                    
                    elif SESSION_KEY_CAMPAIGN_PLAN in st.session_state and st.session_state[SESSION_KEY_CAMPAIGN_PLAN]:
                        st.subheader("📋 Plano da Campanha Gerado:")
                        _marketing_display_output_options(st.session_state[SESSION_KEY_CAMPAIGN_PLAN], f"campaign_plan_output_max{APP_KEY_SUFFIX}", "plano_campanha_max_ia")
                        st.markdown("---")
                        if st.button("✍️ Detalhar Conteúdo da Campanha", key=f"detail_campaign_button{APP_KEY_SUFFIX}"):
                            _marketing_handle_detalhar_campanha(marketing_files_info_for_prompt_local, st.session_state[SESSION_KEY_CAMPAIGN_PLAN], self.llm)
                            st.rerun() 
                        if st.button("💡 Gerar Novo Plano de Campanha", key=f"clear_campaign_plan_button_again{APP_KEY_SUFFIX}"): # Chave diferente
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_PLAN, None)
                            st.session_state.pop(SESSION_KEY_CAMPAIGN_DETAILS, None)
                            st.rerun()
                    else: # Formulário para criar plano de campanha
                        with st.form(key=FORM_KEY_CAMPAIGN_PLAN):
                            campaign_name = st.text_input("Nome da Campanha:", key=f"campaign_name_max{APP_KEY_SUFFIX}")
                            st.subheader(" Plataformas Desejadas:")
                            key_select_all_camp = f"campaign_select_all_max{APP_KEY_SUFFIX}"
                            if key_select_all_camp not in st.session_state: st.session_state[key_select_all_camp] = False

                            def toggle_all_platforms_camp_cb():
                                new_state = not st.session_state[key_select_all_camp]
                                st.session_state[key_select_all_camp] = new_state
                                for _, platform_suffix_iter in platforms_config_options.items():
                                    st.session_state[f"campaign_platform_max_{platform_suffix_iter}{APP_KEY_SUFFIX}"] = new_state

                            st.checkbox("Selecionar Todas", key=key_select_all_camp, on_change=toggle_all_platforms_camp_cb)
                            
                            cols_camp = st.columns(2)
                            for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                                col_index = i % 2
                                platform_key = f"campaign_platform_max_{platform_suffix}{APP_KEY_SUFFIX}"
                                if platform_key not in st.session_state:
                                    st.session_state[platform_key] = st.session_state[key_select_all_camp]
                                with cols_camp[col_index]:
                                    st.checkbox(platform_name, key=platform_key)
                            
                            campaign_details_obj = _marketing_get_objective_details(f"campaign_max{APP_KEY_SUFFIX}", "campanha")
                            campaign_duration = st.text_input("Duração Estimada:", key=f"campaign_duration_max{APP_KEY_SUFFIX}")
                            campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key=f"campaign_budget_max{APP_KEY_SUFFIX}")
                            specific_kpis = st.text_area("KPIs mais importantes:", key=f"campaign_kpis_max{APP_KEY_SUFFIX}")
                            submit_button_pressed_camp_plan = st.form_submit_button("🚀 Gerar Plano de Campanha")

                            if submit_button_pressed_camp_plan:
                                current_selected_platforms_camp = [
                                    name for name, suffix in platforms_config_options.items()
                                    if st.session_state.get(f"campaign_platform_max_{suffix}{APP_KEY_SUFFIX}")
                                ]
                                campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration, "budget": campaign_budget_approx, "kpis": specific_kpis}
                                _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, current_selected_platforms_camp, self.llm)
                                st.rerun()
                
                elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                    st.subheader("📄 Gerador de Estrutura para Landing Pages com Max IA")
                    SESSION_KEY_LP_CONTENT = f'generated_lp_content_new{APP_KEY_SUFFIX}'
                    FORM_KEY_LP = f"landing_page_form_max{APP_KEY_SUFFIX}"

                    if SESSION_KEY_LP_CONTENT in st.session_state and st.session_state[SESSION_KEY_LP_CONTENT]:
                        st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                        st.markdown(st.session_state[SESSION_KEY_LP_CONTENT])
                        try: 
                            st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state[SESSION_KEY_LP_CONTENT].encode('utf-8'), file_name=f"landing_page_sugestoes_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain", key=f"download_lp_max_output_{APP_KEY_SUFFIX}")
                        except Exception as e_dl_lp:
                            st.error(f"Erro ao renderizar botão de download da LP: {e_dl_lp}")
                        if st.button("✨ Criar Nova Estrutura de LP", key=f"clear_lp_content_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_LP_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_LP):
                            lp_purpose = st.text_input("Principal objetivo da landing page:", key=f"lp_purpose_max{APP_KEY_SUFFIX}")
                            lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key=f"lp_audience_max{APP_KEY_SUFFIX}")
                            lp_main_offer = st.text_area("Oferta principal e irresistível:", key=f"lp_offer_max{APP_KEY_SUFFIX}")
                            lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key=f"lp_benefits_max{APP_KEY_SUFFIX}")
                            lp_cta = st.text_input("Chamada para ação (CTA) principal:", key=f"lp_cta_max{APP_KEY_SUFFIX}")
                            lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key=f"lp_visual_max{APP_KEY_SUFFIX}")
                            submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP com Max IA!")
                            if submitted_lp:
                                lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details_dict, self.llm)
                                st.rerun()
                
                elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                    st.subheader("🏗️ Arquiteto de Sites com Max IA")
                    SESSION_KEY_SITE_CONTENT = f'generated_site_content_new{APP_KEY_SUFFIX}'
                    FORM_KEY_SITE = f"site_creator_form_max{APP_KEY_SUFFIX}"
                    if SESSION_KEY_SITE_CONTENT in st.session_state and st.session_state[SESSION_KEY_SITE_CONTENT]:
                        st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                        st.markdown(st.session_state[SESSION_KEY_SITE_CONTENT])
                        try: 
                            st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state[SESSION_KEY_SITE_CONTENT].encode('utf-8'), file_name=f"site_sugestoes_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_site_max_output_{APP_KEY_SUFFIX}")
                        except Exception as e_dl_site:
                            st.error(f"Erro ao renderizar botão de download do Site: {e_dl_site}")
                        if st.button("✨ Criar Nova Estrutura de Site", key=f"clear_site_content_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_SITE_CONTENT, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_SITE):
                            site_business_type = st.text_input("Tipo do seu negócio/empresa:", key=f"site_biz_type_max{APP_KEY_SUFFIX}")
                            site_main_purpose = st.text_area("Principal objetivo do seu site:", key=f"site_purpose_max{APP_KEY_SUFFIX}")
                            site_target_audience = st.text_input("Público principal do site:", key=f"site_audience_max{APP_KEY_SUFFIX}")
                            site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key=f"site_pages_max{APP_KEY_SUFFIX}")
                            site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key=f"site_features_max{APP_KEY_SUFFIX}")
                            site_brand_personality = st.text_input("Personalidade da sua marca:", key=f"site_brand_max{APP_KEY_SUFFIX}")
                            site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key=f"site_visual_ref_max{APP_KEY_SUFFIX}")
                            submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site com Max IA!")
                            if submitted_site:
                                site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                                _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details_dict, self.llm)
                                st.rerun()

                elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                    st.subheader("🎯 Decodificador de Clientes com Max IA")
                    SESSION_KEY_CLIENT_ANALYSIS = f'generated_client_analysis_new{APP_KEY_SUFFIX}'
                    FORM_KEY_CLIENT = f"find_client_form_max{APP_KEY_SUFFIX}"
                    if SESSION_KEY_CLIENT_ANALYSIS in st.session_state and st.session_state[SESSION_KEY_CLIENT_ANALYSIS]:
                        st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                        st.markdown(st.session_state[SESSION_KEY_CLIENT_ANALYSIS])
                        try:
                            st.download_button(label="📥 Baixar Análise de Público",data=st.session_state[SESSION_KEY_CLIENT_ANALYSIS].encode('utf-8'), file_name=f"analise_publico_alvo_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_client_analysis_max_output_{APP_KEY_SUFFIX}")
                        except Exception as e_dl_client:
                            st.error(f"Erro ao renderizar botão de download da Análise de Cliente: {e_dl_client}")
                        if st.button("✨ Nova Análise de Cliente", key=f"clear_client_analysis_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_CLIENT_ANALYSIS, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_CLIENT):
                            fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key=f"fc_campaign_max{APP_KEY_SUFFIX}")
                            fc_location = st.text_input("Cidade(s) ou região de alcance:", key=f"fc_location_max{APP_KEY_SUFFIX}")
                            fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key=f"fc_budget_max{APP_KEY_SUFFIX}")
                            fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key=f"fc_age_gender_max{APP_KEY_SUFFIX}")
                            fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key=f"fc_interests_max{APP_KEY_SUFFIX}")
                            fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key=f"fc_channels_max{APP_KEY_SUFFIX}")
                            fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key=f"fc_deep_max{APP_KEY_SUFFIX}")
                            submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente com Max IA!")
                            if submitted_fc:
                                client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details_dict, self.llm)
                                st.rerun()

                elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                    st.subheader("🧐 Radar da Concorrência com Max IA")
                    SESSION_KEY_COMPETITOR_ANALYSIS = f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'
                    FORM_KEY_COMPETITOR = f"competitor_analysis_form_max{APP_KEY_SUFFIX}"
                    if SESSION_KEY_COMPETITOR_ANALYSIS in st.session_state and st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS]:
                        st.subheader("📊 Análise da Concorrência e Insights:")
                        st.markdown(st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS])
                        try:
                            st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS].encode('utf-8'), file_name=f"analise_concorrencia_max_ia{APP_KEY_SUFFIX}.txt",mime="text/plain",key=f"download_competitor_analysis_max_output_{APP_KEY_SUFFIX}")
                        except Exception as e_dl_comp:
                            st.error(f"Erro ao renderizar botão de download da Análise de Concorrência: {e_dl_comp}")
                        if st.button("✨ Nova Análise de Concorrência", key=f"clear_competitor_analysis_button{APP_KEY_SUFFIX}"):
                            st.session_state.pop(SESSION_KEY_COMPETITOR_ANALYSIS, None)
                            st.rerun()
                    else:
                        with st.form(key=FORM_KEY_COMPETITOR):
                            ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key=f"ca_your_biz_max{APP_KEY_SUFFIX}")
                            ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key=f"ca_competitors_max{APP_KEY_SUFFIX}")
                            ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"ca_aspects_max{APP_KEY_SUFFIX}")
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
                
                current_section_key_finance = "max_financeiro_precos"
                memoria_financeiro = self.memoria_max_financeiro_precos
                
                uploaded_image_calc = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key=f"preco_img_max_financeiro{APP_KEY_SUFFIX}")
                
                system_message_financeiro = "Você é Max IA, um especialista em finanças e precificação para PMEs. Ajude o usuário a calcular o preço de seus produtos ou serviços, considerando custos, margens, mercado e valor percebido. Seja claro e didático."
                chain_financeiro = self._criar_cadeia_conversacional(system_message_financeiro, memoria_financeiro)

                def conversar_max_financeiro_precos(input_usuario, descricao_imagem_contexto=None):
                    prompt_final_usuario = input_usuario
                    if descricao_imagem_contexto:
                        prompt_final_usuario = f"{descricao_imagem_contexto}\n\n{input_usuario}"
                    resposta_ai = chain_financeiro.invoke({"input_usuario": prompt_final_usuario})
                    return resposta_ai['text'] if isinstance(resposta_ai, dict) and 'text' in resposta_ai else str(resposta_ai)


                _handle_chat_with_image(current_section_key_finance, "Descreva o produto/serviço, custos, etc.", conversar_max_financeiro_precos, uploaded_image_calc)
                _sidebar_clear_button_max("Preços (MaxFinanceiro)", memoria_financeiro, current_section_key_finance)

            def exibir_max_administrativo(self):
                st.header("⚙️ MaxAdministrativo")
                st.image("images/max-ia-logo.png", width=150) 
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
                    key=f"selectbox_admin_tool{APP_KEY_SUFFIX}"
                )

                acao_selecionada = opcoes_administrativo.get(escolha_admin_label)
                st.markdown("---")

                if acao_selecionada == "admin_fluxo_caixa": self._admin_render_fluxo_caixa()
                elif acao_selecionada == "admin_planej_financeiro": self._admin_render_planejamento_financeiro()
                elif acao_selecionada == "admin_contabil": self._admin_render_contabil()
                elif acao_selecionada == "admin_controle_estoque": self._admin_render_controle_estoque()
                elif acao_selecionada == "admin_gestao_pessoas": self._admin_render_gestao_pessoas()
                elif acao_selecionada == "admin_plan_estr_objetivos": self._admin_render_planejamento_estrategico_objetivos()
                elif acao_selecionada == "admin_analise_swot": self._admin_render_analise_swot()
                elif acao_selecionada == "admin_def_estrategias": self._admin_render_definicao_estrategias()
                elif acao_selecionada == "admin_analise_risco": self._admin_render_analise_risco()
                elif acao_selecionada == "admin_plan_riscos": self._admin_render_planejamento_riscos()
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
                    key=f"radio_plan_fin{APP_KEY_SUFFIX}"
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
                st.image("images/max-ia-logo.png", width=150) 
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
                    current_section_key_plano = "max_bussola_plano"
                    memoria_plano = self.memoria_max_bussola_plano
                    system_message_plano = "Você é Max IA, um consultor de negócios experiente. Ajude o usuário a criar um rascunho de plano de negócios, seção por seção. Faça perguntas, ofereça sugestões e ajude a estruturar as ideias."
                    chain_plano = self._criar_cadeia_conversacional(system_message_plano, memoria_plano)
                    
                    def conversar_max_bussola_plano(input_usuario):
                        resposta_ai = chain_plano.invoke({"input_usuario": input_usuario})
                        return resposta_ai['text'] if isinstance(resposta_ai, dict) and 'text' in resposta_ai else str(resposta_ai)

                    exibir_chat_e_obter_input(current_section_key_plano, "Sua resposta ou próxima seção do plano...", conversar_max_bussola_plano)
                    _sidebar_clear_button_max("Plano (MaxBússola)", memoria_plano, current_section_key_plano)

                with tab2_ideias:
                    st.subheader("💡 Gerador de Ideias para seu Negócio com Max IA")
                    st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
                    current_section_key_ideias = "max_bussola_ideias"
                    memoria_ideias = self.memoria_max_bussola_ideias
                    system_message_ideias = "Você é Max IA, um especialista em inovação e brainstorming. Ajude o usuário a gerar novas ideias para seus negócios, resolver problemas ou explorar novas oportunidades. Use o contexto de arquivos, se fornecido."
                    chain_ideias = self._criar_cadeia_conversacional(system_message_ideias, memoria_ideias)

                    def conversar_max_bussola_ideias(input_usuario, contexto_arquivos=None):
                        prompt_final_usuario = input_usuario
                        if contexto_arquivos:
                            prompt_final_usuario = f"Contexto dos arquivos:\n{contexto_arquivos}\n\nCom base nisso e na minha solicitação: {input_usuario}"
                        resposta_ai = chain_ideias.invoke({"input_usuario": prompt_final_usuario})
                        return resposta_ai['text'] if isinstance(resposta_ai, dict) and 'text' in resposta_ai else str(resposta_ai)


                    uploaded_files_ideias_ui = st.file_uploader(
                        "Envie arquivos de contexto (opcional - .txt, .png, .jpg):", 
                        type=["txt", "png", "jpg", "jpeg"], 
                        accept_multiple_files=True, 
                        key=f"ideias_file_uploader_max_bussola{APP_KEY_SUFFIX}"
                    )
                    _handle_chat_with_files(current_section_key_ideias, "Descreva seu desafio ou peça ideias:", conversar_max_bussola_ideias, uploaded_files_ideias_ui)
                    _sidebar_clear_button_max("Ideias (MaxBússola)", memoria_ideias, current_section_key_ideias)

            def exibir_max_trainer(self):
                st.header("🎓 MaxTrainer IA")
                st.image("images/max-ia-logo.png", width=150) 
                st.subheader("Olá! Sou o Max, seu treinador pessoal de IA para negócios.")
                st.info("Esta área está em desenvolvimento...")
                st.write("Imagine aprender sobre:")
                st.markdown("""
                - Como criar os melhores prompts...
                - Interpretando os resultados da IA...
                - Novas funcionalidades...
                - Estudos de caso...
                """)
                st.balloons()

        # --- Funções Utilitárias Globais ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'): # Para alguns tipos de memória
                    memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
                    memoria_agente_instancia.chat_memory.messages.clear()
                    memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))

            if area_chave == "max_financeiro_precos":
                st.session_state.pop(f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)
            elif area_chave == "max_bussola_ideias":
                st.session_state.pop(f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)


        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
            if chat_display_key not in st.session_state:
                # Deveria ter sido inicializado por inicializar_ou_resetar_chat. Se não, é um bug no fluxo.
                # Para segurança, inicializa se não existir, mas isso não deveria ser necessário.
                # st.warning(f"Aviso: {chat_display_key} não encontrado. Verifique o fluxo de inicialização do chat.")
                st.session_state[chat_display_key] = [] 

            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]):
                    st.markdown(msg_info["content"])
            
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{APP_KEY_SUFFIX}")
            
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                
                if area_chave in ["max_financeiro_precos", "max_bussola_ideias"]:
                    st.session_state[f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'] = True

                with st.spinner("Max IA está processando... 🤔"):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                    st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()

        def _sidebar_clear_button_max(label, memoria, section_key_prefix):
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key_prefix}{APP_KEY_SUFFIX}_clear_max"):
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key_prefix == "max_financeiro_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços com MaxFinanceiro! Descreva seu produto ou serviço."
                elif section_key_prefix == "max_bussola_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias com MaxBússola! Qual o seu ponto de partida?"
                elif section_key_prefix == "max_bussola_plano": msg_inicial = "Olá! Sou Max IA com a MaxBússola. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia."
                
                inicializar_ou_resetar_chat(section_key_prefix, msg_inicial, memoria)
                st.rerun()

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
            descricao_imagem_para_ia = None
            processed_image_id_key = f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}'
            last_uploaded_info_key = f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}'
            user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'

            if uploaded_image_obj is not None:
                if st.session_state.get(processed_image_id_key) != uploaded_image_obj.file_id or not st.session_state.get(last_uploaded_info_key):
                    try:
                        img_pil = Image.open(uploaded_image_obj); 
                        st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                        st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                        st.session_state[processed_image_id_key] = uploaded_image_obj.file_id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo com Max IA.")
                        st.session_state[user_input_processed_key] = False 
                    except Exception as e_img_proc:
                        st.error(f"Erro ao processar imagem: {e_img_proc}")
                        st.session_state[last_uploaded_info_key] = None; st.session_state[processed_image_id_key] = None
                else:
                    descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
            
            kwargs_chat = {}
            ctx_img_prox_dialogo = st.session_state.get(last_uploaded_info_key)
            if ctx_img_prox_dialogo and not st.session_state.get(user_input_processed_key, False):
                kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
            
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)

            if st.session_state.get(user_input_processed_key, False): # Se o input foi processado
                # Decide se quer limpar o contexto da imagem após o uso.
                # st.session_state.pop(last_uploaded_info_key, None) # Para limpar após cada uso
                st.session_state[user_input_processed_key] = False # Reseta o flag


        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
            contexto_para_ia_local = None
            processed_file_id_key = f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}'
            uploaded_info_key = f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}'
            user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'

            if uploaded_files_objs:
                current_file_signature = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id}" for f in uploaded_files_objs]))
                
                if st.session_state.get(processed_file_id_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                    text_contents, image_info = [], []
                    with st.spinner("Processando arquivos de contexto..."):
                        for f_item in uploaded_files_objs:
                            try:
                                if f_item.type == "text/plain":
                                    text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8', errors='replace')[:3000]}...")
                                elif f_item.type in ["image/png","image/jpeg"]:
                                    image_info.append(f"Usuário forneceu uma imagem chamada '{f_item.name}'.") 
                            except Exception as e_file_proc:
                                st.error(f"Erro ao processar '{f_item.name}': {e_file_proc}")
                    
                    full_ctx_str = ("\n\n--- CONTEÚDO DOS ARQUIVOS DE TEXTO ---\n" + "\n\n".join(text_contents) if text_contents else "") + \
                                   ("\n\n--- INFORMAÇÕES SOBRE IMAGENS FORNECIDAS ---\n" + "\n".join(image_info) if image_info else "")
                    
                    if full_ctx_str.strip():
                        st.session_state[uploaded_info_key] = full_ctx_str.strip()
                        contexto_para_ia_local = st.session_state[uploaded_info_key]
                        st.info("Arquivo(s) de contexto pronto(s) para Max IA.")
                    else:
                        st.session_state.pop(uploaded_info_key, None) 
                    st.session_state[processed_file_id_key] = current_file_signature
                    st.session_state[user_input_processed_key] = False 
                else:
                    contexto_para_ia_local = st.session_state.get(uploaded_info_key)
            
            kwargs_chat = {}
            ctx_files_prox_dialogo = st.session_state.get(uploaded_info_key)
            if ctx_files_prox_dialogo and not st.session_state.get(user_input_processed_key, False):
                kwargs_chat['contexto_arquivos'] = ctx_files_prox_dialogo
            
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)

            if st.session_state.get(user_input_processed_key, False):
                # st.session_state.pop(uploaded_info_key, None) # Para limpar após cada uso
                st.session_state[user_input_processed_key] = False


        # --- Instanciação do Agente ---
        if 'max_agente_instancia' not in st.session_state or \
           not isinstance(st.session_state.max_agente_instancia, MaxAgente) or \
           (hasattr(st.session_state.max_agente_instancia, 'llm') and st.session_state.max_agente_instancia.llm != llm_model_instance):
            
            if llm_model_instance:
                st.session_state.max_agente_instancia = MaxAgente(llm_passed_model=llm_model_instance)
            else:
                st.session_state.max_agente_instancia = None 
        
        agente = None 
        if st.session_state.get('max_agente_instancia') and llm_model_instance:
            agente = st.session_state.max_agente_instancia

            st.sidebar.write(f"Logado como: {display_email}")
            if st.sidebar.button("Logout", key=f"main_app_logout_max{APP_KEY_SUFFIX}"):
                st.session_state.user_session_pyrebase = None
                keys_to_clear_on_logout = [k for k in st.session_state if APP_KEY_SUFFIX in k or k.startswith('memoria_') or k.startswith('chat_display_') or k.startswith('generated_') or 'form' in k.lower() or 'radio' in k.lower() or 'select' in k.lower()]
                keys_to_clear_on_logout.extend([
                    'max_agente_instancia', 'area_selecionada_max_ia',
                    'firebase_init_success_message_shown', 'firebase_app_instance',
                    'firestore_init_success_message_shown', 'firestore_client_instance',
                    'llm_init_success_sidebar_shown_main_app', 'is_user_activated'
                ])
                for key_to_clear in list(st.session_state.keys()): # Itera sobre uma cópia das chaves
                    if key_to_clear in keys_to_clear_on_logout or APP_KEY_SUFFIX in key_to_clear:
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
                "👋 Bem-vindo ao Max IA": "painel_max_ia",
                "🚀 MaxMarketing Total": "max_marketing_total",
                "💰 MaxFinanceiro": "max_financeiro",
                "⚙️ MaxAdministrativo": "max_administrativo",
                "📈 MaxPesquisa de Mercado": "max_pesquisa_mercado",
                "🧭 MaxBússola Estratégica": "max_bussola",
                "🎓 MaxTrainer IA": "max_trainer_ia"
            }
            radio_key_sidebar_main_max = f'sidebar_selection_max_ia{APP_KEY_SUFFIX}'

            if 'area_selecionada_max_ia' not in st.session_state or st.session_state.area_selecionada_max_ia not in opcoes_menu_max_ia.keys():
                st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.keys())[0]

            radio_index_key_nav_max = f'{radio_key_sidebar_main_max}_index'
            # Garante que o índice seja inicializado corretamente
            try:
                current_selection_label = st.session_state.area_selecionada_max_ia
                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(current_selection_label)
            except (ValueError, KeyError): # Fallback se a chave ou valor não for válido
                st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.keys())[0]
                st.session_state[radio_index_key_nav_max] = 0
            
            def on_sidebar_menu_change():
                nova_selecao_label = st.session_state[radio_key_sidebar_main_max]
                st.session_state.area_selecionada_max_ia = nova_selecao_label # Atualiza a área principal
                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(nova_selecao_label) # Atualiza o índice
                
                if nova_selecao_label != "🚀 MaxMarketing Total":
                    keys_to_clear = [f'generated_post_content_new{APP_KEY_SUFFIX}', f'generated_campaign_content_new{APP_KEY_SUFFIX}', f'generated_campaign_details_content{APP_KEY_SUFFIX}', f'generated_lp_content_new{APP_KEY_SUFFIX}', f'generated_site_content_new{APP_KEY_SUFFIX}', f'generated_client_analysis_new{APP_KEY_SUFFIX}', f'generated_competitor_analysis_new{APP_KEY_SUFFIX}']
                    for key in keys_to_clear: st.session_state.pop(key, None)

            area_selecionada_label_max_ia = st.sidebar.radio( # Removido o _max_ia do final da var local
                "Max Agentes IA:",
                options=list(opcoes_menu_max_ia.keys()),
                key=radio_key_sidebar_main_max,
                index=st.session_state[radio_index_key_nav_max],
                on_change=on_sidebar_menu_change 
            )
            
            # A lógica de exibição agora usa st.session_state.area_selecionada_max_ia que é atualizada pelo on_change
            current_section_key_to_display = opcoes_menu_max_ia.get(st.session_state.area_selecionada_max_ia)


            if current_section_key_to_display == "painel_max_ia": # Usar a variável correta
                st.markdown("<div style='text-align: center;'><h1>👋 Bem-vindo ao Max IA!</h1></div>", unsafe_allow_html=True)
                logo_base64 = convert_image_to_base64('images/max-ia-logo.png')
                if logo_base64:
                    st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{logo_base64}' width='200'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align: center;'><p>(Logo não pôde ser carregado)</p></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center;'><p style='font-size: 1.2em;'>Olá! Eu sou o <strong>Max</strong>...</p></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda...</p></div>", unsafe_allow_html=True)
                st.markdown("---")
                st.subheader("Conheça seus Agentes Max IA:")
                cols_cards = st.columns(3)
                card_data = [
                    ("🚀 MaxMarketing Total", "Crie posts, campanhas, sites e muito mais!"),
                    ("💰 MaxFinanceiro", "Inteligência para preços, custos e finanças."),
                    ("⚙️ MaxAdministrativo", "Otimize sua gestão e rotinas."), 
                    ("📈 MaxPesquisa de Mercado", "Desvende seu público e a concorrência (Em breve!)."),
                    ("🧭 MaxBússola Estratégica", "Planejamento, ideias e direção para o futuro."),
                    ("🎓 MaxTrainer IA", "Aprenda a usar todo o poder da IA (Em breve!).")
                ]
                for i, (title, caption) in enumerate(card_data):
                    with cols_cards[i % 3]:
                        matching_key_for_button = None
                        correct_menu_label_for_button = title 
                        for menu_title_iter, section_key_val_iter in opcoes_menu_max_ia.items():
                            if menu_title_iter.strip() == title.strip():
                                matching_key_for_button = section_key_val_iter
                                correct_menu_label_for_button = menu_title_iter
                                break
                        
                        if matching_key_for_button and st.button(title, key=f"btn_goto_card_{matching_key_for_button}{APP_KEY_SUFFIX}", use_container_width=True, help=f"Ir para {title}"):
                            st.session_state[radio_key_sidebar_main_max] = correct_menu_label_for_button # Dispara o on_change
                            on_sidebar_menu_change() # Chama explicitamente para garantir a atualização antes do rerun
                            st.rerun()
                        else:
                             st.markdown(f"**{title}**") 
                        st.caption(caption)
                        st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
                st.balloons()

            elif current_section_key_to_display == "max_marketing_total": agente.exibir_max_marketing_total()
            elif current_section_key_to_display == "max_financeiro": agente.exibir_max_financeiro()
            elif current_section_key_to_display == "max_administrativo": agente.exibir_max_administrativo() 
            elif current_section_key_to_display == "max_pesquisa_mercado": agente.exibir_max_pesquisa_mercado()
            elif current_section_key_to_display == "max_bussola": agente.exibir_max_bussola()
            elif current_section_key_to_display == "max_trainer_ia": agente.exibir_max_trainer()
        
        else: # Agente não pôde ser instanciado ou LLM falhou
            st.error("🚨 O Max IA não pôde ser totalmente iniciado.")
            st.info("Isso pode ter ocorrido devido a um problema com a chave da API do Google, ao contatar os serviços do Google Generative AI, ou o agente não pôde ser instanciado.")
            if llm_init_exception:
                st.exception(llm_init_exception)

    else: # Usuário autenticado, mas NÃO ATIVADO
        display_activation_form(uid, db_firestore)

# --- Seção de Login/Registro ---
else: # user_is_authenticated é False
    st.session_state.pop('auth_error_shown', None)
    st.title("🔑 Bem-vindo ao Max IA")
    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key = "app_auth_choice_pyrebase_max"
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key)
    
    if auth_action_choice == "Login":
        with st.sidebar.form("app_login_form_pyrebase_max"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")
            
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None)
                        st.session_state.pop('firestore_init_success_message_shown', None)
                        st.session_state.pop('is_user_activated', None)
                        st.session_state.pop('auth_error_shown', None) # Limpa erro anterior
                        st.rerun()
                    except Exception as e_login:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        # (Lógica de parsing de erro do Firebase similar à da verificação de sessão)
                        login_error_details_text = ""
                        if hasattr(e_login, 'args') and len(e_login.args) > 0:
                            raw_err = e_login.args[0]
                            if isinstance(raw_err, str): 
                                login_error_details_text = raw_err
                                if raw_err.strip().startswith("{") and "\"error\"" in raw_err.lower():
                                    try:
                                        err_data = json.loads(raw_err)
                                        parsed_msg = err_data.get('error',{}).get('message', login_error_details_text)
                                        if parsed_msg: login_error_details_text = parsed_msg
                                    except: pass
                            else: login_error_details_text = str(raw_err)
                        else: login_error_details_text = str(e_login)

                        if any(code in login_error_details_text for code in ["INVALID_LOGIN_CREDENTIALS", "EMAIL_NOT_FOUND", "INVALID_PASSWORD", "USER_DISABLED", "INVALID_EMAIL", "TOO_MANY_ATTEMPTS_TRY_LATER"]):
                            error_message_login = "Email ou senha inválidos, usuário desabilitado, ou muitas tentativas. Tente mais tarde."
                        elif login_error_details_text: 
                            error_message_login = f"Erro no login: {login_error_details_text}"
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
                
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("app_register_form_pyrebase_max"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try:
                            pb_auth_client.send_email_verification(user['idToken'])
                            st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_local:
                            st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_local}")
                    except Exception as e_register:
                        error_message_register = "Erro no registro."
                        # (Lógica de parsing de erro do Firebase similar)
                        reg_error_details_text = ""
                        if hasattr(e_register, 'args') and len(e_register.args) > 0:
                            raw_err_reg = e_register.args[0]
                            if isinstance(raw_err_reg, str): 
                                reg_error_details_text = raw_err_reg
                                if raw_err_reg.strip().startswith("{") and "\"error\"" in raw_err_reg.lower():
                                    try:
                                        err_data_reg = json.loads(raw_err_reg)
                                        parsed_msg_reg = err_data_reg.get('error',{}).get('message', reg_error_details_text)
                                        if parsed_msg_reg: reg_error_details_text = parsed_msg_reg
                                    except: pass
                            else: reg_error_details_text = str(raw_err_reg)
                        else: reg_error_details_text = str(e_register)

                        if "EMAIL_EXISTS" in reg_error_details_text:
                            error_message_register = "Este email já está registrado. Tente fazer login."
                        elif "WEAK_PASSWORD" in reg_error_details_text : # Exemplo de outro erro
                            error_message_register = "Senha muito fraca. Use pelo menos 6 caracteres."
                        elif reg_error_details_text:
                            error_message_register = f"Erro no registro: {reg_error_details_text}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")

    if not error_message_firebase_init.strip() or (firebase_initialized_successfully and firestore_initialized_successfully):
        st.info("Faça login ou registre-se na barra lateral para usar o Max IA.")
    
    LOGO_PATH_LOGIN_UNAUTH = "images/max-ia-logo.png"
    try:
        st.image(LOGO_PATH_LOGIN_UNAUTH, width=200)
    except Exception:
        st.image("https://i.imgur.com/7IIYxq1.png", width=200, caption="Max IA (Fallback)")

st.sidebar.markdown("---")
st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini Pro")
