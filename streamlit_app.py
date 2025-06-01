import streamlit as st
import json 
import pyrebase 
from PIL import Image 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate # Apenas ChatPromptTemplate para este exemplo
from langchain.chains import LLMChain
from langchain.schema import HumanMessage
import google.generativeai as genai
APP_AGENT_KEY_SUFFIX = "_agente_v1_novo" 

def _marketing_get_objective_details_v1(section_key_agent, type_of_creation_md="post"):
    st.subheader(f"Detalhes para: {type_of_creation_md.capitalize()}")
    details_md = {}
    details_md["objective"] = st.text_area(f"Qual o principal objetivo com este {type_of_creation_md}?", key=f"{section_key_agent}_obj{APP_AGENT_KEY_SUFFIX}")
    details_md["target_audience"] = st.text_input("Público-alvo?", key=f"{section_key_agent}_aud{APP_AGENT_KEY_SUFFIX}")
    details_md["product_service"] = st.text_area("Produto/Serviço a promover?", key=f"{section_key_agent}_prod{APP_AGENT_KEY_SUFFIX}")
    details_md["key_message"] = st.text_area("Mensagem chave?", key=f"{section_key_agent}_msg{APP_AGENT_KEY_SUFFIX}")
    details_md["style_tone"] = st.selectbox("Tom/Estilo?", ("Profissional", "Amigável", "Criativo", "Urgente", "Engraçado", "Informativo"), key=f"{section_key_agent}_tone{APP_AGENT_KEY_SUFFIX}")
    return details_md

def _marketing_handle_criar_post_v1(details_md, platforms_md, llm_instance):
    if not platforms_md: 
        st.warning("Selecione ao menos uma plataforma.")
        return
    if not details_md.get("objective"): 
        st.warning("Descreva o objetivo do post.")
        return

    with st.spinner("🤖 Criando seu post..."):
        prompt_template_str = """
        Crie um texto de post para as seguintes plataformas: {platforms}.
        Detalhes:
        - Produto/Serviço: {product_service}
        - Público-Alvo: {target_audience}
        - Objetivo: {objective}
        - Mensagem Chave: {key_message}
        - Tom/Estilo: {style_tone}
        Inclua emojis e hashtags relevantes. Seja conciso.
        """
        prompt = ChatPromptTemplate.from_template(template=prompt_template_str)
        chain = LLMChain(llm=llm_instance, prompt=prompt)
        
        input_data = {
            "platforms": ", ".join(platforms_md),
            "product_service": details_md.get("product_service", "Não informado"),
            "target_audience": details_md.get("target_audience", "Não informado"),
            "objective": details_md.get("objective", "Não informado"),
            "key_message": details_md.get("key_message", "Não informado"),
            "style_tone": details_md.get("style_tone", "Neutro")
        }
        st.expander("🔍 Debug: Ver Input para LLMChain").write(input_data)
        st.expander("🔍 Debug: Ver Prompt Formatado").write(prompt.format_prompt(**input_data).to_string())

        try:
            response = chain.invoke(input_data)
            st.session_state[f'marketing_post_output{APP_AGENT_KEY_SUFFIX}'] = response['text']
        except Exception as e_post_md_v1:
            st.error(f"Erro ao gerar post: {e_post_md_v1}")
            st.text_area("Detalhe do Erro (para copiar):", str(e_post_md_v1), height=150)
            st.session_state.pop(f'marketing_post_output{APP_AGENT_KEY_SUFFIX}', None)

