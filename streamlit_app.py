import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth
import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth

# LINHAS DE TESTE PARA DIAGNÓSTICO:
st.write("Conteúdo do módulo st_auth:")
st.write(dir(st_auth))
st.stop() # Interrompe o script aqui para vermos o output do dir()

# O restante do seu código continua abaixo, mas não será executado por causa do st.stop()
# st.set_page_config(
# ... (etc.)
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

auth = None
firebase_config_loaded_successfully = False
llm_model_instance = None

try:
    firebase_config_from_secrets = st.secrets["firebase_config"]
    cookie_config_from_secrets = st.secrets["cookie_firebase"]
    
    auth = st_auth.Authenticate(
        config=firebase_config_from_secrets.to_dict() if hasattr(firebase_config_from_secrets, 'to_dict') else dict(firebase_config_from_secrets), 
        cookie_name=cookie_config_from_secrets["name"],
        key=cookie_config_from_secrets["key"],
        cookie_expiry_days=int(cookie_config_from_secrets["expiry_days"])
    )
    firebase_config_loaded_successfully = True

except KeyError as e:
    missing_key_info = str(e)
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Chave não encontrada nos Segredos: {missing_key_info}. Verifique [firebase_config] e [cookie_firebase] (com name, key, expiry_days).")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO FATAL ao inicializar o autenticador Firebase: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

if not auth:
    st.error("Falha crítica: Objeto de autenticação Firebase não pôde ser inicializado.")
    st.stop()

auth.login()

if not st.session_state.get("authentication_status"):
    st.stop()

st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if auth.logout("Logout", "sidebar"):
    keys_to_clear_on_logout = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_logout in keys_to_clear_on_logout:
        if key_logout.startswith("chat_display_") or \
           key_logout.startswith("memoria_") or \
           key_logout.startswith("generated_") or \
           "_v15_" in key_logout or "_v16_" in key_logout or "_auth" in key_logout:
            del st.session_state[key_logout]
    st.experimental_rerun()

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("🚨 ERRO: GOOGLE_API_KEY configurada nos segredos está vazia.")
        st.stop()
    
    genai.configure(api_key=GOOGLE_API_KEY)
    llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                             temperature=0.75,
                                             google_api_key=GOOGLE_API_KEY,
                                             convert_system_message_to_human=True)
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
    st.stop()
except Exception as e:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
    st.stop()

if not llm_model_instance:
    st.error("🚨 Modelo LLM não pôde ser inicializado.")
    st.stop()

def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = f"_{section_key}_fbauth_v1" 
    details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"obj{key_suffix}")
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"audience{key_suffix}")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"product{key_suffix}")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"message{key_suffix}")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"usp{key_suffix}")
    details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"tone{key_suffix}")
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"extra{key_suffix}")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    key_suffix = f"_{section_key}_fbauth_v1"
    st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}{key_suffix}.txt", mime="text/plain", key=f"download{key_suffix}")

def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
    with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil...",
            f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.", f"**Produto/Serviço Principal:** {details_dict['product_service']}",
            f"**Público-Alvo:** {details_dict['target_audience']}", f"**Objetivo do Post:** {details_dict['objective']}",
            f"**Mensagem Chave:** {details_dict['key_message']}", f"**Proposta Única de Valor (USP):** {details_dict['usp']}",
            f"**Tom/Estilo:** {details_dict['style_tone']}", f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
        ] 
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_post_content_new = ai_response.content

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
    with st.spinner("🧠 A IA está elaborando seu plano de campanha..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um estrategista de marketing digital experiente, focado em PMEs no Brasil...",
            f"**Nome da Campanha:** {campaign_specifics['name']}", f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
            f"**Produto/Serviço Principal:** {details_dict['product_service']}", f"**Público-Alvo:** {details_dict['target_audience']}",
            f"**Objetivo Principal:** {details_dict['objective']}", f"**Mensagem Chave:** {details_dict['key_message']}",
            f"**USP:** {details_dict['usp']}", f"**Tom/Estilo:** {details_dict['style_tone']}",
            f"**Duração Estimada:** {campaign_specifics['duration']}", f"**Orçamento Aproximado:** {campaign_specifics['budget']}",
            f"**KPIs:** {campaign_specifics['kpis']}", f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
        ] 
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_campaign_content_new = ai_response.content

