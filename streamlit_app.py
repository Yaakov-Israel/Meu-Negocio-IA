import streamlit as st
import os 
import json 
import pyrebase 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀" 
)
# Não colocaremos st.title() aqui ainda, pois ele pode mudar dependendo da seção ou se o usuário está logado.
# --- Inicialização do Firebase ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False

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
            if 'firebase_app_instance' not in st.session_state: 
                st.session_state.firebase_app_instance = pyrebase.initialize_app(plain_firebase_config_dict)
            
            firebase_app = st.session_state.firebase_app_instance
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_success_message_shown' not in st.session_state and not st.session_state.get('user_session_pyrebase'):
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_success_message_shown = True

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
except AttributeError as e_attr: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr}"
except Exception as e_general: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general}"

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if 'st' in locals() or 'st' in globals(): 
        st.exception(e_general if 'e_general' in locals() else Exception(error_message_firebase_init))
    st.stop()

if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None) 
    except Exception as e_session: 
        error_message_session_check = "Sessão inválida ou expirada."
        try:
            error_details_str = e_session.args[0] if len(e_session.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\""))
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check = f"Erro ao verificar sessão ({api_error_message}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError):
            error_message_session_check = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session)}"
        
        st.session_state.user_session_pyrebase = None 
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state: 
            st.sidebar.warning(error_message_session_check)
            st.session_state.auth_error_shown = True
        
        if not st.session_state.get('running_rerun_after_auth_fail_main', False):
            st.session_state.running_rerun_after_auth_fail_main = True
            st.rerun()
        else:
            st.session_state.pop('running_rerun_after_auth_fail_main', None)

if 'running_rerun_after_auth_fail_main' in st.session_state and st.session_state.running_rerun_after_auth_fail_main:
    st.session_state.pop('running_rerun_after_auth_fail_main', None)
    # Não renderizar o resto da página se estivermos no meio de um rerun forçado por falha de autenticação
