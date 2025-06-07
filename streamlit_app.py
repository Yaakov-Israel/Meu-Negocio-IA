import streamlit as st
import os
import io
import json
import pyrebase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import AIMessage, HumanMessage
import google.generativeai as genai
from PIL import Image
import base64
import time
import datetime
import firebase_admin
from firebase_admin import credentials, firestore as firebase_admin_firestore

# Novas importações para gerar arquivos
from docx import Document
from fpdf import FPDF

# <<< ALTERAÇÃO 1: NOVA IMPORTAÇÃO DO NOSSO ARQUIVO DE UTILIDADES >>>
from utils import carregar_prompts_config

# --- Constantes ---
APP_KEY_SUFFIX = "maxia_app_v1.7_arch_refactor" # Versão incremental refletindo a mudança de arquitetura
USER_COLLECTION = "users"

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# <<< ALTERAÇÃO 2: CARREGAR A CONFIGURAÇÃO DE PROMPTS UMA VEZ NA INICIALIZAÇÃO >>>
PROMPTS_CONFIG = carregar_prompts_config()


# --- Funções Auxiliares Globais ---
def convert_image_to_base64(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        print(f"ERRO convert_image_to_base64: {e}")
    return None

def gerar_arquivo_download(conteudo, formato):
    """Gera o conteúdo de um arquivo em memória para download."""
    if formato == "txt":
        return io.BytesIO(conteudo.encode("utf-8"))
        
    elif formato == "docx":
        document = Document()
        document.add_paragraph(conteudo)
        bio = io.BytesIO()
        document.save(bio)
        bio.seek(0)
        return bio

    elif formato == "pdf":
        pdf = FPDF()
        pdf.add_page()
        
        # <<< ALTERAÇÃO 3: CORREÇÃO DO CAMINHO DA FONTE PARA O PDF >>>
        # Garanta que você tenha a pasta "fonts" na raiz do seu projeto com "DejaVuSans.ttf" dentro.
        caminho_fonte = 'fonts/DejaVuSans.ttf'
        
        try:
            pdf.add_font('DejaVu', '', caminho_fonte, uni=True)
            pdf.set_font('DejaVu', '', 12)
        except RuntimeError:
            print(f"AVISO: Fonte '{caminho_fonte}' não encontrada. Usando 'Arial' como fallback.")
            pdf.set_font("Arial", size=12)

        pdf.multi_cell(0, 10, txt=conteudo.encode('latin-1', 'replace').decode('latin-1'))
        
        return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

    return None

# --- Configuração da Página ---
try:
    page_icon_img_obj = Image.open("images/carinha-agente-max-ia.png") if os.path.exists("images/carinha-agente-max-ia.png") else "🤖"
except Exception:
    page_icon_img_obj = "🤖"
st.set_page_config(page_title="Max IA", page_icon=page_icon_img_obj, layout="wide", initial_sidebar_state="expanded")

# --- INICIALIZAÇÃO E AUTENTICAÇÃO (Estrutura Robusta Mantida) ---
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

llm = None
if user_is_authenticated:
    llm_key = f'{APP_KEY_SUFFIX}_llm_instance'
    if llm_key not in st.session_state:
        try:
            api_key = st.secrets.get("GOOGLE_API_KEY")
            if api_key:
                st.session_state[llm_key] = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key, temperature=0.7)
            else:
                st.error("Chave GOOGLE_API_KEY não configurada nos segredos.")
        except Exception as e: st.error(f"Erro ao inicializar LLM: {e}")
    llm = st.session_state.get(llm_key)