def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
    with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
        prompt_parts = ["**Instrução para IA:** Você é um especialista em UX/UI e copywriting...", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details['target_audience']}", f"**Oferta:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details['key_benefits']}", f"**CTA:** {lp_details['cta']}", f"**Visuais:** {lp_details['visual_prefs']}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_lp_content_new = ai_response.content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
    with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
        prompt_parts = ["**Instrução para IA:** Você é um arquiteto de informação...", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo:** {site_details['main_purpose']}", f"**Público:** {site_details['target_audience']}", f"**Páginas:** {site_details['essential_pages']}", f"**Produtos/Serviços:** {site_details['key_features']}", f"**Marca:** {site_details['brand_personality']}", f"**Referências:** {site_details['visual_references']}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_site_content_new = ai_response.content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
    with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente Detetive de Clientes'...", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details['location']}", f"**Verba:** {client_details['budget']}", f"**Faixa Etária/Gênero:** {client_details['age_gender']}", f"**Interesses:** {client_details['interests']}", f"**Canais:** {client_details['current_channels']}", f"**Deep Research:** {'Ativado' if client_details['deep_research'] else 'Padrão'}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_client_analysis_new = ai_response.content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
    with st.spinner("🔬 A IA está analisando a concorrência..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva'...", f"**Seu Negócio:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_competitor_analysis_new = ai_response.content

class AssistentePMEPro:
    def __init__(self, llm_model_instance_passed):
        self.llm = llm_model_instance_passed
        # Usar chaves únicas para cada instância de memória no session_state
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth', ConversationBufferMemory(memory_key="hist_plano_fb", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth', ConversationBufferMemory(memory_key="hist_precos_fb", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth', ConversationBufferMemory(memory_key="hist_ideias_fb", return_messages=True))

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
        
        marketing_files_info_for_prompt_local = [] 

        main_action_key_marketing = "main_marketing_action_choice_fbauth"
        opcoes_menu_marketing_tuple = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                                     "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                                     "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                                     "6 - Conhecer a concorrência (Análise Competitiva)")
        
        if f"{main_action_key_marketing}_index" not in st.session_state:
             st.session_state[f"{main_action_key_marketing}_index"] = 0

        def on_radio_change_marketing_cb_local():
            current_selection = st.session_state[main_action_key_marketing]
            if current_selection in opcoes_menu_marketing_tuple:
                 st.session_state[f"{main_action_key_marketing}_index"] = opcoes_menu_marketing_tuple.index(current_selection)
            else:
                 st.session_state[f"{main_action_key_marketing}_index"] = 0


        main_action = st.radio(
            "Olá! O que você quer fazer agora em marketing digital?",
            opcoes_menu_marketing_tuple,
            index=st.session_state[f"{main_action_key_marketing}_index"], 
            key=main_action_key_marketing,
            on_change=on_radio_change_marketing_cb_local
        )
        st.markdown("---")
        
        platforms_config_options = { 
            "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", 
            "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
            "E-mail Marketing (lista própria)": "email_own", 
            "E-mail Marketing (Campanha Google Ads)": "email_google"
        }
        platform_names_available_list = list(platforms_config_options.keys())

        if main_action == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            with st.form("post_creator_form_fbauth", clear_on_submit=True):
                st.subheader(" Plataformas Desejadas:")
                key_select_all_post = "post_select_all_cb_fbauth"
                select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_post)
                cols_post = st.columns(2)
                form_platform_selections_post = {}
                
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                    col_index = i % 2
                    platform_key_form = f"post_platform_{platform_suffix}_cb_fbauth"
                    with cols_post[col_index]:
                        is_checked = select_all_post_checked or st.session_state.get(platform_key_form, False)
                        form_platform_selections_post[platform_name] = st.checkbox(platform_name, key=platform_key_form, value=is_checked)
                
                post_details = _marketing_get_objective_details("post_creator", "post")
                submit_button_pressed_post = st.form_submit_button("💡 Gerar Post!")

            if submit_button_pressed_post:
                actual_selected_platforms = []
                if st.session_state.get(key_select_all_post, False):
                    actual_selected_platforms = platform_names_available_list
                else:
                    for platform_name, platform_suffix in platforms_config_options.items():
                         if st.session_state.get(f"post_platform_{platform_suffix}_cb_fbauth", False):
                            actual_selected_platforms.append(platform_name)
                _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, actual_selected_platforms, self.llm)

            if 'generated_post_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_new, "post_output_fbauth", "post_ia")
        
        elif main_action == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            with st.form("campaign_creator_form_fbauth", clear_on_submit=True):
                campaign_name = st.text_input("Nome da Campanha:", key="campaign_name_fbauth")
                st.subheader(" Plataformas Desejadas:")
                key_select_all_camp = "campaign_select_all_cb_fbauth"
                select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_camp)
                cols_camp = st.columns(2)
                form_platform_selections_camp = {}

                for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                    col_index = i % 2
                    platform_key_form = f"campaign_platform_{platform_suffix}_cb_fbauth"
                    with cols_camp[col_index]:
                         form_platform_selections_camp[platform_name] = st.checkbox(platform_name, key=platform_key_form, value=select_all_camp_checked)
                
                campaign_details_obj = _marketing_get_objective_details("campaign_creator", "campanha")
                campaign_duration = st.text_input("Duração Estimada:", key="campaign_duration_fbauth")
                campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key="campaign_budget_fbauth")
                specific_kpis = st.text_area("KPIs mais importantes:", key="campaign_kpis_fbauth")
                submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_button_pressed_camp:
                actual_selected_platforms_camp = []
                if st.session_state.get(key_select_all_camp, False):
                    actual_selected_platforms_camp = platform_names_available_list
                else:
                    for platform_name, platform_suffix in platforms_config_options.items():
                        if st.session_state.get(f"campaign_platform_{platform_suffix}_cb_fbauth", False):
                            actual_selected_platforms_camp.append(platform_name)
                
                campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration,
                                           "budget": campaign_budget_approx, "kpis": specific_kpis}
                _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, actual_selected_platforms_camp, self.llm)

            if 'generated_campaign_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_new, "campaign_output_fbauth", "campanha_ia")

        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form("landing_page_form_fbauth", clear_on_submit=False):
                lp_purpose = st.text_input("Principal objetivo da landing page:", key="lp_purpose_fbauth")
                lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key="lp_audience_fbauth")
                lp_main_offer = st.text_area("Oferta principal e irresistível:", key="lp_offer_fbauth")
                lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key="lp_benefits_fbauth")
                lp_cta = st.text_input("Chamada para ação (CTA) principal:", key="lp_cta_fbauth")
                lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key="lp_visual_fbauth")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")
            if submitted_lp:
                lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details_dict, self.llm)
            if 'generated_lp_content_new' in st.session_state:
                st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                st.markdown(st.session_state.generated_lp_content_new)
                st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state.generated_lp_content_new.encode('utf-8'), file_name="landing_page_sugestoes_ia.txt", mime="text/plain", key="download_lp_fbauth") 

        elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
            st.subheader("🏗️ Arquiteto de Sites com IA")
            with st.form("site_creator_form_fbauth", clear_on_submit=False): 
                site_business_type = st.text_input("Tipo do seu negócio/empresa:", key="site_biz_type_fbauth")
                site_main_purpose = st.text_area("Principal objetivo do seu site:", key="site_purpose_fbauth")
                site_target_audience = st.text_input("Público principal do site:", key="site_audience_fbauth")
                site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key="site_pages_fbauth")
                site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key="site_features_fbauth")
                site_brand_personality = st.text_input("Personalidade da sua marca:", key="site_brand_fbauth")
                site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key="site_visual_ref_fbauth")
                submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")
            if submitted_site:
                site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details_dict, self.llm)
            if 'generated_site_content_new' in st.session_state:
                st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                st.markdown(st.session_state.generated_site_content_new)
                st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state.generated_site_content_new.encode('utf-8'), file_name="site_sugestoes_ia.txt", mime="text/plain",key="download_site_fbauth")

        elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
            st.subheader("🎯 Decodificador de Clientes com IA")
            with st.form("find_client_form_fbauth", clear_on_submit=False):
                fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key="fc_campaign_fbauth")
                fc_location = st.text_input("Cidade(s) ou região de alcance:", key="fc_location_fbauth")
                fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key="fc_budget_fbauth")
                fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key="fc_age_gender_fbauth")
                fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key="fc_interests_fbauth")
                fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key="fc_channels_fbauth")
                fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key="fc_deep_fbauth")
                submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")
            if submitted_fc:
                client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details_dict, self.llm)
            if 'generated_client_analysis_new' in st.session_state:
                st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                st.markdown(st.session_state.generated_client_analysis_new)
                st.download_button(label="📥 Baixar Análise de Público",data=st.session_state.generated_client_analysis_new.encode('utf-8'), file_name="analise_publico_alvo_ia.txt", mime="text/plain",key="download_client_analysis_fbauth")
        
        elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
            st.subheader("🧐 Radar da Concorrência com IA")
            with st.form("competitor_analysis_form_fbauth", clear_on_submit=False):
                ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key="ca_your_biz_fbauth")
                ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key="ca_competitors_fbauth")
                ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key="ca_aspects_fbauth")
                submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")
            if submitted_ca:
                competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details_dict, self.llm)
            if 'generated_competitor_analysis_new' in st.session_state:
                st.subheader("📊 Análise da Concorrência e Insights:")
                st.markdown(st.session_state.generated_competitor_analysis_new)
                st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state.generated_competitor_analysis_new.encode('utf-8'), file_name="analise_concorrencia_ia.txt",mime="text/plain",key="download_competitor_analysis_fbauth")

        elif main_action == "Selecione uma opção...": 
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            LOGO_PATH_MARKETING = "images/logo-pme-ia.png" # Idealmente, esta imagem está no repo do APP
            if os.path.exists(LOGO_PATH_MARKETING):
                st.image(LOGO_PATH_MARKETING, caption="Assistente PME Pro", width=200)
            else:
                st.image("https://i.imgur.com/7IIYxq1.png", caption="Assistente PME Pro (Logo Padrão)", width=200)


    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente especializado em auxiliar Pequenas e Médias Empresas (PMEs) no Brasil a desenvolverem planos de negócios robustos e estratégicos..." # Prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano_v1_auth")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_content = f"O usuário está buscando ajuda para precificar um produto/serviço e forneceu a seguinte informação inicial: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_content = f"Contexto visual da imagem '{descricao_imagem_contexto}' deve ser considerado.\n\n{prompt_content}"
        system_message_precos = f"""Você é o "Assistente PME Pro", um especialista em estratégias de precificação para PMEs no Brasil... {prompt_content}""" # Prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos_v1_auth")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario}) 
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_content = f"O usuário busca ideias de negócios e diz: '{input_usuario}'."
        if contexto_arquivos:
            prompt_content = f"Considerando os seguintes arquivos e contextos fornecidos pelo usuário:\n{contexto_arquivos}\n\n{prompt_content}"
        system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios altamente criativo... {prompt_content}""" # Prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias_v1_auth")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

def inicializar_ou_resetar_chat_global(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    chat_display_key = f"chat_display_{area_chave}"
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
            memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
            memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))

    if area_chave == "calculo_precos": 
        st.session_state.pop('last_uploaded_image_info_pricing', None)
        st.session_state.pop('processed_image_id_pricing', None)
        st.session_state.pop('user_input_processed_pricing', None) 
    elif area_chave == "gerador_ideias": 
        st.session_state.pop('uploaded_file_info_ideias_for_prompt', None)
        st.session_state.pop('processed_file_id_ideias', None)
        st.session_state.pop('user_input_processed_ideias', None)


def exibir_chat_e_obter_input_global(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state: 
        st.session_state[chat_display_key] = [] 

    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]): 
            st.markdown(msg_info["content"])
    
    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_fbauth")
    
    if prompt_usuario:
        st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"): 
            st.markdown(prompt_usuario)
        
        local_kwargs = kwargs_funcao_agente.copy() # Evita modificar o dict original
        if area_chave == "calculo_precos":
            if st.session_state.get('last_uploaded_image_info_pricing'):
                local_kwargs['descricao_imagem_contexto'] = st.session_state.last_uploaded_image_info_pricing
                st.session_state.user_input_processed_pricing = True 

        elif area_chave == "gerador_ideias":
            if st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                local_kwargs['contexto_arquivos'] = st.session_state.uploaded_file_info_ideias_for_prompt
                st.session_state.user_input_processed_ideias = True
            
        with st.spinner("Assistente PME Pro está processando... 🤔"):
            resposta_ai = funcao_conversa_agente(input_usuario=prompt_usuario, **local_kwargs)

        st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
        
        if area_chave == "calculo_precos" and st.session_state.get('user_input_processed_pricing'):
            st.session_state.last_uploaded_image_info_pricing = None 
            st.session_state.user_input_processed_pricing = False
        if area_chave == "gerador_ideias" and st.session_state.get('user_input_processed_ideias'):
            st.session_state.uploaded_file_info_ideias_for_prompt = None
            st.session_state.user_input_processed_ideias = False
        
        st.rerun()

if 'agente_pme' not in st.session_state:
    if llm_model_instance: # Só cria o agente se o LLM estiver pronto
        st.session_state.agente_pme = AssistentePMEPro(llm_passed_model_instance=llm_model_instance)
    # else: # Se o LLM não inicializou, não podemos criar o agente. Erro já tratado.
    #    pass
agente = st.session_state.get('agente_pme') # Pega o agente da sessão se existir

LOGO_PATH_APP_DISPLAY = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_LOGO = "https://i.imgur.com/7IIYxq1.png"

if os.path.exists(LOGO_PATH_APP_DISPLAY):
    st.sidebar.image(LOGO_PATH_APP_DISPLAY, width=150)
else:
    st.sidebar.image(IMGUR_FALLBACK_LOGO, width=150, caption="Logo Padrão")
    if 'logo_warning_main_shown_fbauth' not in st.session_state:
        st.sidebar.warning(f"Logo local '{LOGO_PATH_APP_DISPLAY}' não encontrada. Usando logo padrão.")
        st.session_state.logo_warning_main_shown_fbauth = True

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_main_dict_fbauth = {
    "Página Inicial": "pagina_inicial", 
    "Marketing Digital com IA (Guia)": "marketing_guiado",
    "Elaborar Plano de Negócios com IA": "plano_negocios", 
    "Cálculo de Preços Inteligente": "calculo_precos",
    "Gerador de Ideias para Negócios": "gerador_ideias"
}
opcoes_menu_main_labels_fbauth = list(opcoes_menu_main_dict_fbauth.keys())
radio_key_sidebar_main_app_fbauth = 'sidebar_main_app_selection_fbauth'

if 'area_selecionada_main_app' not in st.session_state or st.session_state.area_selecionada_main_app not in opcoes_menu_main_dict_fbauth:
    st.session_state.area_selecionada_main_app = opcoes_menu_main_labels_fbauth[0]

if f'{radio_key_sidebar_main_app_fbauth}_index' not in st.session_state:
    try:
        st.session_state[f'{radio_key_sidebar_main_app_fbauth}_index'] = opcoes_menu_main_labels_fbauth.index(st.session_state.area_selecionada_main_app)
    except ValueError:
         st.session_state[f'{radio_key_sidebar_main_app_fbauth}_index'] = 0


def on_main_app_radio_change_fbauth():
    st.session_state.area_selecionada_main_app = st.session_state[radio_key_sidebar_main_app_fbauth]
    st.session_state[f'{radio_key_sidebar_main_app_fbauth}_index'] = opcoes_menu_main_labels_fbauth.index(st.session_state[radio_key_sidebar_main_app_fbauth])
    if st.session_state.area_selecionada_main_app != "Marketing Digital com IA (Guia)":
         keys_to_delete_main_fbauth = [k for k in st.session_state if k.startswith("generated_") or "_cb_fbauth" in k or main_action_key_marketing in k]
         for k_del_main_fbauth in keys_to_delete_main_fbauth:
            if k_del_main_fbauth in st.session_state: del st.session_state[k_del_main_fbauth]
    st.session_state.previous_area_selecionada = None 
    st.experimental_rerun()

area_selecionada_label_main = st.sidebar.radio(
    "Como posso te ajudar hoje?", 
    options=opcoes_menu_main_labels_fbauth, 
    key=radio_key_sidebar_main_app_fbauth, 
    index=st.session_state[f'{radio_key_sidebar_main_app_fbauth}_index'],
    on_change=on_main_app_radio_change_fbauth
)

current_section_key_render = opcoes_menu_main_dict_fbauth.get(st.session_state.area_selecionada_main_app)

if current_section_key_render not in ["pagina_inicial", "marketing_guiado"] and agente: # Adicionado check para agente
    if st.session_state.area_selecionada_main_app != st.session_state.get('previous_area_selecionada'):
        chat_display_key_to_init = f"chat_display_{current_section_key_render}"
        if chat_display_key_to_init not in st.session_state or not st.session_state[chat_display_key_to_init]:
            msg_inicial_para_chat_main = ""
            memoria_agente_para_chat_main = None
            if current_section_key_render == "plano_negocios": 
                msg_inicial_para_chat_main = "Olá! Sou seu Assistente PME Pro..."
                memoria_agente_para_chat_main = agente.memoria_plano_negocios
            elif current_section_key_render == "calculo_precos": 
                msg_inicial_para_chat_main = "Olá! Bem-vindo ao assistente de Cálculo de Preços..."
                memoria_agente_para_chat_main = agente.memoria_calculo_precos
            elif current_section_key_render == "gerador_ideias": 
                msg_inicial_para_chat_main = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar..."
                memoria_agente_para_chat_main = agente.memoria_gerador_ideias
            
            if msg_inicial_para_chat_main and memoria_agente_para_chat_main is not None: 
                inicializar_ou_resetar_chat_global(current_section_key_render, msg_inicial_para_chat_main, memoria_agente_para_chat_main)
        st.session_state.previous_area_selecionada = st.session_state.area_selecionada_main_app

if current_section_key_render == "pagina_inicial":
    st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA...</p></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda...</p></div>", unsafe_allow_html=True)
    st.markdown("---")
    logo_to_display_main = LOGO_PATH_APP_DISPLAY if os.path.exists(LOGO_PATH_APP_DISPLAY) else IMGUR_FALLBACK_LOGO
    st.markdown(f"<div style='text-align: center;'><img src='{logo_to_display_main}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
    st.markdown("---")
    
    num_botoes_funcionais_pg_inicial = len(opcoes_menu_main_dict_fbauth) -1 
    if num_botoes_funcionais_pg_inicial > 0 :
        num_cols_render_pg_inicial = min(num_botoes_funcionais_pg_inicial, 3) 
        cols_botoes_pg_inicial_render = st.columns(num_cols_render_pg_inicial)
        btn_idx_pg_inicial_render = 0
        for nome_menu_btn, chave_secao_btn in opcoes_menu_main_dict_fbauth.items():
            if chave_secao_btn != "pagina_inicial":
                col_btn_pg_inicial = cols_botoes_pg_inicial_render[btn_idx_pg_inicial_render % num_cols_render_pg_inicial]
                button_label_pg_final = nome_menu_btn.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                if col_btn_pg_inicial.button(button_label_pg_final, key=f"btn_goto_{chave_secao_btn}_fbauth", use_container_width=True, help=f"Ir para {nome_menu_btn}"):
                    st.session_state.area_selecionada_main_app = nome_menu_btn
                    st.session_state[f'{radio_key_sidebar_main_app_fbauth}_index'] = opcoes_menu_main_labels_fbauth.index(nome_menu_btn)
                    st.experimental_rerun()
                btn_idx_pg_inicial_render +=1
        st.balloons()

elif current_section_key_render == "marketing_guiado" and agente: 
    agente.marketing_digital_guiado()
elif current_section_key_render == "plano_negocios" and agente:
    st.header("📝 Elaborando seu Plano de Negócios com IA")
    st.caption("Converse com o assistente...")
    exibir_chat_e_obter_input_global(current_section_key_render, "Sua resposta...", agente.conversar_plano_de_negocios)
    if st.sidebar.button("🗑️ Limpar Histórico do Plano", key="btn_reset_plano_fbauth"):
        inicializar_ou_resetar_chat_global(current_section_key_render, "Ok, vamos recomeçar...", agente.memoria_plano_negocios)
        st.experimental_rerun()
elif current_section_key_render == "calculo_precos" and agente:
    st.header("💲 Cálculo de Preços Inteligente com IA")
    st.caption("Descreva seu produto/serviço...")
    uploaded_image_pricing_render = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_fbauth")
    
    if uploaded_image_pricing_render is not None:
        if st.session_state.get('processed_image_id_pricing') != uploaded_image_pricing_render.id:
            try:
                img_pil_pricing_render = Image.open(uploaded_image_pricing_render) 
                st.image(img_pil_pricing_render, caption=f"Imagem: {uploaded_image_pricing_render.name}", width=150)
                st.session_state.last_uploaded_image_info_pricing = f"Imagem '{uploaded_image_pricing_render.name}'."
                st.session_state.processed_image_id_pricing = uploaded_image_pricing_render.id
                st.info(f"Imagem '{uploaded_image_pricing_render.name}' pronta.")
            except Exception as e_img_pricing_render:
                st.error(f"Erro: {e_img_pricing_render}")
                st.session_state.last_uploaded_image_info_pricing = None
                st.session_state.processed_image_id_pricing = None
    
    kwargs_preco_chat_render = {}
    if st.session_state.get('last_uploaded_image_info_pricing') and not st.session_state.get('user_input_processed_pricing', False):
        kwargs_preco_chat_render['descricao_imagem_contexto'] = st.session_state.get('last_uploaded_image_info_pricing')
    
    exibir_chat_e_obter_input_global(current_section_key_render, "Descreva produto/serviço, custos...", agente.calcular_precos_interativo, **kwargs_preco_chat_render)
    
    if st.session_state.get('user_input_processed_pricing'):
        st.session_state.last_uploaded_image_info_pricing = None 
        st.session_state.user_input_processed_pricing = False

    if st.sidebar.button("🗑️ Limpar Histórico de Preços", key="btn_reset_precos_fbauth"):
        inicializar_ou_resetar_chat_global(current_section_key_render, "Ok, novo cálculo...", agente.memoria_calculo_precos)
        st.experimental_rerun()

elif current_section_key_render == "gerador_ideias" and agente:
    st.header("💡 Gerador de Ideias para seu Negócio com IA")
    st.caption("Descreva um desafio...")
    uploaded_files_ideias_render = st.file_uploader("Envie arquivos de contexto (.txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_fbauth")
    
    if uploaded_files_ideias_render:
        current_files_sig_ideias_render = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias_render]))
        if st.session_state.get('processed_file_id_ideias') != current_files_sig_ideias_render or not st.session_state.get('uploaded_file_info_ideias_for_prompt'):
            texts_ideias_render = []
            images_info_ideias_render = []
            for up_file_idea_render in uploaded_files_ideias_render:
                try:
                    if up_file_idea_render.type == "text/plain": 
                        texts_ideias_render.append(f"'{up_file_idea_render.name}':\n{up_file_idea_render.read().decode('utf-8')[:3000]}...")
                    elif up_file_idea_render.type in ["image/png", "image/jpeg"]: 
                        st.image(Image.open(up_file_idea_render), caption=f"Contexto: {up_file_idea_render.name}", width=100)
                        images_info_ideias_render.append(f"Imagem '{up_file_idea_render.name}'.")
                except Exception as e_file_idea_render: st.error(f"Erro '{up_file_idea_render.name}': {e_file_idea_render}")
            
            context_str_ideias_render = ""
            if texts_ideias_render: context_str_ideias_render += "\n\nTEXTO:\n" + "\n\n".join(texts_ideias_render)
            if images_info_ideias_render: context_str_ideias_render += "\n\nIMAGENS:\n" + "\n".join(images_info_ideias_render)
            
            if context_str_ideias_render: 
                st.session_state.uploaded_file_info_ideias_for_prompt = context_str_ideias_render.strip()
                st.info("Arquivo(s) de contexto pronto(s).")
            else: 
                st.session_state.uploaded_file_info_ideias_for_prompt = None
            st.session_state.processed_file_id_ideias = current_files_sig_ideias_render
    
    kwargs_ideias_chat_render = {}
    if st.session_state.get('uploaded_file_info_ideias_for_prompt') and not st.session_state.get('user_input_processed_ideias', False): 
        kwargs_ideias_chat_render['contexto_arquivos'] = st.session_state.get('uploaded_file_info_ideias_for_prompt')
    
    exibir_chat_e_obter_input_global(current_section_key_render, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat_render)
    
    if st.session_state.get('user_input_processed_ideias'):
        st.session_state.uploaded_file_info_ideias_for_prompt = None
        st.session_state.user_input_processed_ideias = False

    if st.sidebar.button("🗑️ Limpar Histórico de Ideias", key="btn_reset_ideias_fbauth"):
        inicializar_ou_resetar_chat_global(current_section_key_render, "Ok, vamos buscar novas ideias!", agente.memoria_gerador_ideias)
        st.experimental_rerun()

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
