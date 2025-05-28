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

if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# A função authentication_flow_stauth chama authenticator.login() 
# que renderiza o formulário e atualiza o session_state.
# Chamamos apenas se o status ainda não for True (logado).
if not st.session_state['authentication_status']:
    authentication_flow_stauth(authenticator)


# Verifica o status da autenticação APÓS a tentativa de login (se houver)
if st.session_state['authentication_status']:
    user_name_from_session = st.session_state.get('name', 'Usuário') # Usar o nome do st.session_state
    st.sidebar.success(f"Logado como: {user_name_from_session}")
    authenticator.logout("Logout", "sidebar", key="logout_button_stauth_final")

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
        key_suffix = f"_{section_key}_mkt_obj_v7_stauth"
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
        key_suffix = f"_{section_key}_output_v7_stauth"
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

    # Adicione as outras funções _marketing_handle_... aqui, adaptando as chaves do session_state para _stauth_v3
    # Exemplo: _marketing_handle_criar_landing_page, _marketing_handle_criar_site, etc.

    class AssistentePMEPro:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None: st.error("Erro: Modelo LLM não inicializado."); st.stop()
            self.llm = llm_passed_model
            self.memoria_plano_negocios = ConversationBufferMemory(memory_key="chat_hist_plano_v7stauth", return_messages=True)
            self.memoria_calculo_precos = ConversationBufferMemory(memory_key="chat_hist_precos_v7stauth", return_messages=True)
            self.memoria_gerador_ideias = ConversationBufferMemory(memory_key="chat_hist_ideias_v7stauth", return_messages=True)

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="chat_hist_v7stauth"):
            prompt_template = ChatPromptTemplate.from_messages([ SystemMessagePromptTemplate.from_template(system_message_content), MessagesPlaceholder(variable_name=memory_key_placeholder), HumanMessagePromptTemplate.from_template("{input_usuario}")])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def marketing_digital_guiado(self):
            st.header("🚀 Marketing Digital Interativo com IA")
            st.caption("Seu copiloto para estratégias e mais!")
            st.markdown("---")
            base_key_mkt = "mkt_v7_stauth"
            marketing_files_info_for_prompt = []
            st.sidebar.subheader("📎 Arquivos de Apoio (Marketing)")
            # ... (código do file uploader como antes, usando base_key_mkt) ...

            opcoes_marketing = {"Selecione": "mkt_selecione", "Post": "mkt_post", "Campanha": "mkt_campanha", "Landing Page": "mkt_lp", "Site PME": "mkt_site", "Cliente Ideal": "mkt_cliente", "Concorrência": "mkt_concorrencia"}
            main_action_label = st.radio("Marketing Digital:", options=list(opcoes_marketing.keys()), key=f"{base_key_mkt}_radio", horizontal=True)
            main_action = opcoes_marketing[main_action_label]; st.markdown("---")
            platforms_cfg = {"Instagram": "insta", "Facebook": "fb", "X": "x", "WhatsApp": "wpp", "TikTok": "tt", "YouTube": "yt", "E-mail": "email"}

            if main_action == "mkt_post":
                st.subheader("✨ Criador de Posts")
                with st.form(f"{base_key_mkt}_post_form"):
                    # ... (formulário de post, usando _marketing_get_objective_details)
                    st.subheader("Plataformas:")
                    cols_p = st.columns(len(platforms_cfg))
                    platform_states_post = {name: cols_p[i].checkbox(name, key=f"{base_key_mkt}_post_p_{suf}") for i, (name, suf) in enumerate(platforms_cfg.items())}
                    post_details = _marketing_get_objective_details(f"{base_key_mkt}_post_details", "post")
                    if st.form_submit_button("💡 Gerar Post!"):
                        selected_plats = [name for name, checked in platform_states_post.items() if checked]
                        _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, selected_plats, self.llm)
                if 'generated_post_content_stauth_v3' in st.session_state: _marketing_display_output_options(st.session_state.generated_post_content_stauth_v3, f"{base_key_mkt}_post_out", "post_ia")

            elif main_action == "mkt_campanha":
                st.subheader("🌍 Planejador de Campanhas")
                with st.form(f"{base_key_mkt}_campaign_form"):
                    # ... (formulário de campanha, usando _marketing_get_objective_details)
                    camp_name = st.text_input("Nome da Campanha:", key=f"{base_key_mkt}_camp_name")
                    st.subheader("Plataformas:")
                    cols_c = st.columns(len(platforms_cfg))
                    platform_states_camp = {name: cols_c[i].checkbox(name, key=f"{base_key_mkt}_camp_p_{suf}") for i, (name, suf) in enumerate(platforms_cfg.items())}
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
                    # ... (Lógica para criar ativos, similar à versão anterior, mas botões de ideias fora do form)
                    pass # Implementar UI para criação de ativos aqui

            # ... (outras seções de marketing: mkt_lp, mkt_site, etc.)

            elif main_action == "mkt_selecione": st.info("Escolha uma ferramenta de marketing.")

        def conversar_plano_de_negocios(self, input_usuario):
            system_message = "Assistente PME Pro: Consultor de Plano de Negócios."
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

        def calcular_precos_interativo(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Calculadora de Preços Inteligente."
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

        def gerar_ideias_para_negocios(self, input_usuario, **kwargs):
            system_message = "Assistente PME Pro: Gerador de Ideias para Negócios."
            cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias)
            try: return cadeia.invoke({"input_usuario": input_usuario})['text']
            except Exception as e: return f"Erro: {e}"

    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        chat_display_key = f"chat_display_{area_chave}_v7stauth"
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia: memoria_agente_instancia.clear(); memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        # Limpeza de uploads específicos
        if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_v7stauth', None); st.session_state.pop(f'processed_image_id_pricing_v7stauth', None)
        elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_v7stauth', None); st.session_state.pop(f'processed_file_id_ideias_v7stauth', None)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}_v7stauth"; chat_input_key = f"chat_input_{area_chave}_v7stauth"
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
        agente_key = "agente_pme_v7stauth"
        if agente_key not in st.session_state: st.session_state[agente_key] = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state[agente_key]
        URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png"
        st.sidebar.title("Menu PME Pro"); st.sidebar.markdown("---")
        opcoes_menu = {"Página Inicial": "pagina_inicial", "Marketing Digital": "marketing_guiado", "Plano de Negócios": "plano_negocios", "Cálculo de Preços": "calculo_precos", "Gerador de Ideias": "gerador_ideias"}
        current_area_key_main = "area_selecionada_v7stauth"
        if current_area_key_main not in st.session_state: st.session_state[current_area_key_main] = "Página Inicial"
        for _, chave_secao_init in opcoes_menu.items():
            if chave_secao_init != "marketing_guiado" and f"chat_display_{chave_secao_init}_v7stauth" not in st.session_state: st.session_state[f"chat_display_{chave_secao_init}_v7stauth"] = []

        previous_area_key_main_nav = "previous_area_selec_v7stauth_nav"
        if previous_area_key_main_nav not in st.session_state: st.session_state[previous_area_key_main_nav] = None

        area_selecionada_label = st.sidebar.radio("Navegação Principal:", options=list(opcoes_menu.keys()), key='sidebar_select_v7stauth', index=list(opcoes_menu.keys()).index(st.session_state[current_area_key_main]))
        if area_selecionada_label != st.session_state[current_area_key_main]:
            st.session_state[current_area_key_main] = area_selecionada_label; st.rerun()
        current_section_key_val = opcoes_menu.get(st.session_state[current_area_key_main])

        if current_section_key_val not in ["pagina_inicial", "marketing_guiado"] and st.session_state[current_area_key_main] != st.session_state.get(previous_area_key_main_nav):
            chat_display_key_nav = f"chat_display_{current_section_key_val}_v7stauth"; msg_inicial_nav = ""; memoria_agente_nav = None
            if not st.session_state.get(chat_display_key_nav):
                if current_section_key_val == "plano_negocios": msg_inicial_nav = "Olá! Vamos elaborar seu Plano de Negócios."; memoria_agente_nav = agente.memoria_plano_negocios
                elif current_section_key_val == "calculo_precos": msg_inicial_nav = "Pronto para calcular preços?"; memoria_agente_nav = agente.memoria_calculo_precos
                elif current_section_key_val == "gerador_ideias": msg_inicial_nav = "Vamos gerar algumas ideias!"; memoria_agente_nav = agente.memoria_gerador_ideias
                if msg_inicial_nav and memoria_agente_nav: inicializar_ou_resetar_chat(current_section_key_val, msg_inicial_nav, memoria_agente_nav)
            st.session_state[previous_area_key_main_nav] = st.session_state[current_area_key_main]

        if current_section_key_val == "pagina_inicial":
            st.markdown(f"<div style='text-align: center;'><h1>🚀 Bem-vindo, {user_name_from_session}!</h1><img src='{URL_DO_SEU_LOGO}' width='150'></div>", unsafe_allow_html=True)
        elif current_section_key_val == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key_val == "plano_negocios": st.header("📝 Plano de Negócios"); exibir_chat_e_obter_input(current_section_key_val, "Sua ideia...", agente.conversar_plano_de_negocios);
        elif current_section_key_val == "calculo_precos": st.header("💲 Cálculo de Preços"); exibir_chat_e_obter_input(current_section_key_val, "Detalhes para precificação...", agente.calcular_precos_interativo)
        elif current_section_key_val == "gerador_ideias": st.header("💡 Gerador de Ideias"); exibir_chat_e_obter_input(current_section_key_val, "Seu desafio...", agente.gerar_ideias_para_negocios)
    else: st.error("Modelo de Linguagem não carregado.")

# ESTA PARTE É EXECUTADA QUANDO O USUÁRIO NÃO ESTÁ AUTENTICADO
elif st.session_state['authentication_status'] is False:
    st.error('Nome de usuário/senha incorretos.') # O widget de login do authenticator já mostra isso.
elif st.session_state['authentication_status'] is None:
    st.info('Por favor, insira seu nome de usuário e senha para acessar o Assistente PME Pro.')
    # O formulário de login já foi (ou será) renderizado por authentication_flow_stauth(authenticator)
    # se o status for None. Podemos adicionar um logo aqui se quisermos.
    URL_DO_SEU_LOGO_LOGIN = "https://i.imgur.com/7IIYxq1.png"
    st.image(URL_DO_SEU_LOGO_LOGIN, width=150)
    st.markdown("<h1 style='text-align: center;'>Assistente PME Pro</h1>", unsafe_allow_html=True)

# Estas linhas devem estar fora de qualquer bloco condicional if/else principal, 
# para que sempre apareçam, mas o conteúdo da sidebar só é populado se logado.
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
