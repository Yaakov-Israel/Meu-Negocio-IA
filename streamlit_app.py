import streamlit as st
import os
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

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm_model_instance = None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Adicione sua GOOGLE_API_KEY aos Segredos do seu app no painel do Streamlit Community Cloud.")
    st.stop()
except FileNotFoundError:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        st.error("🚨 ERRO: Chave API não encontrada nos Segredos do Streamlit nem como variável de ambiente.")
        st.info("Configure GOOGLE_API_KEY nos Segredos do Streamlit Cloud ou defina como variável de ambiente local.")
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
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique sua chave API, se a 'Generative Language API' está ativa no Google Cloud e suas cotas.")
        st.stop()

# --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (EXCETO A DOS CHECKBOXES DE PLATAFORMA QUE FOI REMOVIDA) ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    # Usando chaves mais únicas e versionadas
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    details["objective"] = st.text_area(
        f"Qual o principal objetivo com est(e/a) {type_of_creation}?",
        key=f"{section_key}_obj_new_v14" 
    )
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience_new_v14")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product_new_v14")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message_new_v14")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp_new_v14")
    details["style_tone"] = st.selectbox(
        "Qual o tom/estilo da comunicação?",
        ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"),
        key=f"{section_key}_tone_new_v14"
    )
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra_new_v14")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    st.download_button(
        label="📥 Baixar Conteúdo Gerado",
        data=generated_content.encode('utf-8'),
        file_name=f"{file_name_prefix}_{section_key}_new.txt",
        mime="text/plain",
        key=f"download_{section_key}_new_v14"
    )
    cols_actions = st.columns(2)
    with cols_actions[0]:
        if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn_new_v14"):
            st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
            st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
    with cols_actions[1]:
        if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn_new_v14"):
            st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

# --- HANDLER FUNCTIONS ---
def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
    with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em copywriting...", f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.", 
            f"**Objetivo:** {details_dict['objective']}", # ... (prompt completo)
             "6. Se o usuário enviou arquivos de suporte..."
        ] # Prompt completo omitido para brevidade
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_post_content_new = ai_response.content

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
    with st.spinner("🧠 A IA está elaborando seu plano de campanha..."):
        prompt_parts = ["**Instrução para IA:** Você é um estrategista de marketing digital...", f"**Nome da Campanha:** {campaign_specifics['name']}",# ... (prompt completo)
                        "Se o usuário enviou arquivos de suporte..."] # Prompt completo omitido
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_campaign_content_new = ai_response.content

