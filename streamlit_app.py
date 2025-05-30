import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth # Biblioteca correta para autenticação Firebase

# --- Configuração da Página e Inicialização de Variáveis Essenciais ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

auth = None
firebase_config_loaded_successfully = False
llm_model_instance = None

# --- Bloco de Autenticação Firebase ---
try:
    firebase_config_from_secrets = st.secrets["firebase_config"]
    cookie_config_from_secrets = st.secrets["cookie_firebase"]
    
    # CORREÇÃO APLICADA AQUI: Usar FirebaseAuth com 'F' e 'A' maiúsculos
    auth = st_auth.FirebaseAuth( 
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
    st.exception(e) # Mostra o traceback completo do erro para depuração
    st.stop()

if not auth: # Se o objeto auth não foi criado por algum motivo
    st.error("Falha crítica: Objeto de autenticação Firebase não pôde ser inicializado. Verifique os logs e os segredos.")
    st.stop()

# --- Processo de Login ---
# O widget de login será renderizado aqui.
# A biblioteca streamlit-firebase-auth lida com o estado de 'authentication_status' e 'username'
auth.login() 

# Verifica o status da autenticação. Se não estiver autenticado, interrompe o script aqui.
# A tela de login já terá sido exibida pela chamada `auth.login()` acima.
if not st.session_state.get("authentication_status"):
    st.stop() # Para a execução se o usuário não estiver logado.

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---

# Mensagem de boas-vindas e botão de logout na sidebar
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!") # 'username' é o que streamlit-firebase-auth usa
if auth.logout("Logout", "sidebar"): # O método logout() da biblioteca também lida com o rerun.
    # Limpar estados de sessão específicos do app ao fazer logout, se necessário
    keys_to_clear_on_logout = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_logout in keys_to_clear_on_logout:
        if key_logout.startswith("chat_display_") or \
           key_logout.startswith("memoria_") or \
           key_logout.startswith("generated_") or \
           "_fbauth_" in key_logout: # Usando sufixo _fbauth_ para chaves de sessão
            del st.session_state[key_logout]
    st.experimental_rerun() # Força o rerun para refletir o estado de logout

# --- Inicialização do Modelo de Linguagem (LLM) do Google ---
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
    st.error("🚨 Modelo LLM não pôde ser inicializado. O app não pode continuar.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
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
        ai_response = llm.invoke([HumanMessage(content=final_prompt)]) # LLMChain espera uma lista de mensagens ou prompt
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
        ai_response = llm.invoke([HumanMessage(content=final_prompt)])
        st.session_state.generated_campaign_content_new = ai_response.content
# ... (outras funções _marketing_handle_... devem ter llm.invoke([HumanMessage(...)]) também) ...
# Exemplo para landing page (as outras seguem o mesmo padrão)
def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
    with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
        prompt_parts = ["**Instrução para IA:** Você é um especialista em UX/UI e copywriting...", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details['target_audience']}", f"**Oferta:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details['key_benefits']}", f"**CTA:** {lp_details['cta']}", f"**Visuais:** {lp_details['visual_prefs']}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke([HumanMessage(content=final_prompt)])
        st.session_state.generated_lp_content_new = ai_response.content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
    with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
        prompt_parts = ["**Instrução para IA:** Você é um arquiteto de informação...", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo:** {site_details['main_purpose']}", f"**Público:** {site_details['target_audience']}", f"**Páginas:** {site_details['essential_pages']}", f"**Produtos/Serviços:** {site_details['key_features']}", f"**Marca:** {site_details['brand_personality']}", f"**Referências:** {site_details['visual_references']}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke([HumanMessage(content=final_prompt)])
        st.session_state.generated_site_content_new = ai_response.content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
    with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente Detetive de Clientes'...", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details['location']}", f"**Verba:** {client_details['budget']}", f"**Faixa Etária/Gênero:** {client_details['age_gender']}", f"**Interesses:** {client_details['interests']}", f"**Canais:** {client_details['current_channels']}", f"**Deep Research:** {'Ativado' if client_details['deep_research'] else 'Padrão'}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke([HumanMessage(content=final_prompt)])
        st.session_state.generated_client_analysis_new = ai_response.content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
    with st.spinner("🔬 A IA está analisando a concorrência..."):
        prompt_parts = ["**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva'...", f"**Seu Negócio:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke([HumanMessage(content=final_prompt)])
        st.session_state.generated_competitor_analysis_new = ai_response.content


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_model_instance_passed):
        self.llm = llm_model_instance_passed
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
        # ... (restante da função marketing_digital_guiado como antes, usando as funções _marketing_handle_... corrigidas acima)
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
            else: # Caso padrão, se algo der errado com a seleção
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
            with st.form("post_creator_form_fbauth", clear_on_submit=True): # clear_on_submit=True para limpar após gerar
                st.subheader(" Plataformas Desejadas:")
                key_select_all_post = "post_select_all_cb_fbauth"
                select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_post)
                cols_post = st.columns(2)
                form_platform_selections_post = {}
                
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                    col_index = i % 2
                    platform_key_form = f"post_platform_{platform_suffix}_cb_fbauth"
                    with cols_post[col_index]:
                        # Mantém o estado do checkbox individual se "Selecionar Todos" não estiver marcado
                        is_checked = select_all_post_checked or st.session_state.get(platform_key_form, False)
                        form_platform_selections_post[platform_name] = st.checkbox(platform_name, key=platform_key_form, value=is_checked)
                
                post_details = _marketing_get_objective_details("post_creator", "post")
                submit_button_pressed_post = st.form_submit_button("💡 Gerar Post!")

            if submit_button_pressed_post:
                actual_selected_platforms = []
                if st.session_state.get(key_select_all_post, False): # Usa o estado ATUAL do checkbox
                    actual_selected_platforms = platform_names_available_list
                else:
                    for platform_name, platform_suffix in platforms_config_options.items():
                         if st.session_state.get(f"post_platform_{platform_suffix}_cb_fbauth", False): # Verifica o estado de CADA checkbox
                            actual_selected_platforms.append(platform_name)
                _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, actual_selected_platforms, self.llm)
            # Exibe o conteúdo gerado se existir
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

        # ... (código para Landing Page, Site, Cliente Ideal, Concorrência como antes, verificando a chamada do llm.invoke)
        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form("landing_page_form_fbauth", clear_on_submit=False): # Manter valores é útil aqui
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
                _marketing_display_output_options(st.session_state.generated_lp_content_new, "lp_output_fbauth", "landing_page_ia")

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
                _marketing_display_output_options(st.session_state.generated_site_content_new, "site_output_fbauth", "site_ia")

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
                _marketing_display_output_options(st.session_state.generated_client_analysis_new, "client_analysis_fbauth", "analise_publico_ia")
        
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
                _marketing_display_output_options(st.session_state.generated_competitor_analysis_new, "competitor_analysis_fbauth", "analise_concorrencia_ia")

        elif main_action == "Selecione uma opção...": 
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            LOGO_PATH_MARKETING_WELCOME = "images/logo-pme-ia.png" 
            if os.path.exists(LOGO_PATH_MARKETING_WELCOME):
                st.image(LOGO_PATH_MARKETING_WELCOME, caption="Assistente PME Pro", width=200)
            else:
                st.image("https://i.imgur.com/7IIYxq1.png", caption="Assistente PME Pro (Logo Padrão)", width=200)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..." # Seu prompt completo aqui
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_content_calc = f"O usuário está buscando ajuda para precificar: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_content_calc = f"Contexto visual da imagem '{descricao_imagem_contexto}' deve ser considerado.\n\n{prompt_content_calc}"
        system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação... {prompt_content_calc}""" # Seu prompt completo aqui
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario}) 
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_content_ideias = f"O usuário busca ideias de negócios e diz: '{input_usuario}'."
        if contexto_arquivos:
            prompt_content_ideias = f"Considerando os arquivos/contextos: {contexto_arquivos}\n\n{prompt_content_ideias}"
        system_message_ideias = f"""Você é o "Assistente PME Pro", consultor de negócios especialista em IA... {prompt_content_ideias}""" # Seu prompt completo aqui
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    chat_display_key = f"chat_display_{area_chave}_fbauth" # Adicionando sufixo para evitar conflitos
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        # Adiciona a mensagem inicial à memória da LLMChain
        if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
             memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
             memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))


    if area_chave == "calculo_precos": 
        st.session_state.pop('last_uploaded_image_info_pricing_fbauth', None)
        st.session_state.pop('processed_image_id_pricing_fbauth', None)
        st.session_state.pop('user_input_processed_pricing_fbauth', None) 
    elif area_chave == "gerador_ideias": 
        st.session_state.pop('uploaded_file_info_ideias_for_prompt_fbauth', None)
        st.session_state.pop('processed_file_id_ideias_fbauth', None)
        st.session_state.pop('user_input_processed_ideias_fbauth', None)

def exibir_chat_e_obter_input_global(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}_fbauth"
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
        
        local_kwargs = kwargs_funcao_agente.copy()
        if area_chave == "calculo_precos":
            if st.session_state.get('last_uploaded_image_info_pricing_fbauth'):
                local_kwargs['descricao_imagem_contexto'] = st.session_state.get('last_uploaded_image_info_pricing_fbauth')
                st.session_state.user_input_processed_pricing_fbauth = True 
        elif area_chave == "gerador_ideias":
            if st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth'):
                local_kwargs['contexto_arquivos'] = st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth')
                st.session_state.user_input_processed_ideias_fbauth = True
            
        with st.spinner("Assistente PME Pro está processando... 🤔"):
            resposta_ai = funcao_conversa_agente(input_usuario=prompt_usuario, **local_kwargs)

        st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
        
        # Limpar contextos após uso
        if area_chave == "calculo_precos" and st.session_state.get('user_input_processed_pricing_fbauth'):
            st.session_state.last_uploaded_image_info_pricing_fbauth = None 
            st.session_state.user_input_processed_pricing_fbauth = False
        if area_chave == "gerador_ideias" and st.session_state.get('user_input_processed_ideias_fbauth'):
            st.session_state.uploaded_file_info_ideias_for_prompt_fbauth = None
            st.session_state.user_input_processed_ideias_fbauth = False
        
        st.rerun()

# --- Lógica Principal do Aplicativo Streamlit ---
if 'agente_pme' not in st.session_state:
    if llm_model_instance: 
        st.session_state.agente_pme = AssistentePMEPro(llm_model_instance_passed=llm_model_instance)
agente = st.session_state.get('agente_pme') 

LOGO_PATH_APP_MAIN_DISPLAY = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_LOGO_MAIN = "https://i.imgur.com/7IIYxq1.png"

if os.path.exists(LOGO_PATH_APP_MAIN_DISPLAY):
    st.sidebar.image(LOGO_PATH_APP_MAIN_DISPLAY, width=150)
else:
    st.sidebar.image(IMGUR_FALLBACK_LOGO_MAIN, width=150, caption="Logo Padrão")
    if 'logo_warning_main_fbauth' not in st.session_state: # Chave única para o warning
        st.sidebar.warning(f"Logo local '{LOGO_PATH_APP_MAIN_DISPLAY}' não encontrada. Usando logo padrão.")
        st.session_state.logo_warning_main_fbauth = True

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_main_dict = {
    "Página Inicial": "pagina_inicial", 
    "Marketing Digital com IA (Guia)": "marketing_guiado",
    "Elaborar Plano de Negócios com IA": "plano_negocios", 
    "Cálculo de Preços Inteligente": "calculo_precos",
    "Gerador de Ideias para Negócios": "gerador_ideias"
}
opcoes_menu_main_labels = list(opcoes_menu_main_dict.keys())
radio_key_sidebar_main = 'sidebar_main_selection_fbauth' # Chave única

# Gerenciamento da seleção da sidebar e inicialização de chat
if 'area_selecionada_main' not in st.session_state or st.session_state.area_selecionada_main not in opcoes_menu_main_dict:
    st.session_state.area_selecionada_main = opcoes_menu_main_labels[0] 

if f'{radio_key_sidebar_main}_index' not in st.session_state:
    try:
        st.session_state[f'{radio_key_sidebar_main}_index'] = opcoes_menu_main_labels.index(st.session_state.area_selecionada_main)
    except ValueError:
         st.session_state[f'{radio_key_sidebar_main}_index'] = 0 # Default para Página Inicial

def on_main_app_selection_change():
    st.session_state.area_selecionada_main = st.session_state[radio_key_sidebar_main]
    st.session_state[f'{radio_key_sidebar_main}_index'] = opcoes_menu_main_labels.index(st.session_state[radio_key_sidebar_main])
    # Limpa estados de marketing se saiu da seção
    if st.session_state.area_selecionada_main != "Marketing Digital com IA (Guia)":
         keys_to_delete_marketing = [k for k in st.session_state if k.startswith("generated_") or "_cb_fbauth" in k or "main_marketing_action_choice_fbauth" in k]
         for k_del_mkt in keys_to_delete_marketing:
            if k_del_mkt in st.session_state: del st.session_state[k_del_mkt]
    st.session_state.previous_area_selecionada_main = None # Força reinicialização do chat na próxima seção
    st.experimental_rerun()

area_selecionada_label = st.sidebar.radio(
    "Como posso te ajudar hoje?", 
    options=opcoes_menu_main_labels, 
    key=radio_key_sidebar_main, 
    index=st.session_state[f'{radio_key_sidebar_main}_index'],
    on_change=on_main_app_selection_change
)

current_section_key = opcoes_menu_main_dict.get(st.session_state.area_selecionada_main)

# Lógica de inicialização/reset de chat para seções conversacionais
if current_section_key not in ["pagina_inicial", "marketing_guiado"] and agente:
    if st.session_state.area_selecionada_main != st.session_state.get('previous_area_selecionada_main'):
        chat_display_key_init_main = f"chat_display_{current_section_key}_fbauth" # Chave única
        if chat_display_key_init_main not in st.session_state or not st.session_state[chat_display_key_init_main]:
            msg_inicial_para_chat_atual = ""
            memoria_agente_para_chat_atual = None
            if current_section_key == "plano_negocios": 
                msg_inicial_para_chat_atual = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia de negócio, seus principais produtos/serviços, e quem você imagina como seus clientes."
                memoria_agente_para_chat_atual = agente.memoria_plano_negocios
            elif current_section_key == "calculo_precos": 
                msg_inicial_para_chat_atual = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começarmos, por favor, descreva o produto ou serviço para o qual você gostaria de ajuda para precificar. Se tiver uma imagem, pode enviá-la também."
                memoria_agente_para_chat_atual = agente.memoria_calculo_precos
            elif current_section_key == "gerador_ideias": 
                msg_inicial_para_chat_atual = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Você pode me descrever um desafio, uma área que quer inovar, ou simplesmente pedir sugestões. Se tiver algum arquivo de contexto (texto ou imagem), pode enviar também."
                memoria_agente_para_chat_atual = agente.memoria_gerador_ideias
            
            if msg_inicial_para_chat_atual and memoria_agente_para_chat_atual is not None: 
                inicializar_ou_resetar_chat_global(current_section_key, msg_inicial_para_chat_atual, memoria_agente_para_chat_atual)
        st.session_state.previous_area_selecionada_main = st.session_state.area_selecionada_main

# Renderização da Seção Selecionada
if current_section_key == "pagina_inicial":
    st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
    st.markdown("---")
    logo_to_display_pg_inicial = LOGO_PATH_APP_MAIN_DISPLAY if os.path.exists(LOGO_PATH_APP_MAIN_DISPLAY) else IMGUR_FALLBACK_LOGO_MAIN
    st.markdown(f"<div style='text-align: center;'><img src='{logo_to_display_pg_inicial}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
    st.markdown("---")
    
    num_botoes_funcionais = len(opcoes_menu_main_dict) -1 
    if num_botoes_funcionais > 0 :
        num_cols_botoes = min(num_botoes_funcionais, 3) 
        cols_botoes = st.columns(num_cols_botoes)
        btn_idx = 0
        for nome_menu, chave_secao in opcoes_menu_main_dict.items():
            if chave_secao != "pagina_inicial":
                col_atual_btn = cols_botoes[btn_idx % num_cols_botoes]
                button_label_limpo = nome_menu.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                if col_atual_btn.button(button_label_limpo, key=f"btn_goto_{chave_secao}_fbauth", use_container_width=True, help=f"Ir para {nome_menu}"): # Chave única
                    st.session_state.area_selecionada_main = nome_menu
                    st.session_state[f'{radio_key_sidebar_main}_index'] = opcoes_menu_main_labels.index(nome_menu)
                    st.experimental_rerun()
                btn_idx +=1
        st.balloons()

elif current_section_key == "marketing_guiado" and agente: 
    agente.marketing_digital_guiado()
elif current_section_key == "plano_negocios" and agente:
    st.header("📝 Elaborando seu Plano de Negócios com IA")
    st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
    exibir_chat_e_obter_input_global(current_section_key, "Sua ideia, produtos/serviços, clientes...", agente.conversar_plano_de_negocios)
    if st.sidebar.button("🗑️ Limpar Histórico do Plano", key="btn_reset_plano_fbauth"): # Chave única
        inicializar_ou_resetar_chat_global(current_section_key, "Ok, vamos recomeçar o seu Plano de Negócios. Sobre qual aspecto você gostaria de falar primeiro?", agente.memoria_plano_negocios)
        st.experimental_rerun()
elif current_section_key == "calculo_precos" and agente:
    st.header("💲 Cálculo de Preços Inteligente com IA")
    st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
    uploaded_image_pricing = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_fbauth") # Chave única
    
    if uploaded_image_pricing is not None:
        if st.session_state.get('processed_image_id_pricing_fbauth') != uploaded_image_pricing.id:
            try:
                img_pil_pricing = Image.open(uploaded_image_pricing) 
                st.image(img_pil_pricing, caption=f"Imagem: {uploaded_image_pricing.name}", width=150)
                st.session_state.last_uploaded_image_info_pricing_fbauth = f"O usuário carregou uma imagem chamada '{uploaded_image_pricing.name}'. Considere esta informação visualmente e contextualmente."
                st.session_state.processed_image_id_pricing_fbauth = uploaded_image_pricing.id
                st.info(f"Imagem '{uploaded_image_pricing.name}' pronta para ser considerada no próximo diálogo.")
            except Exception as e_img_pricing:
                st.error(f"Erro ao processar a imagem: {e_img_pricing}")
                st.session_state.last_uploaded_image_info_pricing_fbauth = None
                st.session_state.processed_image_id_pricing_fbauth = None
    
    kwargs_preco_chat = {}
    if st.session_state.get('last_uploaded_image_info_pricing_fbauth') and not st.session_state.get('user_input_processed_pricing_fbauth', False):
        kwargs_preco_chat['descricao_imagem_contexto'] = st.session_state.get('last_uploaded_image_info_pricing_fbauth')
    
    exibir_chat_e_obter_input_global(current_section_key, "Descreva o produto/serviço, custos, etc.", agente.calcular_precos_interativo, **kwargs_preco_chat)
    
    if st.session_state.get('user_input_processed_pricing_fbauth'):
        st.session_state.last_uploaded_image_info_pricing_fbauth = None 
        st.session_state.user_input_processed_pricing_fbauth = False

    if st.sidebar.button("🗑️ Limpar Histórico de Preços", key="btn_reset_precos_fbauth"): # Chave única
        inicializar_ou_resetar_chat_global(current_section_key, "Ok, vamos começar um novo cálculo de preços! Descreva seu produto ou serviço.", agente.memoria_calculo_precos)
        st.experimental_rerun()

elif current_section_key == "gerador_ideias" and agente:
    st.header("💡 Gerador de Ideias para seu Negócio com IA")
    st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
    uploaded_files_ideias = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_fbauth") # Chave única
    
    if uploaded_files_ideias:
        current_files_signature_ideias = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias]))
        if st.session_state.get('processed_file_id_ideias_fbauth') != current_files_signature_ideias or not st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth'):
            texts_from_files_ideias = []
            images_info_from_files_ideias = []
            for up_file in uploaded_files_ideias:
                try:
                    if up_file.type == "text/plain": 
                        texts_from_files_ideias.append(f"Conteúdo de '{up_file.name}':\n{up_file.read().decode('utf-8')[:3000]}...") # Limita para não sobrecarregar
                    elif up_file.type in ["image/png", "image/jpeg"]: 
                        st.image(Image.open(up_file), caption=f"Contexto: {up_file.name}", width=100)
                        images_info_from_files_ideias.append(f"Imagem '{up_file.name}' fornecida como contexto visual.")
                except Exception as e_file_proc: st.error(f"Erro ao processar '{up_file.name}': {e_file_proc}")
            
            context_str_for_prompt_ideias = ""
            if texts_from_files_ideias: context_str_for_prompt_ideias += "\n\n--- TEXTO(S) FORNECIDO(S) ---\n" + "\n\n".join(texts_from_files_ideias)
            if images_info_from_files_ideias: context_str_for_prompt_ideias += "\n\n--- IMAGEN(S) FORNECIDA(S) ---\n" + "\n".join(images_info_from_files_ideias)
            
            if context_str_for_prompt_ideias: 
                st.session_state.uploaded_file_info_ideias_for_prompt_fbauth = context_str_for_prompt_ideias.strip()
                st.info("Arquivo(s) de contexto pronto(s) para serem considerados no próximo diálogo.")
            else: 
                st.session_state.uploaded_file_info_ideias_for_prompt_fbauth = None
            st.session_state.processed_file_id_ideias_fbauth = current_files_signature_ideias
    
    kwargs_ideias_chat = {}
    if st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth') and not st.session_state.get('user_input_processed_ideias_fbauth', False): 
        kwargs_ideias_chat['contexto_arquivos'] = st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth')
    
    exibir_chat_e_obter_input_global(current_section_key, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat)
    
    if st.session_state.get('user_input_processed_ideias_fbauth'):
        st.session_state.uploaded_file_info_ideias_for_prompt_fbauth = None
        st.session_state.user_input_processed_ideias_fbauth = False

    if st.sidebar.button("🗑️ Limpar Histórico de Ideias", key="btn_reset_ideias_fbauth"): # Chave única
        inicializar_ou_resetar_chat_global(current_section_key, "Ok, vamos começar uma nova sessão de geração de ideias! Qual o seu ponto de partida?", agente.memoria_gerador_ideias)
        st.experimental_rerun()

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