def render_marketing_digital_section_v1(llm_param):
    st.title("🚀 Marketing Digital com IA")
    
    opcoes_mkt_v1 = [
        "Selecione uma ação...",
        "1 - Criar post para redes sociais ou e-mail",
        "2 - Criar campanha de marketing completa (Em Breve)",
    ]
    sub_action_mkt_key_v1 = f"mkt_sub_action_radio{APP_AGENT_KEY_SUFFIX}"
    if sub_action_mkt_key_v1 not in st.session_state:
        st.session_state[sub_action_mkt_key_v1] = opcoes_mkt_v1[0]

    sub_action = st.radio("O que você quer fazer em marketing digital?", 
                          opcoes_mkt_v1, key=sub_action_mkt_key_v1)

    if sub_action == "1 - Criar post para redes sociais ou e-mail":
        st.markdown("---")
        st.subheader("✨ Criador de Posts")
        
        platforms_options_post_v1 = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x"}
        
        with st.form(f"post_form{APP_AGENT_KEY_SUFFIX}"):
            details_post_v1 = _marketing_get_objective_details_v1(f"post_creator{APP_AGENT_KEY_SUFFIX}", "post")
            st.write("**Plataformas:**")
            cols_platforms_v1 = st.columns(len(platforms_options_post_v1))
            selected_platforms_post_v1 = []
            for i, (plat_name, plat_key_suffix) in enumerate(platforms_options_post_v1.items()):
                if cols_platforms_v1[i].checkbox(plat_name, key=f"post_plat_{plat_key_suffix}{APP_AGENT_KEY_SUFFIX}"):
                    selected_platforms_post_v1.append(plat_name)
            
            submitted_post_v1 = st.form_submit_button("💡 Gerar Post")

        if submitted_post_v1:
            _marketing_handle_criar_post_v1(details_post_v1, selected_platforms_post_v1, llm_param)
        
        if f'marketing_post_output{APP_AGENT_KEY_SUFFIX}' in st.session_state:
            st.subheader("🎉 Post Sugerido:")
            st.markdown(st.session_state[f'marketing_post_output{APP_AGENT_KEY_SUFFIX}'])
            st.download_button("📥 Baixar", st.session_state[f'marketing_post_output{APP_AGENT_KEY_SUFFIX}'].encode('utf-8'), 
                              f"post_ia{APP_AGENT_KEY_SUFFIX}.txt", "text/plain", key=f"dl_post_mkt{APP_AGENT_KEY_SUFFIX}")
    
    elif sub_action != "Selecione uma ação...":
        st.info(f"Funcionalidade '{sub_action}' em desenvolvimento.")
if user_is_authenticated_skel: # No seu esqueleto, esta variável pode ser user_is_authenticated
    st.session_state.pop('auth_error_shown_skel', None) 
    display_email_skel = st.session_state[SESSION_KEY_USER_SKEL].get('email', "Usuário Logado")
    
    LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png"
    FALLBACK_LOGO_URL_SIDEBAR = "https://i.imgur.com/7IIYxq1.png"
    try:
        st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
    except Exception:
        st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR, width=150, caption="Logo (Fallback)")

    st.sidebar.title("Assistente PME Pro")
    st.sidebar.write(f"Bem-vindo(a), {display_email_skel}!")
    
    if st.sidebar.button("Logout", key="logout_button_skel_v2"): # Nova chave para logout
        st.session_state[SESSION_KEY_USER_SKEL] = None
        st.session_state.pop('firebase_init_success_msg_skel', None) # Mantido do seu esqueleto
        st.session_state.pop('firebase_app_instance_skeleton', None) # Mantido do seu esqueleto
        # Limpar chaves específicas desta nova fase
        st.session_state.pop(f"mkt_sub_action_radio{APP_AGENT_KEY_SUFFIX}", None)
        st.session_state.pop(f'marketing_post_output{APP_AGENT_KEY_SUFFIX}', None)
        # Adicionar mais chaves de limpeza conforme adicionamos funcionalidades
        st.rerun() 
    
    st.sidebar.markdown("---")
    
    # --- INICIALIZAÇÃO DO LLM ---
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance_main = None # Nova variável para a instância do LLM
    llm_init_error_msg_main = None

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        llm_init_error_msg_main = "ERRO: GOOGLE_API_KEY não configurada nos Segredos."
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance_main = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
            if 'llm_init_success_main_v2' not in st.session_state:
                st.sidebar.success("✅ Modelo LLM (Gemini) Pronto!")
                st.session_state.llm_init_success_main_v2 = True
        except Exception as e_llm_main_v2:
            llm_init_error_msg_main = f"ERRO AO INICIALIZAR O LLM: {e_llm_main_v2}"

    if llm_init_error_msg_main:
        st.error(llm_init_error_msg_main)
    
    if llm_model_instance_main:
        # --- NAVEGAÇÃO PRINCIPAL DO APLICATIVO (SIMPLIFICADA POR ENQUANTO) ---
        # No futuro, aqui teremos o st.sidebar.radio para escolher entre Marketing, Plano de Negócios etc.
        # Por agora, vamos direto para a seção de Marketing.
        
        render_marketing_digital_section_v1(llm_model_instance_main) # Chamando a função de marketing

    else: # Se o LLM não pôde ser inicializado
        st.title("🚀 Assistente PME Pro") # Título mesmo se LLM falhar
        st.error("🚨 Falha na inicialização do sistema de IA do aplicativo.")
        st.info("Verifique as configurações da API Key do Google ou o status da API no Google Cloud.")
        if llm_init_error_msg_main and 'e_llm_main_v2' in locals() : # Verifica se a exceção foi capturada
             st.exception(locals()['e_llm_main_v2'])


