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

# Tentativa de importação mais específica da classe FirebaseAuth e firebase_admin
from streamlit_firebase_auth.auth import FirebaseAuth
import firebase_admin
from firebase_admin import credentials

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

auth_manager = None
user_is_authenticated = False

try:
    firebase_creds_dict_from_secrets = st.secrets["firebase_config"]
    # Converter AttrDict para dict padrão, pois firebase_admin.credentials.Certificate espera um dict
    plain_firebase_config_dict = {k: v for k, v in firebase_creds_dict_from_secrets.items()}

    # Inicializar firebase_admin manualmente, APENAS SE NÃO JÁ INICIALIZADO
    if not firebase_admin._apps:
        cred = credentials.Certificate(plain_firebase_config_dict)
        firebase_admin.initialize_app(credential=cred)
    
    firebase_app_instance = firebase_admin.app() # Pega a instância do app Firebase padrão

    # Instanciar FirebaseAuth diretamente, passando o app Firebase e a configuração
    auth_manager = FirebaseAuth(
        app=firebase_app_instance,
        # A classe FirebaseAuth pode precisar da config original (como dict ou json string) também
        # para outras operações internas, dependendo da sua implementação.
        # A documentação/código fonte da lib é a melhor referência para os args exatos da classe.
        # No construtor da classe FirebaseAuth de joelfilho, ela espera:
        # app, credentials, cookie_name, cookie_key, cookie_expiry_days, use_session_storage
        # 'credentials' aqui é o service account JSON string, não o config de cliente.
        # Isso é um problema se a classe FirebaseAuth NÃO for projetada para ser usada sem o service account.
        # A função load_auth encapsula essa complexidade. Se load_auth não funciona, esta abordagem pode ter limitações.

        # Para a biblioteca de Joel Filho (streamlit-firebase-auth==1.0.6),
        # a classe FirebaseAuth usa o firebase_app para interagir com o SDK do cliente (pyrebase4)
        # e o firebase_admin para verificação de token, se necessário.
        # O serviceAccountJson (credentials_json_str) é usado para inicializar o cliente pyrebase4 dentro da classe.
        credentials_json=json.dumps(plain_firebase_config_dict), # Necessário para pyrebase4 dentro da FirebaseAuth
        cookie_name='firebase_token_v2', # Use um nome de cookie ligeiramente diferente para testar
        cookie_key='a_very_strong_secret_key_pme_pro_v2', # **IMPORTANTE: Mude para uma chave forte e única, idealmente dos segredos**
        cookie_expiry_days=30,
        use_session_storage=True 
    )

except KeyError:
    st.error("🚨 ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit.")
    st.stop()
except ValueError as ve:
    if "Could not deserializeراہ service account JSON" in str(ve) or "Invalid service account certificate" in str(ve) :
        st.error(f"🚨 ERRO DE CONFIGURAÇÃO FIREBASE: A configuração em '[firebase_config]' não parece ser um service account JSON válido ou está mal formatada para `firebase_admin.credentials.Certificate` ou para o cliente Pyrebase. Detalhe: {ve}")
        st.info("Para `firebase_admin`, geralmente um JSON de service account é necessário. Para autenticação de cliente (Pyrebase), o config de cliente é usado.")
    else:
        st.error(f"🚨 ERRO DE VALOR ao inicializar Firebase Auth: {ve}")
    st.exception(ve)
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO GERAL ao inicializar Firebase Auth manualmente: {e}")
    st.exception(e)
    st.stop()

