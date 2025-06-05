import streamlit as st
import os
import json
import pyrebase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import AIMessage
import google.generativeai as genai
from PIL import Image
import base64
import time
import datetime
import firebase_admin
from firebase_admin import credentials, firestore as firebase_admin_firestore

# --- Constantes ---
APP_KEY_SUFFIX = "maxia_app_v1.2_stable" 
USER_COLLECTION = "users"

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# --- Funções Auxiliares ---
def convert_image_to_base64(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        print(f"ERRO convert_image_to_base64: {e}")
    return None

# --- Configuração da Página ---
try:
    page_icon_img_obj = Image.open("images/carinha-agente-max-ia.png") if os.path.exists("images/carinha-agente-max-ia.png") else "🤖"
except Exception:
    page_icon_img_obj = "🤖"
st.set_page_config(page_title="Max IA", page_icon=page_icon_img_obj, layout="wide", initial_sidebar_state="expanded")

# --- CORREÇÃO 1: INICIALIZAÇÃO CENTRALIZADA E ROBUSTA ---
@st.cache_resource
def initialize_firebase_services():
    init_errors = []
    pb_auth = None
    firestore_db = None
    try:
        conf = st.secrets["firebase_config"]
        pb_auth = pyrebase.initialize_app(dict(conf)).auth()
    except Exception as e:
        init_errors.append(f"ERRO Auth: {e}")
    try:
        sa_creds = st.secrets["gcp_service_account"]
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(sa_creds))
            firebase_admin.initialize_app(cred)
        firestore_db = firebase_admin_firestore.client()
    except Exception as e:
        init_errors.append(f"ERRO Firestore: {e}")
    return pb_auth, firestore_db, init_errors

pb_auth_client, firestore_db, init_errors = initialize_firebase_services()

if f'{APP_KEY_SUFFIX}_init_msgs_shown' not in st.session_state:
    if pb_auth_client: st.sidebar.success("✅ Firebase Auth OK.")
    else: st.sidebar.error("❌ Firebase Auth FALHOU.")
    if firestore_db: st.sidebar.success("✅ Firestore DB OK.")
    else: st.sidebar.error("❌ Firestore DB FALHOU.")
    if init_errors:
        for err in init_errors: st.sidebar.error(f"Init Error: {err}")
    st.session_state[f'{APP_KEY_SUFFIX}_init_msgs_shown'] = True

if not pb_auth_client:
    st.error("ERRO CRÍTICO: Autenticação Firebase não inicializada.")
    st.stop()

# --- Lógica de Sessão e Autenticação (Simplificada) ---
def get_current_user_status(auth_client):
    user_auth, uid, email = False, None, None
    session_key = f'{APP_KEY_SUFFIX}_user_session_data'
    if session_key in st.session_state and st.session_state[session_key]:
        try:
            session_data = st.session_state[session_key]
            account_info = auth_client.get_account_info(session_data['idToken'])
            user_auth = True
            user_info = account_info['users'][0]
            uid = user_info['localId']
            email = user_info.get('email')
            st.session_state[session_key].update({'localId': uid, 'email': email})
        except Exception:
            st.session_state.pop(session_key, None)
            user_auth = False
            if 'auth_error_shown' not in st.session_state:
                st.sidebar.warning("Sessão inválida. Faça login novamente.")
                st.session_state['auth_error_shown'] = True
            st.rerun()
            
    st.session_state.user_is_authenticated = user_auth
    st.session_state.user_uid = uid
    st.session_state.user_email = email
    return user_auth, uid, email

user_is_authenticated, user_uid, user_email = get_current_user_status(pb_auth_client)

# --- Inicialização do LLM ---
llm = None
if user_is_authenticated:
    llm_key = f'{APP_KEY_SUFFIX}_llm_instance'
    if llm_key not in st.session_state:
        try:
            api_key = st.secrets.get("GOOGLE_API_KEY")
            if api_key:
                st.session_state[llm_key] = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key, temperature=0.7)
                if 'llm_msg_shown' not in st.session_state:
                    st.sidebar.success("✅ LLM (Gemini) OK.")
                    st.session_state['llm_msg_shown'] = True
            else:
                st.error("Chave GOOGLE_API_KEY não configurada nos segredos.")
        except Exception as e: st.error(f"Erro ao inicializar LLM: {e}")
    llm = st.session_state.get(llm_key)

