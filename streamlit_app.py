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

# --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = "_v18_assets" 
    details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj_new{key_suffix}")
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience_new{key_suffix}")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product_new{key_suffix}")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message_new{key_suffix}")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)? (Opcional)", key=f"{section_key}_usp_new{key_suffix}")
    details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?",("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone_new{key_suffix}")
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA? (Opcional)", key=f"{section_key}_extra_new{key_suffix}")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    key_suffix = "_v18_assets"
    st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}_new.txt", mime="text/plain", key=f"download_{section_key}_new{key_suffix}")
    cols_actions = st.columns(2)
    with cols_actions[0]:
        if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn_new{key_suffix}"): st.success("Conteúdo pronto para ser copiado!"); st.caption("Adapte para cada plataforma.")
    with cols_actions[1]:
        if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn_new{key_suffix}"): st.info("Agendamento simulado. Use ferramentas dedicadas.")

# --- HANDLER FUNCTIONS ---
def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    required_post_fields = {"objective": "o objetivo do post", "target_audience": "o público-alvo", "product_service": "o produto/serviço", "key_message": "a mensagem chave"}
    for field, desc in required_post_fields.items():
        if not details_dict.get(field) or not str(details_dict[field]).strip(): st.warning(f"Preencha {desc}."); return
    if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
    with st.spinner("🤖 Criando seu post..."):
        prompt_parts = [f"**{k.replace('_', ' ').capitalize()}:** {v if str(v).strip() else 'Não informado'}" for k, v in details_dict.items()]
        prompt_parts.insert(0, "**Instrução para IA:** Você é um especialista em copywriting para PMEs.")
        prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
        prompt_parts.append("**Tarefa:** Gere o conteúdo do post, incluindo sugestões de emojis e hashtags. Se for e-mail, crie Assunto e corpo. Se for vídeo (YT/TikTok/Kwai), forneça um roteiro breve.")
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte (contexto):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        try:
            ai_response = llm.invoke([HumanMessage(content=final_prompt)])
            st.session_state.generated_post_content_new = ai_response.content
        except Exception as e: st.error(f"Erro ao gerar o post: {e}")

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    if not campaign_specifics.get("name") or not str(campaign_specifics["name"]).strip(): st.warning("Preencha o Nome da Campanha."); return
    required_details = {"objective": "o objetivo da campanha", "target_audience": "o público-alvo", "product_service": "o produto/serviço", "key_message": "a mensagem chave"}
    for field, desc in required_details.items():
        if not details_dict.get(field) or not str(details_dict[field]).strip(): st.warning(f"Preencha {desc}."); return
    if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
    with st.spinner("🧠 Elaborando seu plano de campanha..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um estrategista de marketing digital sênior para PMEs.",
            f"**Nome da Campanha:** {campaign_specifics['name']}",
            f"**Plataformas:** {', '.join(selected_platforms_list)}.",
            f"**Duração:** {campaign_specifics.get('duration', '').strip() or 'Não informada'}",
            f"**Orçamento:** {campaign_specifics.get('budget', '').strip() or 'Não informado'}",
            f"**Objetivo Principal:** {details_dict['objective']}", f"**Público-Alvo:** {details_dict['target_audience']}",
            f"**Produto/Serviço:** {details_dict['product_service']}", f"**Mensagem Chave:** {details_dict['key_message']}",
            f"**USP:** {details_dict.get('usp', '').strip() or 'Não informado'}",
            f"**Tom/Estilo:** {details_dict['style_tone']}", f"**KPIs:** {campaign_specifics.get('kpis', '').strip() or 'Não informados'}",
            f"**Extra/CTA:** {details_dict.get('extra_info', '').strip() or 'Não informado'}",
            "**Tarefa:** Elabore um plano de campanha detalhado incluindo: Conceito Criativo, Estrutura/Fases, Mix de Conteúdo por Plataforma (3-5 tipos), Sugestões de Criativos, Mini Calendário Editorial, Estratégia de Hashtags, Recomendações para Impulsionamento, Como Mensurar KPIs, Dicas de Otimização."
        ]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        try:
            ai_response = llm.invoke([HumanMessage(content=final_prompt)])
            st.session_state.generated_campaign_content_new = ai_response.content
            st.session_state.campaign_plan_for_assets = ai_response.content
        except Exception as e: st.error(f"Erro ao gerar o plano de campanha: {e}")

