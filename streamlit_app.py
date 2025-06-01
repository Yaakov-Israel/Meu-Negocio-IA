firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False
auth_exception_object = None 

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]
        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
        else:
            if 'firebase_app_instance_main' not in st.session_state: 
                st.session_state.firebase_app_instance_main = pyrebase.initialize_app(plain_firebase_config_dict)
            firebase_app = st.session_state.firebase_app_instance_main
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_msg_main' not in st.session_state and not st.session_state.get('user_session_main_app'):
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_msg_main = True
except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb_main: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb_main}"
    auth_exception_object = e_attr_fb_main
except Exception as e_general_fb_main: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb_main}"
    auth_exception_object = e_general_fb_main

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object: st.exception(auth_exception_object)
    st.stop()
if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

SESSION_KEY_USER_APP = 'user_session_main_app' 
if SESSION_KEY_USER_APP not in st.session_state:
    st.session_state[SESSION_KEY_USER_APP] = None

user_is_authenticated = False
if st.session_state[SESSION_KEY_USER_APP] and 'idToken' in st.session_state[SESSION_KEY_USER_APP]:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state[SESSION_KEY_USER_APP]['idToken'])
        st.session_state[SESSION_KEY_USER_APP]['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown_app', None) 
    except Exception as e_session_app: 
        error_message_session_check_app = "Sessão inválida ou expirada."
        try:
            error_details_str_app = e_session_app.args[0] if len(e_session_app.args) > 0 else "{}"
            error_data_app = json.loads(error_details_str_app.replace("'", "\"")) 
            api_error_message_app = error_data_app.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO_APP")
            if "TOKEN_EXPIRED" in api_error_message_app or "INVALID_ID_TOKEN" in api_error_message_app:
                error_message_session_check_app = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check_app = f"Erro ao verificar sessão ({api_error_message_app}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check_app = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session_app)}"
        st.session_state[SESSION_KEY_USER_APP] = None 
        user_is_authenticated = False
        if 'auth_error_shown_app' not in st.session_state: 
            st.sidebar.warning(error_message_session_check_app)
            st.session_state.auth_error_shown_app = True
        
        rerun_flag_key_app = 'rerun_auth_fail_app_v1' 
        if not st.session_state.get(rerun_flag_key_app, False):
            st.session_state[rerun_flag_key_app] = True
            st.rerun()
        else:
            st.session_state.pop(rerun_flag_key_app, None)

if rerun_flag_key_app_check := st.session_state.get('rerun_auth_fail_app_v1'): # Python 3.8+
    st.session_state.pop('rerun_auth_fail_app_v1', None)
APP_FUNC_KEY_SUFFIX = "_app_v1" # Sufixo para esta nova fase de construção