# --- Funções de Marketing e Utilitárias (Baseadas no seu código original) ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj")
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp")
    details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone")
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    try:
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'),
                           file_name=f"{file_name_prefix}_{section_key}.txt", mime="text/plain",
                           key=f"download_{section_key}_{file_name_prefix}")
    except Exception as e_download:
        st.error(f"Erro ao tentar renderizar o botão de download: {e_download}")

def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    # Corpo completo da sua função original _marketing_handle_criar_post aqui...
    st.error("DEBUG: EXECUTANDO A VERSÃO CORRIGIDA DE _marketing_handle_criar_post v2")
    if not selected_platforms_list:
        st.warning("Por favor, selecione pelo menos uma plataforma.")
        st.session_state.pop(f'generated_post_content_new_v20_final', None)
        return
    # (Restante do seu código original para esta função...)

# (COLE AQUI O CORPO COMPLETO DE TODAS AS SUAS OUTRAS FUNÇÕES _marketing_handle_...)
# ...

def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    # (Corpo completo da sua função original aqui)
    pass

def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    # (Corpo completo da sua função original aqui)
    pass

def _sidebar_clear_button_max(label, memoria, section_key_prefix):
    # (Corpo completo da sua função original aqui)
    pass

def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
    # (Corpo completo da sua função original aqui)
    pass

def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
    # (Corpo completo da sua função original aqui)
    pass