if not auth_manager.is_logged_in():
    st.sidebar.subheader("Login / Registro")
    choice = st.sidebar.radio("Selecione uma ação:", ("Login", "Registrar Novo Usuário"), key="auth_choice_v3")

    if choice == "Login":
        with st.sidebar.form("login_form_sfa_main_v3"):
            email = st.text_input("Email", key="login_email_v3")
            password = st.text_input("Senha", type="password", key="login_password_v3")
            submit_login = st.form_submit_button("Login")

            if submit_login:
                if email and password:
                    try:
                        user_record = auth_manager.sign_in_with_email_and_password(email, password)
                        if user_record:
                            st.experimental_rerun()
                        else:
                            st.sidebar.error("Login falhou. Verifique suas credenciais.")
                    except Exception as e:
                        st.sidebar.error(f"Erro no login: {e}")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif choice == "Registrar Novo Usuário":
        with st.sidebar.form("register_form_sfa_main_v3"):
            reg_email = st.text_input("Email para registro", key="reg_email_v3")
            reg_password = st.text_input("Senha para registro", type="password", key="reg_password_v3")
            reg_display_name = st.text_input("Seu nome (opcional)", key="reg_display_name_v3")
            submit_register = st.form_submit_button("Registrar")

            if submit_register:
                if reg_email and reg_password:
                    try:
                        user_record = auth_manager.create_user_with_email_and_password(reg_email, reg_password, display_name=reg_display_name if reg_display_name else None)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Faça login.")
                    except Exception as e:
                        st.sidebar.error(f"Erro no registro: {e}")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha para registro.")

    st.info("Por favor, faça login ou registre-se para acessar o Assistente PME Pro.")
    st.stop()

user_is_authenticated = True
user_session_info = auth_manager.get_user_info()
display_name = user_session_info.get('displayName') or user_session_info.get('email', "Usuário")
st.sidebar.write(f"Bem-vindo, {display_name}!")
auth_manager.logout_button("Logout", key="sfa_logout_button_main_v3", location="sidebar")