# ... (Os outros _marketing_handle_... functions não precisam de alteração nesta etapa)
def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
    with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
        prompt_parts = ["**Instrução para IA:** Você é um especialista em UX/UI e copywriting...", f"**Objetivo da Landing Page:** {lp_details['purpose']}", f"**Público-Alvo (Persona):** {lp_details['target_audience']}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Principais Benefícios:** {lp_details['key_benefits']}", f"**Chamada para Ação (CTA):** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details['visual_prefs']}", "**Tarefa:** Crie uma estrutura detalhada..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_lp_content_new = generated_content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
    with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
        prompt_parts = ["**Instrução para IA:** Você é um arquiteto de informação...", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo do Site:** {site_details['main_purpose']}", f"**Público-Alvo:** {site_details['target_audience']}", f"**Páginas Essenciais:** {site_details['essential_pages']}", f"**Principais Produtos/Serviços:** {site_details['key_features']}", f"**Personalidade da Marca:** {site_details['brand_personality']}", f"**Preferências Visuais:** {site_details['visual_references']}", "**Tarefa:** Desenvolva uma proposta de estrutura..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_site_content_new = generated_content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
    with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente Detetive de Clientes'...", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details['location']}", f"**Verba:** {client_details['budget']}", f"**Faixa Etária/Gênero:** {client_details['age_gender']}", f"**Interesses:** {client_details['interests']}", f"**Canais:** {client_details['current_channels']}", f"**Deep Research:** {'Ativado' if client_details['deep_research'] else 'Padrão'}", "**Tarefa:** Realize uma análise completa do público-alvo..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_client_analysis_new = generated_content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
    with st.spinner("🔬 A IA está analisando a concorrência..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva'...", f"**Negócio do Usuário:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}", "**Tarefa:** Elabore um relatório breve e útil..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_competitor_analysis_new = generated_content

# --- Classe do Agente (AssistentePMEPro) ---
class AssistentePMEPro:
    def __init__(self, llm_passed_model):
        if llm_passed_model is None:
            st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
            st.stop()
        self.llm = llm_passed_model
        self.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)
        self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True)

    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        st.markdown("---")

        marketing_files_info_for_prompt = []
        with st.sidebar:
            st.subheader("📎 Suporte para Marketing")
            uploaded_marketing_files = st.file_uploader(
                "Upload para Marketing (opcional):",
                accept_multiple_files=True,
                type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx', 'mp4', 'mov'],
                key="marketing_files_uploader_new_section_v14" 
            )
            if uploaded_marketing_files:
                temp_marketing_files_info = []
                for up_file in uploaded_marketing_files:
                    temp_marketing_files_info.append({"name": up_file.name, "type": up_file.type, "size": up_file.size})
                if temp_marketing_files_info:
                    marketing_files_info_for_prompt = temp_marketing_files_info
                    st.success(f"{len(uploaded_marketing_files)} arquivo(s) de marketing carregado(s)!")
                    with st.expander("Ver arquivos de marketing"):
                        for finfo in marketing_files_info_for_prompt:
                            st.write(f"- {finfo['name']} ({finfo['type']})")
            st.markdown("---")

        main_action_key = "main_marketing_action_choice_new_v14"
        main_action = st.radio(
            "Olá! O que você quer fazer agora em marketing digital?",
            ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
             "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
             "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
             "6 - Conhecer a concorrência (Análise Competitiva)"),
            index=0, key=main_action_key
        )
        st.markdown("---")

        platforms_config_render = { 
            "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", 
            "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
            "E-mail Marketing (lista própria)": "email_own", 
            "E-mail Marketing (Campanha Google Ads)": "email_google"
        }
        platform_names_available = list(platforms_config_render.keys())


        if main_action == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            form_key_post = "post_creator_form_new_v14" 
            with st.form(form_key_post):
                st.subheader(" Plataformas Desejadas:") # Subheader DENTRO do form
                
                key_for_select_all_post = f"post_new_v14_marketing_select_all"
                st.checkbox("Selecionar Todas as Plataformas Acima", key=key_for_select_all_post)
                
                cols_post = st.columns(2)
                keys_for_platforms_post = {}
                has_email_option_post = False
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_render.items()):
                    col_index = i % 2
                    platform_key = f"post_new_v14_marketing_platform_{platform_suffix}"
                    keys_for_platforms_post[platform_name] = platform_key
                    with cols_post[col_index]:
                        st.checkbox(platform_name, key=platform_key) # Sem 'value' dinâmico
                    if "E-mail Marketing" in platform_name: has_email_option_post = True
                if has_email_option_post: st.caption("💡 Para e-mail marketing...")

                post_details = _marketing_get_objective_details("post_new_v14", "post")
                submit_button_pressed = st.form_submit_button("💡 Gerar Post!")

            if submit_button_pressed:
                submitted_select_all_value = st.session_state.get(key_for_select_all_post, False)
                actual_selected_platforms = []
                if submitted_select_all_value:
                    actual_selected_platforms = platform_names_available
                else:
                    for platform_name, platform_key in keys_for_platforms_post.items():
                        if st.session_state.get(platform_key, False):
                            actual_selected_platforms.append(platform_name)
                _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, actual_selected_platforms, self.llm)

            if 'generated_post_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_new, "post_new_v14", "post_ia")

        elif main_action == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            form_key_campaign = "campaign_creator_form_new_v14"
            with st.form(form_key_campaign):
                campaign_name = st.text_input("Nome da Campanha:", key="campaign_name_new_v14")
                st.subheader(" Plataformas Desejadas:")

                key_for_select_all_camp = f"campaign_new_v14_marketing_select_all"
                st.checkbox("Selecionar Todas as Plataformas Acima", key=key_for_select_all_camp)

                cols_camp = st.columns(2)
                keys_for_platforms_camp = {}
                has_email_option_camp = False
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_render.items()):
                    col_index = i % 2
                    platform_key = f"campaign_new_v14_marketing_platform_{platform_suffix}"
                    keys_for_platforms_camp[platform_name] = platform_key
                    with cols_camp[col_index]:
                        st.checkbox(platform_name, key=platform_key) # Sem 'value' dinâmico
                    if "E-mail Marketing" in platform_name: has_email_option_camp = True
                if has_email_option_camp: st.caption("💡 Para e-mail marketing...")
                
                campaign_details_obj = _marketing_get_objective_details("campaign_new_v14", "campanha")
                campaign_duration = st.text_input("Duração Estimada:", key="campaign_duration_new_v14")
                campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key="campaign_budget_new_v14")
                specific_kpis = st.text_area("KPIs mais importantes:", key="campaign_kpis_new_v14")
                submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_button_pressed_camp:
                submitted_select_all_value_camp = st.session_state.get(key_for_select_all_camp, False)
                actual_selected_platforms_camp = []
                if submitted_select_all_value_camp:
                    actual_selected_platforms_camp = platform_names_available
                else:
                    for platform_name, platform_key in keys_for_platforms_camp.items():
                        if st.session_state.get(platform_key, False):
                            actual_selected_platforms_camp.append(platform_name)
                
                campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration,
                                           "budget": campaign_budget_approx, "kpis": specific_kpis}
                _marketing_handle_criar_campanha(marketing_files_info_for_prompt, campaign_details_obj, campaign_specifics_dict, actual_selected_platforms_camp, self.llm)

            if 'generated_campaign_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_new, "campaign_new_v14", "campanha_ia")
        
        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form("landing_page_form_new_v14"):
                lp_purpose = st.text_input("Principal objetivo da landing page:", key="lp_purpose_new_v14")
                lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key="lp_audience_new_v14")
                # ... (resto dos inputs como antes)
                lp_main_offer = st.text_area("Oferta principal e irresistível:", key="lp_offer_new_v14")
                lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key="lp_benefits_new_v14")
                lp_cta = st.text_input("Chamada para ação (CTA) principal:", key="lp_cta_new_v14")
                lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key="lp_visual_new_v14")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")
            if submitted_lp:
                lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details_dict, self.llm)
            if 'generated_lp_content_new' in st.session_state:
                st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                st.markdown(st.session_state.generated_lp_content_new)
                st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state.generated_lp_content_new.encode('utf-8'), file_name="landing_page_sugestoes_ia_new.txt", mime="text/plain", key="download_lp_new_v14") 

        elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
            st.subheader("🏗️ Arquiteto de Sites com IA")
            with st.form("site_creator_form_new_v14"): 
                site_business_type = st.text_input("Tipo do seu negócio/empresa:", key="site_biz_type_new_v14")
                # ... (resto dos inputs como antes)
                site_main_purpose = st.text_area("Principal objetivo do seu site:", key="site_purpose_new_v14")
                site_target_audience = st.text_input("Público principal do site:", key="site_audience_new_v14")
                site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key="site_pages_new_v14")
                site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key="site_features_new_v14")
                site_brand_personality = st.text_input("Personalidade da sua marca:", key="site_brand_new_v14")
                site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key="site_visual_ref_new_v14")
                submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")
            if submitted_site:
                site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details_dict, self.llm)
            if 'generated_site_content_new' in st.session_state:
                st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                st.markdown(st.session_state.generated_site_content_new)
                st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state.generated_site_content_new.encode('utf-8'), file_name="site_sugestoes_ia_new.txt", mime="text/plain",key="download_site_new_v14")

        elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
            st.subheader("🎯 Decodificador de Clientes com IA")
            with st.form("find_client_form_new_v14"):
                # ... (inputs como antes)
                fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key="fc_campaign_new_v14")
                fc_location = st.text_input("Cidade(s) ou região de alcance:", key="fc_location_new_v14")
                fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key="fc_budget_new_v14")
                fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key="fc_age_gender_new_v14")
                fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key="fc_interests_new_v14")
                fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key="fc_channels_new_v14")
                fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key="fc_deep_new_v14")
                submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")
            if submitted_fc:
                client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details_dict, self.llm)
            if 'generated_client_analysis_new' in st.session_state:
                st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                st.markdown(st.session_state.generated_client_analysis_new)
                st.download_button(label="📥 Baixar Análise de Público",data=st.session_state.generated_client_analysis_new.encode('utf-8'), file_name="analise_publico_alvo_ia_new.txt", mime="text/plain",key="download_client_analysis_new_v14")
        
        elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
            st.subheader("🧐 Radar da Concorrência com IA")
            with st.form("competitor_analysis_form_new_v14"):
                # ... (inputs como antes)
                ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key="ca_your_biz_new_v14")
                ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key="ca_competitors_new_v14")
                ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key="ca_aspects_new_v14")
                submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")
            if submitted_ca:
                competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details_dict, self.llm)
            if 'generated_competitor_analysis_new' in st.session_state:
                st.subheader("📊 Análise da Concorrência e Insights:")
                st.markdown(st.session_state.generated_competitor_analysis_new)
                st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state.generated_competitor_analysis_new.encode('utf-8'), file_name="analise_concorrencia_ia_new.txt",mime="text/plain",key="download_competitor_analysis_new_v14")

        elif main_action == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            logo_url_marketing_welcome = "https://i.imgur.com/7IIYxq1.png"
            st.image(logo_url_marketing_welcome, caption="Assistente PME Pro", width=200)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\"..." # Prompt completo omitido
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação com IA...""" # Prompt completo omitido
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios especialista em IA...""" # Prompt completo omitido
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