# --- Definição da Classe MaxAgente ---
class MaxAgente:
    def __init__(self, llm_instance, db_firestore_instance):
        self.llm = llm_instance
        self.db = db_firestore_instance # ESSENCIAL: usa o cliente Firestore
        if not self.llm: st.warning("MaxAgente: LLM não disponível.")
        if not self.db: st.warning("MaxAgente: Firestore não disponível.")

        # --- Bloco de inicialização de memória (Preservado do seu código original) ---
        if f'memoria_max_bussola_plano_v20_final' not in st.session_state:
            st.session_state[f'memoria_max_bussola_plano_v20_final'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_plano_v20_final", return_messages=True)
        if f'memoria_max_bussola_ideias_v20_final' not in st.session_state:
            st.session_state[f'memoria_max_bussola_ideias_v20_final'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_ideias_v20_final", return_messages=True)
        if f'memoria_max_financeiro_precos_v20_final' not in st.session_state:
            st.session_state[f'memoria_max_financeiro_precos_v20_final'] = ConversationBufferMemory(memory_key=f"historico_chat_financeiro_precos_v20_final", return_messages=True)

        self.memoria_max_bussola_plano = st.session_state[f'memoria_max_bussola_plano_v20_final']
        self.memoria_max_bussola_ideias = st.session_state[f'memoria_max_bussola_ideias_v20_final']
        self.memoria_max_financeiro_precos = st.session_state[f'memoria_max_financeiro_precos_v20_final']
        self.memoria_plano_negocios = self.memoria_max_bussola_plano
        self.memoria_calculo_precos = self.memoria_max_financeiro_precos
        self.memoria_gerador_ideias = self.memoria_max_bussola_ideias

    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
        if not self.llm: return None
        actual_memory_key = memoria_especifica.memory_key
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name=actual_memory_key),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    # --- Métodos dos Agentes (Preservados do seu código original) ---
    def exibir_max_marketing_total(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_marketing_total)
        # Exemplo de estrutura mínima:
        st.header("🚀 MaxMarketing Total")
        st.write("Conteúdo e ferramentas de Marketing aqui...")

    def exibir_max_financeiro(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_financeiro)
        st.header("💰 MaxFinanceiro")
        st.write("Conteúdo e ferramentas de Finanças aqui...")
        
    def exibir_max_administrativo(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_administrativo)
        st.header("⚙️ MaxAdministrativo")
        st.write("Conteúdo e ferramentas de Administração aqui...")
    
    def exibir_max_pesquisa_mercado(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_pesquisa_mercado)
        st.header("📈 MaxPesquisa de Mercado")
        st.write("Conteúdo e ferramentas de Pesquisa de Mercado aqui...")
    
    def exibir_max_bussola(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_bussola)
        st.header("🧭 MaxBússola Estratégica")
        st.write("Conteúdo e ferramentas de Estratégia aqui...")
        
    def exibir_max_trainer(self):
        # (COLE AQUI TODO O CONTEÚDO ORIGINAL DA SUA FUNÇÃO exibir_max_trainer)
        st.header("🎓 MaxTrainer IA")
        st.write("Conteúdo e ferramentas de Treinamento aqui...")

# --- Fim da Classe MaxAgente ---
# --- Instanciação do Agente ---
agente = None
if user_is_authenticated:
    if llm and firestore_db:
        agent_key = f'{APP_KEY_SUFFIX}_agente_instancia'
        if agent_key not in st.session_state:
            st.session_state[agent_key] = MaxAgente(llm_instance=llm, db_firestore_instance=firestore_db)
        agente = st.session_state[agent_key]

# --- LÓGICA PRINCIPAL DA INTERFACE ---
if not user_is_authenticated:
    st.title("🔑 Bem-vindo ao Max IA")
    # ... (seu código original para a tela de login/registro, adaptado para usar chaves únicas) ...
    auth_action = st.sidebar.radio("Acesso:", ["Login", "Registrar"], key=f"{APP_KEY_SUFFIX}_auth_choice")
    if auth_action == "Login":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if email and password and pb_auth_client:
                    try:
                        user_creds = pb_auth_client.sign_in_with_email_and_password(email, password)
                        st.session_state[f'{APP_KEY_SUFFIX}_user_session_data'] = dict(user_creds)
                        # Limpa chaves de sessão antigas para garantir um estado limpo
                        for k in list(st.session_state.keys()):
                            if '_init_msgs_shown' in k or 'auth_error_shown' in k:
                                del st.session_state[k]
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Erro no login: Verifique as credenciais.")
    else: # Registrar
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_register_form"):
            email = st.text_input("Seu Email")
            password = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
            if st.form_submit_button("Registrar Conta"):
                if email and password and len(password) >= 6 and pb_auth_client and firestore_db:
                    try:
                        new_user = pb_auth_client.create_user_with_email_and_password(email, password)
                        user_doc = firestore_db.collection(USER_COLLECTION).document(new_user['localId'])
                        user_doc.set({"email": email, "is_activated": False, "registration_date": firebase_admin_firestore.SERVER_TIMESTAMP}, merge=True)
                        st.sidebar.success(f"Conta criada! Por favor, faça o login.")
                    except Exception as e:
                        st.sidebar.error(f"Erro no registro: {e}")
                else:
                    if not firestore_db: st.sidebar.error("Serviço de registro indisponível (DB).")
                    else: st.sidebar.warning("Preencha todos os campos corretamente.")

else: # Usuário está autenticado, exibe o app principal
    # PLANO B: Ativação está desativada por padrão. Todos os usuários logados têm acesso.
    # A verificação de chave foi removida deste fluxo principal para estabilizar o app.
    
    st.sidebar.write(f"Logado como: **{user_email}**")
    if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_logout_button"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    if agente:
        # Lógica de Navegação da Sidebar (Preservada do seu código original)
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
        if 'area_selecionada_max_ia' not in st.session_state:
            st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.keys())[0]

        try:
            radio_index_key_nav_max = list(opcoes_menu_max_ia.keys()).index(st.session_state.area_selecionada_max_ia)
        except ValueError:
            radio_index_key_nav_max = 0

        area_selecionada_label = st.sidebar.radio(
            "Max Agentes IA:",
            options=list(opcoes_menu_max_ia.keys()),
            index=radio_index_key_nav_max,
            key=radio_key_sidebar_main_max
        )
        # Atualiza a área selecionada se o rádio for mudado
        if area_selecionada_label != st.session_state.area_selecionada_max_ia:
            st.session_state.area_selecionada_max_ia = area_selecionada_label
            st.rerun()
        
        current_section_key_to_display = opcoes_menu_max_ia.get(st.session_state.area_selecionada_max_ia)

        # Mapeamento e chamada dos métodos do agente
        if current_section_key_to_display == "painel_max_ia":
            agente.exibir_painel_boas_vindas()
        elif current_section_key_to_display == "max_marketing_total":
            agente.exibir_max_marketing_total()
        elif current_section_key_to_display == "max_financeiro":
            agente.exibir_max_financeiro()
        elif current_section_key_to_display == "max_administrativo":
            agente.exibir_max_administrativo()
        elif current_section_key_to_display == "max_pesquisa_mercado":
            agente.exibir_max_pesquisa_mercado()
        elif current_section_key_to_display == "max_bussola":
            agente.exibir_max_bussola()
        elif current_section_key_to_display == "max_trainer_ia":
            agente.exibir_max_trainer()
    else:
        st.error("Agente Max IA não pôde ser carregado. Verifique os erros de inicialização.")

st.sidebar.markdown("---")
st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini Pro")