if user_is_authenticated:
    st.session_state.pop('auth_error_shown_app', None) 
    display_email = st.session_state[SESSION_KEY_USER_APP].get('email', "Usuário Logado")
    
    LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png"
    FALLBACK_LOGO_URL_SIDEBAR = "https://i.imgur.com/7IIYxq1.png"
    try:
        st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
    except Exception:
        st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR, width=150, caption="Logo (Fallback)")

    st.sidebar.title("Assistente PME Pro")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    
    if st.sidebar.button("Logout", key=f"logout_button_main_app{APP_FUNC_KEY_SUFFIX}"): 
        st.session_state[SESSION_KEY_USER_APP] = None
        st.session_state.pop('firebase_init_msg_main', None)
        st.session_state.pop('firebase_app_instance_main', None)
        st.session_state.pop('llm_init_success_msg_main_app_v1', None)
        # Limpar chaves de sessão específicas dos agentes no futuro
        st.rerun() 
    
    st.sidebar.markdown("---")

    # --- INICIALIZAÇÃO DO LLM (DENTRO DO BLOCO AUTENTICADO) ---
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None
    llm_init_error_msg = None

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        llm_init_error_msg = "ERRO CRÍTICO: GOOGLE_API_KEY não configurada nos Segredos."
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
            if 'llm_init_success_main_app_v1' not in st.session_state:
                st.sidebar.success("✅ Modelo LLM (Gemini) Pronto!")
                st.session_state.llm_init_success_main_app_v1 = True
        except Exception as e_llm_main_app:
            llm_init_error_msg = f"ERRO AO INICIALIZAR O MODELO LLM: {e_llm_main_app}"

    if llm_init_error_msg:
        st.error(llm_init_error_msg)
        # Não usamos st.stop() para permitir que o logout funcione
    
    if llm_model_instance:
        # --- DEFINIÇÃO DAS FUNÇÕES DOS AGENTES ---
        
        # Agente de Marketing Digital
        def _marketing_get_objective_details_md(section_key_md, type_of_creation_md="post"):
            st.subheader(f"Detalhes para: {type_of_creation_md.capitalize()}")
            details_md = {}
            details_md["objective"] = st.text_area("Principal objetivo?", key=f"{section_key_md}_obj{APP_FUNC_KEY_SUFFIX}")
            details_md["target_audience"] = st.text_input("Público-alvo?", key=f"{section_key_md}_aud{APP_FUNC_KEY_SUFFIX}")
            details_md["product_service"] = st.text_area("Produto/Serviço a promover?", key=f"{section_key_md}_prod{APP_FUNC_KEY_SUFFIX}")
            # Adicione mais campos conforme a necessidade de cada sub-função de marketing
            return details_md

        def _marketing_handle_criar_post_md(details_md, platforms_md, llm_md):
            if not platforms_md: st.warning("Selecione ao menos uma plataforma."); return
            if not details_md.get("objective"): st.warning("Descreva o objetivo."); return

            with st.spinner("🤖 Criando seu post..."):
                prompt_template_post = """
                Você é um especialista em copywriting e marketing digital para PMEs no Brasil.
                Crie um texto de post otimizado e engajador para as seguintes plataformas: {platforms}
                Considerando os seguintes detalhes:
                - Produto/Serviço Principal: {product_service}
                - Público-Alvo: {target_audience}
                - Objetivo do Post: {objective}
                Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes.
                Seja conciso e direto ao ponto.
                """
                prompt = ChatPromptTemplate.from_template(template=prompt_template_post)
                chain = LLMChain(llm=llm_md, prompt=prompt)
                
                try:
                    response = chain.invoke({
                        "platforms": ", ".join(platforms_md),
                        "product_service": details_md.get("product_service", "Não informado"),
                        "target_audience": details_md.get("target_audience", "Não informado"),
                        "objective": details_md.get("objective", "Não informado")
                    })
                    st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'] = response['text']
                except Exception as e_post_md:
                    st.error(f"Erro ao gerar post: {e_post_md}")
                    st.session_state.pop(f'marketing_post_output{APP_FUNC_KEY_SUFFIX}', None)

        def render_marketing_digital_section(llm_param):
            st.title("🚀 Marketing Digital com IA")
            st.caption("Seu copiloto para criar estratégias e conteúdo!")
            
            opcoes_mkt = [
                "Selecione uma ação...",
                "1 - Criar post para redes sociais ou e-mail",
                "2 - Criar campanha de marketing completa (Em Breve)",
                "3 - Criar estrutura e conteúdo para landing page (Em Breve)",
                "4 - Criar estrutura e conteúdo para site com IA (Em Breve)",
                "5 - Encontrar meu cliente ideal (Análise de Público-Alvo) (Em Breve)",
                "6 - Conhecer a concorrência (Análise Competitiva) (Em Breve)"
            ]
            sub_action_mkt_key = f"mkt_sub_action_radio{APP_FUNC_KEY_SUFFIX}"
            if sub_action_mkt_key not in st.session_state:
                st.session_state[sub_action_mkt_key] = opcoes_mkt[0]

            sub_action = st.radio("Olá! O que você quer fazer agora em marketing digital?", 
                                  opcoes_mkt, key=sub_action_mkt_key)

            if sub_action == "1 - Criar post para redes sociais ou e-mail":
                st.markdown("---")
                st.subheader("✨ Criador de Posts com IA")
                
                platforms_options_post = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp"}
                
                with st.form(f"post_form{APP_FUNC_KEY_SUFFIX}"):
                    details_post = _marketing_get_objective_details_md(f"post_creator{APP_FUNC_KEY_SUFFIX}", "post")
                    st.write("**Plataformas Desejadas:**")
                    cols_platforms = st.columns(len(platforms_options_post))
                    selected_platforms_post = []
                    for i, (plat_name, plat_key_suffix) in enumerate(platforms_options_post.items()):
                        if cols_platforms[i].checkbox(plat_name, key=f"post_plat_{plat_key_suffix}{APP_FUNC_KEY_SUFFIX}"):
                            selected_platforms_post.append(plat_name)
                    
                    submitted_post = st.form_submit_button("💡 Gerar Post!")

                if submitted_post:
                    _marketing_handle_criar_post_md(details_post, selected_platforms_post, llm_param)
                
                if f'marketing_post_output{APP_FUNC_KEY_SUFFIX}' in st.session_state:
                    st.subheader("🎉 Post Sugerido pela IA:")
                    st.markdown(st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'])
                    st.download_button("📥 Baixar Post", st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'].encode('utf-8'), 
                                      f"post_ia_{APP_FUNC_KEY_SUFFIX}.txt", "text/plain", key=f"download_post_mkt{APP_FUNC_KEY_SUFFIX}")
            
            elif sub_action != "Selecione uma ação...":
                st.info(f"Funcionalidade '{sub_action}' em desenvolvimento.")
        
        # --- Lógica de Navegação Principal (Sidebar) ---
        # (Vamos simplificar a navegação por enquanto e focar em uma seção)
        st.sidebar.markdown("### Ferramentas de IA")
        
        app_tool_choice = st.sidebar.radio(
            "Escolha a ferramenta:",
            ("Marketing Digital", "Plano de Negócios (Em Breve)", "Cálculo de Preços (Em Breve)", "Gerador de Ideias (Em Breve)", "Controle de Estoque (Em Breve)", "Controle Financeiro (Em Breve)"),
            key=f"app_tool_choice_radio{APP_FUNC_KEY_SUFFIX}"
        )

        if app_tool_choice == "Marketing Digital":
            render_marketing_digital_section(llm_model_instance)
        # Adicionar outros elif para as demais ferramentas quando formos construí-las
        # elif app_tool_choice == "Plano de Negócios (Em Breve)":
        #     st.title("📝 Plano de Negócios com IA")
        #     st.info("Em desenvolvimento...")
        else:
            # Página Inicial Padrão se outra ferramenta selecionada (ou nenhuma)
            st.title("🚀 Assistente PME Pro")
            st.header("Bem-vindo(a) de Volta!")
            st.markdown("Selecione uma ferramenta na barra lateral para começar.")
            # NENHUM LOGO AQUI, conforme solicitado

    else: # Se llm_model_instance não foi inicializado ou houve erro
        st.title("🚀 Assistente PME Pro")
        st.error("🚨 Falha na inicialização do sistema de IA.")
        st.info("Verifique as configurações da API Key do Google nos segredos do aplicativo ou o status da API no Google Cloud.")
        if llm_init_exception:
            st.exception(llm_init_exception)

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: 
    st.session_state.pop('auth_error_shown_app', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key_final = f"auth_action_radio_final_v2" # Nova chave
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key_final)

    if auth_action_choice == "Login":
        with st.sidebar.form(f"login_form_final_v2"): 
            login_email = st.text_input("Email", key=f"login_email_final_v2")
            login_password = st.text_input("Senha", type="password", key=f"login_pass_final_v2")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state[SESSION_KEY_USER_APP] = dict(user_session)
                        st.session_state.pop('firebase_init_msg_main', None)
                        st.rerun()
                    except Exception as e_login_app:
                        error_message_login_app = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_app_l = e_login_app.args[0] if len(e_login_app.args) > 0 else "{}"
                            error_data_app_l = json.loads(error_details_str_app_l.replace("'", "\""))
                            api_error_message_app_l = error_data_app_l.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_app_l or "EMAIL_NOT_FOUND" in api_error_message_app_l or "INVALID_PASSWORD" in api_error_message_app_l or "USER_DISABLED" in api_error_message_app_l or "INVALID_EMAIL" in api_error_message_app_l:
                                error_message_login_app = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_app_l: error_message_login_app = f"Erro no login: {api_error_message_app_l}"
                        except: pass 
                        st.sidebar.error(error_message_login_app)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"register_form_final_v2"): 
            reg_email = st.text_input("Email para registro", key=f"reg_email_final_v2")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key=f"reg_pass_final_v2")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_app: 
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_app}")
                    except Exception as e_register_app:
                        error_message_register_app = "Erro no registro."
                        try:
                            error_details_str_reg_app = e_register_app.args[0] if len(e_register_app.args) > 0 else "{}"
                            error_data_reg_app = json.loads(error_details_str_reg_app.replace("'", "\""))
                            api_error_message_reg_app = error_data_reg_app.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_app:
                                error_message_register_app = "Este email já está registrado. Tente fazer login."
                            elif api_error_message_reg_app:
                                error_message_register_app = f"Erro no registro: {api_error_message_reg_app}"
                        except: 
                             error_message_register_app = f"Erro no registro: {str(e_register_app)}"
                        st.sidebar.error(error_message_register_app)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN_UNAUTH_FINAL = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN_UNAUTH_FINAL = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN_UNAUTH_FINAL, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN_UNAUTH_FINAL, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