if user_is_authenticated:
    GOOGLE_API_KEY = None
    llm_model_instance = None
    try:
        GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
        st.stop()

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("🚨 ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
        st.stop()
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
        except Exception as e:
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
            st.stop()

    if llm_model_instance:
        def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
            key_suffix = "_v16_final" 
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?",key=f"{section_key}_obj{key_suffix}")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{key_suffix}")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{key_suffix}")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{key_suffix}")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{key_suffix}")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?",("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"),key=f"{section_key}_tone{key_suffix}")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{key_suffix}")
            return details

        def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            key_suffix = "_v16_final"
            st.download_button(label="📥 Baixar Conteúdo Gerado",data=generated_content.encode('utf-8'),file_name=f"{file_name_prefix}_{section_key}{key_suffix}.txt",mime="text/plain",key=f"download_{section_key}{key_suffix}")
            cols_actions = st.columns(2)
            with cols_actions[0]:
                if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn{key_suffix}"):
                    st.success("Conteúdo pronto para ser copiado e compartilhado!")
            with cols_actions[1]:
                if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn{key_suffix}"):
                    st.info("Agendamento simulado.")

        def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
            with st.spinner("🤖 A IA está criando seu post..."):
                prompt_parts = ["**Instrução para IA:** Você é um especialista em copywriting e marketing digital para PMEs no Brasil...", f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.", f"**Produto/Serviço Principal:** {details_dict['product_service']}", f"**Público-Alvo:** {details_dict['target_audience']}", f"**Objetivo do Post:** {details_dict['objective']}", f"**Mensagem Chave:** {details_dict['key_message']}", f"**Proposta Única de Valor (USP):** {details_dict['usp']}", f"**Tom/Estilo:** {details_dict['style_tone']}", f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state.generated_post_content_new = ai_response.content

        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
            with st.spinner("🧠 A IA está elaborando seu plano de campanha..."):
                prompt_parts = ["**Instrução para IA:** Você é um estrategista de marketing digital experiente para PMEs no Brasil...", f"**Nome da Campanha:** {campaign_specifics['name']}", f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.", f"**Produto/Serviço Principal:** {details_dict['product_service']}", f"**Público-Alvo:** {details_dict['target_audience']}", f"**Objetivo Principal:** {details_dict['objective']}", f"**Mensagem Chave:** {details_dict['key_message']}", f"**USP:** {details_dict['usp']}", f"**Tom/Estilo:** {details_dict['style_tone']}", f"**Duração Estimada:** {campaign_specifics['duration']}", f"**Orçamento Aproximado:** {campaign_specifics['budget']}", f"**KPIs:** {campaign_specifics['kpis']}", f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state.generated_campaign_content_new = ai_response.content
        
        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
            with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
                prompt_parts = ["**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages...", f"**Objetivo da LP:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details['target_audience']}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Principais Benefícios:** {lp_details['key_benefits']}", f"**CTA Principal:** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details['visual_prefs']}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
                st.session_state.generated_lp_content_new = generated_content

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
            with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
                prompt_parts = ["**Instrução para IA:** Você é um arquiteto de informação e web designer experiente...", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Principal Objetivo:** {site_details['main_purpose']}", f"**Público-Alvo:** {site_details['target_audience']}", f"**Páginas Essenciais:** {site_details['essential_pages']}", f"**Principais Características:** {site_details['key_features']}", f"**Personalidade da Marca:** {site_details['brand_personality']}", f"**Referências Visuais:** {site_details['visual_references']}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
                st.session_state.generated_site_content_new = generated_content

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
            with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
                prompt_parts = ["**Instrução para IA:** Você é um 'Agente Detetive de Clientes'...", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details['location']}", f"**Verba:** {client_details['budget']}", f"**Faixa Etária/Gênero:** {client_details['age_gender']}", f"**Interesses:** {client_details['interests']}", f"**Canais Atuais:** {client_details['current_channels']}", f"**Nível de Pesquisa:** {'Deep Research Ativado' if client_details['deep_research'] else 'Pesquisa Padrão'}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
                st.session_state.generated_client_analysis_new = generated_content

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
            with st.spinner("🔬 A IA está analisando a concorrência..."):
                prompt_parts = ["**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva'...", f"**Seu Negócio:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
                st.session_state.generated_competitor_analysis_new = generated_content
        
        class AssistentePMEPro:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None: st.stop()
                self.llm = llm_passed_model
                if 'memoria_plano_negocios' not in st.session_state: st.session_state.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
                if 'memoria_calculo_precos' not in st.session_state: st.session_state.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)
                if 'memoria_gerador_ideias' not in st.session_state: st.session_state.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True)
                self.memoria_plano_negocios = st.session_state.memoria_plano_negocios
                self.memoria_calculo_precos = st.session_state.memoria_calculo_precos
                self.memoria_gerador_ideias = st.session_state.memoria_gerador_ideias

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
                prompt_template = ChatPromptTemplate.from_messages([SystemMessagePromptTemplate.from_template(system_message_content), MessagesPlaceholder(variable_name=memory_key_placeholder), HumanMessagePromptTemplate.from_template("{input_usuario}")])
                return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

            def marketing_digital_guiado(self):
                st.header("🚀 Marketing Digital Interativo com IA")
                st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
                st.markdown("---")
                marketing_files_info_for_prompt_local = [] 
                with st.sidebar: 
                    uploaded_marketing_files = st.file_uploader("Upload de arquivos de CONTEXTO para Marketing (opcional):", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'], key="marketing_files_uploader_v16")
                    if uploaded_marketing_files:
                        temp_marketing_files_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                        if temp_marketing_files_info:
                            marketing_files_info_for_prompt_local = temp_marketing_files_info 
                            st.success(f"{len(uploaded_marketing_files)} arquivo(s) de contexto carregado(s)!")
                            with st.expander("Ver arquivos de contexto"): [st.write(f"- {f['name']} ({f['type']})") for f in marketing_files_info_for_prompt_local]
                main_action_key = "main_marketing_action_choice_v16"
                opcoes_menu_marketing = {"Selecione uma opção...":0, "1 - Criar post para redes sociais ou e-mail":1, "2 - Criar campanha de marketing completa":2, "3 - Criar estrutura e conteúdo para landing page":3, "4 - Criar estrutura e conteúdo para site com IA":4, "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":5, "6 - Conhecer a concorrência (Análise Competitiva)":6}
                main_action = st.radio("Olá! O que você quer fazer agora em marketing digital?", list(opcoes_menu_marketing.keys()), index=st.session_state.get(f"{main_action_key}_index", 0), key=main_action_key, on_change=lambda: st.session_state.update({f"{main_action_key}_index": list(opcoes_menu_marketing.keys()).index(st.session_state[main_action_key]) if st.session_state[main_action_key] in opcoes_menu_marketing else 0}))
                st.markdown("---")
                platforms_config_options = {"Instagram":"insta", "Facebook":"fb", "X (Twitter)":"x", "WhatsApp":"wpp", "TikTok":"tt", "Kwai":"kwai", "YouTube (descrição/roteiro)":"yt", "E-mail Marketing (lista própria)":"email_own", "E-mail Marketing (Campanha Google Ads)":"email_google"}
                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com IA")
                    with st.form("post_creator_form_v16"):
                        st.subheader("Plataformas Desejadas:")
                        select_all_post_checked = st.checkbox("Selecionar Todas", key="post_v16_select_all")
                        cols_post = st.columns(2); selected_platforms_post_ui = []
                        for i, (p_name, p_sfx) in enumerate(platforms_config_options.items()):
                            with cols_post[i%2]:
                                if st.checkbox(p_name, key=f"post_v16_platform_{p_sfx}", value=select_all_post_checked): selected_platforms_post_ui.append(p_name)
                                if "E-mail Marketing" in p_name and st.session_state.get(f"post_v16_platform_{p_sfx}"): st.caption("💡 Para e-mail, segmente sua lista.")
                        post_details = _marketing_get_objective_details("post_v16", "post")
                        if st.form_submit_button("💡 Gerar Post!"): _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, selected_platforms_post_ui, self.llm)
                    if 'generated_post_content_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_post_content_new, "post_v16", "post_ia")
                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas com IA")
                    with st.form("campaign_creator_form_v16"):
                        campaign_name = st.text_input("Nome da Campanha:", key="campaign_name_v16")
                        st.subheader("Plataformas Desejadas:")
                        select_all_camp_checked = st.checkbox("Selecionar Todas", key="camp_v16_select_all")
                        cols_camp = st.columns(2); selected_platforms_camp_ui = []
                        for i, (p_name, p_sfx) in enumerate(platforms_config_options.items()):
                            with cols_camp[i%2]:
                                if st.checkbox(p_name, key=f"camp_v16_platform_{p_sfx}", value=select_all_camp_checked): selected_platforms_camp_ui.append(p_name)
                        camp_details_obj = _marketing_get_objective_details("campaign_v16", "campanha")
                        camp_duration = st.text_input("Duração Estimada:", key="campaign_duration_v16"); camp_budget = st.text_input("Orçamento (opcional):", key="campaign_budget_v16"); kpis = st.text_area("KPIs:", key="campaign_kpis_v16")
                        if st.form_submit_button("🚀 Gerar Plano de Campanha!"): _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, camp_details_obj, {"name":campaign_name, "duration":camp_duration, "budget":camp_budget, "kpis":kpis}, selected_platforms_camp_ui, self.llm)
                    if 'generated_campaign_content_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_campaign_content_new, "campaign_v16", "campanha_ia")
                elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                    st.subheader("📄 Gerador de Landing Pages com IA")
                    with st.form("lp_form_v16"):
                        lp_details = {"purpose": st.text_input("Objetivo da LP:", key="lp_purpose_v16"), "target_audience": st.text_input("Persona:", key="lp_audience_v16"), "main_offer": st.text_area("Oferta principal:", key="lp_offer_v16"), "key_benefits": st.text_area("Benefícios:", key="lp_benefits_v16"), "cta": st.text_input("CTA principal:", key="lp_cta_v16"), "visual_prefs": st.text_input("Preferências visuais (opcional):", key="lp_visual_v16")}
                        if st.form_submit_button("🛠️ Gerar Estrutura da LP!"): _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details, self.llm)
                    if 'generated_lp_content_new' in st.session_state: st.markdown(st.session_state.generated_lp_content_new); st.download_button("📥 Baixar LP", st.session_state.generated_lp_content_new.encode('utf-8'), "lp_ia.txt", "text/plain", key="dl_lp_v16")
                elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                    st.subheader("🏗️ Arquiteto de Sites com IA")
                    with st.form("site_creator_form_v16"):
                        site_details = {"business_type":st.text_input("Tipo do negócio:",key="site_biz_v16"), "main_purpose":st.text_area("Objetivo do site:",key="site_purpose_v16"), "target_audience":st.text_input("Público:",key="site_audience_v16"), "essential_pages":st.text_area("Páginas (Home, Sobre):",key="site_pages_v16"), "key_features":st.text_area("Diferenciais:",key="site_features_v16"), "brand_personality":st.text_input("Marca:",key="site_brand_v16"), "visual_references":st.text_input("Referências (opcional):",key="site_visual_v16")}
                        if st.form_submit_button("🏛️ Gerar Estrutura!"): _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details, self.llm)
                    if 'generated_site_content_new' in st.session_state: st.markdown(st.session_state.generated_site_content_new); st.download_button("📥 Baixar Site",st.session_state.generated_site_content_new.encode('utf-8'),"site_ia.txt","text/plain",key="dl_site_v16")
                elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                    st.subheader("🎯 Decodificador de Clientes com IA")
                    with st.form("find_client_form_v16"):
                        client_details = {"product_campaign":st.text_area("Produto/campanha:",key="fc_camp_v16"),"location":st.text_input("Local:",key="fc_loc_v16"),"budget":st.text_input("Verba (opcional):",key="fc_budget_v16"),"age_gender":st.text_input("Idade/Gênero:",key="fc_age_v16"),"interests":st.text_area("Interesses/Dores:",key="fc_int_v16"),"current_channels":st.text_area("Canais atuais:",key="fc_chan_v16"),"deep_research":st.checkbox("Deep Research",key="fc_deep_v16")}
                        if st.form_submit_button("🔍 Encontrar Cliente!"): _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details, self.llm)
                    if 'generated_client_analysis_new' in st.session_state: st.markdown(st.session_state.generated_client_analysis_new); st.download_button("📥 Baixar Análise",st.session_state.generated_client_analysis_new.encode('utf-8'),"publico_ia.txt","text/plain",key="dl_client_v16")
                elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                    st.subheader("🧐 Radar da Concorrência com IA")
                    with st.form("competitor_form_v16"):
                        competitor_details = {"your_business":st.text_area("Seu negócio:",key="ca_biz_v16"), "competitors_list":st.text_area("Concorrentes:",key="ca_comp_v16"), "aspects_to_analyze":st.multiselect("Analisar:",["Presença Online","Conteúdo","Comunicação","Forças/Fraquezas"],default=["Presença Online","Forças/Fraquezas"],key="ca_asp_v16")}
                        if st.form_submit_button("📡 Analisar!"): _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details, self.llm)
                    if 'generated_competitor_analysis_new' in st.session_state: st.markdown(st.session_state.generated_competitor_analysis_new); st.download_button("📥 Baixar Análise",st.session_state.generated_competitor_analysis_new.encode('utf-8'),"concorrencia_ia.txt","text/plain",key="dl_comp_v16")
                elif main_action == "Selecione uma opção...":
                    st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA!")
                    st.image("https://i.imgur.com/7IIYxq1.png", caption="Assistente PME Pro", width=200)

            def conversar_plano_de_negocios(self, input_usuario):
                system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..."
                cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
                prompt_content = f"Usuário busca ajuda para precificar: '{input_usuario}'."
                if descricao_imagem_contexto: prompt_content = f"{descricao_imagem_contexto}\n\n{prompt_content}"
                system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação... {prompt_content} Faça perguntas sobre custos, margem, concorrência, valor percebido, objetivos..."""
                cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que forneci, próximos passos para definir o preço?"}) 
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
                prompt_content = f"Usuário busca ideias: '{input_usuario}'."
                if contexto_arquivos: prompt_content = f"Contexto de arquivos:\n{contexto_arquivos}\n\n{prompt_content}"
                system_message_ideias = f"""Você é o "Assistente PME Pro", consultor criativo... {prompt_content} Forneça 3-5 ideias distintas (Conceito, Potencial, Primeiros Passos)..."""
                cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que descrevi, quais ideias inovadoras você sugere?"})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'): memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages'): memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
            if area_chave == "calculo_precos": st.session_state.last_uploaded_image_info_pricing = None; st.session_state.processed_image_id_pricing = None; st.session_state.user_input_processed_pricing = False 
            elif area_chave == "gerador_ideias": st.session_state.uploaded_file_info_ideias_for_prompt = None; st.session_state.processed_file_id_ideias = None; st.session_state.user_input_processed_ideias = False

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}"
            if chat_display_key not in st.session_state: st.session_state[chat_display_key] = [] 
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v16")
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing = True
                elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias = True
                with st.spinner("Assistente PME Pro está processando..."):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()

        if 'agente_pme' not in st.session_state:
            st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme
        
        if 'llm_success_message_shown' not in st.session_state and llm_model_instance:
            st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
            st.session_state.llm_success_message_shown = True

        URL_DO_SEU_LOGO_APP = "images/logo-pme-ia.png"
        try:
            if os.path.exists(URL_DO_SEU_LOGO_APP): st.sidebar.image(URL_DO_SEU_LOGO_APP, width=150)
            else: 
                st.sidebar.image("https://i.imgur.com/7IIYxq1.png", width=150, caption="Logo (Fallback)")
                if 'logo_fallback_warning' not in st.session_state: st.sidebar.warning(f"Logo '{URL_DO_SEU_LOGO_APP}' não encontrada."); st.session_state.logo_fallback_warning = True
        except Exception as e:
            st.sidebar.image("https://i.imgur.com/7IIYxq1.png", width=150, caption="Logo (Erro)")
            if 'logo_exception_warning' not in st.session_state: st.sidebar.warning(f"Erro ao carregar logo: {e}"); st.session_state.logo_exception_warning = True

        st.sidebar.title("Assistente PME Pro")
        st.sidebar.markdown("IA para seu Negócio Decolar!")
        st.sidebar.markdown("---")
        opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado", "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos", "Gerador de Ideias para Negócios": "gerador_ideias"}
        if 'area_selecionada' not in st.session_state or st.session_state.area_selecionada not in opcoes_menu: st.session_state.area_selecionada = "Página Inicial"
        radio_key_sidebar = 'sidebar_selection_v16'
        if f'{radio_key_sidebar}_index' not in st.session_state: st.session_state[f'{radio_key_sidebar}_index'] = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)
        area_selecionada_label = st.sidebar.radio("Como posso te ajudar hoje?", options=list(opcoes_menu.keys()), key=radio_key_sidebar, index=st.session_state[f'{radio_key_sidebar}_index'], on_change=lambda: st.session_state.update({f"{radio_key_sidebar}_index": list(opcoes_menu.keys()).index(st.session_state[radio_key_sidebar])}))
        if area_selecionada_label != st.session_state.area_selecionada:
            st.session_state.area_selecionada = area_selecionada_label
            if area_selecionada_label != "Marketing Digital com IA (Guia)":
                for k in list(st.session_state.keys()):
                    if (k.startswith("generated_") and k.endswith("_new")) or k.startswith("post_v15_platform_") or k.startswith("campaign_v15_platform_") or k in ["post_v15_select_all", "campaign_v15_select_all"]:
                        if st.session_state.get(k) is not None: del st.session_state[k]
            st.rerun()
        current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
        if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
            if st.session_state.area_selecionada != st.session_state.get('previous_area_selecionada_for_chat_init_v16') or f"chat_display_{current_section_key}" not in st.session_state or not st.session_state[f"chat_display_{current_section_key}"]:
                msg_inicial_nav, memoria_agente_nav = "", None
                if current_section_key == "plano_negocios": msg_inicial_nav, memoria_agente_nav = "Olá! Vamos elaborar seu plano de negócios?", agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav, memoria_agente_nav = "Olá! Para precificar, descreva seu produto/serviço.", agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav, memoria_agente_nav = "Olá! Buscando ideias? Descreva seu desafio.", agente.memoria_gerador_ideias
                if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
                st.session_state['previous_area_selecionada_for_chat_init_v16'] = st.session_state.area_selecionada
        if current_section_key == "pagina_inicial":
            st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1><p style='font-size: 1.1em;'>Use o menu à esquerda.</p></div>", unsafe_allow_html=True)
            st.markdown("---"); st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO_APP if os.path.exists(URL_DO_SEU_LOGO_APP) else 'https://i.imgur.com/7IIYxq1.png'}' width='150'></div>", unsafe_allow_html=True); st.markdown("---")
            if len(opcoes_menu)-1 > 0:
                cols_btns = st.columns(min(len(opcoes_menu)-1,3))
                idx_btn = 0
                for nome, chave in opcoes_menu.items():
                    if chave != "pagina_inicial":
                        lbl = nome.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                        if cols_btns[idx_btn % min(len(opcoes_menu)-1,3)].button(lbl, key=f"btn_goto_{chave}_v16",use_container_width=True): st.session_state.area_selecionada=nome; st.session_state[f'{radio_key_sidebar}_index']=list(opcoes_menu.keys()).index(nome); st.rerun()
                        idx_btn+=1
                st.balloons()
        elif current_section_key == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key == "plano_negocios": st.header("📝 Plano de Negócios com IA"); exibir_chat_e_obter_input(current_section_key, "Sua resposta...", agente.conversar_plano_de_negocios); _sidebar_clear_button("Plano", agente.memoria_plano_negocios, current_section_key)
        elif current_section_key == "calculo_precos": st.header("💲 Cálculo de Preços com IA"); uploaded_image = st.file_uploader("Imagem do produto (opcional):", type=["png","jpg","jpeg"],key="preco_img_v16"); _handle_chat_with_image("calculo_precos", "Descreva produto/custos...", agente.calcular_precos_interativo, uploaded_image); _sidebar_clear_button("Preços", agente.memoria_calculo_precos, current_section_key)
        elif current_section_key == "gerador_ideias": st.header("💡 Gerador de Ideias com IA"); uploaded_files_ideias = st.file_uploader("Arquivos de contexto (opcional):",type=["txt","png","jpg"],accept_multiple_files=True,key="ideias_files_v16"); _handle_chat_with_files("gerador_ideias", "Descreva seu desafio...", agente.gerar_ideias_para_negocios, uploaded_files_ideias); _sidebar_clear_button("Ideias", agente.memoria_gerador_ideias, current_section_key)
    else:
        st.error("🚨 Modelo LLM não inicializado.")
else:
    pass

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")

def _sidebar_clear_button(label, memoria, section_key):
    if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key}_v16_clear"):
        msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
        if section_key == "calculo_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços! Descreva seu produto ou serviço."
        elif section_key == "gerador_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias! Qual o seu ponto de partida?"
        inicializar_ou_resetar_chat(section_key, msg_inicial, memoria)
        st.rerun()

def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
    descricao_imagem_para_ia = None
    if uploaded_image_obj is not None:
        if st.session_state.get(f'processed_image_id_{area_chave}_v16') != uploaded_image_obj.id:
            try:
                img_pil = Image.open(uploaded_image_obj)
                st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                st.session_state[f'last_uploaded_image_info_{area_chave}_v16'] = descricao_imagem_para_ia
                st.session_state[f'processed_image_id_{area_chave}_v16'] = uploaded_image_obj.id
                st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo.")
            except Exception as e:
                st.error(f"Erro ao processar imagem: {e}")
                st.session_state[f'last_uploaded_image_info_{area_chave}_v16'] = None
                st.session_state[f'processed_image_id_{area_chave}_v16'] = None
        else:
            descricao_imagem_para_ia = st.session_state.get(f'last_uploaded_image_info_{area_chave}_v16')
    kwargs_chat = {}
    ctx_img_prox_dialogo = st.session_state.get(f'last_uploaded_image_info_{area_chave}_v16')
    if ctx_img_prox_dialogo and not st.session_state.get(f'user_input_processed_{area_chave}_v16', False):
        kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
    exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
    if f'user_input_processed_{area_chave}_v16' in st.session_state and st.session_state[f'user_input_processed_{area_chave}_v16']:
        if st.session_state.get(f'last_uploaded_image_info_{area_chave}_v16'): st.session_state[f'last_uploaded_image_info_{area_chave}_v16'] = None
        st.session_state[f'user_input_processed_{area_chave}_v16'] = False

def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
    contexto_para_ia_local = None
    if uploaded_files_objs:
        current_file_signature = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_objs]))
        if st.session_state.get(f'processed_file_id_{area_chave}_v16') != current_file_signature or not st.session_state.get(f'uploaded_file_info_{area_chave}_for_prompt_v16'):
            text_contents, image_info = [], []
            for f_item in uploaded_files_objs:
                try:
                    if f_item.type == "text/plain": text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...")
                    elif f_item.type in ["image/png","image/jpeg"]: st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100); image_info.append(f"Imagem '{f_item.name}'.")
                except Exception as e: st.error(f"Erro ao processar '{f_item.name}': {e}")
            full_ctx_str = ""
            if text_contents: full_ctx_str += "\n\n--- TEXTO DOS ARQUIVOS ---\n" + "\n\n".join(text_contents)
            if image_info: full_ctx_str += "\n\n--- IMAGENS FORNECIDAS ---\n" + "\n".join(image_info)
            if full_ctx_str: st.session_state[f'uploaded_file_info_{area_chave}_for_prompt_v16'] = full_ctx_str.strip(); contexto_para_ia_local = st.session_state[f'uploaded_file_info_{area_chave}_for_prompt_v16']; st.info("Arquivo(s) de contexto pronto(s).")
            else: st.session_state[f'uploaded_file_info_{area_chave}_for_prompt_v16'] = None
            st.session_state[f'processed_file_id_{area_chave}_v16'] = current_file_signature
        else: contexto_para_ia_local = st.session_state.get(f'uploaded_file_info_{area_chave}_for_prompt_v16')
    kwargs_chat = {}
    if contexto_para_ia_local and not st.session_state.get(f'user_input_processed_{area_chave}_v16', False):
        kwargs_chat['contexto_arquivos'] = contexto_para_ia_local
    exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
    if f'user_input_processed_{area_chave}_v16' in st.session_state and st.session_state[f'user_input_processed_{area_chave}_v16']:
        if st.session_state.get(f'uploaded_file_info_{area_chave}_for_prompt_v16'): st.session_state[f'uploaded_file_info_{area_chave}_for_prompt_v16'] = None
        st.session_state[f'user_input_processed_{area_chave}_v16'] = False