# O bloco 'else:' (para user_is_authenticated_skel == False) do seu esqueleto continua igual abaixo:
else: 
    st.session_state.pop('auth_error_shown_skel', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_skel_key = "auth_action_choice_skeleton_v2" # Nova chave
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_skel_key)

    if auth_action_choice == "Login":
        with st.sidebar.form("login_form_skeleton_v2"): 
            login_email = st.text_input("Email", key="login_email_skel_v2")
            login_password = st.text_input("Senha", type="password", key="login_pass_skel_v2")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state[SESSION_KEY_USER_SKEL] = dict(user_session)
                        st.session_state.pop('firebase_init_success_msg_skel', None)
                        st.rerun()
                    except Exception as e_login_skel_v2:
                        error_message_login_skel_v2 = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_skel_l_v2 = e_login_skel_v2.args[0] if len(e_login_skel_v2.args) > 0 else "{}"
                            error_data_skel_l_v2 = json.loads(error_details_str_skel_l_v2.replace("'", "\""))
                            api_error_message_skel_l_v2 = error_data_skel_l_v2.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_skel_l_v2 or "EMAIL_NOT_FOUND" in api_error_message_skel_l_v2 or "INVALID_PASSWORD" in api_error_message_skel_l_v2 or "USER_DISABLED" in api_error_message_skel_l_v2 or "INVALID_EMAIL" in api_error_message_skel_l_v2:
                                error_message_login_skel_v2 = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_skel_l_v2: error_message_login_skel_v2 = f"Erro no login: {api_error_message_skel_l_v2}"
                        except: pass 
                        st.sidebar.error(error_message_login_skel_v2)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("register_form_skeleton_v2"): 
            reg_email = st.text_input("Email para registro", key="reg_email_skel_v2")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password", key="reg_pass_skel_v2")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_skel_v2: 
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_skel_v2}")
                    except Exception as e_register_skel_v2:
                        error_message_register_skel_v2 = "Erro no registro."
                        try:
                            error_details_str_reg_skel_v2 = e_register_skel_v2.args[0] if len(e_register_skel_v2.args) > 0 else "{}"
                            error_data_reg_skel_v2 = json.loads(error_details_str_reg_skel_v2.replace("'", "\""))
                            api_error_message_reg_skel_v2 = error_data_reg_skel_v2.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_skel_v2:
                                error_message_register_skel_v2 = "Este email já está registrado. Tente fazer login."
                            elif api_error_message_reg_skel_v2:
                                error_message_register_skel_v2 = f"Erro no registro: {api_error_message_reg_skel_v2}"
                        except: 
                             error_message_register_skel_v2 = f"Erro no registro: {str(e_register_skel_v2)}"
                        st.sidebar.error(error_message_register_skel_v2)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN, width=200, caption="Logo (Fallback)")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