import streamlit as st
import json 
import pyrebase 
from PIL import Image 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
from langchain.schema import HumanMessage
import google.generativeai as genai

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="🚀" 
)
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False
auth_exception_object = None 

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]
        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
        else:
            if 'firebase_app_instance_main' not in st.session_state: 
                st.session_state.firebase_app_instance_main = pyrebase.initialize_app(plain_firebase_config_dict)
            firebase_app = st.session_state.firebase_app_instance_main
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_msg_main' not in st.session_state and not st.session_state.get('user_session_main_app'):
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_msg_main = True
except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb_main: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb_main}"
    auth_exception_object = e_attr_fb_main
except Exception as e_general_fb_main: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb_main}"
    auth_exception_object = e_general_fb_main

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object: st.exception(auth_exception_object)
    st.stop()
if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

SESSION_KEY_USER_APP = 'user_session_main_app' 
if SESSION_KEY_USER_APP not in st.session_state:
    st.session_state[SESSION_KEY_USER_APP] = None

user_is_authenticated = False
if st.session_state[SESSION_KEY_USER_APP] and 'idToken' in st.session_state[SESSION_KEY_USER_APP]:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state[SESSION_KEY_USER_APP]['idToken'])
        st.session_state[SESSION_KEY_USER_APP]['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown_app', None) 
    except Exception as e_session_app: 
        error_message_session_check_app = "Sessão inválida ou expirada."
        try:
            error_details_str_app = e_session_app.args[0] if len(e_session_app.args) > 0 else "{}"
            error_data_app = json.loads(error_details_str_app.replace("'", "\"")) 
            api_error_message_app = error_data_app.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO_APP")
            if "TOKEN_EXPIRED" in api_error_message_app or "INVALID_ID_TOKEN" in api_error_message_app:
                error_message_session_check_app = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check_app = f"Erro ao verificar sessão ({api_error_message_app}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check_app = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session_app)}"
        st.session_state[SESSION_KEY_USER_APP] = None 
        user_is_authenticated = False
        if 'auth_error_shown_app' not in st.session_state: 
            st.sidebar.warning(error_message_session_check_app)
            st.session_state.auth_error_shown_app = True
        
        rerun_flag_key_app = 'rerun_auth_fail_app_v1' 
        if not st.session_state.get(rerun_flag_key_app, False):
            st.session_state[rerun_flag_key_app] = True
            st.rerun()
        else:
            st.session_state.pop(rerun_flag_key_app, None)