# --- Interface do Usuário Condicional e Lógica Principal do App ---
if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    
    # Inicialização do LLM (SÓ SE AUTENTICADO)
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
            # Usando um modelo mais recente se disponível, ou manter o gemini-1.5-flash
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash", 
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
        except Exception as e_llm:
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm}")
            st.stop()

    if llm_model_instance:
        KEY_SUFFIX_APP = "_v21_full" # Novo sufixo para esta versão completa

        # --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (Objetivos e Output) ---
        def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj{KEY_SUFFIX_APP}")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{KEY_SUFFIX_APP}")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{KEY_SUFFIX_APP}")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{KEY_SUFFIX_APP}")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{KEY_SUFFIX_APP}")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone{KEY_SUFFIX_APP}")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{KEY_SUFFIX_APP}")
            return details

        def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}{KEY_SUFFIX_APP}.txt", mime="text/plain", key=f"download_{section_key}{KEY_SUFFIX_APP}")
            cols_actions = st.columns(2)
            with cols_actions[0]:
                if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn{KEY_SUFFIX_APP}"):
                    st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
                    st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
            with cols_actions[1]:
                if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn{KEY_SUFFIX_APP}"):
                    st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

        # --- HANDLER FUNCTIONS ---
        def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
            with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil...", # Resumido
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                    f"**Produto/Serviço Principal:** {details_dict['product_service']}",
                    f"**Público-Alvo:** {details_dict['target_audience']}",
                    f"**Objetivo do Post:** {details_dict['objective']}",
                    f"**Mensagem Chave:** {details_dict['key_message']}",
                    f"**Proposta Única de Valor (USP):** {details_dict['usp']}",
                    f"**Tom/Estilo:** {details_dict['style_tone']}",
                    f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
                ] 
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_post_content{KEY_SUFFIX_APP}'] = ai_response.content # Usando sufixo para evitar colisão

        # ... (Outras funções _marketing_handle_... devem ser adaptadas similarmente para usar KEY_SUFFIX_APP e chaves de session_state únicas) ...
        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
            with st.spinner("🧠 A IA está elaborando seu plano de campanha..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um estrategista de marketing digital experiente para PMEs no Brasil...", # Resumido
                    f"**Nome da Campanha:** {campaign_specifics['name']}",
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                    f"**Produto/Serviço Principal da Campanha:** {details_dict['product_service']}",
                    # ... (restante do prompt) ...
                    f"**Informações Adicionais/CTA da Campanha:** {details_dict['extra_info']}"
                ] 
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_campaign_content{KEY_SUFFIX_APP}'] = ai_response.content

        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
            with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
                prompt_parts = [ "**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages...", # Resumido
                    # ... (restante do prompt) ...
                ]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_lp_content{KEY_SUFFIX_APP}'] = ai_response.content

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
            with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
                prompt_parts = [ "**Instrução para IA:** Você é um arquiteto de informação e web designer experiente...", # Resumido
                    # ... (restante do prompt) ...
                ]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_site_content{KEY_SUFFIX_APP}'] = ai_response.content

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
            with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
                prompt_parts = [ "**Instrução para IA:** Você é um 'Agente Detetive de Clientes'...", # Resumido
                    # ... (restante do prompt) ...
                ]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_client_analysis{KEY_SUFFIX_APP}'] = ai_response.content

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
            with st.spinner("🔬 A IA está analisando a concorrência..."):
                prompt_parts = [ "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva'...", # Resumido
                    # ... (restante do prompt) ...
                ]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_competitor_analysis{KEY_SUFFIX_APP}'] = ai_response.content
        
        # --- Classe do Agente (AssistentePMEPro) ---
        class AssistentePMEPro:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None: st.stop()
                self.llm = llm_passed_model
                # Usando KEY_SUFFIX_APP para chaves de memória
                if f'memoria_plano_negocios{KEY_SUFFIX_APP}' not in st.session_state: st.session_state[f'memoria_plano_negocios{KEY_SUFFIX_APP}'] = ConversationBufferMemory(memory_key=f"historico_chat_plano{KEY_SUFFIX_APP}", return_messages=True)
                if f'memoria_calculo_precos{KEY_SUFFIX_APP}' not in st.session_state: st.session_state[f'memoria_calculo_precos{KEY_SUFFIX_APP}'] = ConversationBufferMemory(memory_key=f"historico_chat_precos{KEY_SUFFIX_APP}", return_messages=True)
                if f'memoria_gerador_ideias{KEY_SUFFIX_APP}' not in st.session_state: st.session_state[f'memoria_gerador_ideias{KEY_SUFFIX_APP}'] = ConversationBufferMemory(memory_key=f"historico_chat_ideias{KEY_SUFFIX_APP}", return_messages=True)
                
                self.memoria_plano_negocios = st.session_state[f'memoria_plano_negocios{KEY_SUFFIX_APP}']
                self.memoria_calculo_precos = st.session_state[f'memoria_calculo_precos{KEY_SUFFIX_APP}']
                self.memoria_gerador_ideias = st.session_state[f'memoria_gerador_ideias{KEY_SUFFIX_APP}']

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat_placeholder"): # Placeholder atualizado
                prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(system_message_content),
                    MessagesPlaceholder(variable_name=memory_key_placeholder), # Usar o placeholder do argumento
                    HumanMessagePromptTemplate.from_template("{input_usuario}")
                ])
                return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

            # ... (definições de marketing_digital_guiado, conversar_plano_de_negocios, etc. da sua versão anterior) ...
            # Certifique-se que as chaves de widget e session_state dentro dessas funções também usam KEY_SUFFIX_APP para evitar conflitos.
            # Vou colar a marketing_digital_guiado como exemplo de adaptação:
            def marketing_digital_guiado(self):
                st.header("🚀 Marketing Digital Interativo com IA")
                st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
                st.markdown("---")
                marketing_files_info_for_prompt_local = [] 
                with st.sidebar: 
                    st.subheader("📎 Suporte para Marketing")
                    uploaded_marketing_files = st.file_uploader( "Upload de arquivos de CONTEXTO para Marketing (opcional):",  accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'],  key=f"marketing_files_uploader{KEY_SUFFIX_APP}")
                    if uploaded_marketing_files:
                        temp_marketing_files_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                        if temp_marketing_files_info: marketing_files_info_for_prompt_local = temp_marketing_files_info; st.success(f"{len(uploaded_marketing_files)} arquivo(s) de contexto carregado(s)!")
                        with st.expander("Ver arquivos de contexto"): [st.write(f"- {f['name']} ({f['type']})") for f in marketing_files_info_for_prompt_local]
                    st.markdown("---")

                main_action_key = f"main_marketing_action_choice{KEY_SUFFIX_APP}"
                opcoes_menu_marketing_dict = { "Selecione uma opção...":0, "1 - Criar post para redes sociais ou e-mail":1, "2 - Criar campanha de marketing completa":2, "3 - Criar estrutura e conteúdo para landing page":3, "4 - Criar estrutura e conteúdo para site com IA":4, "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":5, "6 - Conhecer a concorrência (Análise Competitiva)":6}
                opcoes_radio_marketing = list(opcoes_menu_marketing_dict.keys())
                if f"{main_action_key}_index" not in st.session_state: st.session_state[f"{main_action_key}_index"] = 0
                def update_marketing_radio_index(): st.session_state[f"{main_action_key}_index"] = opcoes_radio_marketing.index(st.session_state[main_action_key])
                main_action = st.radio("Olá! O que você quer fazer agora em marketing digital?", opcoes_radio_marketing, index=st.session_state[f"{main_action_key}_index"], key=main_action_key, on_change=update_marketing_radio_index)
                st.markdown("---")
                platforms_config_options = { "Instagram":"insta", "Facebook":"fb", "X (Twitter)":"x", "WhatsApp":"wpp", "TikTok":"tt", "Kwai":"kwai", "YouTube (descrição/roteiro)":"yt", "E-mail Marketing (lista própria)":"email_own", "E-mail Marketing (Campanha Google Ads)":"email_google"}

                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com IA")
                    with st.form(f"post_creator_form{KEY_SUFFIX_APP}"):
                        st.subheader("Plataformas Desejadas:")
                        select_all_post_checked = st.checkbox("Selecionar Todas", key=f"post_select_all{KEY_SUFFIX_APP}")
                        cols_post = st.columns(2); selected_platforms_post_ui = []
                        for i, (p_name, p_sfx) in enumerate(platforms_config_options.items()):
                            with cols_post[i%2]:
                                if st.checkbox(p_name, key=f"post_platform_{p_sfx}{KEY_SUFFIX_APP}", value=select_all_post_checked): selected_platforms_post_ui.append(p_name)
                        post_details = _marketing_get_objective_details(f"post_creator{KEY_SUFFIX_APP}", "post")
                        if st.form_submit_button("💡 Gerar Post!"): _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, selected_platforms_post_ui, self.llm)
                    if f'generated_post_content{KEY_SUFFIX_APP}' in st.session_state: _marketing_display_output_options(st.session_state[f'generated_post_content{KEY_SUFFIX_APP}'], f"post_output{KEY_SUFFIX_APP}", "post_ia")
                
                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas com IA")
                    with st.form(f"campaign_creator_form{KEY_SUFFIX_APP}"):
                        campaign_name = st.text_input("Nome da Campanha:", key=f"campaign_name{KEY_SUFFIX_APP}")
                        st.subheader("Plataformas Desejadas:")
                        select_all_camp_checked = st.checkbox("Selecionar Todas", key=f"camp_select_all{KEY_SUFFIX_APP}")
                        cols_camp = st.columns(2); selected_platforms_camp_ui = []
                        for i, (p_name, p_sfx) in enumerate(platforms_config_options.items()):
                            with cols_camp[i%2]:
                                if st.checkbox(p_name, key=f"camp_platform_{p_sfx}{KEY_SUFFIX_APP}", value=select_all_camp_checked): selected_platforms_camp_ui.append(p_name)
                        camp_details_obj = _marketing_get_objective_details(f"campaign_creator{KEY_SUFFIX_APP}", "campanha")
                        camp_duration = st.text_input("Duração Estimada:", key=f"campaign_duration{KEY_SUFFIX_APP}"); camp_budget = st.text_input("Orçamento (opcional):", key=f"campaign_budget{KEY_SUFFIX_APP}"); kpis = st.text_area("KPIs:", key=f"campaign_kpis{KEY_SUFFIX_APP}")
                        if st.form_submit_button("🚀 Gerar Plano de Campanha!"): _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, camp_details_obj, {"name":campaign_name, "duration":camp_duration, "budget":camp_budget, "kpis":kpis}, selected_platforms_camp_ui, self.llm)
                    if f'generated_campaign_content{KEY_SUFFIX_APP}' in st.session_state: _marketing_display_output_options(st.session_state[f'generated_campaign_content{KEY_SUFFIX_APP}'], f"campaign_output{KEY_SUFFIX_APP}", "campanha_ia")

                elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                    st.subheader("📄 Gerador de Landing Pages com IA")
                    with st.form(f"lp_form{KEY_SUFFIX_APP}"):
                        lp_details = {"purpose": st.text_input("Objetivo da LP:", key=f"lp_purpose{KEY_SUFFIX_APP}"), "target_audience": st.text_input("Persona:", key=f"lp_audience{KEY_SUFFIX_APP}"), "main_offer": st.text_area("Oferta principal:", key=f"lp_offer{KEY_SUFFIX_APP}"), "key_benefits": st.text_area("Benefícios:", key=f"lp_benefits{KEY_SUFFIX_APP}"), "cta": st.text_input("CTA principal:", key=f"lp_cta{KEY_SUFFIX_APP}"), "visual_prefs": st.text_input("Preferências visuais (opcional):", key=f"lp_visual{KEY_SUFFIX_APP}")}
                        if st.form_submit_button("🛠️ Gerar Estrutura da LP!"): _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details, self.llm)
                    if f'generated_lp_content{KEY_SUFFIX_APP}' in st.session_state: st.markdown(st.session_state[f'generated_lp_content{KEY_SUFFIX_APP}']); st.download_button("📥 Baixar LP", st.session_state[f'generated_lp_content{KEY_SUFFIX_APP}'].encode('utf-8'), f"lp_ia{KEY_SUFFIX_APP}.txt", "text/plain", key=f"dl_lp{KEY_SUFFIX_APP}")

                elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                    st.subheader("🏗️ Arquiteto de Sites com IA")
                    with st.form(f"site_creator_form{KEY_SUFFIX_APP}"):
                        site_details = {"business_type":st.text_input("Tipo do negócio:",key=f"site_biz{KEY_SUFFIX_APP}"), "main_purpose":st.text_area("Objetivo do site:",key=f"site_purpose{KEY_SUFFIX_APP}"), "target_audience":st.text_input("Público:",key=f"site_audience{KEY_SUFFIX_APP}"), "essential_pages":st.text_area("Páginas (Home, Sobre):",key=f"site_pages{KEY_SUFFIX_APP}"), "key_features":st.text_area("Diferenciais:",key=f"site_features{KEY_SUFFIX_APP}"), "brand_personality":st.text_input("Marca:",key=f"site_brand{KEY_SUFFIX_APP}"), "visual_references":st.text_input("Referências (opcional):",key=f"site_visual{KEY_SUFFIX_APP}")}
                        if st.form_submit_button("🏛️ Gerar Estrutura!"): _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details, self.llm)
                    if f'generated_site_content{KEY_SUFFIX_APP}' in st.session_state: st.markdown(st.session_state[f'generated_site_content{KEY_SUFFIX_APP}']); st.download_button("📥 Baixar Site",st.session_state[f'generated_site_content{KEY_SUFFIX_APP}'].encode('utf-8'),f"site_ia{KEY_SUFFIX_APP}.txt","text/plain",key=f"dl_site{KEY_SUFFIX_APP}")

                elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                    st.subheader("🎯 Decodificador de Clientes com IA")
                    with st.form(f"find_client_form{KEY_SUFFIX_APP}"):
                        client_details = {"product_campaign":st.text_area("Produto/campanha:",key=f"fc_camp{KEY_SUFFIX_APP}"),"location":st.text_input("Local:",key=f"fc_loc{KEY_SUFFIX_APP}"),"budget":st.text_input("Verba (opcional):",key=f"fc_budget{KEY_SUFFIX_APP}"),"age_gender":st.text_input("Idade/Gênero:",key=f"fc_age{KEY_SUFFIX_APP}"),"interests":st.text_area("Interesses/Dores:",key=f"fc_int{KEY_SUFFIX_APP}"),"current_channels":st.text_area("Canais atuais:",key=f"fc_chan{KEY_SUFFIX_APP}"),"deep_research":st.checkbox("Deep Research",key=f"fc_deep{KEY_SUFFIX_APP}")}
                        if st.form_submit_button("🔍 Encontrar Cliente!"): _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details, self.llm)
                    if f'generated_client_analysis{KEY_SUFFIX_APP}' in st.session_state: st.markdown(st.session_state[f'generated_client_analysis{KEY_SUFFIX_APP}']); st.download_button("📥 Baixar Análise",st.session_state[f'generated_client_analysis{KEY_SUFFIX_APP}'].encode('utf-8'),f"publico_ia{KEY_SUFFIX_APP}.txt","text/plain",key=f"dl_client{KEY_SUFFIX_APP}")

                elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                    st.subheader("🧐 Radar da Concorrência com IA")
                    with st.form(f"competitor_form{KEY_SUFFIX_APP}"):
                        competitor_details = {"your_business":st.text_area("Seu negócio:",key=f"ca_biz{KEY_SUFFIX_APP}"), "competitors_list":st.text_area("Concorrentes:",key=f"ca_comp{KEY_SUFFIX_APP}"), "aspects_to_analyze":st.multiselect("Analisar:",["Presença Online","Conteúdo","Comunicação","Forças/Fraquezas"],default=["Presença Online","Forças/Fraquezas"],key=f"ca_asp{KEY_SUFFIX_APP}")}
                        if st.form_submit_button("📡 Analisar!"): _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details, self.llm)
                    if f'generated_competitor_analysis{KEY_SUFFIX_APP}' in st.session_state: st.markdown(st.session_state[f'generated_competitor_analysis{KEY_SUFFIX_APP}']); st.download_button("📥 Baixar Análise",st.session_state[f'generated_competitor_analysis{KEY_SUFFIX_APP}'].encode('utf-8'),f"concorrencia_ia{KEY_SUFFIX_APP}.txt","text/plain",key=f"dl_comp{KEY_SUFFIX_APP}")
                
                elif main_action == "Selecione uma opção...":
                    st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
                    st.image("images/logo-pme-ia.png", caption="Assistente PME Pro", width=200) # Usando o logo local


            def conversar_plano_de_negocios(self, input_usuario):
                system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..." # Resumido
                cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder=f"historico_chat_plano{KEY_SUFFIX_APP}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
                prompt_content = f"Usuário busca ajuda para precificar: '{input_usuario}'."
                if descricao_imagem_contexto: prompt_content = f"{descricao_imagem_contexto}\n\n{prompt_content}"
                system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação... {prompt_content} Faça perguntas...""" # Resumido
                cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder=f"historico_chat_precos{KEY_SUFFIX_APP}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que forneci, próximos passos para definir o preço?"}) 
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
                prompt_content = f"Usuário busca ideias: '{input_usuario}'."
                if contexto_arquivos: prompt_content = f"Contexto de arquivos:\n{contexto_arquivos}\n\n{prompt_content}"
                system_message_ideias = f"""Você é o "Assistente PME Pro", consultor criativo... {prompt_content} Forneça 3-5 ideias...""" # Resumido
                cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder=f"historico_chat_ideias{KEY_SUFFIX_APP}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que descrevi, quais ideias inovadoras você sugere?"})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

        # --- Funções Utilitárias de Chat ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}{KEY_SUFFIX_APP}"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                # Adicionando a mensagem inicial à memória Langchain
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'): memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages'): memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
            
            # Limpeza de estado de upload específico da área
            if area_chave == "calculo_precos": 
                st.session_state.pop(f'last_uploaded_image_info_{area_chave}{KEY_SUFFIX_APP}', None)
                st.session_state.pop(f'processed_image_id_{area_chave}{KEY_SUFFIX_APP}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{KEY_SUFFIX_APP}', None)
            elif area_chave == "gerador_ideias": 
                st.session_state.pop(f'uploaded_file_info_{area_chave}_for_prompt{KEY_SUFFIX_APP}', None)
                st.session_state.pop(f'processed_file_id_{area_chave}{KEY_SUFFIX_APP}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{KEY_SUFFIX_APP}', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}{KEY_SUFFIX_APP}"
            if chat_display_key not in st.session_state: st.session_state[chat_display_key] = [] 
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
            
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{KEY_SUFFIX_APP}")
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                if area_chave == "calculo_precos": st.session_state[f'user_input_processed_{area_chave}{KEY_SUFFIX_APP}'] = True
                elif area_chave == "gerador_ideias": st.session_state[f'user_input_processed_{area_chave}{KEY_SUFFIX_APP}'] = True
                with st.spinner("Assistente PME Pro está processando... 🤔"):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()
        
        def _sidebar_clear_button(label, memoria, section_key, key_suffix_version_local): 
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key}{key_suffix_version_local}_clear"):
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key == "calculo_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços! Descreva seu produto ou serviço."
                elif section_key == "gerador_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias! Qual o seu ponto de partida?"
                inicializar_ou_resetar_chat(section_key, msg_inicial, memoria) # KEY_SUFFIX_APP será usado implicitamente
                st.rerun()

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj, key_suffix_version_local): 
            descricao_imagem_para_ia = None
            if uploaded_image_obj is not None:
                if st.session_state.get(f'processed_image_id_{area_chave}{key_suffix_version_local}') != uploaded_image_obj.id:
                    try:
                        img_pil = Image.open(uploaded_image_obj); st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                        st.session_state[f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}'] = descricao_imagem_para_ia
                        st.session_state[f'processed_image_id_{area_chave}{key_suffix_version_local}'] = uploaded_image_obj.id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo.")
                    except Exception as e: st.error(f"Erro ao processar imagem: {e}"); st.session_state[f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}'] = None; st.session_state[f'processed_image_id_{area_chave}{key_suffix_version_local}'] = None
                else: descricao_imagem_para_ia = st.session_state.get(f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}')
            kwargs_chat = {}
            ctx_img_prox_dialogo = st.session_state.get(f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}')
            if ctx_img_prox_dialogo and not st.session_state.get(f'user_input_processed_{area_chave}{key_suffix_version_local}', False): kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat) # KEY_SUFFIX_APP será usado implicitamente
            if f'user_input_processed_{area_chave}{key_suffix_version_local}' in st.session_state and st.session_state[f'user_input_processed_{area_chave}{key_suffix_version_local}']:
                if st.session_state.get(f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}'): st.session_state[f'last_uploaded_image_info_{area_chave}{key_suffix_version_local}'] = None
                st.session_state[f'user_input_processed_{area_chave}{key_suffix_version_local}'] = False

        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs, key_suffix_version_local):
            contexto_para_ia_local = None
            if uploaded_files_objs:
                current_file_signature = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_objs]))
                processed_file_key = f'processed_file_id_{area_chave}{key_suffix_version_local}'
                uploaded_info_key = f'uploaded_file_info_{area_chave}_for_prompt{key_suffix_version_local}'
                if st.session_state.get(processed_file_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                    text_contents, image_info = [], []
                    for f_item in uploaded_files_objs:
                        try:
                            if f_item.type == "text/plain": text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...")
                            elif f_item.type in ["image/png","image/jpeg"]: st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100); image_info.append(f"Imagem '{f_item.name}'.")
                        except Exception as e: st.error(f"Erro ao processar '{f_item.name}': {e}")
                    full_ctx_str = ("\n\n--- TEXTO DOS ARQUIVOS ---\n" + "\n\n".join(text_contents) if text_contents else "") + \
                                   ("\n\n--- IMAGENS FORNECIDAS ---\n" + "\n".join(image_info) if image_info else "")
                    if full_ctx_str.strip(): st.session_state[uploaded_info_key] = full_ctx_str.strip(); contexto_para_ia_local = st.session_state[uploaded_info_key]; st.info("Arquivo(s) de contexto pronto(s).")
                    else: st.session_state[uploaded_info_key] = None
                    st.session_state[processed_file_key] = current_file_signature
                else: contexto_para_ia_local = st.session_state.get(uploaded_info_key)
            kwargs_chat = {}
            user_input_processed_key = f'user_input_processed_{area_chave}{key_suffix_version_local}'
            if contexto_para_ia_local and not st.session_state.get(user_input_processed_key, False): kwargs_chat['contexto_arquivos'] = contexto_para_ia_local
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat) # KEY_SUFFIX_APP será usado implicitamente
            if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
                if st.session_state.get(uploaded_info_key): st.session_state[uploaded_info_key] = None
                st.session_state[user_input_processed_key] = False

        # --- Interface Principal Streamlit (Lógica de Navegação) ---
        if 'agente_pme' not in st.session_state:
            st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme
        
        if 'llm_success_message_shown_v21_full' not in st.session_state and llm_model_instance:
            st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
            st.session_state.llm_success_message_shown_v21_full = True

        st.sidebar.write(f"Logado como: {display_email}")
        if st.sidebar.button("Logout", key=f"main_app_logout{KEY_SUFFIX_APP}"):
            st.session_state.user_session_pyrebase = None
            st.session_state.pop('firebase_init_success_message_shown', None)
            st.session_state.pop('firebase_app_instance', None) 
            st.session_state.pop('firebase_app_initialized', None)
            keys_to_clear_on_logout = [k for k in st.session_state if KEY_SUFFIX_APP in k or k.startswith('memoria_') or k.startswith('chat_display_') or k == 'agente_pme']
            for key_to_clear in keys_to_clear_on_logout: st.session_state.pop(key_to_clear, None)
            st.rerun()

        LOGO_PATH_SIDEBAR_AUTH = "images/logo-pme-ia.png"
        FALLBACK_LOGO_URL_SIDEBAR_AUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.sidebar.image(LOGO_PATH_SIDEBAR_AUTH, width=150)
        except Exception:
            st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR_AUTH, width=150, caption="Logo (Fallback)")

        st.sidebar.title("Assistente PME Pro")
        st.sidebar.markdown("IA para seu Negócio Decolar!")
        st.sidebar.markdown("---")

        opcoes_menu = { "Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado", "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos", "Gerador de Ideias para Negócios": "gerador_ideias" }
        radio_key_sidebar_main = f'sidebar_selection{KEY_SUFFIX_APP}_main'
        if 'area_selecionada' not in st.session_state or st.session_state.area_selecionada not in opcoes_menu: st.session_state.area_selecionada = "Página Inicial"
        if f'{radio_key_sidebar_main}_index' not in st.session_state:
            try: st.session_state[f'{radio_key_sidebar_main}_index'] = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)
            except ValueError: st.session_state[f'{radio_key_sidebar_main}_index'] = 0; st.session_state.area_selecionada = list(opcoes_menu.keys())[0]
        
        def update_main_radio_index_full(): st.session_state[f"{radio_key_sidebar_main}_index"] = list(opcoes_menu.keys()).index(st.session_state[radio_key_sidebar_main])
        area_selecionada_label = st.sidebar.radio( "Como posso te ajudar hoje?", options=list(opcoes_menu.keys()), key=radio_key_sidebar_main, index=st.session_state[f'{radio_key_sidebar_main}_index'], on_change=update_main_radio_index_full )

        if area_selecionada_label != st.session_state.area_selecionada:
            st.session_state.area_selecionada = area_selecionada_label
            if area_selecionada_label != "Marketing Digital com IA (Guia)": # Limpar estado de marketing se sair da seção
                keys_to_clear_marketing = [k for k in st.session_state if k.startswith(f"generated_") and KEY_SUFFIX_APP in k or k.startswith(f"post_platform_") or k.startswith(f"campaign_platform_") or k.startswith(f"post_select_all{KEY_SUFFIX_APP}") or k.startswith(f"campaign_select_all{KEY_SUFFIX_APP}")]
                for key_to_clear in keys_to_clear_marketing:
                    if st.session_state.get(key_to_clear) is not None: del st.session_state[key_to_clear]
            st.rerun() 

        current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
        
        if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
            chat_init_flag_key = f'previous_area_selecionada_for_chat_init{KEY_SUFFIX_APP}'
            chat_display_key_specific = f"chat_display_{current_section_key}{KEY_SUFFIX_APP}"
            if st.session_state.area_selecionada != st.session_state.get(chat_init_flag_key) or chat_display_key_specific not in st.session_state or not st.session_state.get(chat_display_key_specific):
                msg_inicial_nav, memoria_agente_nav = "", None
                if current_section_key == "plano_negocios": msg_inicial_nav, memoria_agente_nav = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia de negócio, seus principais produtos/serviços, e quem você imagina como seus clientes.", agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav, memoria_agente_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Descreva o produto ou serviço.", agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav, memoria_agente_nav = "Olá! Sou o Assistente PME Pro. Buscando ideias? Descreva seu desafio.", agente.memoria_gerador_ideias
                if msg_inicial_nav and memoria_agente_nav is not None: inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
                st.session_state[chat_init_flag_key] = st.session_state.area_selecionada

        # --- SELEÇÃO E EXIBIÇÃO DA SEÇÃO ATUAL ---
        if current_section_key == "pagina_inicial":
            st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
            st.markdown("---")
            
            LOGO_PATH_MAIN = "images/logo-pme-ia.png" 
            FALLBACK_LOGO_URL_MAIN = "https://i.imgur.com/7IIYxq1.png"
            cols_logo_main_page = st.columns([1,2,1]) 
            with cols_logo_main_page[1]: 
                try:
                    st.image(LOGO_PATH_MAIN, width=150, caption="Logo Assistente PME Pro")
                except Exception:
                    st.image(FALLBACK_LOGO_URL_MAIN, width=150, caption="Logo Assistente PME Pro (Fallback)")
            st.markdown("---")
            
            num_botoes_funcionais = len(opcoes_menu) -1 
            if num_botoes_funcionais > 0 :
                num_cols_render = min(num_botoes_funcionais, 3) 
                cols_botoes_pg_inicial = st.columns(num_cols_render)
                btn_idx_pg_inicial = 0
                for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                    if chave_secao_btn_pg != "pagina_inicial":
                        col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                        button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                        if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}{KEY_SUFFIX_APP}", use_container_width=True, help=f"Ir para {nome_menu_btn_pg}"):
                            st.session_state.area_selecionada = nome_menu_btn_pg
                            st.session_state[f'{radio_key_sidebar_main}_index'] = list(opcoes_menu.keys()).index(nome_menu_btn_pg) 
                            st.rerun()
                        btn_idx_pg_inicial +=1
                st.balloons()
        elif current_section_key == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key == "plano_negocios": st.header("📝 Plano de Negócios com IA"); exibir_chat_e_obter_input(current_section_key, "Sua resposta...", agente.conversar_plano_de_negocios); _sidebar_clear_button("Plano", agente.memoria_plano_negocios, current_section_key, KEY_SUFFIX_APP) 
        elif current_section_key == "calculo_precos": st.header("💲 Cálculo de Preços com IA"); uploaded_image = st.file_uploader("Imagem do produto (opcional):", type=["png","jpg","jpeg"],key=f"preco_img{KEY_SUFFIX_APP}"); _handle_chat_with_image("calculo_precos", "Descreva produto/custos...", agente.calcular_precos_interativo, uploaded_image, KEY_SUFFIX_APP); _sidebar_clear_button("Preços", agente.memoria_calculo_precos, current_section_key, KEY_SUFFIX_APP) 
        elif current_section_key == "gerador_ideias": st.header("💡 Gerador de Ideias com IA"); uploaded_files_ideias = st.file_uploader("Arquivos de contexto (opcional):",type=["txt","png","jpg","jpeg"],accept_multiple_files=True,key=f"ideias_files{KEY_SUFFIX_APP}"); _handle_chat_with_files("gerador_ideias", "Descreva seu desafio...", agente.gerar_ideias_para_negocios, uploaded_files_ideias, KEY_SUFFIX_APP); _sidebar_clear_button("Ideias", agente.memoria_gerador_ideias, current_section_key, KEY_SUFFIX_APP) 
    
    else: # Se llm_model_instance falhou em inicializar
        st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key do Google e a configuração do modelo LLM.")
        st.info("Isso pode acontecer se a chave API não estiver nos segredos ou se houver um problema ao contatar os serviços do Google Generative AI.")

# Seção de Login/Registro (executada se user_is_authenticated for False)
else: 
    st.session_state.pop('auth_error_shown', None) 
    st.sidebar.subheader("Login / Registro")
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=f"app_auth_action_choice{KEY_SUFFIX_APP}_else")

    if auth_action_choice == "Login":
        with st.sidebar.form(f"app_login_form{KEY_SUFFIX_APP}_else"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None)
                        st.rerun()
                    except Exception as e:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: error_message_login = f"Erro no login: {api_error_message}"
                        except: pass
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"app_register_form{KEY_SUFFIX_APP}_else"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: pb_auth_client.send_email_verification(user['idToken']); st.sidebar.info("Email de verificação enviado.")
                        except Exception as verify_email_error: st.sidebar.caption(f"Nota: Envio de email de verificação falhou: {verify_email_error}")
                    except Exception as e:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message: error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message: error_message_register = f"Erro no registro: {api_error_message}"
                        except: error_message_register = f"Erro no registro: {str(e)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    st.title("Bem-vindo ao Assistente PME Pro!") # Título para a tela de login
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_UNAUTH = "images/logo-pme-ia.png" # Deve ser "images"
        FALLBACK_LOGO_URL_UNAUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_UNAUTH, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_UNAUTH, width=200, caption="Logo (Fallback)")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
