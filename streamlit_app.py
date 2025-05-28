import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

# Importar as funções de autenticação com o nome correto
from auth import initialize_authenticator, authentication_flow_stauth

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

authenticator = initialize_authenticator()

# Inicializa as chaves do session_state se não existirem
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# A função authentication_flow_stauth chama authenticator.login() 
# que renderiza o formulário e atualiza o session_state.
# Chamamos aqui para que o formulário de login apareça no corpo principal da página
# se o usuário ainda não estiver logado.
if not st.session_state['authentication_status']:
    authentication_flow_stauth(authenticator)


# Verifica o status da autenticação APÓS a tentativa de login (se houver)
if st.session_state['authentication_status']:
    user_name_from_session = st.session_state.get('name', 'Usuário') 
    st.sidebar.success(f"Logado como: {user_name_from_session}")
    authenticator.logout("Logout", "sidebar", key="logout_button_stauth_final_v2") # Chave única

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

    # --- INÍCIO DO CÓDIGO ORIGINAL DO SEU APLICATIVO (DENTRO DO IF AUTENTICADO) ---

    def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
        key_suffix = f"_{section_key}_mkt_obj_v8_stauth" # Chaves únicas
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
        key_suffix = f"_{section_key}_output_v8_stauth"
        st.subheader("🎉 Resultado da IA e Próximos Passos:")
        st.markdown(generated_content)
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}.txt", mime="text/plain", key=f"download{key_suffix}")

    def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
        if not all(details_dict.get(k) for k in ["objective", "target_audience", "product_service", "key_message"]): st.warning("Preencha todos os campos obrigatórios do post."); return
        if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
        with st.spinner("🤖 Criando seu post..."):
            prompt_parts = [f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in details_dict.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Copywriter para PMEs.")
            prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
            prompt_parts.append("**Tarefa:** Gere conteúdo para post (com emojis/hashtags). Se e-mail: Assunto e corpo. Se vídeo: roteiro breve.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts)
            try: st.session_state.generated_post_content_stauth_v3 = llm.invoke([HumanMessage(content=final_prompt)]).content
            except Exception as e: st.error(f"Erro ao gerar post: {e}")

    def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
        if not campaign_specifics.get("name") or not all(details_dict.get(k) for k in ["objective", "target_audience", "product_service", "key_message"]): st.warning("Preencha nome e todos os detalhes obrigatórios da campanha."); return
        if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
        with st.spinner("🧠 Elaborando plano de campanha..."):
            prompt_parts = ["**Instrução para IA:** Estrategista de marketing digital sênior para PMEs."]
            prompt_parts.extend([f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in campaign_specifics.items()])
            prompt_parts.extend([f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in details_dict.items()])
            prompt_parts.append(f"**Plataformas:** {', '.join(selected_platforms_list)}.")
            prompt_parts.append("**Tarefa:** Elabore um plano de campanha detalhado.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts)
            try: st.session_state.generated_campaign_content_stauth_v3 = llm.invoke([HumanMessage(content=final_prompt)]).content
            except Exception as e: st.error(f"Erro ao gerar plano de campanha: {e}")

    def _marketing_handle_gerar_texto_ativo(campaign_plan_context, asset_description, asset_objective, llm):
        if not asset_description or not asset_objective: st.warning("Descreva o ativo e seu objetivo."); return
        with st.spinner("✍️ IA escrevendo..."):
            prompt = (f"**Contexto Campanha:**\n{campaign_plan_context}\n\n"
                        f"**Instrução IA:** Copywriter. Gere texto para o ativo:\n"
                        f"**Ativo:** {asset_description}\n**Objetivo:** {asset_objective}\n\n"
                        "**Tarefa:** Gere texto apropriado (com emojis/hashtags se social; Assunto/corpo se e-mail).")
            try: st.session_state.current_generated_asset_text_stauth_v3 = llm.invoke([HumanMessage(content=prompt)]).content
            except Exception as e: st.error(f"Erro: {e}"); st.session_state.current_generated_asset_text_stauth_v3 = "Erro."

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details.get("purpose") or not lp_details.get("main_offer") or not lp_details.get("cta"): st.warning("Preencha objetivo, oferta e CTA."); return
        with st.spinner("🎨 Desenhando landing page..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in lp_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Especialista em UX/UI e copy para landing pages.")
            prompt_parts.append("**Tarefa:** Crie estrutura detalhada e copy.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_lp_content_stauth_v3 = ai_response.content

    def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
        if not site_details.get("business_type") or not site_details.get("main_purpose"): st.warning("Informe tipo de negócio e objetivo."); return
        with st.spinner("🛠️ Arquitetando site..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in site_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Arquiteto de informação.")
            prompt_parts.append("**Tarefa:** Desenvolva proposta de estrutura e conteúdo.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_site_content_stauth_v3 = ai_response.content

    def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
        if not client_details.get("product_campaign"): st.warning("Descreva produto/campanha."); return
        with st.spinner("🕵️ Investigando público-alvo..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or ('Não informado' if not isinstance(v, bool) else 'Ativado' if v else 'Padrão')}" for k,v in client_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** 'Agente Detetive de Clientes'.")
            prompt_parts.append("**Tarefa:** Análise completa do público-alvo.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_client_analysis_stauth_v3 = ai_response.content

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details.get("your_business") or not competitor_details.get("competitors_list"): st.warning("Descreva seu negócio e concorrentes."); return
        with st.spinner("🔬 Analisando concorrência..."):
            competitor_details["aspects_to_analyze"] = ', '.join(competitor_details.get('aspects_to_analyze',[])) # Transforma lista em string
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in competitor_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** 'Agente de Inteligência Competitiva'.")
            prompt_parts.append("**Tarefa:** Elabore um relatório breve e útil.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_competitor_analysis_stauth_v3 = ai_response.content

    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: st.error("Erro: Modelo LLM não inicializado."); st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_v8stauth", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_v8stauth", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_v8stauth", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_v8stauth"):
            prompt_template = ChatPromptTemplate.from_messages([ SystemMessagePromptTemplate.from_template(system_message_content), MessagesPlaceholder(variable_name=memory_key_placeholder), HumanMessagePromptTemplate.from_template("{input_usuario}")])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            base_key_mkt = "mkt_v8_stauth" # Chave base atualizada
            marketing_files_info_for_prompt = []
            # File uploader na sidebar, se desejar
            # with st.sidebar:
            #     st.subheader("📎 Arquivos de Apoio (Marketing)")
            #     # ... código do file uploader ...
            opcoes_marketing = {"Selecione": "mkt_selecione", "Post": "mkt_post", "Campanha": "mkt_campanha", "Landing Page": "mkt_lp", "Site PME": "mkt_site", "Cliente Ideal": "mkt_cliente", "Concorrência": "mkt_concorrencia"}
            main_action_label = st.radio("Ferramentas de Marketing:", options=list(opcoes_marketing.keys()), key=f"{base_key_mkt}_radio", horizontal=True)
            main_action = opcoes_marketing[main_action_label]
            st.markdown("---")
            platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X": "x", "WhatsApp": "wpp", "TikTok": "tt", "YouTube": "yt", "E-mail": "email"}

            if main_action == "mkt_post":
                st.subheader("✨ Criador de Posts")
                with st.form(f"{base_key_mkt}_post_form"):
                    st.subheader("Plataformas:")
                    cols_p = st.columns(min(len(platforms_cfg), 4)) # Ajusta colunas
                    platform_states_post = {}
                    for i, name in enumerate(platforms_cfg.keys()):
                        with cols_p[i % len(cols_p)]: platform_states_post[name] = st.checkbox(name, key=f"{base_key_mkt}_post_p_{platforms_cfg[name]}")
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    if st.form_submit_button("💡 Gerar Post!"):
                        selected_plats = [name for name, checked in platform_states_post.items() if checked]
                        _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_post_content_stauth_v3, f"{base_key_mkt}_post_out", "post_ia")

            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name")
                    st.subheader("Plataformas:")
                    cols_c = st.columns(min(len(platforms_cfg), 4))
                    platform_states_camp = {}
                    for i, name in enumerate(platforms_cfg.keys()):
                        with cols_c[i % len(cols_c)]: platform_states_camp[name] = st.checkbox(name, key=f"{base_key_mkt}_camp_p_{platforms_cfg[name]}")
                    camp_details_obj = _marketing_get_objective_details(f"{base_key_mkt}_camp_details", "campanha")
                    camp_duration = st.text_input("Duração:", key=f"{base_key_mkt}_camp_duration")
                    camp_budget = st.text_input("Orçamento (opcional):", key=f"{base_key_mkt}_camp_budget")
                    camp_kpis = st.text_area("KPIs:", key=f"{base_key_mkt}_camp_kpis")
                    if st.form_submit_button("🚀 Gerar Plano!"):
                        selected_plats_camp = [name for name, checked in platform_states_camp.items() if checked]
                        camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                        _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
                if 'generated_campaign_content_stauth_v3' in st.session_state:
                    _marketing_display_output_options(st.session_state.generated_campaign_content_stauth_v3, f"{base_key_mkt}_camp_out", "campanha_ia")
                    if st.button("🚀 Criar Ativos da Campanha", key=f"{base_key_mkt}_btn_create_assets"):
                        st.session_state.creating_campaign_assets_stauth_v3 = True
                        st.session_state.current_campaign_plan_context_stauth_v3 = st.session_state.generated_campaign_content_stauth_v3
                        st.session_state.campaign_assets_list_stauth_v3 = []
                        st.rerun()
                if st.session_state.get("creating_campaign_assets_stauth_v3"):
                    st.markdown("---"); st.subheader("🛠️ Criador de Ativos para Campanha")
                    st.info(st.session_state.get('current_campaign_plan_context_stauth_v3', "Contexto não carregado."))
                    asset_form_key = f"{base_key_mkt}_asset_creator_form"
                    with st.form(asset_form_key, clear_on_submit=True):
                        asset_desc = st.text_input("Nome/Descrição do Ativo:", key=f"{asset_form_key}_desc_asset")
                        asset_obj = st.text_area("Objetivo Específico:", key=f"{asset_form_key}_obj_asset")
                        submit_generate_text_asset = st.form_submit_button("✍️ Gerar Texto para Ativo")
                        img_asset = st.file_uploader("Carregar Imagem (ativo):", type=['png', 'jpg', 'jpeg'], key=f"{asset_form_key}_img_upload_asset_v2")
                        vid_asset = st.file_uploader("Carregar Vídeo (ativo):", type=['mp4', 'mov', 'avi'], key=f"{asset_form_key}_vid_upload_asset_v2")
                        if st.session_state.get('current_generated_asset_text_stauth_v3'): st.text_area("Texto Gerado:", value=st.session_state.current_generated_asset_text_stauth_v3, height=150, disabled=True, key=f"{asset_form_key}_text_display_asset")
                        submit_add_asset = st.form_submit_button("➕ Adicionar Ativo à Lista")
                        if submit_generate_text_asset:
                            if asset_desc and asset_obj: _marketing_handle_gerar_texto_ativo(st.session_state.get('current_campaign_plan_context_stauth_v3'), asset_desc, asset_obj, self.llm); st.rerun()
                            else: st.warning("Preencha Descrição e Objetivo.")
                        if submit_add_asset:
                            if asset_desc:
                                new_asset = {"descricao": asset_desc, "objetivo": asset_obj, "texto_gerado": st.session_state.get('current_generated_asset_text_stauth_v3', ""),"imagem_carregada": img_asset.name if img_asset else None, "video_carregado": vid_asset.name if vid_asset else None}
                                st.session_state.campaign_assets_list_stauth_v3.append(new_asset)
                                st.success(f"Ativo '{asset_desc}' adicionado!"); st.session_state.current_generated_asset_text_stauth_v3 = ""; st.rerun()
                            else: st.warning("Adicione uma descrição.")
                    c1b,c2b = st.columns(2)
                    if c1b.button("💡 Ideias de Imagem (Campanha)", key=f"{base_key_mkt}_btn_img_ideas_asset_outside_v3"): st.info("Em desenvolvimento.")
                    if c2b.button("💡 Ideias de Vídeo (Campanha)", key=f"{base_key_mkt}_btn_vid_ideas_asset_outside_v3"): st.info("Em desenvolvimento.")
                    if st.session_state.get('campaign_assets_list_stauth_v3', []):
                        st.markdown("---"); st.subheader("📦 Ativos Adicionados:")
                        for i, asset in enumerate(st.session_state.campaign_assets_list_stauth_v3):
                            with st.expander(f"Ativo {i+1}: {asset['descricao']}"): st.write(asset)
                    if st.button("🏁 Concluir Criação de Ativos", key=f"{base_key_mkt}_btn_finish_assets_v3"):
                        st.session_state.creating_campaign_assets_stauth_v3 = False; st.success("Criação de ativos concluída!"); st.balloons(); st.rerun()

            elif main_action == "mkt_lp":
                st.subheader("📄 Gerador de Estrutura para Landing Pages")
                with st.form(f"{base_key_mkt}_lp_form"):
                    lp_details = _marketing_get_objective_details(f"{base_key_mkt}_lp_form_details", "landing page")
                    if st.form_submit_button("🛠️ Gerar Estrutura de LP!"):
                        _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details, self.llm)
                if 'generated_lp_content_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_lp_content_stauth_v3, f"{base_key_mkt}_lp_out", "lp_ia")

            elif main_action == "mkt_site":
                st.subheader("🏗️ Arquiteto de Sites PME")
                with st.form(f"{base_key_mkt}_site_form"):
                    site_details = _marketing_get_objective_details(f"{base_key_mkt}_site_form_details", "site") # Reutilizando a função
                    site_details["business_type"] = st.text_input("Tipo do seu Negócio/Empresa:", key=f"{base_key_mkt}_site_biz_type") # Campo específico para site
                    site_details["essential_pages"] = st.text_area("Páginas Essenciais (Ex: Home, Sobre, Serviços, Contato):", key=f"{base_key_mkt}_site_pages")
                    if st.form_submit_button("🏛️ Gerar Estrutura de Site!"):
                         _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details, self.llm)
                if 'generated_site_content_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_site_content_stauth_v3, f"{base_key_mkt}_site_out", "site_ia")

            elif main_action == "mkt_cliente":
                st.subheader("🎯 Decodificador de Clientes")
                with st.form(f"{base_key_mkt}_client_form"):
                    client_details = {}
                    client_details["product_campaign"] = st.text_area("Produto/serviço/campanha para o qual busca clientes:", key=f"{base_key_mkt}_fc_campaign")
                    client_details["location"] = st.text_input("Localização (opcional):", key=f"{base_key_mkt}_fc_location")
                    client_details["budget"] = st.text_input("Verba para marketing (opcional):", key=f"{base_key_mkt}_fc_budget")
                    client_details["age_gender"] = st.text_input("Faixa etária e/ou gênero principal:", key=f"{base_key_mkt}_fc_age_gender")
                    client_details["interests"] = st.text_area("Interesses, hobbies, dores ou necessidades do público:", key=f"{base_key_mkt}_fc_interests")
                    client_details["current_channels"] = st.text_area("Canais onde já tentou alcançar ou considera:", key=f"{base_key_mkt}_fc_channels")
                    client_details["deep_research"] = st.checkbox("Habilitar 'Deep Research'", value=True, key=f"{base_key_mkt}_fc_deep")
                    if st.form_submit_button("🔍 Encontrar Cliente Ideal!"):
                        _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details, self.llm)
                if 'generated_client_analysis_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_client_analysis_stauth_v3, f"{base_key_mkt}_client_out", "cliente_ia")

            elif main_action == "mkt_concorrencia":
                st.subheader("🧐 Radar da Concorrência")
                with st.form(f"{base_key_mkt}_competitor_form"):
                    competitor_details = {}
                    competitor_details["your_business"] = st.text_area("Descreva seu negócio/produto principal:", key=f"{base_key_mkt}_ca_your_biz")
                    competitor_details["competitors_list"] = st.text_area("Liste seus principais concorrentes (nomes ou sites):", key=f"{base_key_mkt}_ca_competitors")
                    competitor_details["aspects_to_analyze"] = st.multiselect( "Aspectos a analisar:", ["Presença Online", "Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços"], default=["Presença Online", "Pontos Fortes"], key=f"{base_key_mkt}_ca_aspects")
                    if st.form_submit_button("📡 Analisar Concorrência!"):
                        _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details, self.llm)
                if 'generated_competitor_analysis_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_competitor_analysis_stauth_v3, f"{base_key_mkt}_competitor_out", "concorrencia_ia")

            elif main_action == "mkt_selecione": st.info("Escolha uma ferramenta de marketing acima.")

       def conversar_plano_de_negocios(self, input_usuario):
           # ... (implementação como antes) ...
           return "Resposta do Plano de Negócios"
       def calcular_precos_interativo(self, input_usuario, **kwargs):
           # ... (implementação como antes) ...
           return "Resposta do Cálculo de Preços"
       def gerar_ideias_para_negocios(self, input_usuario, **kwargs):
           # ... (implementação como antes) ...
           return "Resposta do Gerador de Ideias"

    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        chat_display_key = f"chat_display_{area_chave}_v8stauth" # Chaves únicas
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia: memoria_agente_instancia.clear(); memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}_v8stauth"; chat_input_key = f"chat_input_{area_chave}_v8stauth"
        if chat_display_key not in st.session_state: st.warning("Sessão de chat não iniciada."); return
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
        prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            with st.spinner("Processando..."): resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai}); st.rerun()

    if llm_model_instance:
        agente_key = "agente_pme_v8stauth"
        if agente_key not in st.session_state: st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state[agente_key]
        URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
        st.sidebar.title("Menu PME Pro"); st.sidebar.markdown("---") # Título da Sidebar movido para cá

        opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital": "marketing_guiado", "Plano de Negócios": "plano_negocios", "Cálculo de Preços": "calculo_precos", "Gerador de Ideias": "gerador_ideias"}
        current_area_key_main = "area_selecionada_v8stauth"
        if current_area_key_main not in st.session_state: st.session_state[current_area_key_main] = "Página Inicial"

        # Inicializa display de chat para todas as seções de chat
        for _, chave_secao_init in opcoes_menu.items():
            if chave_secao_init not in ["marketing_guiado", "pagina_inicial"]: # Marketing não é chat, página inicial também não
                chat_key_init = f"chat_display_{chave_secao_init}_v8stauth"
                if chat_key_init not in st.session_state:
                    st.session_state[chat_key_init] = []

        previous_area_key_main_nav = "previous_area_selec_v8stauth_nav"
        if previous_area_key_main_nav not in st.session_state: st.session_state[previous_area_key_main_nav] = None

        area_selecionada_label = st.sidebar.radio("Navegação Principal:", options=list(opcoes_menu.keys()), key='sidebar_select_v8stauth', index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main]))

        if area_selecionada_label != st.session_state[current_area_key_main]:
            st.session_state[current_area_key_main] = area_selecionada_label
            # Limpar estados de marketing se sair da seção de marketing
            if area_selecionada_label != "Marketing Digital": # Note o nome exato do menu
                # ... (lógica de limpeza de session_state para marketing, se necessário)
                pass
            st.rerun()

        current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

        # Inicialização de chats ao navegar para seções de chat
        if current_section_key_val not in ["pagina_inicial", "marketing_guiado"]:
            if st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_main_nav):
                chat_display_key_nav = f"chat_display_{current_section_key_val}_v8stauth"
                msg_inicial_nav = ""; memoria_agente_nav = None
                if not st.session_state.get(chat_display_key_nav): # Só inicializa se o chat estiver vazio
                    if current_section_key_val == "plano_negocios": msg_inicial_nav = "Olá! Vamos elaborar seu Plano de Negócios."; memoria_agente_nav = agente.memoria_plano_negocios
                    elif current_section_key_val == "calculo_precos": msg_inicial_nav = "Pronto para calcular preços?"; memoria_agente_nav = agente.memoria_calculo_precos
                    elif current_section_key_val == "gerador_ideias": msg_inicial_nav = "Vamos gerar algumas ideias!"; memoria_agente_nav = agente.memoria_gerador_ideias
                    if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
                st.session_state[previous_area_key_main_nav] = st.session_state[current_area_key_main]

        # Renderização da seção
        if current_section_key_val == "pagina_inicial":
            st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {st.session_state.get('name', 'Usuário')}!</h1><img src='{URL_DO_SEU_LOGO}' width='150'></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p>Use o menu à esquerda para explorar as funcionalidades do Assistente PME Pro.</p></div>", unsafe_allow_html=True)
        elif current_section_key_val == "marketing_guiado":
            agente.marketing_digital_guiado()
        elif current_section_key_val == "plano_negocios":
            st.header("📝 Plano de Negócios com IA")
            exibir_chat_e_obter_input(current_section_key_val, "Descreva sua ideia ou faça perguntas sobre seu plano de negócios...", agente.conversar_plano_de_negocios)
            if st.sidebar.button("Reiniciar Plano", key="btn_reset_plano_v8stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Ok, vamos recomeçar seu Plano de Negócios.", agente.memoria_plano_negocios); st.rerun()
        elif current_section_key_val == "calculo_precos":
            st.header("💲 Cálculo de Preços Inteligente")
            # Adicionar uploader de imagem se necessário para esta seção
            exibir_chat_e_obter_input(current_section_key_val, "Descreva o produto/serviço, custos, margem desejada...", agente.calcular_precos_interativo)
            if st.sidebar.button("Reiniciar Cálculo", key="btn_reset_precos_v8stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Novo cálculo! Descreva o item.", agente.memoria_calculo_precos); st.rerun()
        elif current_section_key_val == "gerador_ideias":
            st.header("💡 Gerador de Ideias para Negócios")
            # Adicionar uploader de arquivos se necessário para esta seção
            exibir_chat_e_obter_input(current_section_key_val, "Qual seu desafio ou área de interesse para novas ideias?", agente.gerar_ideias_para_negocios)
            if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v8stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Vamos ter novas ideias! Qual o foco?", agente.memoria_gerador_ideias); st.rerun()
    else:
        st.error("Modelo de Linguagem (LLM) não pôde ser carregado. Verifique a GOOGLE_API_KEY nos Segredos do aplicativo.")

# SE O USUÁRIO NÃO ESTIVER AUTENTICADO
elif st.session_state['authentication_status'] is False:
    # A biblioteca streamlit-authenticator já mostra mensagens de erro de login.
    # st.error('Nome de usuário/senha incorretos.') # Opcional, se quiser duplicar
    pass 
elif st.session_state['authentication_status'] is None:
    # A biblioteca streamlit-authenticator já mostra o formulário de login.
    # st.info('Por favor, insira seu nome de usuário e senha para acessar o Assistente PME Pro.') # Opcional
    # Pode adicionar um logo aqui se o formulário de login estiver na área principal
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    st.image(URL_DO_SEU_LOGO_LOGIN, width=150) # Mostra o logo acima do formulário de login
    st.markdown("<h1 style='text-align: center;'>Assistente PME Pro</h1>", unsafe_allow_html=True)


# Estas linhas sempre aparecem no final da sidebar
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