if rerun_flag_key_app_check := st.session_state.get('rerun_auth_fail_app_v1'): # Python 3.8+
    st.session_state.pop('rerun_auth_fail_app_v1', None)
APP_FUNC_KEY_SUFFIX = "_app_v1" # Sufixo para esta nova fase de construção

if user_is_authenticated:
    st.session_state.pop('auth_error_shown_app', None) 
    display_email = st.session_state[SESSION_KEY_USER_APP].get('email', "Usuário Logado")
    
    LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png"
    FALLBACK_LOGO_URL_SIDEBAR = "https://i.imgur.com/7IIYxq1.png"
    try:
        st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
    except Exception:
        st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR, width=150, caption="Logo (Fallback)")

    st.sidebar.title("Assistente PME Pro")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    
    if st.sidebar.button("Logout", key=f"logout_button_main_app{APP_FUNC_KEY_SUFFIX}"): 
        st.session_state[SESSION_KEY_USER_APP] = None
        st.session_state.pop('firebase_init_msg_main', None)
        st.session_state.pop('firebase_app_instance_main', None)
        st.session_state.pop('llm_init_success_msg_main_app_v1', None)
        # Limpar chaves de sessão específicas dos agentes no futuro
        st.rerun() 
    
    st.sidebar.markdown("---")

    # --- INICIALIZAÇÃO DO LLM (DENTRO DO BLOCO AUTENTICADO) ---
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None
    llm_init_error_msg = None

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        llm_init_error_msg = "ERRO CRÍTICO: GOOGLE_API_KEY não configurada nos Segredos."
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
            if 'llm_init_success_main_app_v1' not in st.session_state:
                st.sidebar.success("✅ Modelo LLM (Gemini) Pronto!")
                st.session_state.llm_init_success_main_app_v1 = True
        except Exception as e_llm_main_app:
            llm_init_error_msg = f"ERRO AO INICIALIZAR O MODELO LLM: {e_llm_main_app}"

    if llm_init_error_msg:
        st.error(llm_init_error_msg)
        # Não usamos st.stop() para permitir que o logout funcione
    
    if llm_model_instance:
        # --- DEFINIÇÃO DAS FUNÇÕES DOS AGENTES ---
        
        # Agente de Marketing Digital
        def _marketing_get_objective_details_md(section_key_md, type_of_creation_md="post"):
            st.subheader(f"Detalhes para: {type_of_creation_md.capitalize()}")
            details_md = {}
            details_md["objective"] = st.text_area("Principal objetivo?", key=f"{section_key_md}_obj{APP_FUNC_KEY_SUFFIX}")
            details_md["target_audience"] = st.text_input("Público-alvo?", key=f"{section_key_md}_aud{APP_FUNC_KEY_SUFFIX}")
            details_md["product_service"] = st.text_area("Produto/Serviço a promover?", key=f"{section_key_md}_prod{APP_FUNC_KEY_SUFFIX}")
            # Adicione mais campos conforme a necessidade de cada sub-função de marketing
            return details_md

        def _marketing_handle_criar_post_md(details_md, platforms_md, llm_md):
            if not platforms_md: st.warning("Selecione ao menos uma plataforma."); return
            if not details_md.get("objective"): st.warning("Descreva o objetivo."); return

            with st.spinner("🤖 Criando seu post..."):
                prompt_template_post = """
                Você é um especialista em copywriting e marketing digital para PMEs no Brasil.
                Crie um texto de post otimizado e engajador para as seguintes plataformas: {platforms}
                Considerando os seguintes detalhes:
                - Produto/Serviço Principal: {product_service}
                - Público-Alvo: {target_audience}
                - Objetivo do Post: {objective}
                Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes.
                Seja conciso e direto ao ponto.
                """
                prompt = ChatPromptTemplate.from_template(template=prompt_template_post)
                chain = LLMChain(llm=llm_md, prompt=prompt)
                
                try:
                    response = chain.invoke({
                        "platforms": ", ".join(platforms_md),
                        "product_service": details_md.get("product_service", "Não informado"),
                        "target_audience": details_md.get("target_audience", "Não informado"),
                        "objective": details_md.get("objective", "Não informado")
                    })
                    st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'] = response['text']
                except Exception as e_post_md:
                    st.error(f"Erro ao gerar post: {e_post_md}")
                    st.session_state.pop(f'marketing_post_output{APP_FUNC_KEY_SUFFIX}', None)

        def render_marketing_digital_section(llm_param):
            st.title("🚀 Marketing Digital com IA")
            st.caption("Seu copiloto para criar estratégias e conteúdo!")
            
            opcoes_mkt = [
                "Selecione uma ação...",
                "1 - Criar post para redes sociais ou e-mail",
                "2 - Criar campanha de marketing completa (Em Breve)",
                "3 - Criar estrutura e conteúdo para landing page (Em Breve)",
                "4 - Criar estrutura e conteúdo para site com IA (Em Breve)",
                "5 - Encontrar meu cliente ideal (Análise de Público-Alvo) (Em Breve)",
                "6 - Conhecer a concorrência (Análise Competitiva) (Em Breve)"
            ]
            sub_action_mkt_key = f"mkt_sub_action_radio{APP_FUNC_KEY_SUFFIX}"
            if sub_action_mkt_key not in st.session_state:
                st.session_state[sub_action_mkt_key] = opcoes_mkt[0]

            sub_action = st.radio("Olá! O que você quer fazer agora em marketing digital?", 
                                  opcoes_mkt, key=sub_action_mkt_key)

            if sub_action == "1 - Criar post para redes sociais ou e-mail":
                st.markdown("---")
                st.subheader("✨ Criador de Posts com IA")
                
                platforms_options_post = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp"}
                
                with st.form(f"post_form{APP_FUNC_KEY_SUFFIX}"):
                    details_post = _marketing_get_objective_details_md(f"post_creator{APP_FUNC_KEY_SUFFIX}", "post")
                    st.write("**Plataformas Desejadas:**")
                    cols_platforms = st.columns(len(platforms_options_post))
                    selected_platforms_post = []
                    for i, (plat_name, plat_key_suffix) in enumerate(platforms_options_post.items()):
                        if cols_platforms[i].checkbox(plat_name, key=f"post_plat_{plat_key_suffix}{APP_FUNC_KEY_SUFFIX}"):
                            selected_platforms_post.append(plat_name)
                    
                    submitted_post = st.form_submit_button("💡 Gerar Post!")

                if submitted_post:
                    _marketing_handle_criar_post_md(details_post, selected_platforms_post, llm_param)
                
                if f'marketing_post_output{APP_FUNC_KEY_SUFFIX}' in st.session_state:
                    st.subheader("🎉 Post Sugerido pela IA:")
                    st.markdown(st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'])
                    st.download_button("📥 Baixar Post", st.session_state[f'marketing_post_output{APP_FUNC_KEY_SUFFIX}'].encode('utf-8'), 
                                      f"post_ia_{APP_FUNC_KEY_SUFFIX}.txt", "text/plain", key=f"download_post_mkt{APP_FUNC_KEY_SUFFIX}")
            
            elif sub_action != "Selecione uma ação...":
                st.info(f"Funcionalidade '{sub_action}' em desenvolvimento.")
        
        # --- Lógica de Navegação Principal (Sidebar) ---
        # (Vamos simplificar a navegação por enquanto e focar em uma seção)
        st.sidebar.markdown("### Ferramentas de IA")
        
        app_tool_choice = st.sidebar.radio(
            "Escolha a ferramenta:",
            ("Marketing Digital", "Plano de Negócios (Em Breve)", "Cálculo de Preços (Em Breve)", "Gerador de Ideias (Em Breve)", "Controle de Estoque (Em Breve)", "Controle Financeiro (Em Breve)"),
            key=f"app_tool_choice_radio{APP_FUNC_KEY_SUFFIX}"
        )

        if app_tool_choice == "Marketing Digital":
            render_marketing_digital_section(llm_model_instance)
        # Adicionar outros elif para as demais ferramentas quando formos construí-las
        # elif app_tool_choice == "Plano de Negócios (Em Breve)":
        #     st.title("📝 Plano de Negócios com IA")
        #     st.info("Em desenvolvimento...")
        else:
            # Página Inicial Padrão se outra ferramenta selecionada (ou nenhuma)
            st.title("🚀 Assistente PME Pro")
            st.header("Bem-vindo(a) de Volta!")
            st.markdown("Selecione uma ferramenta na barra lateral para começar.")
            # NENHUM LOGO AQUI, conforme solicitado

    else: # Se llm_model_instance não foi inicializado ou houve erro
        st.title("🚀 Assistente PME Pro")
        st.error("🚨 Falha na inicialização do sistema de IA.")
        st.info("Verifique as configurações da API Key do Google nos segredos do aplicativo ou o status da API no Google Cloud.")
        if llm_init_exception:
            st.exception(llm_init_exception)

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: 
    st.session_state.pop('auth_error_shown_app', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key_final = f"auth_action_radio_final_v2" # Nova chave
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key_final)

    if auth_action_choice == "Login":
        with st.sidebar.form(f"login_form_final_v2"): 
            login_email = st.text_input("Email", key=f"login_email_final_v2")
            login_password = st.text_input("Senha", type="password", key=f"login_pass_final_v2")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state[SESSION_KEY_USER_APP] = dict(user_session)
                        st.session_state.pop('firebase_init_msg_main', None)
                        st.rerun()
                    except Exception as e_login_app:
                        error_message_login_app = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_app_l = e_login_app.args[0] if len(e_login_app.args) > 0 else "{}"
                            error_data_app_l = json.loads(error_details_str_app_l.replace("'", "\""))
                            api_error_message_app_l = error_data_app_l.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_app_l or "EMAIL_NOT_FOUND" in api_error_message_app_l or "INVALID_PASSWORD" in api_error_message_app_l or "USER_DISABLED" in api_error_message_app_l or "INVALID_EMAIL" in api_error_message_app_l:
                                error_message_login_app = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_app_l: error_message_login_app = f"Erro no login: {api_error_message_app_l}"
                        except: pass 
                        st.sidebar.error(error_message_login_app)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"register_form_final_v2"): 
            reg_email = st.text_input("Email para registro", key=f"reg_email_final_v2")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key=f"reg_pass_final_v2")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_app: 
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_app}")
                    except Exception as e_register_app:
                        error_message_register_app = "Erro no registro."
                        try:
                            error_details_str_reg_app = e_register_app.args[0] if len(e_register_app.args) > 0 else "{}"
                            error_data_reg_app = json.loads(error_details_str_reg_app.replace("'", "\""))
                            api_error_message_reg_app = error_data_reg_app.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_app:
                                error_message_register_app = "Este email já está registrado. Tente fazer login."
                            elif api_error_message_reg_app:
                                error_message_register_app = f"Erro no registro: {api_error_message_reg_app}"
                        except: 
                             error_message_register_app = f"Erro no registro: {str(e_register_app)}"
                        st.sidebar.error(error_message_register_app)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN_UNAUTH_FINAL = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN_UNAUTH_FINAL = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN_UNAUTH_FINAL, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN_UNAUTH_FINAL, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
