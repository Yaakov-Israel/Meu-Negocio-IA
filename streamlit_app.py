import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

# Importa as funções do nosso auth.py
from auth import initialize_authenticator, authentication_flow_stauth

st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# Inicializa o autenticador
authenticator = initialize_authenticator()

# Inicializa as variáveis de estado da sessão se não existirem
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# Chama a função que renderiza o formulário de login e atualiza o estado da sessão
# Esta função precisa ser chamada em cada execução para que o formulário apareça se necessário
# e para que o estado da sessão seja atualizado.
authentication_flow_stauth(authenticator) # Esta função agora só atualiza o session_state

# Verifica o estado da autenticação
if st.session_state.get('authentication_status') is True:
    user_name_from_session = st.session_state.get('name', 'Usuário') 
    st.sidebar.success(f"Logado como: {user_name_from_session}")
    authenticator.logout("Logout", "sidebar", key="logout_button_v_final") # Botão de logout

    # Aviso sobre cookie_key (se for fraca ou placeholder)
    cookie_config = st.secrets.get("cookie", {}).to_dict()
    cookie_key_check = cookie_config.get("key")
    placeholder_cookie_keys = [
        "some_signature_key", "NovaChaveSecretaSuperForteParaAuthenticatorV2", 
        "COLOQUE_AQUI_SUA_NOVA_CHAVE_SECRETA_FORTE_E_UNICA",
        "Chaim5778ToViN5728erobmaloRU189154", "wR#sVn8gP!zY2qXmK7@cJ3*bL1$fH9",
        "Yi18#MAP246@YSZcM12J88*bl$999H2" # Adicionando a sua chave atual para o aviso
    ]
    if cookie_key_check in placeholder_cookie_keys:
        st.sidebar.warning("Aviso: cookie.key é um placeholder. Para produção, use uma chave ÚNICA e FORTE!", icon="⚠️")

    # --- Carregar API Key e Configurar Modelo (SOMENTE SE AUTENTICADO) ---
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
            # st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!") # Já tem o "Logado como"
        except Exception as e:
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
            st.stop()

    # --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL ---
    # (Seu código de _marketing_get_objective_details, etc. permanece aqui, como na sua versão funcional)
    def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
        st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
        details = {}
        key_suffix = "_v18_assets_auth" # Adicionando sufixo para unicidade
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
        key_suffix = "_v18_assets_auth"
        st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}_new.txt", mime="text/plain", key=f"download_{section_key}_new{key_suffix}")
        # Removidos botões simulados para simplificar
        # cols_actions = st.columns(2)
        # with cols_actions[0]:
        #     if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn_new{key_suffix}"): st.success("Conteúdo pronto para ser copiado!"); st.caption("Adapte para cada plataforma.")
        # with cols_actions[1]:
        #     if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn_new{key_suffix}"): st.info("Agendamento simulado. Use ferramentas dedicadas.")

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
                st.session_state.generated_campaign_content_new = ai_response.content # Usar chave consistente
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
                st.session_state.current_generated_asset_text = ai_response.content # Usar chave consistente
            except Exception as e: st.error(f"Erro ao gerar texto do ativo: {e}"); st.session_state.current_generated_asset_text = "Erro."

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details["purpose"] or not str(lp_details["purpose"]).strip() or not lp_details["main_offer"] or not str(lp_details["main_offer"]).strip() or not lp_details["cta"] or not str(lp_details["cta"]).strip(): st.warning("Preencha objetivo, oferta e CTA da landing page."); return
        with st.spinner("🎨 Desenhando estrutura da landing page..."):
            prompt_parts = ["**Instrução para IA:** Especialista em UX/UI e copywriting para landing pages.", f"**Objetivo:** {lp_details['purpose']}", f"**Público-Alvo:** {lp_details.get('target_audience','').strip() or 'Não informado'}", f"**Oferta Principal:** {lp_details['main_offer']}", f"**Benefícios:** {lp_details.get('key_benefits','').strip() or 'Não informados'}", f"**CTA:** {lp_details['cta']}", f"**Preferências Visuais:** {lp_details.get('visual_prefs','').strip() or 'Não informadas'}", "**Tarefa:** Crie estrutura detalhada e copy..."]
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
            prompt_parts = ["**Instrução para IA:** 'Agente Detetive de Clientes'.", f"**Produto/Campanha:** {client_details['product_campaign']}", f"**Localização:** {client_details.get('location','').strip() or 'Não informada'}", f"**Verba:** {client_details.get('budget','').strip() or 'Não informada'}", f"**Faixa Etária/Gênero:** {client_details.get('age_gender','').strip() or 'Não informados'}", f"**Interesses:** {client_details.get('interests','').strip() or 'Não informados'}", f"**Canais:** {client_details.get('current_channels','').strip() or 'Não informados'}", f"**Deep Research:** {'Ativado' if client_details['deep_research'] else 'Padrão'}", "**Tarefa:** Análise completa do público-alvo..."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_client_analysis_new = ai_response.content

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details["your_business"] or not str(competitor_details["your_business"]).strip() or not competitor_details["competitors_list"] or not str(competitor_details["competitors_list"]).strip(): st.warning("Descreva seu negócio e liste concorrentes."); return
        with st.spinner("🔬 Analisando a concorrência..."):
            prompt_parts = ["**Instrução para IA:** 'Agente de Inteligência Competitiva'.", f"**Negócio do Usuário:** {competitor_details['your_business']}", f"**Concorrentes:** {competitor_details['competitors_list']}", f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}", "**Tarefa:** Elabore um relatório breve e útil..."]
            if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
            final_prompt = "\n\n".join(prompt_parts); ai_response = llm.invoke([HumanMessage(content=final_prompt)]); st.session_state.generated_competitor_analysis_new = ai_response.content
    
    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: 
                st.error("Erro: Modelo LLM não inicializado corretamente.")
                st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_v_app", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_v_app", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_v_app", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_v_app"):
            prompt_template = ChatPromptTemplate.from_messages([ 
                SystemMessagePromptTemplate.from_template(system_message_content), 
                MessagesPlaceholder(variable_name=memory_key_placeholder), 
                HumanMessagePromptTemplate.from_template("{input_usuario}")
            ])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            base_key_mkt = "mkt_v_app" 
            marketing_files_info_for_prompt = []
            
            with st.sidebar: 
                st.subheader("📎 Apoio ao Marketing")
                uploaded_marketing_files = st.file_uploader("Upload para Marketing (opcional):", 
                                                          accept_multiple_files=True, 
                                                          type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf'], 
                                                          key=f"{base_key_mkt}_geral_uploader")
                if uploaded_marketing_files:
                    temp_info = [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_marketing_files]
                    if temp_info: 
                        marketing_files_info_for_prompt = temp_info
                        st.success(f"{len(uploaded_marketing_files)} arquivo(s) carregados!")
                        with st.expander("Ver arquivos"): st.write(marketing_files_info_for_prompt)
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
                    st.caption("Detalhes para seu post.")
                    cols_p = st.columns(min(len(platforms_cfg), 3))
                    platform_states_post = {name: cols_p[i % len(cols_p)].checkbox(name, key=f"{base_key_mkt}_post_p_{suf}") for i, (name, suf) in enumerate(platforms_cfg.items())}
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    if st.form_submit_button("💡 Gerar Post!"):
                        selected_plats = [name for name, checked in platform_states_post.items() if checked]
                        _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_new' in st.session_state: 
                    _marketing_display_output_options(st.session_state.generated_post_content_new, f"{base_key_mkt}_post_out", "post_ia")
            
            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name")
                    st.subheader("Plataformas:")
                    cols_c = st.columns(min(len(platforms_cfg),3))
                    platform_states_camp = {name: cols_c[i % len(cols_c)].checkbox(name, key=f"{base_key_mkt}_camp_p_{suf}") for i, (name, suf) in enumerate(platforms_cfg.items())}
                    camp_details_obj = _marketing_get_objective_details(f"{base_key_mkt}_camp_details", "campanha")
                    camp_duration = st.text_input("Duração:", key=f"{base_key_mkt}_camp_duration")
                    camp_budget = st.text_input("Orçamento (opcional):", key=f"{base_key_mkt}_camp_budget")
                    camp_kpis = st.text_area("KPIs:", key=f"{base_key_mkt}_camp_kpis")
                    if st.form_submit_button("🚀 Gerar Plano!"):
                        selected_plats_camp = [name for name, checked in platform_states_camp.items() if checked]
                        camp_specifics = {"name": camp_name, "duration": camp_duration, "budget": camp_budget, "kpis": camp_kpis}
                        _marketing_handle_criar_campanha(marketing_files_info_for_prompt, camp_details_obj, camp_specifics, selected_plats_camp, self.llm)
                if 'generated_campaign_content_new' in st.session_state:
                    _marketing_display_output_options(st.session_state.generated_campaign_content_new, f"{base_key_mkt}_camp_out", "campanha_ia")
                    # Lógica para criar ativos da campanha (se necessário, mova para fora do form)
                    # if st.button("🚀 Criar Ativos da Campanha", key=f"{base_key_mkt}_btn_create_assets"):
                    #    ... (lógica de criação de ativos) ...
            
            # Adicione os outros elif para mkt_lp, mkt_site, etc. aqui, seguindo o padrão
            # de usar st.form e _marketing_get_objective_details ou campos específicos.

            elif main_action == "mkt_selecione": 
                st.info("Escolha uma ferramenta de marketing.")

        def conversar_plano_de_negocios(self, input_usuario):
            system_message = "Assistente PME Pro: Consultor de Plano de Negócios."
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro no Plano de Negócios: {e}"

        def calcular_precos_interativo(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Calculadora de Preços."
            if kwargs.get('descricao_imagem_contexto'):
                system_message += f" Contexto da imagem: {kwargs['descricao_imagem_contexto']}"
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro no Cálculo de Preços: {e}"

        def gerar_ideias_para_negocios(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Gerador de Ideias."
            if kwargs.get('contexto_arquivos'):
                system_message += f" Contexto dos arquivos: {kwargs['contexto_arquivos']}"
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro na Geração de Ideias: {e}"

    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        chat_display_key = f"chat_display_{area_chave}_v_app"
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia: 
            memoria_agente_instancia.clear()
            memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_v_app', None)
        elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_v_app', None)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}_v_app"; chat_input_key = f"chat_input_{area_chave}_v_app"
        if chat_display_key not in st.session_state: st.session_state[chat_display_key] = []
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
        prompt_usuario = st.chat_input(prompt_placeholder, key=chat_input_key)
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            with st.spinner("Processando..."): resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
            st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai}); st.rerun()

    if llm_model_instance:
        agente_key = "agente_pme_v_app"
        if agente_key not in st.session_state: 
            st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state[agente_key]
        URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
        st.sidebar.title("Menu Assistente PME Pro")
        st.sidebar.markdown("---")
        opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital": "marketing_guiado", "Plano de Negócios": "plano_negocios", "Cálculo de Preços": "calculo_precos", "Gerador de Ideias": "gerador_ideias"}
        current_area_key_main = "area_selecionada_v_app"
        if current_area_key_main not in st.session_state: 
            st.session_state[current_area_key_main] = "Página Inicial"
        for _, chave_secao_init in opcoes_menu.items():
            if chave_secao_init not in ["marketing_guiado", "pagina_inicial"]:
                chat_key_init = f"chat_display_{chave_secao_init}_v_app"
                if chat_key_init not in st.session_state: st.session_state[chat_key_init] = []
        
        previous_area_key_nav = "previous_area_selec_v_app_nav"
        if previous_area_key_nav not in st.session_state: st.session_state[previous_area_key_nav] = None
        
        area_selecionada_label = st.sidebar.radio("Navegação Principal:", options=list(opcoes_menu.keys()), key='sidebar_select_v_app', index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main]))
        if area_selecionada_label != st.session_state[current_area_key_main]:
            st.session_state[current_area_key_main] = area_selecionada_label; st.rerun()
        current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

        if current_section_key_val not in ["pagina_inicial", "marketing_guiado"]:
            if st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_nav):
                chat_display_key_nav = f"chat_display_{current_section_key_val}_v_app"
                msg_inicial_nav = ""; memoria_agente_nav = None
                if not st.session_state.get(chat_display_key_nav): 
                    if current_section_key_val == "plano_negocios": msg_inicial_nav = "Assistente de Plano de Negócios pronto!"; memoria_agente_nav = agente.memoria_plano_negocios
                    elif current_section_key_val == "calculo_precos": msg_inicial_nav = "Assistente de Cálculo de Preços pronto!"; memoria_agente_nav = agente.memoria_calculo_precos
                    elif current_section_key_val == "gerador_ideias": msg_inicial_nav = "Assistente Gerador de Ideias pronto!"; memoria_agente_nav = agente.memoria_gerador_ideias
                    if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
                st.session_state[previous_area_key_nav] = st.session_state[current_area_key_main]

        if current_section_key_val == "pagina_inicial":
            st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name_from_session}!</h1><img src='{URL_DO_SEU_LOGO}' width='150'></div>", unsafe_allow_html=True)
        elif current_section_key_val == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key_val == "plano_negocios": st.header("📝 Plano de Negócios"); exibir_chat_e_obter_input(current_section_key_val, "Ideia ou perguntas...", agente.conversar_plano_de_negocios)
        elif current_section_key_val == "calculo_precos": st.header("💲 Cálculo de Preços"); exibir_chat_e_obter_input(current_section_key_val, "Detalhes do produto...", agente.calcular_precos_interativo)
        elif current_section_key_val == "gerador_ideias": st.header("💡 Gerador de Ideias"); exibir_chat_e_obter_input(current_section_key_val, "Seu desafio...", agente.gerar_ideias_para_negocios)
    else:
        if st.session_state.get('authentication_status'): # Somente mostra erro do LLM se estiver autenticado
            st.error("Modelo de Linguagem (LLM) não pôde ser carregado.")

elif st.session_state.get('authentication_status') is False:
    # Mensagem de erro de login já é tratada pelo widget do streamlit-authenticator
    # st.error('Nome de usuário ou senha incorretos.') # Opcional, se quiser duplicar
    pass 
elif st.session_state.get('authentication_status') is None:
    # O formulário de login é renderizado pela chamada a authentication_flow_stauth(authenticator)
    # Podemos adicionar um logo ou título geral aqui se quisermos
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    cols_login_header = st.columns([1,1,1]) # 3 colunas para melhor centralização
    with cols_login_header[1]: 
        if URL_DO_SEU_LOGO_LOGIN:
            st.image(URL_DO_SEU_LOGO_LOGIN, width=200) 
    st.markdown("<h2 style='text-align: center;'>Assistente PME Pro</h2>", unsafe_allow_html=True)
    # A mensagem "Please enter username/password" já é mostrada pelo widget de login.

# Estas linhas sempre aparecem no final da sidebar, independente do status de login
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