def _marketing_handle_gerar_texto_ativo(campaign_plan_context, asset_description, asset_objective, llm):
    if not str(asset_description).strip(): st.warning("Descreva o ativo para gerar o texto."); return
    if not str(asset_objective).strip(): st.warning("Defina o objetivo específico deste ativo."); return
    with st.spinner("✍️ IA está escrevendo o texto..."):
        prompt = (f"**Contexto do Plano de Campanha Geral:**\n{campaign_plan_context}\n\n"
                  f"**Instrução para IA:** Copywriter especialista. Gere o texto para um ativo específico desta campanha.\n\n"
                  f"**Ativo a ser Criado:** {asset_description}\n"
                  f"**Objetivo Específico deste Ativo:** {asset_objective}\n\n"
                  "**Tarefa:** Gere o texto apropriado. Se redes sociais: inclua emojis e hashtags. Se e-mail: Assunto e corpo. Se anúncio: foco em clareza e CTA.")
        try:
            ai_response = llm.invoke([HumanMessage(content=prompt)])
            st.session_state.current_generated_asset_text = ai_response.content
        except Exception as e: st.error(f"Erro ao gerar texto do ativo: {e}"); st.session_state.current_generated_asset_text = "Erro."
# ... (Outros handlers _marketing_handle_... permanecem, garantindo o uso de [HumanMessage(...)] para invoke)
def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not str(lp_details["purpose"]).strip() or not lp_details["main_offer"] or not str(lp_details["main_offer"]).strip() or not lp_details["cta"] or not str(lp_details["cta"]).strip(): st.warning("Preencha objetivo, oferta e CTA da landing page."); return
    with st.spinner("🎨 Desenhando estrutura da landing page..."):
        prompt_parts = ["**Instrução para IA:** Especialista em UX/UI e copywriting para landing pages de alta conversão.", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details.get('target_audience','').strip() or 'Não informado'}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details.get('key_benefits','').strip() or 'Não informados'}", f"**CTA:** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details.get('visual_prefs','').strip() or 'Não informadas'}", "**Tarefa:** Crie estrutura detalhada e copy..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_lp_content_new = ai_response.content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not str(site_details["business_type"]).strip() or not site_details["main_purpose"] or not str(site_details["main_purpose"]).strip(): st.warning("Informe tipo de negócio e objetivo do site."); return
    with st.spinner("🛠️ Arquitetando seu site..."):
        prompt_parts = ["**Instrução para IA:** Arquiteto de informação e web designer conceitual.", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo do Site:** {site_details['main_purpose']}", f"**Público-Alvo:** {site_details.get('target_audience','').strip() or 'Não informado'}", f"**Páginas Essenciais:** {site_details.get('essential_pages','').strip() or 'Não informadas'}", f"**Produtos/Serviços Chave:** {site_details.get('key_features','').strip() or 'Não informados'}", f"**Personalidade da Marca:** {site_details.get('brand_personality','').strip() or 'Não informada'}", f"**Referências Visuais:** {site_details.get('visual_references','').strip() or 'Não informadas'}", "**Tarefa:** Desenvolva proposta de estrutura e conteúdo..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_site_content_new = ai_response.content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"] or not str(client_details["product_campaign"]).strip() : st.warning("Descreva o produto/serviço ou campanha."); return
    with st.spinner("🕵️ Investigando seu público-alvo..."):
        prompt_parts = ["**Instrução para IA:** 'Agente Detetive de Clientes', especialista em marketing e pesquisa.", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details.get('location','').strip() or 'Não informada'}", f"**Verba:** {client_details.get('budget','').strip() or 'Não informada'}", f"**Faixa Etária/Gênero:** {client_details.get('age_gender','').strip() or 'Não informados'}", f"**Interesses:** {client_details.get('interests','').strip() or 'Não informados'}", f"**Canais:** {client_details.get('current_channels','').strip() or 'Não informados'}", f"**Deep Research:** {'Ativado' if client_details['deep_research'] else 'Padrão'}", "**Tarefa:** Análise completa do público-alvo..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_client_analysis_new = ai_response.content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not str(competitor_details["your_business"]).strip() or not competitor_details["competitors_list"] or not str(competitor_details["competitors_list"]).strip(): st.warning("Descreva seu negócio e liste concorrentes."); return
    with st.spinner("🔬 Analisando a concorrência..."):
        prompt_parts = ["**Instrução para IA:** 'Agente de Inteligência Competitiva'.", f"**Negócio do Usuário:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}", "**Tarefa:** Elabore um relatório breve e útil..."]
        if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_competitor_analysis_new = ai_response.content

# --- Classe do Agente (AssistentePMEPro) ---
class AssistentePMEPro:
    def __init__(self, llm_passed_model):
        if llm_passed_model is None: st.error("❌ Erro: Modelo LLM não inicializado."); st.stop()
        self.llm = llm_passed_model
        self.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        self.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)
        self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True)

    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([ SystemMessagePromptTemplate.from_template(system_message_content), MessagesPlaceholder(variable_name=memory_key_placeholder), HumanMessagePromptTemplate.from_template("{input_usuario}")])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        st.markdown("---")
        key_suffix_page = "_v18_assets"

        marketing_files_info_for_prompt = []
        with st.sidebar:
            st.subheader("📎 Suporte para Marketing")
            uploaded_marketing_files = st.file_uploader("Upload para Marketing (opcional):",accept_multiple_files=True,type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx', 'mp4', 'mov'],key=f"mkt_uploader{key_suffix_page}" )
            if uploaded_marketing_files:
                temp_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                if temp_info: marketing_files_info_for_prompt = temp_info; st.success(f"{len(uploaded_marketing_files)} arquivo(s) carregados!"); st.expander("Ver arquivos").write(marketing_files_info_for_prompt)
            st.markdown("---")

        main_action = st.radio( "Olá! O que você quer fazer?",
            ("Selecione uma opção...", "1 - Criar post", "2 - Criar campanha completa", "3 - Criar landing page", "4 - Criar site com IA", "5 - Encontrar meu cliente", "6 - Conhecer a concorrência"),
            index=0, key=f"mkt_main_action{key_suffix_page}")
        st.markdown("---")
        
        platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", "TikTok": "tt", "Kwai": "kwai", "YouTube": "yt", "E-mail (lista própria)": "email_own", "E-mail (Google Ads)": "email_google"}
        platform_names = list(platforms_cfg.keys())

        # Inicializar estados para criação de ativos da campanha (garantido no início da função)
        for state_key, default_value in [
            ('creating_campaign_assets', False), ('campaign_assets_list', []),
            ('current_campaign_plan_context', ""), ('current_asset_description', ""),
            ('current_asset_objective', ""), ('current_generated_asset_text', ""),
            ('current_asset_uploaded_image', None), ('current_asset_uploaded_video', None)
        ]:
            if state_key not in st.session_state: st.session_state[state_key] = default_value
        
        # Seção de Criar Post
        if main_action == "1 - Criar post":
            st.subheader("✨ Criador de Posts com IA")
            with st.form(f"post_form{key_suffix_page}"): 
                st.subheader(" Plataformas:"); key_select_all_post = f"post{key_suffix_page}_select_all"
                st.checkbox("Selecionar todas abaixo", key=key_select_all_post)
                cols_p = st.columns(2); keys_for_plats_post = {name: f"post{key_suffix_page}_p_{suf}" for name, suf in platforms_cfg.items()}
                for i, (name, _) in enumerate(platforms_cfg.items()):
                    with cols_p[i%2]: st.checkbox(name, key=keys_for_plats_post[name])
                if any("E-mail" in name for name in platforms_cfg): st.caption("💡 Para e-mail marketing...")
                post_details = _marketing_get_objective_details(f"post{key_suffix_page}", "post")
                submit_post = st.form_submit_button("💡 Gerar Post!")
            if submit_post:
                selected_plats = platform_names if st.session_state.get(key_select_all_post,False) else [name for name, key in keys_for_plats_post.items() if st.session_state.get(key,False)]
                _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
            if 'generated_post_content_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_post_content_new, f"post{key_suffix_page}", "post_ia")

        # Seção de Criar Campanha Completa
        elif main_action == "2 - Criar campanha completa":
            st.subheader("🌍 Planejador de Campanhas com IA")
            with st.form(f"campaign_form{key_suffix_page}"):
                camp_name = st.text_input("Nome da Campanha:", key=f"camp_name{key_suffix_page}")
                st.subheader(" Plataformas:"); key_select_all_camp = f"camp{key_suffix_page}_select_all"
                st.checkbox("Selecionar todas abaixo", key=key_select_all_camp)
                cols_c = st.columns(2); keys_for_plats_camp = {name: f"camp{key_suffix_page}_p_{suf}" for name, suf in platforms_cfg.items()}
                for i, (name, _) in enumerate(platforms_cfg.items()):
                    with cols_c[i%2]: st.checkbox(name, key=keys_for_plats_camp[name])
                if any("E-mail" in name for name in platforms_cfg): st.caption("💡 Para e-mail marketing...")
                camp_details_obj = _marketing_get_objective_details(f"camp{key_suffix_page}", "campanha")
                camp_duration = st.text_input("Duração Estimada:", key=f"camp_duration{key_suffix_page}")
                camp_budget = st.text_input("Orçamento (opcional):", key=f"camp_budget{key_suffix_page}")
                camp_kpis = st.text_area("KPIs mais importantes:", key=f"camp_kpis{key_suffix_page}")
                submit_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_camp:
                selected_plats_camp = platform_names if st.session_state.get(key_select_all_camp,False) else [name for name, key in keys_for_plats_camp.items() if st.session_state.get(key,False)]
                camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
            
            if 'generated_campaign_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_new, f"camp{key_suffix_page}", "campanha_ia")
                if st.button("🚀 Criar Ativos da Campanha Agora!", key=f"btn_create_assets{key_suffix_page}"):
                    st.session_state.creating_campaign_assets = True
                    st.session_state.current_campaign_plan_context = st.session_state.generated_campaign_content_new
                    st.session_state.campaign_assets_list = [] 
                    st.session_state.current_asset_description = ""; st.session_state.current_asset_objective = ""
                    st.session_state.current_generated_asset_text = ""; st.session_state.current_asset_uploaded_image = None 
                    st.session_state.current_asset_uploaded_video = None
                    # Não precisa de st.rerun() aqui, o clique no botão já causa um.
            
            if st.session_state.get("creating_campaign_assets"):
                st.markdown("---"); st.subheader("🛠️ Criador de Ativos para a Campanha")
                st.markdown("**Plano da Campanha (Contexto):**"); st.info(st.session_state.get('current_campaign_plan_context', "Contexto não disponível."))
                with st.form(f"asset_creator_form{key_suffix_page}"):
                    st.session_state.current_asset_description = st.text_input("Nome/Descrição do Ativo:", value=st.session_state.current_asset_description, key=f"asset_desc{key_suffix_page}")
                    st.session_state.current_asset_objective = st.text_area("Objetivo Específico deste Ativo:", value=st.session_state.current_asset_objective, key=f"asset_obj{key_suffix_page}")
                    
                    col1_asset, col2_asset, col3_asset = st.columns(3)
                    with col1_asset:
                        if st.form_submit_button("✍️ Gerar Texto"): # Mudado para ser um dos submit buttons do form
                            if st.session_state.current_asset_description and st.session_state.current_asset_objective:
                                _marketing_handle_gerar_texto_ativo(st.session_state.get('current_campaign_plan_context'), st.session_state.current_asset_description, st.session_state.current_asset_objective, self.llm)
                            else: st.warning("Preencha Descrição e Objetivo do ativo.")
                    # Botões de "Gerar Ideias" podem ser st.button normais se não submetem o form principal de ativos
                    with col2_asset: st.markdown("🖼️ **Imagens:**"); st.button("💡 Gerar Ideias de Imagem", key=f"btn_img_ideas{key_suffix_page}", on_click=lambda: st.info("Ideias de imagem em desenvolvimento."))
                    with col3_asset: st.markdown("🎬 **Vídeos:**"); st.button("💡 Gerar Ideias de Vídeo", key=f"btn_vid_ideas{key_suffix_page}", on_click=lambda: st.info("Ideias de vídeo em desenvolvimento."))
                    
                    st.session_state.current_asset_uploaded_image = st.file_uploader("Carregar Imagem:", type=['png', 'jpg', 'jpeg'], key=f"asset_img_upload{key_suffix_page}")
                    st.session_state.current_asset_uploaded_video = st.file_uploader("Carregar Vídeo:", type=['mp4', 'mov', 'avi'], key=f"asset_vid_upload{key_suffix_page}")

                    if st.session_state.current_generated_asset_text: st.text_area("Texto Gerado:", value=st.session_state.current_generated_asset_text, height=150, key=f"gen_text_disp{key_suffix_page}")
                    if st.session_state.current_asset_uploaded_image: st.success(f"Imagem '{st.session_state.current_asset_uploaded_image.name}' carregada.")
                    if st.session_state.current_asset_uploaded_video: st.success(f"Vídeo '{st.session_state.current_asset_uploaded_video.name}' carregado.")

                    if st.form_submit_button("➕ Adicionar Ativo à Campanha e Limpar", key=f"btn_add_save_asset{key_suffix_page}"): # Botão principal do form de ativos
                        if st.session_state.current_asset_description:
                            new_asset = {"descricao": st.session_state.current_asset_description, "objetivo": st.session_state.current_asset_objective, "texto_gerado": st.session_state.current_generated_asset_text, "imagem_carregada": st.session_state.current_asset_uploaded_image.name if st.session_state.current_asset_uploaded_image else None, "video_carregado": st.session_state.current_asset_uploaded_video.name if st.session_state.current_asset_uploaded_video else None}
                            st.session_state.campaign_assets_list.append(new_asset)
                            st.success(f"Ativo '{st.session_state.current_asset_description}' adicionado!")
                            st.session_state.current_asset_description = ""; st.session_state.current_asset_objective = ""; st.session_state.current_generated_asset_text = ""
                            # Limpar file_uploaders é complexo sem rerun ou chaves dinâmicas. Por agora, o usuário precisa remover manualmente ou o rerun limpará com nova chave.
                            # Para forçar a limpeza visual do file_uploader, um rerun seria necessário aqui, mas pode complicar.
                            # st.session_state.current_asset_uploaded_image = None # Não limpa visualmente o widget
                            # st.session_state.current_asset_uploaded_video = None
                            st.rerun() # Para limpar os campos de input e atualizar a lista de ativos
                        else: st.warning("Adicione uma descrição para o ativo.")

                if st.session_state.campaign_assets_list:
                    st.markdown("---"); st.subheader("📦 Ativos da Campanha Criados:")
                    for i, asset in enumerate(st.session_state.campaign_assets_list):
                        with st.expander(f"Ativo {i+1}: {asset['descricao']}"):
                            st.write(f"**Objetivo:** {asset['objetivo']}")
                            if asset["texto_gerado"]: st.markdown(f"**Texto:**\n```\n{asset['texto_gerado']}\n```")
                            if asset["imagem_carregada"]: st.write(f"**Imagem Carregada:** {asset['imagem_carregada']}")
                            if asset["video_carregado"]: st.write(f"**Vídeo Carregado:** {asset['video_carregado']}")
                if st.button("🏁 Concluir Criação de Ativos", key=f"btn_finish_assets{key_suffix_page}"):
                    st.session_state.creating_campaign_assets = False; st.balloons(); st.rerun()
        
        # ... (blocos elif restantes para landing page, site, etc. como antes, usando key_suffix_page para seus forms e widgets)
        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form(f"lp_form{key_suffix_page}"):
                lp_purpose = st.text_input("Objetivo principal:", key=f"lp_purpose{key_suffix_page}")
                # ... demais inputs ...
                lp_target_audience = st.text_input("Público-alvo (Persona):", key=f"lp_audience{key_suffix_page}")
                lp_main_offer = st.text_area("Oferta principal:", key=f"lp_offer{key_suffix_page}")
                lp_key_benefits = st.text_area("Benefícios (3-5):", key=f"lp_benefits{key_suffix_page}")
                lp_cta = st.text_input("CTA principal:", key=f"lp_cta{key_suffix_page}")
                lp_visual_prefs = st.text_input("Preferências visuais (Opcional):", key=f"lp_visual{key_suffix_page}")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura!")
            if submitted_lp:
                lp_details = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details, self.llm)
            if 'generated_lp_content_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_lp_content_new, f"lp{key_suffix_page}", "lp_ia")

        elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
            st.subheader("🏗️ Arquiteto de Sites com IA")
            with st.form(f"site_form{key_suffix_page}"):
                site_business_type = st.text_input("Tipo do negócio:", key=f"site_biz_type{key_suffix_page}")
                # ... demais inputs ...
                site_main_purpose = st.text_area("Objetivo principal do site:", key=f"site_purpose{key_suffix_page}")
                site_target_audience = st.text_input("Público principal:", key=f"site_audience{key_suffix_page}")
                site_essential_pages = st.text_area("Páginas essenciais:", key=f"site_pages{key_suffix_page}")
                site_key_features = st.text_area("Principais produtos/diferenciais:", key=f"site_features{key_suffix_page}")
                site_brand_personality = st.text_input("Personalidade da marca:", key=f"site_brand{key_suffix_page}")
                site_visual_references = st.text_input("Referências visuais (Opcional):", key=f"site_visual_ref{key_suffix_page}")
                submitted_site = st.form_submit_button("🏛️ Gerar Estrutura!")
            if submitted_site:
                site_details = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details, self.llm)
            if 'generated_site_content_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_site_content_new, f"site{key_suffix_page}", "site_ia")

        elif main_action == "5 - Encontrar meu cliente ideal":
            st.subheader("🎯 Decodificador de Clientes com IA")
            with st.form(f"client_form{key_suffix_page}"):
                fc_product_campaign = st.text_area("Produto/serviço/campanha:", key=f"fc_campaign{key_suffix_page}")
                # ... demais inputs ...
                fc_location = st.text_input("Localização:", key=f"fc_location{key_suffix_page}")
                fc_budget = st.text_input("Verba (Opcional):", key=f"fc_budget{key_suffix_page}")
                fc_age_gender = st.text_input("Faixa etária/gênero:", key=f"fc_age_gender{key_suffix_page}")
                fc_interests = st.text_area("Interesses/dores/necessidades:", key=f"fc_interests{key_suffix_page}")
                fc_current_channels = st.text_area("Canais atuais/considerados:", key=f"fc_channels{key_suffix_page}")
                fc_deep_research = st.checkbox("Habilitar 'Deep Research'", key=f"fc_deep{key_suffix_page}")
                submitted_fc = st.form_submit_button("🔍 Encontrar Cliente!")
            if submitted_fc:
                client_details = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details, self.llm)
            if 'generated_client_analysis_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_client_analysis_new, f"client{key_suffix_page}", "cliente_ia")

        elif main_action == "6 - Conhecer a concorrência":
            st.subheader("🧐 Radar da Concorrência com IA")
            with st.form(f"competitor_form{key_suffix_page}"):
                ca_your_business = st.text_area("Descreva seu negócio/produto:", key=f"ca_your_biz{key_suffix_page}")
                # ... demais inputs ...
                ca_competitors_list = st.text_area("Liste seus concorrentes:", key=f"ca_competitors{key_suffix_page}")
                ca_aspects_to_analyze = st.multiselect( "Aspectos a analisar:", ["Presença Online", "Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"ca_aspects{key_suffix_page}")
                submitted_ca = st.form_submit_button("📡 Analisar!")
            if submitted_ca:
                competitor_details = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details, self.llm)
            if 'generated_competitor_analysis_new' in st.session_state: _marketing_display_output_options(st.session_state.generated_competitor_analysis_new, f"competitor{key_suffix_page}", "concorrencia_ia")

        elif main_action == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção de Marketing Digital! Escolha uma opção.")
            st.image("https://i.imgur.com/7IIYxq1.png", caption="Assistente PME Pro", width=200)

    def conversar_plano_de_negocios(self, input_usuario): 
        # ... (código original)
        system_message_plano = "Você é o \"Assistente PME Pro\"..." 
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        # ... (código original)
        system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação com IA..."""
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        # ... (código original)
        system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios especialista em IA..."""
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

# --- Funções Utilitárias de Chat ---
def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    # ... (código original)
    chat_display_key = f"chat_display_{area_chave}"
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'): memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        elif hasattr(memoria_agente_instancia.chat_memory, 'messages'): memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
    if area_chave == "calculo_precos": st.session_state.last_uploaded_image_info_pricing = None; st.session_state.processed_image_id_pricing = None
    elif area_chave == "gerador_ideias": st.session_state.uploaded_file_info_ideias_for_prompt = None; st.session_state.processed_file_id_ideias = None

def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    # ... (código original)
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state: st.session_state[chat_display_key] = []
    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v18_final")
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
    if 'agente_pme' not in st.session_state: st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
    agente = st.session_state.agente_pme
    URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
    st.sidebar.image(URL_DO_SEU_LOGO, width=200); st.sidebar.title("Assistente PME Pro"); st.sidebar.markdown("IA para seu Negócio Decolar!"); st.sidebar.markdown("---")
    opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado", "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos", "Gerador de Ideias para Negócios": "gerador_ideias"}
    if 'area_selecionada' not in st.session_state: st.session_state.area_selecionada = "Página Inicial"
    for nome_menu_init, chave_secao_init in opcoes_menu.items():
        if chave_secao_init != "marketing_guiado" and f"chat_display_{chave_secao_init}" not in st.session_state:
            st.session_state[f"chat_display_{chave_secao_init}"] = []
    if 'previous_area_selecionada_for_chat_init_processed_v18' not in st.session_state: st.session_state['previous_area_selecionada_for_chat_init_processed_v18'] = None
    
    area_selecionada_label = st.sidebar.radio("Como posso te ajudar hoje?", options=list(opcoes_menu.keys()), key='sidebar_selection_v28_final', index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0)
    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        if area_selecionada_label != "Marketing Digital com IA (Guia)": # Limpa estados do marketing
            for key_to_clear in list(st.session_state.keys()):
                if key_to_clear.startswith(("generated_", "post_v18_", "campaign_v18_", "current_asset_", "campaign_assets_list", "creating_campaign_assets", "current_campaign_plan_context")) or \
                   "_marketing_select_all_v" in key_to_clear or "_marketing_platform_" in key_to_clear :
                     if st.session_state.get(key_to_clear) is not None: del st.session_state[key_to_clear]
        st.rerun()
    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
    if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
        if st.session_state.area_selecionada != st.session_state.get('previous_area_selecionada_for_chat_init_processed_v18'):
            chat_display_key_nav = f"chat_display_{current_section_key}"; msg_inicial_nav = ""; memoria_agente_nav = None
            if chat_display_key_nav not in st.session_state or not st.session_state[chat_display_key_nav]:
                if current_section_key == "plano_negocios": msg_inicial_nav = "Olá! Sou seu Assistente PME Pro..."; memoria_agente_nav = agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços..."; memoria_agente_nav = agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav = "Olá! Sou o Assistente PME Pro..."; memoria_agente_nav = agente.memoria_gerador_ideias
                if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
            st.session_state['previous_area_selecionada_for_chat_init_processed_v18'] = st.session_state.area_selecionada
    if current_section_key == "pagina_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo!</h1></div>", unsafe_allow_html=True); st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda.</p></div>", unsafe_allow_html=True)
        st.markdown("---"); st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo' width='200'></div>", unsafe_allow_html=True); st.markdown("---")
        num_botoes_funcionais = len(opcoes_menu) -1
        if num_botoes_funcionais > 0 :
            num_cols_render = min(num_botoes_funcionais, 4); cols_botoes_pg_inicial = st.columns(num_cols_render); btn_idx_pg_inicial = 0
            for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                if chave_secao_btn_pg != "pagina_inicial":
                    col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                    button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" para ")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" (Guia)","")
                    if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v18_final", use_container_width=True): st.session_state.area_selecionada = nome_menu_btn_pg; st.rerun()
                    btn_idx_pg_inicial +=1
            st.balloons()
    elif current_section_key == "marketing_guiado": agente.marketing_digital_guiado()
    elif current_section_key == "plano_negocios":
        st.header("📝 Plano de Negócios com IA"); exibir_chat_e_obter_input(current_section_key, "Sua resposta...", agente.conversar_plano_de_negocios)
        if st.sidebar.button("Reiniciar Plano", key="btn_reset_plano_v18"): inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar...", agente.memoria_plano_negocios); st.rerun()
    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços com IA"); uploaded_image = st.file_uploader("Imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v18")
        descricao_imagem_para_ia = None 
        if uploaded_image is not None:
            if st.session_state.get('processed_image_id_pricing') != uploaded_image.id:
                try:
                    img_pil = Image.open(uploaded_image); st.image(img_pil, caption=f"Imagem: {uploaded_image.name}", width=150)
                    descricao_imagem_para_ia = f"Imagem: '{uploaded_image.name}'."; st.session_state.last_uploaded_image_info_pricing = descricao_imagem_para_ia
                    st.session_state.processed_image_id_pricing = uploaded_image.id; st.info(f"'{uploaded_image.name}' pronta.")
                except Exception as e: st.error(f"Erro ao processar imagem: {e}"); st.session_state.last_uploaded_image_info_pricing = None; st.session_state.processed_image_id_pricing = None
            else: descricao_imagem_para_ia = st.session_state.get('last_uploaded_image_info_pricing')
        kwargs_preco_chat = {}; current_image_context = st.session_state.get('last_uploaded_image_info_pricing')
        if current_image_context: kwargs_preco_chat['descricao_imagem_contexto'] = current_image_context
        exibir_chat_e_obter_input(current_section_key, "Sua resposta...", agente.calcular_precos_interativo, **kwargs_preco_chat)
        if 'user_input_processed_pricing' in st.session_state and st.session_state.user_input_processed_pricing:
            if st.session_state.get('last_uploaded_image_info_pricing'): st.session_state.last_uploaded_image_info_pricing = None 
            st.session_state.user_input_processed_pricing = False
        if st.sidebar.button("Reiniciar Preços", key="btn_reset_precos_v18"): inicializar_ou_resetar_chat(current_section_key, "Ok, novo cálculo! Compra e revende ou produz/cria?", agente.memoria_calculo_precos); st.rerun()
    elif current_section_key == "gerador_ideias":
        st.header("💡 Gerador de Ideias com IA"); uploaded_files_ideias_ui = st.file_uploader("Upload de arquivos (.txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_v18")
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
        if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v18"): inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar...", agente.memoria_gerador_ideias); st.rerun()

else: st.error("🚨 O Assistente PME Pro não pôde ser iniciado.")
st.sidebar.markdown("---"); st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
