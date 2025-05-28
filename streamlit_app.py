import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

from auth import initialize_authenticator, authentication_flow

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

authenticator = initialize_authenticator()
is_authenticated = authentication_flow(authenticator)

if is_authenticated:
    user_email = st.session_state.get('user_info', {}).get('email', 'Usuário')
    user_name = st.session_state.get('user_info', {}).get('name', user_email)
    st.sidebar.success(f"Logado como: {user_name}")
    authenticator.logout("Logout", "sidebar", key="logout_button_sidebar_main_v2")

    GOOGLE_API_KEY = None
    llm_model_instance = None

    try:
        GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
        st.stop()

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
        st.stop()
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                 temperature=0.75,
                                                 google_api_key=GOOGLE_API_KEY,
                                                 convert_system_message_to_human=True)
        except Exception as e:
            st.error(f"ERRO AO INICIALIZAR O MODELO LLM: {e}")
            st.stop()

    def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
        # Usar um sufixo de chave único para evitar colisões entre seções e execuções
        key_suffix = f"_{section_key}_mkt_obj_v3"
        st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
        details = {}
        details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"objective{key_suffix}")
        details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"target_audience{key_suffix}")
        details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"product_service{key_suffix}")
        details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"key_message{key_suffix}")
        details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)? (Opcional)", key=f"usp{key_suffix}")
        details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?",("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"style_tone{key_suffix}")
        details["extra_info"] = st.text_area("Alguma informação adicional/CTA? (Opcional)", key=f"extra_info{key_suffix}")
        return details

    def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
        key_suffix = f"_{section_key}_output_v3"
        st.subheader("🎉 Resultado da IA e Próximos Passos:")
        st.markdown(generated_content)
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}.txt", mime="text/plain", key=f"download{key_suffix}")
        # Removidos botões simulados para simplificar e evitar problemas de callback dentro de possíveis forms aninhados.
        # Se precisar deles, adicione fora de qualquer st.form ou como parte de uma lógica de submissão de formulário.

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
                f"**Nome da Campanha:** {campaign_specifics['name']}", f"**Plataformas:** {', '.join(selected_platforms_list)}.",
                f"**Duração:** {campaign_specifics.get('duration', '').strip() or 'Não informada'}", f"**Orçamento:** {campaign_specifics.get('budget', '').strip() or 'Não informado'}",
                f"**Objetivo Principal:** {details_dict['objective']}", f"**Público-Alvo:** {details_dict['target_audience']}",
                f"**Produto/Serviço:** {details_dict['product_service']}", f"**Mensagem Chave:** {details_dict['key_message']}",
                f"**USP:** {details_dict.get('usp', '').strip() or 'Não informado'}", f"**Tom/Estilo:** {details_dict['style_tone']}",
                f"**KPIs:** {campaign_specifics.get('kpis', '').strip() or 'Não informados'}", f"**Extra/CTA:** {details_dict.get('extra_info', '').strip() or 'Não informado'}",
                "**Tarefa:** Elabore um plano de campanha detalhado incluindo: Conceito Criativo, Estrutura/Fases, Mix de Conteúdo por Plataforma (3-5 tipos), Sugestões de Criativos, Mini Calendário Editorial, Estratégia de Hashtags, Recomendações para Impulsionamento, Como Mensurar KPIs, Dicas de Otimização."
            ]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts)
            try:
                ai_response = llm.invoke([HumanMessage(content=final_prompt)])
                st.session_state.generated_campaign_content_new = ai_response.content
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
            except Exception as e: st.error(f"Erro ao gerar texto do ativo: {e}"); st.session_state.current_generated_asset_text = "Erro ao gerar texto."

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details.get("purpose") or not lp_details.get("main_offer") or not lp_details.get("cta"): st.warning("Preencha objetivo, oferta e CTA da landing page."); return
        with st.spinner("🎨 Desenhando estrutura da landing page..."):
            prompt_parts = ["**Instrução para IA:** Especialista em UX/UI e copywriting para landing pages de alta conversão.", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details.get('target_audience','').strip() or 'Não informado'}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details.get('key_benefits','').strip() or 'Não informados'}", f"**CTA:** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details.get('visual_prefs','').strip() or 'Não informadas'}", "**Tarefa:** Crie estrutura detalhada e copy para cada seção de uma landing page de alta conversão."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_lp_content_new = ai_response.content

    def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
        if not site_details.get("business_type") or not site_details.get("main_purpose"): st.warning("Informe tipo de negócio e objetivo do site."); return
        with st.spinner("🛠️ Arquitetando seu site..."):
            prompt_parts = ["**Instrução para IA:** Arquiteto de informação e web designer conceitual.", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo do Site:** {site_details['main_purpose']}", f"**Público-Alvo:** {site_details.get('target_audience','').strip() or 'Não informado'}", f"**Páginas Essenciais:** {site_details.get('essential_pages','').strip() or 'Não informadas'}", f"**Produtos/Serviços Chave:** {site_details.get('key_features','').strip() or 'Não informados'}", f"**Personalidade da Marca:** {site_details.get('brand_personality','').strip() or 'Não informada'}", f"**Referências Visuais:** {site_details.get('visual_references','').strip() or 'Não informadas'}", "**Tarefa:** Desenvolva proposta de estrutura (sitemap) e conteúdo principal para cada página essencial de um site PME."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_site_content_new = ai_response.content

    def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
        if not client_details.get("product_campaign"): st.warning("Descreva o produto/serviço ou campanha."); return
        with st.spinner("🕵️ Investigando seu público-alvo..."):
            prompt_parts = ["**Instrução para IA:** 'Agente Detetive de Clientes', especialista em marketing e pesquisa.", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details.get('location','').strip() or 'Não informada'}", f"**Verba:** {client_details.get('budget','').strip() or 'Não informada'}", f"**Faixa Etária/Gênero:** {client_details.get('age_gender','').strip() or 'Não informados'}", f"**Interesses:** {client_details.get('interests','').strip() or 'Não informados'}", f"**Canais:** {client_details.get('current_channels','').strip() or 'Não informados'}", f"**Deep Research:** {'Ativado' if client_details.get('deep_research', False) else 'Padrão'}", "**Tarefa:** Análise completa do público-alvo, incluindo: Personas (2-3), Dores e Necessidades, Comportamento Online, Canais preferidos, Sugestões de Mensagem e Tom."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_client_analysis_new = ai_response.content

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details.get("your_business") or not competitor_details.get("competitors_list"): st.warning("Descreva seu negócio e liste concorrentes."); return
        with st.spinner("🔬 Analisando a concorrência..."):
            prompt_parts = ["**Instrução para IA:** 'Agente de Inteligência Competitiva'.", f"**Negócio do Usuário:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details.get('aspects_to_analyze',[]))}", "**Tarefa:** Elabore um relatório breve e útil sobre os concorrentes, focando nos aspectos solicitados. Destaque pontos fortes, fracos e oportunidades para o negócio do usuário."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_competitor_analysis_new = ai_response.content

    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None:
                st.error("Erro: Modelo LLM não inicializado.")
                st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_history_plano_v2", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_history_precos_v2", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_history_ideias_v2", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_history_v2"):
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
            # Chave base para widgets de marketing, para evitar conflitos de sessão
            base_key_mkt = "mkt_v4"

            marketing_files_info_for_prompt = []
            # Removido o file_uploader da sidebar para simplificar, pode ser colocado dentro de cada seção se necessário
            # Se for global para todas as seções de marketing, considerar um local mais proeminente.
            
            # Opções de marketing
            opcoes_marketing = {
                "Selecione uma opção...": "mkt_selecione",
                "1 - Criar post para redes sociais/e-mail": "mkt_post",
                "2 - Criar campanha de marketing completa": "mkt_campanha",
                "3 - Gerar estrutura para Landing Page": "mkt_lp",
                "4 - Gerar estrutura para Site PME": "mkt_site",
                "5 - Encontrar meu cliente ideal (Persona)": "mkt_cliente",
                "6 - Analisar a concorrência": "mkt_concorrencia"
            }
            main_action_label = st.radio("O que você quer criar ou analisar hoje em Marketing Digital?",
                                         options=list(opcoes_marketing.keys()),
                                         key=f"{base_key_mkt}_main_action_radio")
            main_action = opcoes_marketing[main_action_label]
            st.markdown("---")

            platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", "TikTok": "tt", "Kwai": "kwai", "YouTube": "yt", "E-mail (lista própria)": "email_own", "E-mail (Google Ads)": "email_google"}
            platform_names = list(platforms_cfg.keys())
            
            # File uploader global para a seção de marketing, se aplicável
            st.sidebar.subheader("📎 Arquivos de Apoio (Marketing)")
            uploaded_marketing_files = st.file_uploader("Upload para Marketing (opcional, geral):",
                                                       accept_multiple_files=True,
                                                       type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'],
                                                       key=f"{base_key_mkt}_geral_uploader")
            if uploaded_marketing_files:
                temp_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                if temp_info:
                    marketing_files_info_for_prompt = temp_info
                    st.sidebar.success(f"{len(uploaded_marketing_files)} arquivo(s) de apoio carregados!")
                    st.sidebar.expander("Ver arquivos de apoio").write(marketing_files_info_for_prompt)
            st.sidebar.markdown("---")


            if main_action == "mkt_post":
                st.subheader("✨ Criador de Posts com IA")
                with st.form(f"{base_key_mkt}_post_form"):
                    st.subheader("Plataformas:")
                    key_select_all_post = f"{base_key_mkt}_post_select_all"
                    if st.checkbox("Selecionar todas abaixo", key=key_select_all_post):
                        for p_key in keys_for_plats_post.values(): st.session_state[p_key] = True
                    
                    cols_p = st.columns(2)
                    keys_for_plats_post = {name: f"{base_key_mkt}_post_p_{suf}" for name, suf in platforms_cfg.items()}
                    for i, (name, _) in enumerate(platforms_cfg.items()):
                        with cols_p[i%2]: st.checkbox(name, key=keys_for_plats_post[name])
                    if any(st.session_state.get(keys_for_plats_post[p_name]) for p_name in platforms_cfg if "E-mail" in p_name):
                        st.caption("💡 Para e-mail marketing, o conteúdo gerado incluirá Assunto e Corpo.")
                    
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    submit_post = st.form_submit_button("💡 Gerar Post!")
                if submit_post:
                    selected_plats = [name for name, key in keys_for_plats_post.items() if st.session_state.get(key,False)]
                    _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_new' in st.session_state and st.session_state.generated_post_content_new:
                     _marketing_display_output_options(st.session_state.generated_post_content_new, f"{base_key_mkt}_post_output", "post_ia")

            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas com IA")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name")
                    st.subheader("Plataformas:")
                    key_select_all_camp = f"{base_key_mkt}_camp_select_all"
                    if st.checkbox("Selecionar todas abaixo", key=key_select_all_camp):
                        for p_key in keys_for_plats_camp.values(): st.session_state[p_key] = True

                    cols_c = st.columns(2)
                    keys_for_plats_camp = {name: f"{base_key_mkt}_camp_p_{suf}" for name, suf in platforms_cfg.items()}
                    for i, (name, _) in enumerate(platforms_cfg.items()):
                        with cols_c[i%2]: st.checkbox(name, key=keys_for_plats_camp[name])
                    if any(st.session_state.get(keys_for_plats_camp[p_name]) for p_name in platforms_cfg if "E-mail" in p_name):
                        st.caption("💡 Para e-mail marketing, o conteúdo gerado incluirá Assunto e Corpo.")
                    
                    camp_details_obj = _marketing_get_objective_details(f"{base_key_mkt}_camp_details", "campanha")
                    camp_duration = st.text_input("Duração Estimada:", key=f"{base_key_mkt}_camp_duration")
                    camp_budget = st.text_input("Orçamento (opcional):", key=f"{base_key_mkt}_camp_budget")
                    camp_kpis = st.text_area("KPIs mais importantes:", key=f"{base_key_mkt}_camp_kpis")
                    submit_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")
                if submit_camp:
                    selected_plats_camp = [name for name, key in keys_for_plats_camp.items() if st.session_state.get(key,False)]
                    camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                    _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
                
                if 'generated_campaign_content_new' in st.session_state and st.session_state.generated_campaign_content_new:
                    _marketing_display_output_options(st.session_state.generated_campaign_content_new, f"{base_key_mkt}_camp_output", "campanha_ia")
                    if st.button("🚀 Criar Ativos da Campanha Agora!", key=f"{base_key_mkt}_btn_create_assets"):
                        st.session_state.creating_campaign_assets = True
                        st.session_state.current_campaign_plan_context = st.session_state.generated_campaign_content_new
                        st.session_state.campaign_assets_list = []
                        st.session_state.current_asset_description = ""
                        st.session_state.current_asset_objective = ""
                        st.session_state.current_generated_asset_text = ""
                        # Não resetar uploads aqui, eles são por ativo
                        st.rerun()
                
                if st.session_state.get("creating_campaign_assets"):
                    st.markdown("---"); st.subheader("🛠️ Criador de Ativos para a Campanha")
                    st.markdown("**Plano da Campanha (Contexto):**")
                    st.info(st.session_state.get('current_campaign_plan_context', "Contexto não disponível."))
                    
                    asset_form_key = f"{base_key_mkt}_asset_creator_form"
                    with st.form(asset_form_key):
                        asset_desc_val = st.session_state.get('current_asset_description','')
                        asset_obj_val = st.session_state.get('current_asset_objective','')
                        
                        st.session_state.current_asset_description = st.text_input("Nome/Descrição do Ativo:", value=asset_desc_val, key=f"{asset_form_key}_desc")
                        st.session_state.current_asset_objective = st.text_area("Objetivo Específico deste Ativo:", value=asset_obj_val, key=f"{asset_form_key}_obj")
                        
                        # Botões de "Gerar Texto/Ideias" são submissões do formulário de ativos
                        submit_generate_text = st.form_submit_button("✍️ Gerar Texto para este Ativo")
                        # Botões de ideias de imagem/vídeo podem ser colocados fora do form se não submeterem este form específico
                        
                        # File uploaders para este ativo específico
                        img_upload_key_asset = f"{asset_form_key}_img_upload_{len(st.session_state.get('campaign_assets_list', []))}"
                        vid_upload_key_asset = f"{asset_form_key}_vid_upload_{len(st.session_state.get('campaign_assets_list', []))}"
                        current_img_asset = st.file_uploader("Carregar Imagem (para este ativo):", type=['png', 'jpg', 'jpeg'], key=img_upload_key_asset)
                        current_vid_asset = st.file_uploader("Carregar Vídeo (para este ativo):", type=['mp4', 'mov', 'avi'], key=vid_upload_key_asset)

                        if st.session_state.get('current_generated_asset_text'): 
                            st.text_area("Texto Gerado para o Ativo:", value=st.session_state.current_generated_asset_text, height=150, key=f"{asset_form_key}_gen_text_display", disabled=True)
                        if current_img_asset: st.success(f"Imagem '{current_img_asset.name}' pronta para o ativo.")
                        if current_vid_asset: st.success(f"Vídeo '{current_vid_asset.name}' pronto para o ativo.")

                        submit_add_asset = st.form_submit_button("➕ Adicionar Ativo à Lista e Limpar")

                        if submit_generate_text:
                            if st.session_state.current_asset_description and st.session_state.current_asset_objective:
                                _marketing_handle_gerar_texto_ativo(st.session_state.get('current_campaign_plan_context'), st.session_state.current_asset_description, st.session_state.current_asset_objective, self.llm)
                                st.rerun() # Rerun para mostrar o texto gerado
                            else: st.warning("Preencha Descrição e Objetivo do ativo antes de gerar o texto.")
                        
                        if submit_add_asset:
                            if st.session_state.current_asset_description:
                                new_asset = {
                                    "descricao": st.session_state.current_asset_description, "objetivo": st.session_state.current_asset_objective,
                                    "texto_gerado": st.session_state.get('current_generated_asset_text', ""),
                                    "imagem_carregada": current_img_asset.name if current_img_asset else None,
                                    "video_carregado": current_vid_asset.name if current_vid_asset else None
                                }
                                st.session_state.campaign_assets_list.append(new_asset)
                                st.success(f"Ativo '{st.session_state.current_asset_description}' adicionado à lista!")
                                st.session_state.current_asset_description = ""
                                st.session_state.current_asset_objective = ""
                                st.session_state.current_generated_asset_text = ""
                                st.rerun() # Rerun para limpar campos e atualizar lista
                            else: st.warning("Adicione uma descrição para o ativo antes de adicioná-lo.")
                    
                    # Botões de ideias fora do form de criação de ativo para não causar conflito de submit
                    cols_ideias_btn = st.columns(2)
                    with cols_ideias_btn[0]:
                        if st.button("💡 Gerar Ideias de Imagem (para contexto geral da campanha)", key=f"{base_key_mkt}_btn_img_ideas"):
                            st.info("Funcionalidade de ideias de imagem em desenvolvimento.")
                    with cols_ideias_btn[1]:
                        if st.button("💡 Gerar Ideias de Vídeo (para contexto geral da campanha)", key=f"{base_key_mkt}_btn_vid_ideas"):
                            st.info("Funcionalidade de ideias de vídeo em desenvolvimento.")

                    if st.session_state.campaign_assets_list:
                        st.markdown("---"); st.subheader("📦 Ativos da Campanha Adicionados à Lista:")
                        for i, asset in enumerate(st.session_state.campaign_assets_list):
                            with st.expander(f"Ativo {i+1}: {asset['descricao']}"):
                                st.write(f"**Objetivo:** {asset['objetivo']}")
                                if asset["texto_gerado"]: st.markdown(f"**Texto:**\n```\n{asset['texto_gerado']}\n```")
                                if asset["imagem_carregada"]: st.write(f"**Imagem Carregada:** {asset['imagem_carregada']}")
                                if asset["video_carregado"]: st.write(f"**Vídeo Carregado:** {asset['video_carregado']}")
                    if st.button("🏁 Concluir Criação de Ativos da Campanha", key=f"{base_key_mkt}_btn_finish_assets"):
                        st.session_state.creating_campaign_assets = False
                        st.success("Criação de ativos para esta campanha concluída!")
                        st.balloons(); st.rerun()
            
            elif main_action == "mkt_lp":
                st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
                with st.form(f"{base_key_mkt}_lp_form"):
                    lp_details = {}
                    lp_details["purpose"] = st.text_input("Objetivo principal:", key=f"{base_key_mkt}_lp_purpose")
                    lp_details["target_audience"] = st.text_input("Público-alvo (Persona):", key=f"{base_key_mkt}_lp_audience")
                    lp_details["main_offer"] = st.text_area("Oferta principal:", key=f"{base_key_mkt}_lp_offer")
                    lp_details["key_benefits"] = st.text_area("Benefícios (3-5):", key=f"{base_key_mkt}_lp_benefits")
                    lp_details["cta"] = st.text_input("CTA principal:", key=f"{base_key_mkt}_lp_cta")
                    lp_details["visual_prefs"] = st.text_input("Preferências visuais (Opcional):", key=f"{base_key_mkt}_lp_visual")
                    submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura de Landing Page!")
                if submitted_lp:
                    _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details, self.llm)
                if 'generated_lp_content_new' in st.session_state and st.session_state.generated_lp_content_new:
                     _marketing_display_output_options(st.session_state.generated_lp_content_new, f"{base_key_mkt}_lp_output", "lp_ia")

            elif main_action == "mkt_site":
                st.subheader("🏗️ Arquiteto de Sites PME com IA")
                with st.form(f"{base_key_mkt}_site_form"):
                    site_details = {}
                    site_details["business_type"] = st.text_input("Tipo do negócio:", key=f"{base_key_mkt}_site_biz_type")
                    site_details["main_purpose"] = st.text_area("Objetivo principal do site:", key=f"{base_key_mkt}_site_purpose")
                    site_details["target_audience"] = st.text_input("Público principal:", key=f"{base_key_mkt}_site_audience")
                    site_details["essential_pages"] = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços, Contato, Blog):", key=f"{base_key_mkt}_site_pages")
                    site_details["key_features"] = st.text_area("Principais produtos/diferenciais a destacar:", key=f"{base_key_mkt}_site_features")
                    site_details["brand_personality"] = st.text_input("Personalidade da marca (ex: séria, divertida, inovadora):", key=f"{base_key_mkt}_site_brand")
                    site_details["visual_references"] = st.text_input("Referências visuais ou sites que você gosta (Opcional):", key=f"{base_key_mkt}_site_visual_ref")
                    submitted_site = st.form_submit_button("🏛️ Gerar Estrutura de Site!")
                if submitted_site:
                    _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details, self.llm)
                if 'generated_site_content_new' in st.session_state and st.session_state.generated_site_content_new:
                     _marketing_display_output_options(st.session_state.generated_site_content_new, f"{base_key_mkt}_site_output", "site_ia")

            elif main_action == "mkt_cliente":
                st.subheader("🎯 Decodificador de Clientes com IA")
                with st.form(f"{base_key_mkt}_client_form"):
                    client_details = {}
                    client_details["product_campaign"] = st.text_area("Produto/serviço/campanha para o qual busca clientes:", key=f"{base_key_mkt}_fc_campaign")
                    client_details["location"] = st.text_input("Localização (cidade/estado/país, se aplicável):", key=f"{base_key_mkt}_fc_location")
                    client_details["budget"] = st.text_input("Verba disponível para marketing (Opcional):", key=f"{base_key_mkt}_fc_budget")
                    client_details["age_gender"] = st.text_input("Faixa etária e/ou gênero principal:", key=f"{base_key_mkt}_fc_age_gender")
                    client_details["interests"] = st.text_area("Interesses, hobbies, dores ou necessidades do público:", key=f"{base_key_mkt}_fc_interests")
                    client_details["current_channels"] = st.text_area("Canais onde já tentou alcançar ou considera:", key=f"{base_key_mkt}_fc_channels")
                    client_details["deep_research"] = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada)", value=True, key=f"{base_key_mkt}_fc_deep")
                    submitted_fc = st.form_submit_button("🔍 Encontrar Cliente Ideal!")
                if submitted_fc:
                    _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details, self.llm)
                if 'generated_client_analysis_new' in st.session_state and st.session_state.generated_client_analysis_new:
                     _marketing_display_output_options(st.session_state.generated_client_analysis_new, f"{base_key_mkt}_client_output", "cliente_ia")

            elif main_action == "mkt_concorrencia":
                st.subheader("🧐 Radar da Concorrência com IA")
                with st.form(f"{base_key_mkt}_competitor_form"):
                    competitor_details = {}
                    competitor_details["your_business"] = st.text_area("Descreva seu negócio/produto principal:", key=f"{base_key_mkt}_ca_your_biz")
                    competitor_details["competitors_list"] = st.text_area("Liste seus principais concorrentes (nomes ou sites, um por linha):", key=f"{base_key_mkt}_ca_competitors")
                    competitor_details["aspects_to_analyze"] = st.multiselect( "Aspectos a analisar:", 
                                                                          ["Presença Online", "Qualidade do Conteúdo", "Tom de Comunicação", "Produtos/Serviços Oferecidos", "Pontos Fortes", "Pontos Fracos", "Estratégia de Preços", "Engajamento do Público"], 
                                                                          default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"{base_key_mkt}_ca_aspects")
                    submitted_ca = st.form_submit_button("📡 Analisar Concorrência!")
                if submitted_ca:
                    _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details, self.llm)
                if 'generated_competitor_analysis_new' in st.session_state and st.session_state.generated_competitor_analysis_new:
                     _marketing_display_output_options(st.session_state.generated_competitor_analysis_new, f"{base_key_mkt}_competitor_output", "concorrencia_ia")
            
            elif main_action == "mkt_selecione":
                st.info("👋 Bem-vindo à seção de Marketing Digital! Escolha uma opção acima para começar.")

        def conversar_plano_de_negocios(self, input_usuario):
            system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente. Ajude a elaborar um plano de negócios conciso, fazendo perguntas relevantes e fornecendo insights práticos."
            cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="chat_history_plano_v2")
            try:
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text']
            except Exception as e: return f"Erro na conversação do plano de negócios: {e}"

        def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
            prompt_base_calculo = f"""Você é o "Assistente PME Pro", especialista em precificação. Ajude a calcular preços de forma interativa. Considere custos, margem, concorrência e valor percebido. Contexto da imagem: {descricao_imagem_contexto if descricao_imagem_contexto else "Nenhuma"}"""
            cadeia = self._criar_cadeia_conversacional(prompt_base_calculo, self.memoria_calculo_precos, memory_key_placeholder="chat_history_precos_v2")
            try:
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text']
            except Exception as e: return f"Erro no cálculo de preços: {e}"

        def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
            prompt_base_ideias = f"""Você é o "Assistente PME Pro", um gerador de ideias criativas. Ajude com novas ideias de negócios, produtos ou melhorias. Contexto de arquivos: {contexto_arquivos if contexto_arquivos else "Nenhum"}"""
            cadeia = self._criar_cadeia_conversacional(prompt_base_ideias, self.memoria_gerador_ideias, memory_key_placeholder="chat_history_ideias_v2")
            try:
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text']
            except Exception as e: return f"Erro na geração de ideias: {e}"

    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        # Usar um sufixo consistente para chaves de chat relacionadas à autenticação
        chat_display_key = f"chat_display_{area_chave}_v3auth"
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia:
            memoria_agente_instancia.clear()
            if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
            elif hasattr(memoria_agente_instancia.chat_memory, 'messages'):
                memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
        # Limpar estados específicos de uploaders para cada chat
        if area_chave == "calculo_precos":
            st.session_state.pop('last_uploaded_image_info_pricing_v3auth', None)
            st.session_state.pop('processed_image_id_pricing_v3auth', None)
        elif area_chave == "gerador_ideias":
            st.session_state.pop('uploaded_file_info_ideias_for_prompt_v3auth', None)
            st.session_state.pop('processed_file_id_ideias_v3auth', None)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}_v3auth"
        chat_input_key = f"chat_input_{area_chave}_v3auth"

        if chat_display_key not in st.session_state:
            st.warning("Sessão de chat não iniciada. Tente reiniciar ou voltar à página inicial.")
            return

        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])

        prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            
            # Flags para processamento de input específico da área
            if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing_v3auth = True
            elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias_v3auth = True

            with st.spinner("Assistente PME Pro está processando... 🤔"):
                resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
            st.rerun()

    if llm_model_instance:
        if 'agente_pme_v3auth' not in st.session_state: # Chave única para o agente na sessão autenticada
            st.session_state.agente_pme_v3auth = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme_v3auth

        URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
        st.sidebar.title("Menu PME Pro")
        st.sidebar.markdown("IA para seu Negócio Decolar!")
        st.sidebar.markdown("---")

        opcoes_menu = {
            "Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado",
            "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos",
            "Gerador de Ideias para Negócios": "gerador_ideias"
        }
        
        current_area_key = "area_selecionada_v3auth" # Chave única para a área selecionada
        if current_area_key not in st.session_state:
            st.session_state[current_area_key] = "Página Inicial"

        # Inicializa o histórico de chat para cada seção se ainda não existir
        for nome_menu_init, chave_secao_init in opcoes_menu.items():
            if chave_secao_init != "marketing_guiado":
                chat_key_init = f"chat_display_{chave_secao_init}_v3auth"
                if chat_key_init not in st.session_state:
                    st.session_state[chat_key_init] = []
        
        previous_area_key = "previous_area_selecionada_v3auth"
        if previous_area_key not in st.session_state:
            st.session_state[previous_area_key] = None

        area_selecionada_label = st.sidebar.radio(
            "Como posso te ajudar hoje?", options=list(opcoes_menu.keys()),
            key='sidebar_selection_v3auth', # Chave única
            index=list(opcoes_menu.keys()).index(st.session_state[current_area_key])
        )

        if area_selecionada_label != st.session_state[current_area_key]:
            st.session_state[current_area_key] = area_selecionada_label
            # Limpar estados de marketing se sair da seção de marketing
            if area_selecionada_label != "Marketing Digital com IA (Guia)":
                # Lista de chaves de sessão de marketing para limpar
                mkt_keys_to_clear = [
                    'generated_post_content_new', 'generated_campaign_content_new', 
                    'generated_lp_content_new', 'generated_site_content_new',
                    'generated_client_analysis_new', 'generated_competitor_analysis_new',
                    'creating_campaign_assets', 'campaign_assets_list', 
                    'current_campaign_plan_context', 'current_asset_description', 
                    'current_asset_objective', 'current_generated_asset_text'
                ]
                # Adicionar prefixos de chaves de widget de marketing também
                mkt_widget_prefixes = ["mkt_v4_"] 
                
                for key in list(st.session_state.keys()):
                    if key in mkt_keys_to_clear:
                        del st.session_state[key]
                    for prefix in mkt_widget_prefixes:
                        if key.startswith(prefix):
                            del st.session_state[key]
            st.rerun()

        current_section_key_val = opcoes_menu.get(st.session_state[current_area_key])

        # Inicialização de chats ao navegar
        if current_section_key_val not in ["pagina_inicial", "marketing_guiado"]:
            if st.session_state[current_area_key] != st.session_state.get(previous_area_key):
                chat_display_key_nav = f"chat_display_{current_section_key_val}_v3auth"
                msg_inicial_nav = ""; memoria_agente_nav = None
                if not st.session_state.get(chat_display_key_nav): # Só inicializa se o chat estiver vazio
                    if current_section_key_val == "plano_negocios":
                        msg_inicial_nav = "Olá! Sou seu Assistente PME Pro para Planos de Negócios. Em que posso ajudar?"
                        memoria_agente_nav = agente.memoria_plano_negocios
                    elif current_section_key_val == "calculo_precos":
                        msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Vamos começar?"
                        memoria_agente_nav = agente.memoria_calculo_precos
                    elif current_section_key_val == "gerador_ideias":
                        msg_inicial_nav = "Olá! Sou o Assistente PME Pro para Geração de Ideias. Qual seu desafio?"
                        memoria_agente_nav = agente.memoria_gerador_ideias
                    if msg_inicial_nav and memoria_agente_nav:
                        inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
                st.session_state[previous_area_key] = st.session_state[current_area_key]

        if current_section_key_val == "pagina_inicial":
            st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name}!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda.</p></div>", unsafe_allow_html=True)
            st.markdown("---"); st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo' width='150'></div>", unsafe_allow_html=True); st.markdown("---")
            num_botoes_funcionais = len(opcoes_menu) - 1
            if num_botoes_funcionais > 0:
                st.subheader("Acesso Rápido:")
                num_cols_render = min(num_botoes_funcionais, 3)
                cols_botoes_pg_inicial = st.columns(num_cols_render)
                btn_idx_pg_inicial = 0
                for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                    if chave_secao_btn_pg != "pagina_inicial":
                        col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                        button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" para ")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" (Guia)","")
                        if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v3auth", use_container_width=True):
                            st.session_state[current_area_key] = nome_menu_btn_pg; st.rerun()
                        btn_idx_pg_inicial +=1
        elif current_section_key_val == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key_val == "plano_negocios":
            st.header("📝 Plano de Negócios com IA")
            exibir_chat_e_obter_input(current_section_key_val, "Sua resposta...", agente.conversar_plano_de_negocios)
            if st.sidebar.button("Reiniciar Plano", key="btn_reset_plano_v3auth"): inicializar_ou_resetar_chat(current_section_key_val, "Ok, vamos recomeçar seu Plano de Negócios.", agente.memoria_plano_negocios); st.rerun()
        elif current_section_key_val == "calculo_precos":
            st.header("💲 Cálculo de Preços Inteligente com IA")
            uploaded_image_pricing = st.file_uploader("Imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v3auth")
            descricao_imagem_para_ia_pricing = None
            if uploaded_image_pricing is not None:
                if st.session_state.get('processed_image_id_pricing_v3auth') != uploaded_image_pricing.id:
                    try:
                        img_pil_pricing = Image.open(uploaded_image_pricing)
                        st.image(img_pil_pricing, caption=f"Imagem: {uploaded_image_pricing.name}", width=150)
                        descricao_imagem_para_ia_pricing = f"Imagem: '{uploaded_image_pricing.name}'."
                        st.session_state.last_uploaded_image_info_pricing_v3auth = descricao_imagem_para_ia_pricing
                        st.session_state.processed_image_id_pricing_v3auth = uploaded_image_pricing.id
                        st.info(f"'{uploaded_image_pricing.name}' pronta.")
                    except Exception as e: st.error(f"Erro ao processar imagem: {e}")
                else: descricao_imagem_para_ia_pricing = st.session_state.get('last_uploaded_image_info_pricing_v3auth')
            kwargs_preco_chat = {'descricao_imagem_contexto': descricao_imagem_para_ia_pricing} if descricao_imagem_para_ia_pricing else {}
            exibir_chat_e_obter_input(current_section_key_val, "Descreva o produto/serviço, custos...", agente.calcular_precos_interativo, **kwargs_preco_chat)
            if st.session_state.get('user_input_processed_pricing_v3auth'):
                st.session_state.pop('last_uploaded_image_info_pricing_v3auth', None) 
                st.session_state.user_input_processed_pricing_v3auth = False
            if st.sidebar.button("Reiniciar Preços", key="btn_reset_precos_v3auth"): inicializar_ou_resetar_chat(current_section_key_val, "Ok, novo cálculo! Compra e revende ou produz/cria?", agente.memoria_calculo_precos); st.rerun()
        elif current_section_key_val == "gerador_ideias":
            st.header("💡 Gerador de Ideias para Negócios com IA")
            uploaded_files_ideias = st.file_uploader("Upload de arquivos (.txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_v3auth")
            contexto_para_ia_ideias = None
            if uploaded_files_ideias:
                current_file_signature_ideias = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias]))
                if st.session_state.get('processed_file_id_ideias_v3auth') != current_file_signature_ideias:
                    text_contents_ideias = []; image_info_ideias = []
                    for uploaded_file_item_ideias in uploaded_files_ideias:
                        try:
                            if uploaded_file_item_ideias.type == "text/plain": text_contents_ideias.append(f"'{uploaded_file_item_ideias.name}':\n{uploaded_file_item_ideias.read().decode('utf-8')[:1000]}...")
                            elif uploaded_file_item_ideias.type in ["image/png", "image/jpeg"]: st.image(Image.open(uploaded_file_item_ideias), caption=f"Ref: {uploaded_file_item_ideias.name}", width=100); image_info_ideias.append(f"Imagem '{uploaded_file_item_ideias.name}'")
                        except Exception as e: st.error(f"Erro ao processar '{uploaded_file_item_ideias.name}': {e}")
                    full_context_str_ideias = ""
                    if text_contents_ideias: full_context_str_ideias += "\nContexto de Texto:\n" + "\n".join(text_contents_ideias)
                    if image_info_ideias: full_context_str_ideias += "\nContexto de Imagem:\n" + "\n".join(image_info_ideias)
                    if full_context_str_ideias: st.session_state.uploaded_file_info_ideias_for_prompt_v3auth = full_context_str_ideias.strip(); st.info("Arquivo(s) de contexto pronto(s).")
                    st.session_state.processed_file_id_ideias_v3auth = current_file_signature_ideias
                contexto_para_ia_ideias = st.session_state.get('uploaded_file_info_ideias_for_prompt_v3auth')
            kwargs_ideias_chat = {'contexto_arquivos': contexto_para_ia_ideias} if contexto_para_ia_ideias else {}
            exibir_chat_e_obter_input(current_section_key_val, "Descreva seu desafio ou peça ideias...", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat)
            if st.session_state.get('user_input_processed_ideias_v3auth'):
                st.session_state.user_input_processed_ideias_v3auth = False # Reset flag
            if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v3auth"): inicializar_ou_resetar_chat(current_section_key_val, "Ok, vamos recomeçar a gerar ideias!", agente.memoria_gerador_ideias); st.rerun()
    else:
        st.error("Modelo de Linguagem (LLM) não pôde ser carregado. Verifique a GOOGLE_API_KEY nos Segredos.")
else:
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    if URL_DO_SEU_LOGO_LOGIN:
      st.image(URL_DO_SEU_LOGO_LOGIN, width=150)
    st.markdown("<h1 style='text-align: center;'>Bem-vindo ao Assistente PME Pro!</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Faça login ou registre-se para continuar.</p>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