# --- Definição da Classe MaxAgente ---
class MaxAgente:
    def __init__(self, llm_instance, db_firestore_instance):
        self.llm = llm_instance
        self.db = db_firestore_instance
        if not self.llm: st.warning("MaxAgente: LLM não disponível.")
        if not self.db: st.warning("MaxAgente: Firestore não disponível.")

    def exibir_painel_boas_vindas(self):
        st.markdown("<div style='text-align: center;'><h1>👋 Bem-vindo ao Max IA!</h1></div>", unsafe_allow_html=True)
        logo_base64 = convert_image_to_base64('images/max-ia-logo.png')
        if logo_base64:
            st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{logo_base64}' width='200'></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.2em;'>Olá! Eu sou o <strong>Max</strong>, seu conjunto de agentes de IA dedicados a impulsionar o sucesso da sua Pequena ou Média Empresa.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para selecionar um agente especializado e começar a transformar seu negócio hoje mesmo.</p></div>", unsafe_allow_html=True)
        st.balloons()

    def exibir_max_marketing_total(self):
        st.header("🚀 MaxMarketing Total")
        st.caption("Seu copiloto Max IA para criar estratégias, posts, campanhas e mais!")
        st.markdown("---")
        
        session_key_post = f"marketing_post_content_{APP_KEY_SUFFIX}"
        if session_key_post not in st.session_state:
            st.session_state[session_key_post] = None

        opcoes_marketing = ["Criar post", "Criar campanha", "Detalhar campanha"]
        acao_selecionada = st.radio("O que vamos criar hoje?", opcoes_marketing, key=f"mkt_radio_{APP_KEY_SUFFIX}")

        if acao_selecionada == "Criar post":
            if st.session_state[session_key_post]:
                st.subheader("🎉 Post Gerado pelo Max IA!")
                conteudo_post = st.session_state[session_key_post]
                st.markdown(conteudo_post)
                st.markdown("---")

                st.subheader("📥 Baixar Conteúdo")
                col1, col2 = st.columns([0.7, 0.3])
                
                with col1:
                    formato_escolhido = st.selectbox(
                        "Escolha o formato do arquivo:",
                        ("txt", "docx", "pdf"),
                        key=f"download_format_{APP_KEY_SUFFIX}"
                    )
                
                with col2:
                    st.write("") 
                    st.write("") 
                    try:
                        arquivo_bytes = gerar_arquivo_download(conteudo_post, formato_escolhido)
                        if arquivo_bytes:
                            st.download_button(
                               label=f"Baixar como .{formato_escolhido}",
                               data=arquivo_bytes,
                               file_name=f"post_max_ia.{formato_escolhido}",
                               use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Erro ao gerar arquivo para download: {e}")

                st.markdown("---")
                if st.button("✨ Criar Novo Post"):
                    st.session_state[session_key_post] = None
                    st.rerun()
            else:
                st.subheader("📝 Briefing para Criação de Post")
                st.write("Por favor, preencha os campos abaixo para que eu possa criar o melhor post para você.")
                with st.form(key=f"post_briefing_form_{APP_KEY_SUFFIX}"):
                    objetivo = st.text_area("1) Qual o objetivo do seu post?")
                    publico = st.text_input("2) Quem você quer alcançar?")
                    produto_servico = st.text_area("3) Qual produto ou serviço principal você está promovendo?")
                    mensagem_chave = st.text_area("4) Qual mensagem chave você quer comunicar?")
                    usp = st.text_area("5) O que torna seu produto/serviço especial (USP - Proposta Única de Venda)?")
                    tom_estilo = st.selectbox("6) Qual o tom/estilo da comunicação?",("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"))
                    info_adicional = st.text_area("7) Alguma informação adicional/CTA (Chamada para Ação)?")
                    
                    submitted = st.form_submit_button("💡 Gerar Post com Max IA!")
                    if submitted:
                        if not objetivo:
                            st.warning("Por favor, preencha pelo menos o objetivo do post.")
                        
                        # <<< ALTERAÇÃO 4: LÓGICA DE GERAÇÃO DE PROMPT TOTALMENTE REATORADA >>>
                        elif not PROMPTS_CONFIG:
                             st.error("A configuração de prompts não foi carregada. Não é possível gerar o post.")
                        else:
                            with st.spinner("🤖 Max IA está criando a mágica... Aguarde!"):
                                try:
                                    # Pega o template do nosso arquivo JSON
                                    mkt_config = PROMPTS_CONFIG['agentes']['max_marketing']['tarefas']['criar_post']
                                    prompt_template = mkt_config['prompt_template']
                                    
                                    # Formata o template com os dados do formulário
                                    prompt_para_ia = prompt_template.format(
                                        instrucao=mkt_config['instrucao'],
                                        formato_saida=mkt_config['formato_saida'],
                                        objetivo=objetivo,
                                        publico=publico,
                                        produto_servico=produto_servico,
                                        mensagem_chave=mensagem_chave,
                                        usp=usp,
                                        tom_estilo=tom_estilo,
                                        info_adicional=info_adicional
                                    )

                                    if self.llm:
                                        resposta_ia = self.llm.invoke(prompt_para_ia)
                                        st.session_state[session_key_post] = resposta_ia.content
                                        st.rerun()
                                    else:
                                        st.error("O modelo de linguagem (LLM) não está disponível.")
                                except KeyError as e:
                                    st.error(f"Erro de configuração: A chave {e} não foi encontrada no arquivo prompts.json.")
                                except Exception as e:
                                    st.error(f"Ocorreu um erro ao contatar a IA: {e}")
        else:
            st.info(f"A funcionalidade '{acao_selecionada}' está em nossa fila de construção. Em breve estará disponível!")

    # Demais agentes (placeholders por enquanto)
    def exibir_max_financeiro(self):
        st.header("💰 MaxFinanceiro")
        st.info("Em breve: ferramentas para cálculo de preços, análise de custos e projeções financeiras.")
    def exibir_max_administrativo(self):
        st.header("⚙️ MaxAdministrativo")
        st.info("Em breve: otimização de fluxo de trabalho, análise SWOT e gestão de tarefas.")
    def exibir_max_pesquisa_mercado(self):
        st.header("📈 MaxPesquisa de Mercado")
        st.info("Em breve: análise de concorrência, tendências de mercado e perfil de cliente ideal.")
    def exibir_max_bussola(self):
        st.header("🧭 MaxBússola Estratégica")
        st.info("Em breve: construção de plano de negócios e sessões de brainstorming para novas ideias.")
    def exibir_max_trainer(self):
        st.header("🎓 MaxTrainer IA")
        st.info("Em breve: tutoriais e dicas para você extrair o máximo da inteligência artificial para o seu negócio.")


# --- Instanciação e Interface Principal ---
if user_is_authenticated:
    if 'agente' not in st.session_state:
        if llm and firestore_db:
            st.session_state.agente = MaxAgente(llm_instance=llm, db_firestore_instance=firestore_db)
    agente = st.session_state.get('agente')
    if agente:
        st.sidebar.title("Max IA")
        st.sidebar.markdown("Seu Agente IA para Maximizar Resultados!")
        st.sidebar.markdown("---")
        st.sidebar.write(f"Logado como: **{user_email}**")
        if st.sidebar.button("Logout", key=f"{APP_KEY_SUFFIX}_logout"):
            keys_to_del = list(st.session_state.keys())
            for k in keys_to_del: del st.session_state[k]
            st.rerun()
        opcoes_menu = {
            "👋 Bem-vindo ao Max IA": agente.exibir_painel_boas_vindas,
            "🚀 MaxMarketing Total": agente.exibir_max_marketing_total,
            "💰 MaxFinanceiro": agente.exibir_max_financeiro,
            "⚙️ MaxAdministrativo": agente.exibir_max_administrativo,
            "📈 MaxPesquisa de Mercado": agente.exibir_max_pesquisa_mercado,
            "🧭 MaxBússola Estratégica": agente.exibir_max_bussola,
            "🎓 MaxTrainer IA": agente.exibir_max_trainer
        }
        selecao_label = st.sidebar.radio("Max Agentes IA:", list(opcoes_menu.keys()), key=f"main_nav_{APP_KEY_SUFFIX}")
        
        # Verifica se o agente e as configurações de prompt estão prontos antes de chamar a função
        if PROMPTS_CONFIG:
            funcao_do_agente = opcoes_menu[selecao_label]
            funcao_do_agente()
        else:
            st.error("A aplicação não pode ser iniciada porque o arquivo de configuração de prompts não foi carregado corretamente.")

    else:
        st.error("Agente Max IA não pôde ser carregado. Verifique os segredos da aplicação e a conexão.")
else:
    # --- TELA DE LOGIN ---
    st.title("🔑 Bem-vindo ao Max IA")
    st.info("Faça login ou registre-se na barra lateral para começar.")
    logo_base64 = convert_image_to_base64('images/max-ia-logo.png')
    if logo_base64: st.image(f"data:image/png;base64,{logo_base64}", width=200)
    auth_action = st.sidebar.radio("Acesso:", ["Login", "Registrar"], key=f"{APP_KEY_SUFFIX}_auth_choice")
    if auth_action == "Login":
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                try:
                    user_creds = pb_auth_client.sign_in_with_email_and_password(email, password)
                    st.session_state[f'{APP_KEY_SUFFIX}_user_session_data'] = dict(user_creds)
                    st.rerun()
                except Exception:
                    st.sidebar.error("Erro no login. Verifique as credenciais ou registre-se.")
    else:
        with st.sidebar.form(f"{APP_KEY_SUFFIX}_register_form"):
            email = st.text_input("Seu Email")
            password = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
            if st.form_submit_button("Registrar Conta"):
                if email and len(password) >= 6:
                    try:
                        new_user = pb_auth_client.create_user_with_email_and_password(email, password)
                        user_doc = firestore_db.collection(USER_COLLECTION).document(new_user['localId'])
                        user_doc.set({"email": email, "registration_date": firebase_admin_firestore.SERVER_TIMESTAMP}, merge=True)
                        st.sidebar.success("Conta criada! Por favor, faça o login.")
                    except Exception:
                        st.sidebar.error("Erro no registro. O e-mail pode já estar em uso.")
                else:
                    st.sidebar.warning("Preencha todos os campos corretamente.")
st.sidebar.markdown("---")
st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini")
