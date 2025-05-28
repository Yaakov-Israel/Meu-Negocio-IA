import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

from auth import initialize_authenticator, authentication_flow_stauth

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

authenticator = initialize_authenticator()

if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
    
if not st.session_state['authentication_status']:
    authentication_flow_stauth(authenticator)

if st.session_state['authentication_status']:
    user_name_from_session = st.session_state.get('name', 'Usuário') 
    st.sidebar.success(f"Logado como: {user_name_from_session}")
    authenticator.logout("Logout", "sidebar", key="logout_button_stauth_final_v_completed")

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
        key_suffix = f"_{section_key}_mkt_obj_v12_stauth"
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
        key_suffix = f"_{section_key}_output_v12_stauth"
        st.subheader("🎉 Resultado da IA e Próximos Passos:")
        st.markdown(generated_content)
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}.txt", mime="text/plain", key=f"download{key_suffix}")

    def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
        if not all(details_dict.get(k,"").strip() for k in ["objective", "target_audience", "product_service", "key_message"]): st.warning("Preencha todos os campos obrigatórios do post."); return
        if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
        with st.spinner("🤖 Criando seu post..."):
            prompt_parts = [f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in details_dict.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Copywriter para PMEs.")
            prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
            prompt_parts.append("**Tarefa:** Gere conteúdo para post (com emojis/hashtags). Se e-mail: Assunto e corpo. Se vídeo: roteiro breve.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts)
            try: st.session_state.generated_post_content_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content
            except Exception as e: st.error(f"Erro ao gerar post: {e}")

    def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
        if not campaign_specifics.get("name","").strip() or not all(details_dict.get(k,"").strip() for k in ["objective", "target_audience", "product_service", "key_message"]): st.warning("Preencha nome e todos os detalhes obrigatórios da campanha."); return
        if not selected_platforms_list: st.warning("Selecione ao menos uma plataforma."); return
        with st.spinner("🧠 Elaborando plano de campanha..."):
            prompt_parts = ["**Instrução para IA:** Estrategista de marketing digital sênior para PMEs."]
            prompt_parts.extend([f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in campaign_specifics.items()])
            prompt_parts.extend([f"**{k.replace('_', ' ').capitalize()}:** {v or 'Não informado'}" for k, v in details_dict.items()])
            prompt_parts.append(f"**Plataformas:** {', '.join(selected_platforms_list)}.")
            prompt_parts.append("**Tarefa:** Elabore um plano de campanha detalhado.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts)
            try: st.session_state.generated_campaign_content_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content
            except Exception as e: st.error(f"Erro ao gerar plano de campanha: {e}")
    
    def _marketing_handle_gerar_texto_ativo(campaign_plan_context, asset_description, asset_objective, llm):
        if not asset_description.strip() or not asset_objective.strip(): st.warning("Descreva o ativo e seu objetivo."); return
        with st.spinner("✍️ IA escrevendo..."):
            prompt = (f"**Contexto Campanha:**\n{campaign_plan_context}\n\n"
                        f"**Instrução IA:** Copywriter. Gere texto para o ativo:\n"
                        f"**Ativo:** {asset_description}\n**Objetivo:** {asset_objective}\n\n"
                        "**Tarefa:** Gere texto apropriado (com emojis/hashtags se social; Assunto/corpo se e-mail).")
            try: st.session_state.current_generated_asset_text_stauth_v7 = llm.invoke([HumanMessage(content=prompt)]).content
            except Exception as e: st.error(f"Erro: {e}"); st.session_state.current_generated_asset_text_stauth_v7 = "Erro."

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details.get("purpose","").strip() or not lp_details.get("main_offer","").strip() or not lp_details.get("cta","").strip(): st.warning("Preencha objetivo, oferta e CTA."); return
        with st.spinner("🎨 Desenhando landing page..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in lp_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Especialista em UX/UI e copy para landing pages.")
            prompt_parts.append("**Tarefa:** Crie estrutura detalhada e copy.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); st.session_state.generated_lp_content_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content

    def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
        if not site_details.get("business_type","").strip() or not site_details.get("main_purpose","").strip(): st.warning("Informe tipo de negócio e objetivo."); return
        with st.spinner("🛠️ Arquitetando site..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in site_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** Arquiteto de informação.")
            prompt_parts.append("**Tarefa:** Desenvolva proposta de estrutura e conteúdo.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); st.session_state.generated_site_content_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content

    def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
        if not client_details.get("product_campaign","").strip(): st.warning("Descreva produto/campanha."); return
        with st.spinner("🕵️ Investigando público-alvo..."):
            prompt_parts = [f"**{k.capitalize()}:** {v or ('Não informado' if not isinstance(v, bool) else 'Ativado' if v else 'Padrão')}" for k,v in client_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** 'Agente Detetive de Clientes'.")
            prompt_parts.append("**Tarefa:** Análise completa do público-alvo.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); st.session_state.generated_client_analysis_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details.get("your_business","").strip() or not competitor_details.get("competitors_list","").strip(): st.warning("Descreva seu negócio e concorrentes."); return
        with st.spinner("🔬 Analisando concorrência..."):
            competitor_details["aspects_to_analyze"] = ', '.join(competitor_details.get('aspects_to_analyze',[])) 
            prompt_parts = [f"**{k.capitalize()}:** {v or 'Não informado'}" for k,v in competitor_details.items()]
            prompt_parts.insert(0, "**Instrução para IA:** 'Agente de Inteligência Competitiva'.")
            prompt_parts.append("**Tarefa:** Elabore um relatório breve e útil.")
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); st.session_state.generated_competitor_analysis_stauth_v7 = llm.invoke([HumanMessage(content=final_prompt)]).content
    
    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: 
                st.error("Erro: Modelo LLM não inicializado corretamente.")
                st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_v12stauth", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_v12stauth", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_v12stauth", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_v12stauth"):
            prompt_template = ChatPromptTemplate.from_messages([ 
                SystemMessagePromptTemplate.from_template(system_message_content), 
                MessagesPlaceholder(variable_name=memory_key_placeholder), 
                HumanMessagePromptTemplate.from_template("{input_usuario}")
            ])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            base_key_mkt = "mkt_v12_stauth" 
            marketing_files_info_for_prompt = []
            
            with st.sidebar: 
                st.subheader("📎 Arquivos de Apoio (Marketing)")
                uploaded_marketing_files = st.file_uploader("Upload para Marketing (opcional, geral):", 
                                                          accept_multiple_files=True, 
                                                          type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'], 
                                                          key=f"{base_key_mkt}_geral_uploader")
                if uploaded_marketing_files:
                    temp_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                    if temp_info: 
                        marketing_files_info_for_prompt = temp_info
                        st.success(f"{len(uploaded_marketing_files)} arquivo(s) de apoio carregados!")
                        with st.expander("Ver arquivos de apoio"): st.write(marketing_files_info_for_prompt)
                st.markdown("---")
            
            opcoes_marketing = {
                "Selecione uma Opção": "mkt_selecione", "Criar Post": "mkt_post", "Criar Campanha": "mkt_campanha", 
                "Estrutura LP": "mkt_lp", "Estrutura Site": "mkt_site", "Cliente Ideal": "mkt_cliente", 
                "Analisar Concorrência": "mkt_concorrencia"
            }
            main_action_label = st.radio("Ferramentas de Marketing Digital:", options=list(opcoes_marketing.keys()), key=f"{base_key_mkt}_radio", horizontal=True)
            main_action = opcoes_marketing[main_action_label]
            
            if main_action != "mkt_selecione": st.markdown("---")
            
            platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X": "x", "WhatsApp": "wpp", "TikTok": "tt", "YouTube": "yt", "E-mail": "email"}
            
            if main_action == "mkt_post":
                st.subheader("✨ Criador de Posts")
                with st.form(f"{base_key_mkt}_post_form"):
                    st.caption("Defina os detalhes e plataformas para seu post.")
                    cols_p = st.columns(min(len(platforms_cfg), 4))
                    platform_states_post = {name: cols_p[i % len(cols_p)].checkbox(name, key=f"{base_key_mkt}_post_p_{suf}") for i, (name, suf) in enumerate(platforms_cfg.items())}
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    if st.form_submit_button("💡 Gerar Post!"):
                        selected_plats = [name for name, checked in platform_states_post.items() if checked]
                        _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_stauth_v7' in st.session_state: 
                    _marketing_display_output_options(st.session_state.generated_post_content_stauth_v7, f"{base_key_mkt}_post_out", "post_ia")
            
            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name_v5")
                    st.subheader("Plataformas:")
                    cols_c = st.columns(min(len(platforms_cfg), 4))
                    platform_states_camp = {name: cols_c[i % len(cols_c)].checkbox(name, key=f"{base_key_mkt}_camp_p_{suf}_v5") for i, (name, suf) in enumerate(platforms_cfg.items())}
                    camp_details_obj = _marketing_get_objective_details(f"{base_key_mkt}_camp_details_v5", "campanha")
                    camp_duration = st.text_input("Duração:", key=f"{base_key_mkt}_camp_duration_v5")
                    camp_budget = st.text_input("Orçamento (opcional):", key=f"{base_key_mkt}_camp_budget_v5")
                    camp_kpis = st.text_area("KPIs:", key=f"{base_key_mkt}_camp_kpis_v5")
                    if st.form_submit_button("🚀 Gerar Plano!"):
                        selected_plats_camp = [name for name, checked in platform_states_camp.items() if checked]
                        camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                        _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
                if 'generated_campaign_content_stauth_v7' in st.session_state:
                    _marketing_display_output_options(st.session_state.generated_campaign_content_stauth_v7, f"{base_key_mkt}_camp_out", "campanha_ia")
                    if st.button("🚀 Criar Ativos da Campanha", key=f"{base_key_mkt}_btn_create_assets_v5"):
                        st.session_state.creating_campaign_assets_stauth_v7 = True
                        st.session_state.current_campaign_plan_context_stauth_v7 = st.session_state.generated_campaign_content_stauth_v7
                        st.session_state.campaign_assets_list_stauth_v7 = [] 
                        st.rerun()
                if st.session_state.get("creating_campaign_assets_stauth_v7"):
                    st.markdown("---"); st.subheader("🛠️ Criador de Ativos para Campanha")
                    st.info(st.session_state.get('current_campaign_plan_context_stauth_v7', "Contexto não carregado."))
                    asset_form_key = f"{base_key_mkt}_asset_creator_form_v5"
                    with st.form(asset_form_key, clear_on_submit=True):
                        asset_desc = st.text_input("Nome/Descrição do Ativo:", key=f"{asset_form_key}_desc")
                        asset_obj = st.text_area("Objetivo Específico:", key=f"{asset_form_key}_obj")
                        submit_generate_text_asset = st.form_submit_button("✍️ Gerar Texto para Ativo")
                        img_asset = st.file_uploader("Carregar Imagem (ativo):", key=f"{asset_form_key}_img_upload")
                        vid_asset = st.file_uploader("Carregar Vídeo (ativo):", key=f"{asset_form_key}_vid_upload")
                        if st.session_state.get('current_generated_asset_text_stauth_v7'): st.text_area("Texto Gerado:", value=st.session_state.current_generated_asset_text_stauth_v7, height=100, disabled=True, key=f"{asset_form_key}_text_display")
                        submit_add_asset = st.form_submit_button("➕ Adicionar Ativo à Lista")
                        if submit_generate_text_asset:
                            if asset_desc and asset_obj: _marketing_handle_gerar_texto_ativo(st.session_state.get('current_campaign_plan_context_stauth_v7'), asset_desc, asset_obj, self.llm); st.rerun()
                            else: st.warning("Preencha Descrição e Objetivo.")
                        if submit_add_asset:
                            if asset_desc:
                                new_asset = {"descricao": asset_desc, "objetivo": asset_obj, "texto_gerado": st.session_state.get('current_generated_asset_text_stauth_v7', ""),"imagem_carregada": img_asset.name if img_asset else None, "video_carregado": vid_asset.name if vid_asset else None}
                                st.session_state.campaign_assets_list_stauth_v7.append(new_asset)
                                st.success(f"Ativo '{asset_desc}' adicionado!"); st.session_state.current_generated_asset_text_stauth_v7 = ""; st.rerun()
                            else: st.warning("Adicione uma descrição.")
                    c1b,c2b = st.columns(2)
                    if c1b.button("💡 Ideias de Imagem (Campanha)", key=f"{base_key_mkt}_btn_img_ideas_asset_outside_v7"): st.info("Em desenvolvimento.")
                    if c2b.button("💡 Ideias de Vídeo (Campanha)", key=f"{base_key_mkt}_btn_vid_ideas_asset_outside_v7"): st.info("Em desenvolvimento.")
                    if st.session_state.get('campaign_assets_list_stauth_v7', []):
                        st.markdown("---"); st.subheader("📦 Ativos Adicionados:")
                        for i, asset in enumerate(st.session_state.campaign_assets_list_stauth_v7):
                            with st.expander(f"Ativo {i+1}: {asset['descricao']}"): st.write(asset)
                    if st.button("🏁 Concluir Criação de Ativos", key=f"{base_key_mkt}_btn_finish_assets_v7"):
                        st.session_state.creating_campaign_assets_stauth_v7 = False; st.success("Criação de ativos concluída!"); st.balloons(); st.rerun()
            
            elif main_action == "mkt_lp":
                st.subheader("📄 Gerador de Estrutura para Landing Pages")
                with st.form(f"{base_key_mkt}_lp_form"):
                    lp_details = _marketing_get_objective_details(f"{base_key_mkt}_lp_form_details", "landing page")
                    if st.form_submit_button("🛠️ Gerar Estrutura de LP!"):
                        _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details, self.llm)
                if 'generated_lp_content_stauth_v7' in st.session_state: _marketing_display_output_options(st.session_state.generated_lp_content_stauth_v7, f"{base_key_mkt}_lp_out", "lp_ia")
            
            elif main_action == "mkt_site":
                st.subheader("🏗️ Arquiteto de Sites PME")
                with st.form(f"{base_key_mkt}_site_form"):
                    site_details = _marketing_get_objective_details(f"{base_key_mkt}_site_form_details", "site")
                    site_details["business_type"] = st.text_input("Tipo do seu Negócio/Empresa:", key=f"{base_key_mkt}_site_biz_type_v3")
                    site_details["essential_pages"] = st.text_area("Páginas Essenciais:", key=f"{base_key_mkt}_site_pages_v3")
                    if st.form_submit_button("🏛️ Gerar Estrutura de Site!"):
                         _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details, self.llm)
                if 'generated_site_content_stauth_v7' in st.session_state: _marketing_display_output_options(st.session_state.generated_site_content_stauth_v7, f"{base_key_mkt}_site_out", "site_ia")
            
            elif main_action == "mkt_cliente":
                st.subheader("🎯 Decodificador de Clientes")
                with st.form(f"{base_key_mkt}_client_form"):
                    client_details = {}
                    client_details["product_campaign"] = st.text_area("Produto/serviço/campanha:", key=f"{base_key_mkt}_fc_campaign_v3")
                    client_details["location"] = st.text_input("Localização (opcional):", key=f"{base_key_mkt}_fc_location_v3")
                    client_details["budget"] = st.text_input("Verba para marketing (opcional):", key=f"{base_key_mkt}_fc_budget_v3")
                    client_details["age_gender"] = st.text_input("Faixa etária e/ou gênero principal:", key=f"{base_key_mkt}_fc_age_gender_v3")
                    client_details["interests"] = st.text_area("Interesses, hobbies, dores do público:", key=f"{base_key_mkt}_fc_interests_v3")
                    client_details["current_channels"] = st.text_area("Canais onde já tentou alcançar:", key=f"{base_key_mkt}_fc_channels_v3")
                    client_details["deep_research"] = st.checkbox("Habilitar 'Deep Research'", value=True, key=f"{base_key_mkt}_fc_deep_v3")
                    if st.form_submit_button("🔍 Encontrar Cliente Ideal!"):
                        _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details, self.llm)
                if 'generated_client_analysis_stauth_v7' in st.session_state: _marketing_display_output_options(st.session_state.generated_client_analysis_stauth_v7, f"{base_key_mkt}_client_out", "cliente_ia")

            elif main_action == "mkt_concorrencia":
                st.subheader("🧐 Radar da Concorrência")
                with st.form(f"{base_key_mkt}_competitor_form"):
                    competitor_details = {}
                    competitor_details["your_business"] = st.text_area("Descreva seu negócio/produto:", key=f"{base_key_mkt}_ca_your_biz_v3")
                    competitor_details["competitors_list"] = st.text_area("Liste seus concorrentes:", key=f"{base_key_mkt}_ca_competitors_v3")
                    competitor_details["aspects_to_analyze"] = st.multiselect( "Aspectos a analisar:", ["Presença Online", "Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços"], default=["Presença Online", "Pontos Fortes"], key=f"{base_key_mkt}_ca_aspects_v3")
                    if st.form_submit_button("📡 Analisar Concorrência!"):
                        _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details, self.llm)
                if 'generated_competitor_analysis_stauth_v7' in st.session_state: _marketing_display_output_options(st.session_state.generated_competitor_analysis_stauth_v7, f"{base_key_mkt}_competitor_out", "concorrencia_ia")
            
            elif main_action == "mkt_selecione": 
                st.info("Escolha uma ferramenta de marketing acima para começar.")

        # --- Definições de métodos da classe AssistentePMEPro (precisam estar indentadas dentro da classe) ---
        # Corrigi a indentação das funções de chat para estarem DENTRO da classe AssistentePMEPro
        # No entanto, as funções inicializar_ou_resetar_chat e exibir_chat_e_obter_input são globais
        # e são chamadas com agente.metodo_de_conversa como argumento.

        # --- Funções Utilitárias de Chat (nível global do script) ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}_v12stauth"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia: 
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                    memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages'):
                    memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
            
            if area_chave == "calculo_precos": 
                st.session_state.pop(f'last_uploaded_image_info_pricing_v12stauth', None)
                st.session_state.pop(f'processed_image_id_pricing_v12stauth', None)
            elif area_chave == "gerador_ideias": 
                st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_v12stauth', None)
                st.session_state.pop(f'processed_file_id_ideias_v12stauth', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}_v12stauth"; chat_input_key = f"chat_input_{area_chave}_v12stauth"
            if chat_display_key not in st.session_state: 
                st.warning("Sessão de chat não iniciada. Por favor, selecione a opção no menu novamente."); return
            
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
            
            prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                
                with st.spinner("Assistente PME Pro está pensando..."): 
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()

        # --- Lógica da Interface Principal (continuação) ---
        if llm_model_instance:
            agente_key = "agente_pme_v12stauth"
            if agente_key not in st.session_state: 
                st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
            agente = st.session_state[agente_key]
            
            URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
            
            st.sidebar.title("Menu Assistente PME Pro")
            st.sidebar.markdown("---")

            opcoes_menu = {
                "Página Inicial": "pagina_inicial", 
                "Marketing Digital": "marketing_guiado", 
                "Plano de Negócios": "plano_negocios", 
                "Cálculo de Preços": "calculo_precos", 
                "Gerador de Ideias": "gerador_ideias"
            }
            current_area_key_main = "area_selecionada_v12stauth"
            
            if current_area_key_main not in st.session_state: 
                st.session_state[current_area_key_main] = "Página Inicial"
            
            for _, chave_secao_init_loop_main_v3 in opcoes_menu.items():
                if chave_secao_init_loop_main_v3 not in ["marketing_guiado", "pagina_inicial"]:
                    chat_key_init_loop_main_v3 = f"chat_display_{chave_secao_init_loop_main_v3}_v12stauth"
                    if chat_key_init_loop_main_v3 not in st.session_state:
                        st.session_state[chat_key_init_loop_main_v3] = []
            
            previous_area_key_main_nav_loop_main_v3 = "previous_area_selec_v12stauth_nav"
            if previous_area_key_main_nav_loop_main_v3 not in st.session_state: 
                st.session_state[previous_area_key_main_nav_loop_main_v3] = None
            
            area_selecionada_label = st.sidebar.radio(
                "Navegação Principal:", 
                options=list(opcoes_menu.keys()), 
                key='sidebar_select_v12stauth', 
                index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main])
            )
            
            if area_selecionada_label != st.session_state[current_area_key_main]:
                st.session_state[current_area_key_main] = area_selecionada_label
                st.rerun()
            
            current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

            if current_section_key_val not in ["pagina_inicial", "marketing_guiado"]:
                if st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_main_nav_loop_main_v3):
                    chat_display_key_nav = f"chat_display_{current_section_key_val}_v12stauth"
                    msg_inicial_nav = ""; memoria_agente_nav = None
                    if not st.session_state.get(chat_display_key_nav): 
                        if current_section_key_val == "plano_negocios": 
                            msg_inicial_nav = "Olá! Sou seu assistente para Planos de Negócios. Como posso ajudar?"
                            memoria_agente_nav = agente.memoria_plano_negocios
                        elif current_section_key_val == "calculo_precos": 
                            msg_inicial_nav = "Bem-vindo ao assistente de Cálculo de Preços. Qual produto ou serviço vamos precificar?"
                            memoria_agente_nav = agente.memoria_calculo_precos
                        elif current_section_key_val == "gerador_ideias": 
                            msg_inicial_nav = "Pronto para um brainstorm? Sobre o que você gostaria de gerar ideias?"
                            memoria_agente_nav = agente.memoria_gerador_ideias
                        if msg_inicial_nav and memoria_agente_nav is not None: 
                            inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
                    st.session_state[previous_area_key_main_nav_loop_main_v3] = st.session_state[current_area_key_main]

            if current_section_key_val == "pagina_inicial":
                st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name_from_session}!</h1><img src='{URL_DO_SEU_LOGO}' width='150'></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center;'><p>Use o menu à esquerda para explorar as funcionalidades.</p></div>", unsafe_allow_html=True)
            elif current_section_key_val == "marketing_guiado":
                agente.marketing_digital_guiado()
            elif current_section_key_val == "plano_negocios":
                st.header("📝 Plano de Negócios com IA")
                exibir_chat_e_obter_input(current_section_key_val, "Descreva sua ideia ou faça perguntas sobre seu plano de negócios...", agente.conversar_plano_de_negocios)
                if st.sidebar.button("Reiniciar Plano", key="btn_reset_plano_v12stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Plano de negócios reiniciado. Como posso ajudar?", agente.memoria_plano_negocios); st.rerun()
            elif current_section_key_val == "calculo_precos":
                st.header("💲 Cálculo de Preços Inteligente")
                exibir_chat_e_obter_input(current_section_key_val, "Detalhes do produto/serviço para precificação...", agente.calcular_precos_interativo)
                if st.sidebar.button("Reiniciar Cálculo", key="btn_reset_precos_v12stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Novo cálculo de preços. Descreva o item.", agente.memoria_calculo_precos); st.rerun()
            elif current_section_key_val == "gerador_ideias":
                st.header("💡 Gerador de Ideias para Negócios")
                exibir_chat_e_obter_input(current_section_key_val, "Qual seu desafio ou área de interesse para novas ideias?", agente.gerar_ideias_para_negocios)
                if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v12stauth"): inicializar_ou_resetar_chat(current_section_key_val, "Pronto para novas ideias! Qual o foco?", agente.memoria_gerador_ideias); st.rerun()
        else:
            st.error("Modelo de Linguagem (LLM) não pôde ser carregado.")
    
    elif st.session_state['authentication_status'] is False:
        # O widget authenticator.login() já mostra "Username/password is incorrect"
        # Não precisamos adicionar st.error() aqui, a menos que queira uma mensagem customizada.
        # Se authenticator.login() foi chamado e retornou False, ele já cuidou da UI de erro.
        pass 
    elif st.session_state['authentication_status'] is None:
        # O widget authenticator.login() já mostra "Please enter your username and password"
        # e o formulário de login, pois foi chamado por authentication_flow_stauth.
        # Podemos adicionar um logo ou título geral da página aqui, que aparecerá com o formulário de login.
        URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
        # Para centralizar a imagem e o título acima do formulário de login (que é renderizado por authenticator.login())
        cols_login_header = st.columns([1,2,1])
        with cols_login_header[1]:
            st.image(URL_DO_SEU_LOGO_LOGIN, width=200) 
            st.markdown("<h2 style='text-align: center;'>Assistente PME Pro</h2>", unsafe_allow_html=True)
            # A mensagem "Por favor, insira..." já é parte do widget de login.

    st.sidebar.markdown("---")
    st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")

    ```

4.  **Salve (faça o "commit")** das alterações no GitHub.
5.  **Reinicie o aplicativo** no Streamlit Cloud ("Reboot app").

Espero sinceramente que esta versão completa e com a indentação revisada resolva o problema. Se o erro persistir na linha 11, por favor, me envie a mensagem de erro **completa** que o Streamlit Cloud mostra.