# --- Funções Utilitárias de Chat ---
def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    chat_display_key = f"chat_display_{area_chave}"
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
            memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        elif hasattr(memoria_agente_instancia.chat_memory, 'messages'):
             memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
    if area_chave == "calculo_precos": st.session_state.last_uploaded_image_info_pricing = None; st.session_state.processed_image_id_pricing = None
    elif area_chave == "gerador_ideias": st.session_state.uploaded_file_info_ideias_for_prompt = None; st.session_state.processed_file_id_ideias = None

def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state: st.session_state[chat_display_key] = []
    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v14_final")
    if prompt_usuario:
        st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"): st.markdown(prompt_usuario)
        if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing = True
        elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias = True
        with st.spinner("Assistente PME Pro está processando... 🤔"):
            resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
        st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
        st.rerun()

# --- Interface Principal Streamlit ---
if llm_model_instance:
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
    agente = st.session_state.agente_pme

    URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
    st.sidebar.image(URL_DO_SEU_LOGO, width=200)
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("IA para seu Negócio Decolar!")
    st.sidebar.markdown("---")

    opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado",
                   "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos",
                   "Gerador de Ideias para Negócios": "gerador_ideias"}

    if 'area_selecionada' not in st.session_state: st.session_state.area_selecionada = "Página Inicial"
    for nome_menu_init, chave_secao_init in opcoes_menu.items():
        if chave_secao_init != "marketing_guiado" and f"chat_display_{chave_secao_init}" not in st.session_state:
            st.session_state[f"chat_display_{chave_secao_init}"] = []
    
    if 'previous_area_selecionada_for_chat_init_processed_v14' not in st.session_state:
        st.session_state['previous_area_selecionada_for_chat_init_processed_v14'] = None

    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?", options=list(opcoes_menu.keys()), key='sidebar_selection_v24_final', 
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        if area_selecionada_label != "Marketing Digital com IA (Guia)":
            for key_to_clear in list(st.session_state.keys()):
                if key_to_clear.startswith("generated_") and key_to_clear.endswith("_new"): del st.session_state[key_to_clear]
                if "_marketing_select_all_v" in key_to_clear or "_marketing_platform_" in key_to_clear:
                     if st.session_state.get(key_to_clear) is not None: del st.session_state[key_to_clear]
        st.rerun()

    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
        if st.session_state.area_selecionada != st.session_state.get('previous_area_selecionada_for_chat_init_processed_v14'):
            chat_display_key_nav = f"chat_display_{current_section_key}"
            if chat_display_key_nav not in st.session_state or not st.session_state[chat_display_key_nav]:
                msg_inicial_nav = ""; memoria_agente_nav = None
                if current_section_key == "plano_negocios": msg_inicial_nav = "Olá! Sou seu Assistente PME Pro..."; memoria_agente_nav = agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços..."; memoria_agente_nav = agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar..."; memoria_agente_nav = agente.memoria_gerador_ideias
                if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
            st.session_state['previous_area_selecionada_for_chat_init_processed_v14'] = st.session_state.area_selecionada

    if current_section_key == "pagina_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA...</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda...</p></div>", unsafe_allow_html=True)
        st.markdown("---"); st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo' width='200'></div>", unsafe_allow_html=True); st.markdown("---")
        num_botoes_funcionais = len(opcoes_menu) -1
        if num_botoes_funcionais > 0 :
            num_cols_render = min(num_botoes_funcionais, 4); cols_botoes_pg_inicial = st.columns(num_cols_render)
            btn_idx_pg_inicial = 0
            for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                if chave_secao_btn_pg != "pagina_inicial":
                    col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                    button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" para ")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" (Guia)","")
                    if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v13_final_v14", use_container_width=True):
                        st.session_state.area_selecionada = nome_menu_btn_pg; st.rerun()
                    btn_idx_pg_inicial +=1
            st.balloons()

    elif current_section_key == "marketing_guiado": agente.marketing_digital_guiado()
    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA"); st.caption("Converse comigo...")
        exibir_chat_e_obter_input(current_section_key, "Sua resposta...", agente.conversar_plano_de_negocios)
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v14_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar...", agente.memoria_plano_negocios); st.rerun()
    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA"); st.caption("Vamos definir os melhores preços...")
        uploaded_image = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v14_final")
        descricao_imagem_para_ia = None
        if uploaded_image is not None:
            if st.session_state.get('processed_image_id_pricing') != uploaded_image.id:
                try:
                    st.image(Image.open(uploaded_image), caption=f"Imagem: {uploaded_image.name}", width=150)
                    descricao_imagem_para_ia = f"O usuário carregou uma imagem chamada '{uploaded_image.name}'. Considere esta informação."
                    st.session_state.last_uploaded_image_info_pricing = descricao_imagem_para_ia
                    st.session_state.processed_image_id_pricing = uploaded_image.id
                    st.info(f"Imagem '{uploaded_image.name}' pronta para ser considerada no próximo diálogo.")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {e}")
                    st.session_state.last_uploaded_image_info_pricing = None
                    st.session_state.processed_image_id_pricing = None
        kwargs_preco_chat = {}
        current_image_context = st.session_state.get('last_uploaded_image_info_pricing')
        if current_image_context: kwargs_preco_chat['descricao_imagem_contexto'] = current_image_context
        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou descreva o produto/serviço", agente.calcular_precos_interativo, **kwargs_preco_chat)
        if 'user_input_processed_pricing' in st.session_state and st.session_state.user_input_processed_pricing:
            if st.session_state.get('last_uploaded_image_info_pricing'): st.session_state.last_uploaded_image_info_pricing = None
            st.session_state.user_input_processed_pricing = False
        if st.sidebar.button("Reiniciar Cálculo de Preços", key="btn_reset_precos_v14_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar um novo cálculo de preços! ...", agente.memoria_calculo_precos); st.rerun()

    elif current_section_key == "gerador_ideias":
        st.header("💡 Gerador de Ideias para seu Negócio com IA"); st.caption("Descreva seus desafios...")
        uploaded_files_ideias_ui = st.file_uploader("Envie arquivos (.txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_v14_final")
        contexto_para_ia_ideias_local = None
        if uploaded_files_ideias_ui:
            current_file_signature = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias_ui]))
            if st.session_state.get('processed_file_id_ideias') != current_file_signature or not st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                text_contents_ui = []; image_info_ui = []
                for uploaded_file_item in uploaded_files_ideias_ui:
                    try:
                        if uploaded_file_item.type == "text/plain": text_contents_ui.append(f"Conteúdo de '{uploaded_file_item.name}':\n{uploaded_file_item.read().decode('utf-8')[:2000]}...")
                        elif uploaded_file_item.type in ["image/png", "image/jpeg"]: st.image(Image.open(uploaded_file_item), caption=f"Imagem: {uploaded_file_item.name}", width=100); image_info_ui.append(f"Imagem '{uploaded_file_item.name}' carregada.")
                    except Exception as e: st.error(f"Erro ao processar '{uploaded_file_item.name}': {e}")
                full_context_ui = ""; 
                if text_contents_ui: full_context_ui += "\n\n--- TEXTO ---\n" + "\n\n".join(text_contents_ui)
                if image_info_ui: full_context_ui += "\n\n--- IMAGENS ---\n" + "\n".join(image_info_ui)
                if full_context_ui: st.session_state.uploaded_file_info_ideias_for_prompt = full_context_ui.strip(); contexto_para_ia_ideias_local = st.session_state.uploaded_file_info_ideias_for_prompt; st.info("Arquivo(s) pronto(s).")
                else: st.session_state.uploaded_file_info_ideias_for_prompt = None
                st.session_state.processed_file_id_ideias = current_file_signature
            else: contexto_para_ia_ideias_local = st.session_state.get('uploaded_file_info_ideias_for_prompt')
        kwargs_ideias_chat_ui = {}; 
        if contexto_para_ia_ideias_local: kwargs_ideias_chat_ui['contexto_arquivos'] = contexto_para_ia_ideias_local
        exibir_chat_e_obter_input(current_section_key, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat_ui)
        if 'user_input_processed_ideias' in st.session_state and st.session_state.user_input_processed_ideias: st.session_state.user_input_processed_ideias = False
        if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v14_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar uma nova busca por ideias! ...", agente.memoria_gerador_ideias); st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
