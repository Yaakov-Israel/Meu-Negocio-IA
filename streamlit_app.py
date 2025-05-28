import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

# Importar as novas funções de autenticação do auth.py
from auth import initialize_authenticator, handle_authentication

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

authenticator = initialize_authenticator()

# Tenta obter o status da sessão. Se não existir, define como None.
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None

# A função handle_authentication renderiza o formulário de login se necessário
# e atualiza st.session_state['authentication_status']
# Ela deve ser chamada em um local onde o formulário de login possa ser exibido.
# Se o usuário já estiver logado (status=True), ela não renderizará o formulário.
if not st.session_state['authentication_status']:
    # Chama handle_authentication para renderizar o login e verificar o status
    # Isso acontecerá se o usuário ainda não estiver logado.
    # A função login() dentro de handle_authentication irá exibir os campos.
    handle_authentication(authenticator)


# Agora, verificamos o status da autenticação que foi definido por handle_authentication
if st.session_state['authentication_status']:
    user_name = st.session_state.get('name', 'Usuário') # Obtém o nome do usuário do session_state
    st.sidebar.success(f"Logado como: {user_name}")
    authenticator.logout("Logout", "sidebar", key="logout_button_stauth_v2") # Adiciona botão de logout

    # --- CARREGAMENTO DE API KEY E MODELO LLM (SÓ SE AUTENTICADO) ---
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

    # --- INÍCIO DO CÓDIGO ORIGINAL DO SEU APLICATIVO ---

    def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
        key_suffix = f"_{section_key}_mkt_obj_v5_stauth" # Chaves únicas
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
        key_suffix = f"_{section_key}_output_v5_stauth"
        st.subheader("🎉 Resultado da IA e Próximos Passos:")
        st.markdown(generated_content)
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}.txt", mime="text/plain", key=f"download{key_suffix}")

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
                st.session_state.generated_post_content_new_stauth = ai_response.content # Chave de session_state única
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
                st.session_state.generated_campaign_content_new_stauth = ai_response.content # Chave de session_state única
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
                st.session_state.current_generated_asset_text_stauth = ai_response.content # Chave de session_state única
            except Exception as e: st.error(f"Erro ao gerar texto do ativo: {e}"); st.session_state.current_generated_asset_text_stauth = "Erro ao gerar texto."

    # ... (demais funções _marketing_handle_... permanecem aqui, adaptando chaves do session_state se necessário para _stauth)

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details.get("purpose") or not lp_details.get("main_offer") or not lp_details.get("cta"): st.warning("Preencha objetivo, oferta e CTA da landing page."); return
        with st.spinner("🎨 Desenhando estrutura da landing page..."):
            prompt_parts = ["**Instrução para IA:** Especialista em UX/UI e copywriting para landing pages.", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details.get('target_audience','Não informado')}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details.get('key_benefits','Não informados')}", f"**CTA:** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details.get('visual_prefs','Não informadas')}", "**Tarefa:** Crie estrutura e copy."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_lp_content_new_stauth = ai_response.content

    def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
        if not site_details.get("business_type") or not site_details.get("main_purpose"): st.warning("Informe tipo de negócio e objetivo do site."); return
        with st.spinner("🛠️ Arquitetando seu site..."):
            prompt_parts = ["**Instrução para IA:** Arquiteto de informação.", f"**Tipo de Negócio:** {site_details['business_type']}", f"**Objetivo do Site:** {site_details['main_purpose']}", f"**Público-Alvo:** {site_details.get('target_audience','Não informado')}", f"**Páginas Essenciais:** {site_details.get('essential_pages','Não informadas')}", f"**Produtos/Serviços Chave:** {site_details.get('key_features','Não informados')}", f"**Personalidade da Marca:** {site_details.get('brand_personality','Não informada')}", f"**Referências Visuais:** {site_details.get('visual_references','Não informadas')}", "**Tarefa:** Desenvolva proposta de estrutura e conteúdo."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_site_content_new_stauth = ai_response.content

    def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
        if not client_details.get("product_campaign"): st.warning("Descreva o produto/serviço ou campanha."); return
        with st.spinner("🕵️ Investigando seu público-alvo..."):
            prompt_parts = ["**Instrução para IA:** 'Agente Detetive de Clientes'.", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details.get('location','Não informada')}", f"**Verba:** {client_details.get('budget','Não informada')}", f"**Faixa Etária/Gênero:** {client_details.get('age_gender','Não informados')}", f"**Interesses:** {client_details.get('interests','Não informados')}", f"**Canais:** {client_details.get('current_channels','Não informados')}", f"**Deep Research:** {'Ativado' if client_details.get('deep_research', False) else 'Padrão'}", "**Tarefa:** Análise completa do público-alvo."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_client_analysis_new_stauth = ai_response.content

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details.get("your_business") or not competitor_details.get("competitors_list"): st.warning("Descreva seu negócio e liste concorrentes."); return
        with st.spinner("🔬 Analisando a concorrência..."):
            prompt_parts = ["**Instrução para IA:** 'Agente de Inteligência Competitiva'.", f"**Negócio do Usuário:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details.get('aspects_to_analyze',[]))}", "**Tarefa:** Elabore um relatório breve e útil."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_competitor_analysis_new_stauth = ai_response.content

    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: st.error("Erro: Modelo LLM não inicializado."); st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_stauth", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_stauth", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_stauth", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_stauth"):
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(system_message_content),
                MessagesPlaceholder(variable_name=memory_key_placeholder),
                HumanMessagePromptTemplate.from_template("{input_usuario}")])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
            st.markdown("---")
            base_key_mkt = "mkt_v5_stauth"
            marketing_files_info_for_prompt = []
            st.sidebar.subheader("📎 Arquivos de Apoio (Marketing)")
            uploaded_marketing_files = st.file_uploader("Upload para Marketing (opcional, geral):", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'], key=f"{base_key_mkt}_geral_uploader")
            if uploaded_marketing_files:
                temp_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                if temp_info: marketing_files_info_for_prompt = temp_info; st.sidebar.success(f"{len(uploaded_marketing_files)} arquivo(s) de apoio carregados!"); st.sidebar.expander("Ver arquivos de apoio").write(marketing_files_info_for_prompt)
            st.sidebar.markdown("---")
            opcoes_marketing = {"Selecione uma opção...": "mkt_selecione", "1 - Criar post para redes sociais/e-mail": "mkt_post", "2 - Criar campanha de marketing completa": "mkt_campanha", "3 - Gerar estrutura para Landing Page": "mkt_lp", "4 - Gerar estrutura para Site PME": "mkt_site", "5 - Encontrar meu cliente ideal (Persona)": "mkt_cliente", "6 - Analisar a concorrência": "mkt_concorrencia"}
            main_action_label = st.radio("O que você quer criar ou analisar hoje em Marketing Digital?", options=list(opcoes_marketing.keys()), key=f"{base_key_mkt}_main_action_radio")
            main_action = opcoes_marketing[main_action_label]; st.markdown("---")
            platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", "TikTok": "tt", "Kwai": "kwai", "YouTube": "yt", "E-mail (lista própria)": "email_own", "E-mail (Google Ads)": "email_google"}

            if main_action == "mkt_post":
                st.subheader("✨ Criador de Posts com IA")
                with st.form(f"{base_key_mkt}_post_form"):
                    st.subheader("Plataformas:")
                    # Gerenciamento dos checkboxes de plataformas
                    cols_p = st.columns(2); platform_states_post = {}
                    for i, name in enumerate(platforms_cfg.keys()):
                        with cols_p[i%2]: platform_states_post[name] = st.checkbox(name, key=f"{base_key_mkt}_post_p_{platforms_cfg[name]}")
                    if any(platform_states_post.get(p_name, False) for p_name in platforms_cfg if "E-mail" in p_name): st.caption("💡 Para e-mail, o conteúdo incluirá Assunto e Corpo.")
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    submit_post = st.form_submit_button("💡 Gerar Post!")
                if submit_post:
                    selected_plats = [name for name, checked in platform_states_post.items() if checked]
                    _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_new_stauth' in st.session_state and st.session_state.generated_post_content_new_stauth:
                     _marketing_display_output_options(st.session_state.generated_post_content_new_stauth, f"{base_key_mkt}_post_output", "post_ia")

            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas com IA")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name")
                    st.subheader("Plataformas:")
                    cols_c = st.columns(2); platform_states_camp = {}
                    for i, name in enumerate(platforms_cfg.keys()):
                        with cols_c[i%2]: platform_states_camp[name] = st.checkbox(name, key=f"{base_key_mkt}_camp_p_{platforms_cfg[name]}")
                    if any(platform_states_camp.get(p_name, False) for p_name in platforms_cfg if "E-mail" in p_name): st.caption("💡 Para e-mail, o conteúdo incluirá Assunto e Corpo.")
                    camp_details_obj = _marketing_get_objective_details(f"{base_key_mkt}_camp_details", "campanha")
                    camp_duration = st.text_input("Duração Estimada:", key=f"{base_key_mkt}_camp_duration")
                    camp_budget = st.text_input("Orçamento (opcional):", key=f"{base_key_mkt}_camp_budget")
                    camp_kpis = st.text_area("KPIs mais importantes:", key=f"{base_key_mkt}_camp_kpis")
                    submit_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")
                if submit_camp:
                    selected_plats_camp = [name for name, checked in platform_states_camp.items() if checked]
                    camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                    _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
                if 'generated_campaign_content_new_stauth' in st.session_state and st.session_state.generated_campaign_content_new_stauth:
                    _marketing_display_output_options(st.session_state.generated_campaign_content_new_stauth, f"{base_key_mkt}_camp_output", "campanha_ia")
                    if st.button("🚀 Criar Ativos da Campanha Agora!", key=f"{base_key_mkt}_btn_create_assets"):
                        st.session_state.creating_campaign_assets_stauth = True
                        st.session_state.current_campaign_plan_context_stauth = st.session_state.generated_campaign_content_new_stauth
                        st.session_state.campaign_assets_list_stauth = []
                        st.rerun()
                if st.session_state.get("creating_campaign_assets_stauth"):
                    st.markdown("---"); st.subheader("🛠️ Criador de Ativos para a Campanha")
                    st.info(st.session_state.get('current_campaign_plan_context_stauth', "Contexto não carregado."))
                    asset_form_key = f"{base_key_mkt}_asset_creator_form"
                    with st.form(asset_form_key, clear_on_submit=True):
                        asset_desc = st.text_input("Nome/Descrição do Ativo:", key=f"{asset_form_key}_desc")
                        asset_obj = st.text_area("Objetivo Específico:", key=f"{asset_form_key}_obj")
                        submit_generate_text_asset = st.form_submit_button("✍️ Gerar Texto para Ativo")
                        img_asset = st.file_uploader("Carregar Imagem (ativo):", type=['png', 'jpg', 'jpeg'], key=f"{asset_form_key}_img_upload")
                        vid_asset = st.file_uploader("Carregar Vídeo (ativo):", type=['mp4', 'mov', 'avi'], key=f"{asset_form_key}_vid_upload")
                        if st.session_state.get('current_generated_asset_text_stauth'): st.text_area("Texto Gerado:", value=st.session_state.current_generated_asset_text_stauth, height=150, disabled=True, key=f"{asset_form_key}_text_display")
                        submit_add_asset = st.form_submit_button("➕ Adicionar Ativo à Lista")
                        if submit_generate_text_asset:
                            if asset_desc and asset_obj: _marketing_handle_gerar_texto_ativo(st.session_state.get('current_campaign_plan_context_stauth'), asset_desc, asset_obj, self.llm); st.rerun()
                            else: st.warning("Preencha Descrição e Objetivo.")
                        if submit_add_asset:
                            if asset_desc:
                                new_asset = {"descricao": asset_desc, "objetivo": asset_obj, "texto_gerado": st.session_state.get('current_generated_asset_text_stauth', ""),"imagem_carregada": img_asset.name if img_asset else None, "video_carregado": vid_asset.name if vid_asset else None}
                                st.session_state.campaign_assets_list_stauth.append(new_asset)
                                st.success(f"Ativo '{asset_desc}' adicionado!"); st.session_state.current_generated_asset_text_stauth = ""; st.rerun()
                            else: st.warning("Adicione uma descrição.")
                    # Botões de ideias fora do form
                    c1,c2 = st.columns(2)
                    if c1.button("💡 Ideias de Imagem (Campanha)", key=f"{base_key_mkt}_btn_img_ideas_asset_outside"): st.info("Em desenvolvimento.")
                    if c2.button("💡 Ideias de Vídeo (Campanha)", key=f"{base_key_mkt}_btn_vid_ideas_asset_outside"): st.info("Em desenvolvimento.")
                    if st.session_state.get('campaign_assets_list_stauth', []):
                        st.markdown("---"); st.subheader("📦 Ativos Adicionados:")
                        for i, asset in enumerate(st.session_state.campaign_assets_list_stauth):
                            with st.expander(f"Ativo {i+1}: {asset['descricao']}"): st.write(asset)
                    if st.button("🏁 Concluir Criação de Ativos", key=f"{base_key_mkt}_btn_finish_assets"):
                        st.session_state.creating_campaign_assets_stauth = False; st.success("Criação de ativos concluída!"); st.balloons(); st.rerun()

            # Adicione aqui os blocos elif para mkt_lp, mkt_site, mkt_cliente, mkt_concorrencia,
            # seguindo o padrão de usar {base_key_mkt}_nome_secao_form e adaptando as chaves do session_state
            # para _stauth se elas guardarem resultados gerados pela IA.

            elif main_action == "mkt_selecione":
                st.info("👋 Bem-vindo à seção de Marketing Digital! Escolha uma opção acima para começar.")

       def conversar_plano_de_negocios(self, input_usuario):
           system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente."
           cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios)
           try: return cadeia.invoke({"input_usuario": input_usuario})['text']
           except Exception as e: return f"Erro: {e}"

       def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
           prompt_base = f"Você é o \"Assistente PME Pro\", especialista em precificação. Contexto da imagem: {descricao_imagem_contexto or 'Nenhuma'}"
           cadeia = self._criar_cadeia_conversacional(prompt_base, self.memoria_calculo_precos)
           try: return cadeia.invoke({"input_usuario": input_usuario})['text']
           except Exception as e: return f"Erro: {e}"

       def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
           prompt_base = f"Você é o \"Assistente PME Pro\", um gerador de ideias. Contexto de arquivos: {contexto_arquivos or 'Nenhum'}"
           cadeia = self._criar_cadeia_conversacional(prompt_base, self.memoria_gerador_ideias)
           try: return cadeia.invoke({"input_usuario": input_usuario})['text']
           except Exception as e: return f"Erro: {e}"

   def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
       chat_display_key = f"chat_display_{area_chave}_v5stauth" # Chaves únicas
       st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
       if memoria_agente_instancia: memoria_agente_instancia.clear(); memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
       # Limpeza de uploads específicos da seção
       if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_v5stauth', None); st.session_state.pop(f'processed_image_id_pricing_v5stauth', None)
       elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_v5stauth', None); st.session_state.pop(f'processed_file_id_ideias_v5stauth', None)

   def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
       chat_display_key = f"chat_display_{area_chave}_v5stauth"; chat_input_key = f"chat_input_{area_chave}_v5stauth"
       if chat_display_key not in st.session_state: st.warning("Sessão de chat não iniciada."); return
       for msg_info in st.session_state[chat_display_key]:
           with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
       prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
       if prompt_usuario:
           st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
           with st.chat_message("user"): st.markdown(prompt_usuario)
           if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing_v5stauth = True
           elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias_v5stauth = True
           with st.spinner("Assistente PME Pro processando..."): resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
           st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai}); st.rerun()

   if llm_model_instance:
       agente_key = "agente_pme_v5stauth" # Chave única para o agente
       if agente_key not in st.session_state: st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
       agente = st.session_state[agente_key]
       URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
       st.sidebar.title("Menu PME Pro"); st.sidebar.markdown("IA para seu Negócio Decolar!"); st.sidebar.markdown("---")
       opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital com IA (Guia)": "marketing_guiado", "Elaborar Plano de Negócios com IA": "plano_negocios", "Cálculo de Preços Inteligente": "calculo_precos", "Gerador de Ideias para Negócios": "gerador_ideias"}
       current_area_key_main = "area_selecionada_v5stauth"
       if current_area_key_main not in st.session_state: st.session_state[current_area_key_main] = "Página Inicial"
       for nome_menu_init, chave_secao_init in opcoes_menu.items():
           if chave_secao_init != "marketing_guiado" and f"chat_display_{chave_secao_init}_v5stauth" not in st.session_state: st.session_state[f"chat_display_{chave_secao_init}_v5stauth"] = []
       previous_area_key_main = "previous_area_selecionada_v5stauth"
       if previous_area_key_main not in st.session_state: st.session_state[previous_area_key_main] = None

       area_selecionada_label = st.sidebar.radio("Como posso te ajudar hoje?", options=list(opcoes_menu.keys()), key='sidebar_selection_v5stauth', index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main]))
       if area_selecionada_label != st.session_state[current_area_key_main]:
           st.session_state[current_area_key_main] = area_selecionada_label; st.rerun()
       current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

       if current_section_key_val not in ["pagina_inicial", "marketing_guiado"] and st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_main):
           chat_display_key_nav = f"chat_display_{current_section_key_val}_v5stauth"; msg_inicial_nav = ""; memoria_agente_nav = None
           if not st.session_state.get(chat_display_key_nav):
               if current_section_key_val == "plano_negocios": msg_inicial_nav = "Olá! Vamos elaborar seu Plano de Negócios."; memoria_agente_nav = agente.memoria_plano_negocios
               elif current_section_key_val == "calculo_precos": msg_inicial_nav = "Pronto para calcular preços?"; memoria_agente_nav = agente.memoria_calculo_precos
               elif current_section_key_val == "gerador_ideias": msg_inicial_nav = "Vamos gerar algumas ideias!"; memoria_agente_nav = agente.memoria_gerador_ideias
               if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
           st.session_state[previous_area_key_main] = st.session_state[current_area_key_main]

       if current_section_key_val == "pagina_inicial":
           st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name}!</h1></div>", unsafe_allow_html=True)
           st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo' width='150'></div>", unsafe_allow_html=True)
       elif current_section_key_val == "marketing_guiado": agente.marketing_digital_guiado()
       elif current_section_key_val == "plano_negocios": st.header("📝 Plano de Negócios com IA"); exibir_chat_e_obter_input(current_section_key_val, "Detalhes para o plano...", agente.conversar_plano_de_negocios)
       elif current_section_key_val == "calculo_precos": 
            st.header("💲 Cálculo de Preços Inteligente")
            # Adicionar uploader e lógica de contexto de imagem aqui se necessário para esta seção
            exibir_chat_e_obter_input(current_section_key_val, "Detalhes para precificação...", agente.calcular_precos_interativo) # Passar kwargs_preco_chat se necessário
       elif current_section_key_val == "gerador_ideias": 
            st.header("💡 Gerador de Ideias para Negócios")
            # Adicionar uploader e lógica de contexto de arquivos aqui se necessário
            exibir_chat_e_obter_input(current_section_key_val, "Descreva seu desafio...", agente.gerar_ideias_para_negocios) # Passar kwargs_ideias_chat se necessário
   else: st.error("Modelo de Linguagem (LLM) não pôde ser carregado.")

# SE O USUÁRIO NÃO ESTIVER AUTENTICADO (st.session_state['authentication_status'] é False ou None)
elif st.session_state['authentication_status'] is False:
    # A mensagem de erro de login já é tratada por handle_authentication / authenticator.login()
    pass # Ou você pode adicionar uma mensagem genérica se quiser
elif st.session_state['authentication_status'] is None:
    # A mensagem de info para inserir credenciais já é tratada por handle_authentication / authenticator.login()
    # Pode adicionar um logo ou mensagem de boas-vindas geral aqui também se o formulário estiver em 'main'
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    if 'authenticator' not in st.session_state or not st.session_state.authenticator: # Evita mostrar se o authenticator falhou
        st.image(URL_DO_SEU_LOGO_LOGIN, width=150)
        st.markdown("<h1 style='text-align: center;'>Bem-vindo ao Assistente PME Pro!</h1>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
