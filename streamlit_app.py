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

# --- NOVAS FUNÇÕES AUXILIARES PARA MARKETING DIGITAL INTERATIVO ---
def _marketing_display_social_media_options(section_key_prefix: str):
    st.subheader(" Plataformas Desejadas:")
    platforms_config = {
        "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x",
        "WhatsApp": "wpp", "TikTok": "tt", "Kwai": "kwai",
        "YouTube (descrição/roteiro)": "yt",
        "E-mail Marketing (lista própria)": "email_own",
        "E-mail Marketing (Campanha Google Ads)": "email_google"
    }
    
    key_select_all = f"{section_key_prefix}_marketing_select_all_v5" # Chave única e versionada
    # Este 'select_all_checkbox_value' refletirá o estado submetido do checkbox "Selecionar Todos"
    # APÓS a submissão do formulário. Durante a renderização inicial ou antes da submissão,
    # ele é apenas um widget sendo definido.
    select_all_checkbox_value = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all)

    cols = st.columns(2)
    # Este dicionário guardará as variáveis dos checkboxes individuais.
    # Após a submissão, elas conterão os valores True/False submetidos.
    platform_checkbox_widgets = {} 
    any_email_platform_potentially_selected = False

    for i, (platform_name, platform_suffix) in enumerate(platforms_config.items()):
        col_index = i % 2
        platform_key = f"{section_key_prefix}_marketing_platform_{platform_suffix}_v5" # Chave única e versionada
        
        # O valor inicial para renderização: se "Select All" está marcado AGORA, mostre marcado.
        # Senão, use o estado persistido do checkbox individual (ou False se não existir).
        # Streamlit lida com a persistência do estado do widget através da sua chave.
        initial_display_value = True if select_all_checkbox_value else st.session_state.get(platform_key, False)
        if select_all_checkbox_value: # Garante que se "select all" for marcado, todos apareçam marcados nesta renderização
            initial_display_value = True

        with cols[col_index]:
            # A variável python 'is_checked' receberá o valor do checkbox após a submissão do form.
            is_checked = st.checkbox(
                platform_name,
                value=initial_display_value, # Define como o checkbox aparece nesta renderização
                key=platform_key
            )
            platform_checkbox_widgets[platform_name] = is_checked # Armazena a variável do widget
            if "E-mail Marketing" in platform_name and is_checked:
                 any_email_platform_potentially_selected = True
    
    if select_all_checkbox_value:
        any_email_platform_potentially_selected = True # Se "Selecionar Tudo" está marcado, implica que emails também estão.

    if any_email_platform_potentially_selected:
        st.caption("💡 Para e-mail marketing, a IA ajudará na criação do texto...")

    # Retorna a variável do checkbox "Selecionar Todas" e o dicionário das variáveis dos checkboxes individuais.
    # Os valores corretos (submetidos) estarão nessas variáveis APÓS o st.form_submit_button ser processado.
    return select_all_checkbox_value, platform_checkbox_widgets


def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    details["objective"] = st.text_area(
        f"Qual o principal objetivo com est(e/a) {type_of_creation}? (Ex: Aumentar vendas, gerar leads, divulgar evento, construir marca)",
        key=f"{section_key}_obj_new"
    )
    details["target_audience"] = st.text_input("Quem você quer alcançar? (Descreva seu público-alvo)", key=f"{section_key}_audience_new")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product_new")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message_new")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial ou diferente da concorrência (USP)?", key=f"{section_key}_usp_new")
    details["style_tone"] = st.selectbox(
        "Qual o tom/estilo da comunicação?",
        ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"),
        key=f"{section_key}_tone_new"
    )
    details["extra_info"] = st.text_area("Alguma informação adicional, promoção específica, ou call-to-action (CTA) principal que devemos incluir?", key=f"{section_key}_extra_new")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)

    st.download_button(
        label="📥 Baixar Conteúdo Gerado",
        data=generated_content.encode('utf-8'),
        file_name=f"{file_name_prefix}_{section_key}_new.txt",
        mime="text/plain",
        key=f"download_{section_key}_new"
    )
    cols_actions = st.columns(2)
    with cols_actions[0]:
        if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn_new"):
            st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
            st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
    with cols_actions[1]:
        if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn_new"):
            st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

# --- HANDLER FUNCTIONS FOR EACH MARKETING ACTION ---
# (Estes handlers agora recebem 'llm' e operam com os dados do formulário)

def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    if not selected_platforms_list: # Checagem movida para o handler principal
        st.warning("Por favor, selecione pelo menos uma plataforma.")
        return
    if not details_dict["objective"]:
        st.warning("Por favor, descreva o objetivo do post.")
        return

    with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em copywriting e marketing digital criando um post para pequenas empresas.",
            f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
            f"**Objetivo do Post:** {details_dict['objective']}",
            f"**Público-Alvo:** {details_dict['target_audience']}",
            f"**Produto/Serviço Promovido:** {details_dict['product_service']}",
            f"**Mensagem Chave:** {details_dict['key_message']}",
            f"**Diferencial (USP):** {details_dict['usp']}",
            f"**Tom/Estilo:** {details_dict['style_tone']}",
            f"**Informações Adicionais/CTA:** {details_dict['extra_info']}",
            "**Tarefa:**",
            "1. Gere o conteúdo do post. Se múltiplas plataformas foram selecionadas, forneça uma versão base com dicas de adaptação para cada uma, ou versões ligeiramente diferentes se a natureza da plataforma exigir (ex: WhatsApp mais direto, E-mail com Assunto e corpo).",
            "2. Inclua sugestões de 3-5 hashtags relevantes e populares, se aplicável.",
            "3. Sugira 2-3 emojis apropriados para o tom e conteúdo.",
            "4. Se for para e-mail, crie um Assunto (Subject Line) chamativo e o corpo do e-mail.",
            "5. Se for para YouTube/TikTok/Kwai, forneça um roteiro breve ou ideias principais para um vídeo curto (até 1 minuto), incluindo sugestões para o visual e áudio.",
            "6. Se o usuário enviou arquivos de suporte, mencione como eles podem ser usados (ex: 'use a imagem [nome_arquivo_imagem] como principal' ou 'baseie-se nos dados da planilha [nome_arquivo_planilha]')."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")

        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Criar Post)", final_prompt, height=150, key="dbg_prompt_post_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
        st.session_state.generated_post_content_new = generated_content

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    if not selected_platforms_list:
        st.warning("Por favor, selecione pelo menos uma plataforma para a campanha.")
        return
    if not details_dict["objective"]:
        st.warning("Por favor, descreva o objetivo principal da campanha.")
        return

    with st.spinner("🧠 A IA está elaborando seu plano de campanha... Isso pode levar um momento."):
        prompt_parts = [
            "**Instrução para IA:** Você é um estrategista de marketing digital sênior, criando um plano de campanha completo e acionável para uma pequena empresa.",
            f"**Nome da Campanha:** {campaign_specifics['name']}",
            f"**Plataformas Envolvidas:** {', '.join(selected_platforms_list)}.",
            f"**Duração Estimada:** {campaign_specifics['duration']}",
            f"**Orçamento para Impulsionamento (Referência):** {campaign_specifics['budget']}",
            f"**Objetivo Principal da Campanha:** {details_dict['objective']}",
            f"**Público-Alvo Detalhado:** {details_dict['target_audience']}",
            f"**Produto/Serviço Central:** {details_dict['product_service']}",
            f"**Mensagem Chave Central:** {details_dict['key_message']}",
            f"**Principal Diferencial (USP):** {details_dict['usp']}",
            f"**Tom/Estilo Geral da Campanha:** {details_dict['style_tone']}",
            f"**KPIs Principais:** {campaign_specifics['kpis']}",
            f"**Informações Adicionais/CTA Principal:** {details_dict['extra_info']}",
            "**Tarefa:** Elabore um plano de campanha que inclua:",
            "1.  **Conceito Criativo Central.**", "2.  **Estrutura da Campanha (Fases).**",
            "3.  **Mix de Conteúdo por Plataforma (3-5 tipos).**", "4.  **Sugestões de Criativos.**",
            "5.  **Mini Calendário Editorial.**", "6.  **Estratégia de Hashtags.**",
            "7.  **Recomendações para Impulsionamento.**", "8.  **Como Mensurar os KPIs.**", "9.  **Dicas de Otimização.**",
            "Se o usuário enviou arquivos de suporte, integre informações relevantes deles no plano."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")

        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Criar Campanha)", final_prompt, height=150, key="dbg_prompt_camp_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
        st.session_state.generated_campaign_content_new = generated_content

# ... (restante dos handlers _marketing_handle_criar_landing_page, _marketing_handle_criar_site, etc. permanecem iguais,
# pois já usam o 'llm' passado e não têm a complexidade do 'select all')

def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]:
        st.warning("Por favor, preencha o objetivo, a oferta principal e o CTA da landing page.")
        return
    with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em UX/UI e copywriting, focado em criar landing pages de alta conversão para pequenas empresas.",
            f"**Objetivo da Landing Page:** {lp_details['purpose']}",
            f"**Público-Alvo (Persona):** {lp_details['target_audience']}",
            f"**Oferta Principal:** {lp_details['main_offer']}",
            f"**Principais Benefícios da Oferta:** {lp_details['key_benefits']}",
            f"**Chamada para Ação (CTA) Principal:** {lp_details['cta']}",
            f"**Preferências Visuais/Referências:** {lp_details['visual_prefs']}",
            "**Tarefa:** Crie uma estrutura detalhada e sugestões de conteúdo (copy) para esta landing page. Inclua: Título(s), Subtítulo, Seções (Problema, Solução/Oferta, Benefícios, Prova Social, CTA), Elementos Adicionais (FAQ, Garantia), Tom de Voz, Sugestões de Layout/Design (descritivas).",
            "Se o usuário enviou arquivos de suporte, sugira como integrá-los."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Criar LP)", final_prompt, height=150, key="dbg_prompt_lp_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
        st.session_state.generated_lp_content_new = generated_content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not site_details["main_purpose"]:
        st.warning("Por favor, informe o tipo de negócio e o objetivo principal do site.")
        return
    with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um arquiteto de informação e web designer conceitual, ajudando uma pequena empresa a planejar a estrutura e conteúdo de seu novo site.",
            f"**Tipo de Negócio:** {site_details['business_type']}",
            f"**Objetivo Principal do Site:** {site_details['main_purpose']}",
            f"**Público-Alvo Principal:** {site_details['target_audience']}",
            f"**Páginas Essenciais Sugeridas pelo Usuário:** {site_details['essential_pages']}",
            f"**Principais Produtos/Serviços/Diferenciais a Destacar:** {site_details['key_features']}",
            f"**Personalidade da Marca:** {site_details['brand_personality']}",
            f"**Preferências Visuais/Referências:** {site_details['visual_references']}",
            "**Tarefa:** Desenvolva uma proposta de estrutura e conteúdo para o site. Inclua: Mapa do Site, Detalhes por Página (Objetivo, Seções, Copy, Visuais, CTAs), Conceito de Design/Layout, Slogan (opcional), Dicas SEO On-Page.",
            "Se o usuário enviou arquivos de suporte, sugira como incorporá-los."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Criar Site)", final_prompt, height=150, key="dbg_prompt_site_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
        st.session_state.generated_site_content_new = generated_content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"]:
        st.warning("Por favor, descreva o produto/serviço ou campanha.")
        return
    with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado.",
            f"**Produto/Serviço/Campanha em Foco:** {client_details['product_campaign']}",
            f"**Localização Principal:** {client_details['location']}",
            f"**Verba de Marketing (Referência):** {client_details['budget']}",
            f"**Faixa Etária e Gênero (Informado):** {client_details['age_gender']}",
            f"**Interesses/Dores/Necessidades (Informado):** {client_details['interests']}",
            f"**Canais Atuais/Considerados:** {client_details['current_channels']}",
            f"**Nível de Pesquisa Solicitado:** {'Deep Research Ativado' if client_details['deep_research'] else 'Pesquisa Padrão'}",
            "**Tarefa:** Realize uma análise completa do público-alvo. Inclua: Persona(s), Segmentação para Anúncios, Melhores Canais, Estratégia de Conteúdo, CPC/CPA Estimado (se possível), Sugestão de Impulsionamento. Se 'Deep Research' ativo, adicione Insights Comportamentais, Influenciadores, Objeções, Linguagem, Simulação de Pesquisa Google, Oportunidades Não Óbvias.",
            "Se o usuário enviou arquivos de suporte, considere-os."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Encontre Cliente)", final_prompt, height=150, key="dbg_prompt_cliente_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
        st.session_state.generated_client_analysis_new = generated_content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not competitor_details["competitors_list"]:
        st.warning("Por favor, descreva seu negócio e liste pelo menos um concorrente.")
        return
    with st.spinner("🔬 A IA está analisando a concorrência..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em analisar o mercado e os concorrentes de pequenas empresas.",
            f"**Negócio do Usuário (para Ponto de Referência):** {competitor_details['your_business']}",
            f"**Concorrentes a Serem Analisados (Informados pelo Usuário):** {competitor_details['competitors_list']}",
            f"**Principais Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}",
            "**Tarefa:** Elabore um relatório breve e útil sobre os concorrentes. Para cada concorrente principal: resumo da análise dos aspectos. Comparativo Geral: Pontos Fortes/Fracos da concorrência. Recomendações Estratégicas para o usuário (diferenciação, ações de marketing). Simule pesquisa pública.",
            "Se o usuário enviou arquivos de suporte, considere-os."
        ]
        if uploaded_files_info:
            prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        st.text_area("Debug: Prompt Enviado para IA (Concorrencia)", final_prompt, height=150, key="dbg_prompt_concor_new")

        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        generated_content = ai_response.content
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

    def _criar_cadeia_simples(self, system_message_content, human_message_content_template="{solicitacao_usuario}"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            HumanMessagePromptTemplate.from_template(human_message_content_template)
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, verbose=False)

    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_content),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

    # ***** MÉTODO DE MARKETING DIGITAL ATUALIZADO *****
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
                key="marketing_files_uploader_new_section_v4" # Chave atualizada
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

        main_action_key = "main_marketing_action_choice_new_v4" # Chave atualizada
        main_action = st.radio(
            "Olá! O que você quer fazer agora em marketing digital?",
            (
                "Selecione uma opção...",
                "1 - Criar post para redes sociais ou e-mail",
                "2 - Criar campanha de marketing completa",
                "3 - Criar estrutura e conteúdo para landing page",
                "4 - Criar estrutura e conteúdo para site com IA",
                "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                "6 - Conhecer a concorrência (Análise Competitiva)"
            ),
            index=0, key=main_action_key
        )
        st.markdown("---")

        # Define platform names for constructing the list after submission
        platform_names_available = [
            "Instagram", "Facebook", "X (Twitter)", "WhatsApp", "TikTok", "Kwai",
            "YouTube (descrição/roteiro)", "E-mail Marketing (lista própria)",
            "E-mail Marketing (Campanha Google Ads)"
        ]

        if main_action == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            form_key_post = "post_creator_form_new_v4" # Chave atualizada
            with st.form(form_key_post):
                # Estas variáveis receberão os valores SUBMETIDOS dos widgets
                submitted_select_all_state, submitted_platform_checkbox_widgets = _marketing_display_social_media_options("post_new_v4")
                post_details = _marketing_get_objective_details("post_new_v4", "post")
                submit_button_pressed = st.form_submit_button("💡 Gerar Post!")

            if submit_button_pressed:
                actual_selected_platforms = []
                if submitted_select_all_state: # Valor do checkbox "Selecionar Todos" após submissão
                    actual_selected_platforms = platform_names_available
                else:
                    for platform_name, is_selected_widget_var in submitted_platform_checkbox_widgets.items():
                        if is_selected_widget_var: # Valor do checkbox individual após submissão
                            actual_selected_platforms.append(platform_name)
                
                _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, actual_selected_platforms, self.llm)

            if 'generated_post_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_new, "post_new_v4", "post_ia")

        elif main_action == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            form_key_campaign = "campaign_creator_form_new_v4" # Chave atualizada
            with st.form(form_key_campaign):
                campaign_name = st.text_input("Nome da Campanha (para sua organização):", key="campaign_name_new_v4")
                submitted_select_all_state_camp, submitted_platform_checkbox_widgets_camp = _marketing_display_social_media_options("campaign_new_v4")
                campaign_details_obj = _marketing_get_objective_details("campaign_new_v4", "campanha")
                campaign_duration = st.text_input("Duração Estimada da Campanha:", key="campaign_duration_new_v4")
                campaign_budget_approx = st.text_input("Orçamento Aproximado para Impulsionamento (opcional):", key="campaign_budget_new_v4")
                specific_kpis = st.text_area("KPIs mais importantes:", placeholder="Ex: Nº de vendas, leads, CPC alvo.", key="campaign_kpis_new_v4")
                submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_button_pressed_camp:
                actual_selected_platforms_camp = []
                if submitted_select_all_state_camp:
                    actual_selected_platforms_camp = platform_names_available
                else:
                    for platform_name, is_selected_widget_var in submitted_platform_checkbox_widgets_camp.items():
                        if is_selected_widget_var:
                            actual_selected_platforms_camp.append(platform_name)
                
                campaign_specifics_dict = {
                    "name": campaign_name, "duration": campaign_duration,
                    "budget": campaign_budget_approx, "kpis": specific_kpis
                }
                _marketing_handle_criar_campanha(marketing_files_info_for_prompt, campaign_details_obj, campaign_specifics_dict, actual_selected_platforms_camp, self.llm)

            if 'generated_campaign_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_new, "campaign_new_v4", "campanha_ia")
        
        # ... (Lógica similar de tratamento de form para as outras seções de marketing) ...

        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form("landing_page_form_new_v4"): # Chave única
                lp_purpose = st.text_input("Principal objetivo da landing page:", key="lp_purpose_new_v4")
                lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key="lp_audience_new_v4")
                lp_main_offer = st.text_area("Oferta principal e irresistível:", key="lp_offer_new_v4")
                lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key="lp_benefits_new_v4")
                lp_cta = st.text_input("Chamada para ação (CTA) principal:", key="lp_cta_new_v4")
                lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key="lp_visual_new_v4")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")

            if submitted_lp:
                lp_details_dict = {
                    "purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer,
                    "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs
                }
                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details_dict, self.llm)

            if 'generated_lp_content_new' in st.session_state:
                st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                st.markdown(st.session_state.generated_lp_content_new)
                st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state.generated_lp_content_new.encode('utf-8'),
                                   file_name="landing_page_sugestoes_ia_new.txt", mime="text/plain", key="download_lp_new_v4") 

        elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
            st.subheader("🏗️ Arquiteto de Sites com IA")
            with st.form("site_creator_form_new_v4"): 
                site_business_type = st.text_input("Tipo do seu negócio/empresa:", key="site_biz_type_new_v4")
                site_main_purpose = st.text_area("Principal objetivo do seu site:", key="site_purpose_new_v4")
                site_target_audience = st.text_input("Público principal do site:", key="site_audience_new_v4")
                site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key="site_pages_new_v4")
                site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key="site_features_new_v4")
                site_brand_personality = st.text_input("Personalidade da sua marca:", key="site_brand_new_v4")
                site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key="site_visual_ref_new_v4")
                submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")
            
            if submitted_site:
                site_details_dict = {
                    "business_type": site_business_type, "main_purpose": site_main_purpose,
                    "target_audience": site_target_audience, "essential_pages": site_essential_pages,
                    "key_features": site_key_features, "brand_personality": site_brand_personality,
                    "visual_references": site_visual_references
                }
                _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details_dict, self.llm)

            if 'generated_site_content_new' in st.session_state:
                st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                st.markdown(st.session_state.generated_site_content_new)
                st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state.generated_site_content_new.encode('utf-8'),
                                   file_name="site_sugestoes_ia_new.txt", mime="text/plain",key="download_site_new_v4")

        elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
            st.subheader("🎯 Decodificador de Clientes com IA")
            with st.form("find_client_form_new_v4"):
                fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key="fc_campaign_new_v4")
                fc_location = st.text_input("Cidade(s) ou região de alcance:", key="fc_location_new_v4")
                fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key="fc_budget_new_v4")
                fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key="fc_age_gender_new_v4")
                fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key="fc_interests_new_v4")
                fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key="fc_channels_new_v4")
                fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key="fc_deep_new_v4")
                submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")

            if submitted_fc:
                client_details_dict = {
                    "product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget,
                    "age_gender": fc_age_gender, "interests": fc_interests,
                    "current_channels": fc_current_channels, "deep_research": fc_deep_research
                }
                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details_dict, self.llm)

            if 'generated_client_analysis_new' in st.session_state:
                st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                st.markdown(st.session_state.generated_client_analysis_new)
                st.download_button(label="📥 Baixar Análise de Público",data=st.session_state.generated_client_analysis_new.encode('utf-8'),
                                   file_name="analise_publico_alvo_ia_new.txt", mime="text/plain",key="download_client_analysis_new_v4")
        
        elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
            st.subheader("🧐 Radar da Concorrência com IA")
            with st.form("competitor_analysis_form_new_v4"):
                ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key="ca_your_biz_new_v4")
                ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key="ca_competitors_new_v4")
                ca_aspects_to_analyze = st.multiselect(
                    "Quais aspectos da concorrência analisar?",
                    ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"],
                    default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key="ca_aspects_new_v4"
                )
                submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")

            if submitted_ca:
                competitor_details_dict = {
                    "your_business": ca_your_business, "competitors_list": ca_competitors_list,
                    "aspects_to_analyze": ca_aspects_to_analyze
                }
                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details_dict, self.llm)

            if 'generated_competitor_analysis_new' in st.session_state:
                st.subheader("📊 Análise da Concorrência e Insights:")
                st.markdown(st.session_state.generated_competitor_analysis_new)
                st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state.generated_competitor_analysis_new.encode('utf-8'),
                                   file_name="analise_concorrencia_ia_new.txt",mime="text/plain",key="download_competitor_analysis_new_v4")

        elif main_action == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            logo_url_marketing_welcome = "https://i.imgur.com/7IIYxq1.png"
            st.image(logo_url_marketing_welcome, caption="Assistente PME Pro", width=200)


    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios especialista em IA. Sua tarefa é ajudar um empreendedor a ESBOÇAR e depois DETALHAR um PLANO DE NEGÓCIOS. Você faz perguntas UMA DE CADA VEZ para coletar informações. Use linguagem clara e seja encorajador.\n\n**FLUXO DA CONVERSA:**\n\n**INÍCIO DA CONVERSA / PEDIDO INICIAL:**\nSe o usuário indicar que quer criar um plano de negócios (ex: \"Crie meu plano de negócios\", \"Quero ajuda com meu plano\", \"sim\" para um botão de iniciar plano), SUA PRIMEIRA PERGUNTA DEVE SER: \"Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?\"\n\n**COLETA PARA O ESBOÇO:**\nApós saber o ramo, continue fazendo UMA PERGUNTA POR VEZ para obter informações para as seguintes seções (não precisa ser exatamente nesta ordem, mas cubra-as):\n1.  Nome da Empresa\n2.  Missão da Empresa\n3.  Visão da Empresa\n4.  Principais Objetivos\n5.  Produtos/Serviços Principais\n6.  Público-Alvo Principal\n7.  Principal Diferencial\n8.  Ideias Iniciais de Marketing e Vendas\n9.  Ideias Iniciais de Operações\n10. Estimativas Financeiras Muito Básicas\n\n**GERAÇÃO DO ESBOÇO:**\nQuando você sentir que coletou informações suficientes para estas 10 áreas, VOCÊ DEVE PERGUNTAR:\n\"Com as informações que reunimos até agora, você gostaria que eu montasse um primeiro ESBOÇO do seu plano de negócios? Ele terá as seções principais que discutimos.\"\n\nSe o usuário disser \"sim\":\n    - Gere um ESBOÇO do plano de negócios com as seções: Sumário Executivo, Descrição da Empresa, Produtos e Serviços, Público-Alvo e Diferenciais, Estratégias Iniciais de Marketing e Vendas, Operações Iniciais, Panorama Financeiro Inicial.\n    - No final do esboço, ADICIONE: \"Este é um esboço inicial para organizar suas ideias. Ele pode ser muito mais detalhado e aprofundado.\"\n    - ENTÃO, PERGUNTE: \"Este esboço inicial te ajuda a visualizar melhor? Gostaria de DETALHAR este plano de negócios agora? Podemos aprofundar cada seção, e você poderá me fornecer mais informações (e no futuro, até mesmo subir documentos).\"\n\n**DETALHAMENTO DO PLANO (SE O USUÁRIO ACEITAR):**\nSe o usuário disser \"sim\" para detalhar:\n    - Responda com entusiasmo: \"Ótimo! Para detalharmos, vamos focar em cada seção do plano. Aplicaremos princípios de administração e marketing (como os de Chiavenato e Kotler) para enriquecer a análise.\"\n    - ENTÃO, PERGUNTE: \"Em qual seção do plano de negócios você gostaria de começar a aprofundar ou fornecer mais detalhes? Por exemplo, 'Análise de Mercado', 'Estratégias de Marketing Detalhadas', ou 'Projeções Financeiras'?\"\n    - A partir da escolha, faça perguntas específicas para aquela seção."
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)


    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        system_message_precos = f"""
        Você é o "Assistente PME Pro", especialista em precificação com IA.
        Sua tarefa é ajudar o usuário a definir o preço de venda de um produto ou serviço, atuando como um consultor que busca as informações necessárias.
        Você faz perguntas UMA DE CADA VEZ e guia o usuário.
        {(f"Contexto da imagem que o usuário enviou: '{descricao_imagem_contexto}'. Considere esta informação ao falar sobre o produto.") if descricao_imagem_contexto else ""}

        **FLUXO DA CONVERSA PARA PRECIFICAR:**

        **1. PERGUNTA INICIAL (SEMPRE FAÇA ESTA PRIMEIRO QUANDO O USUÁRIO ENTRAR NESTA FUNCIONALIDADE):**
            "Olá! Sou o Assistente PME Pro, pronto para te ajudar com a precificação. Para começar, o produto ou serviço que você quer precificar é algo que você COMPRA E REVENDE, ou é algo que sua empresa MESMA PRODUZ/CRIA?"

        **2. SE O USUÁRIO ESCOLHER "COMPRA E REVENDE":**
            a. PERGUNTE: "Entendido, é para revenda. Qual é o nome ou tipo específico do produto que você revende?" (Ex: SSD Interno 1TB Western Digital Blue, Camiseta XYZ)
            b. PERGUNTE: "Qual o seu CUSTO DE AQUISIÇÃO por unidade deste produto? (Quanto você paga ao seu fornecedor por cada um)."
            c. PERGUNTE: "Em qual CIDADE e ESTADO (Ex: Juiz de Fora - MG) sua loja ou negócio principal opera? Isso nos ajudará a considerar o mercado."
            d. APÓS OBTER ESSAS INFORMAÇÕES, DIGA:
                "Ok, tenho as informações básicas: produto '[NOME DO PRODUTO INFORMADO PELO USUÁRIO]', seu custo de R$[VALOR DO CUSTO INFORMADO] em [CIDADE/ESTADO INFORMADO].
                Agora, o passo CRUCIAL é entendermos o preço de mercado. **Vou te ajudar a analisar os preços praticados para produtos similares na sua região.** (No futuro, este app poderá fazer buscas automáticas na web, mas por enquanto, vamos analisar juntos com base no seu conhecimento e no que eu posso inferir).
                Para termos um ponto de partida, qual MARGEM DE LUCRO (em porcentagem, ex: 20%, 50%, 100%) você gostaria de ter sobre o seu custo de R$[VALOR DO CUSTO INFORMADO]? Ou você já tem um PREÇO DE VENDA ALVO em mente?"
            e. QUANDO O USUÁRIO RESPONDER A MARGEM/PREÇO ALVO:
                - Calcule o preço de venda sugerido (Custo / (1 - %MargemDesejada/100)) ou (Custo * (1 + %MarkupDesejado/100)). Explique o cálculo de forma simples.
                - APRESENTE O PREÇO CALCULADO e diga: "Com base no seu custo e na margem desejada, o preço de venda sugerido seria R$ X.XX.
                  Para validar este preço, sugiro que você pesquise em pelo menos 3-5 concorrentes online e locais. Compare este preço calculado com os preços praticados. Se estiver muito diferente, precisaremos ajustar a margem ou reanalisar os custos e a estratégia de precificação."
                - PERGUNTE: "Este preço inicial faz sentido? Quer simular com outra margem?"

        **3. SE O USUÁRIO ESCOLHER "PRODUZ/CRIA":**
            a. PERGUNTE: "Excelente! Para precificar seu produto/serviço próprio, vamos detalhar os custos. Qual o nome do produto ou tipo de serviço que você cria/oferece?"
            b. PERGUNTE sobre CUSTOS DIRETOS DE MATERIAL/INSUMOS: "Quais são os custos diretos de material ou insumos que você gasta para produzir UMA unidade do produto ou para realizar UMA vez o serviço? Por favor, liste os principais itens e seus custos."
            c. PERGUNTE sobre MÃO DE OBRA DIRETA: "Quanto tempo de trabalho (seu ou de funcionários) é gasto diretamente na produção de UMA unidade ou na prestação de UMA vez o serviço? E qual o custo estimado dessa mão de obra por unidade/serviço?"
            d. PERGUNTE sobre CUSTOS FIXOS MENSAIS TOTAIS: "Quais são seus custos fixOS mensais totais (aluguel, luz, internet, salários administrativos, etc.) que precisam ser cobertos?"
            e. PERGUNTE sobre VOLUME DE PRODUÇÃO/VENDAS MENSAL ESPERADO: "Quantas unidades desse produto você espera vender por mês, ou quantos serviços espera prestar? Isso nos ajudará a ratear os custos fixos por unidade."
            f. APÓS OBTER ESSAS INFORMAÇÕES, explique: "Com esses dados, podemos calcular o Custo Total Unitário. Depois, adicionaremos sua margem de lucro desejada. Existem métodos como Markup ou Margem de Contribuição que podemos usar."
            g. PERGUNTE: "Qual MARGEM DE LUCRO (em porcentagem) você gostaria de adicionar sobre o custo total de produção para definirmos o preço de venda?"
            h. QUANDO O USUÁRIO RESPONDER A MARGEM:
                - Calcule o preço de venda sugerido.
                - APRESENTE O PREÇO CALCULADO e diga: "Com base nos seus custos e na margem desejada, o preço de venda sugerido seria R$ X.XX."
                - PERGUNTE: "Este preço cobre todos os seus custos e te dá a lucratividade esperada? Como ele se compara ao que você imagina que o mercado pagaria?"

        **FINALIZAÇÃO DA INTERAÇÃO (PARA AMBOS OS CASOS):**
        - Após uma sugestão de preço, sempre ofereça: "Podemos refinar este cálculo, simular outros cenários ou discutir estratégias de precificação com base nos princípios de marketing de Kotler?"

        Mantenha a conversa fluida e profissional, mas acessível. O objetivo é entregar o 'bolo pronto com a velinha', ou seja, uma análise e sugestão de preço fundamentada.
        """
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        system_message_ideias = f"""
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA, com foco em INOVAÇÃO e SOLUÇÃO DE PROBLEMAS.
        Sua tarefa é ajudar empreendedores a gerar ideias criativas e práticas para seus negócios, seja para resolver dores, encontrar novas oportunidades ou inovar.
        Você faz perguntas UMA DE CADA VEZ para entender o contexto do usuário.
        {(f"INFORMAÇÃO ADICIONAL FORNECIDA PELO USUÁRIO (pode ser de arquivos que ele carregou): '{contexto_arquivos}'. Por favor, CONSIDERE esta informação ao interagir e gerar ideias. Se for um arquivo de texto, use o conteúdo. Se for uma imagem, peça ao usuário para descrever como ela se relaciona com o desafio dele.") if contexto_arquivos else ""}

        **FLUXO DA CONVERSA:**

        **INÍCIO DA CONVERSA / PEDIDO INICIAL:**
        - Se o usuário indicar que quer ideias (ex: "Preciso de ideias para aumentar vendas", "Estou com dificuldade em X", "Como posso inovar meu serviço Y?") ou simplesmente iniciar a conversa nesta seção,
          SUA PRIMEIRA PERGUNTA DEVE SER (de forma empática e aberta): "Olá! Que bom que você quer explorar novas ideias. {('Recebi as informações dos arquivos que você carregou. ' if contexto_arquivos else 'Você também pode carregar arquivos de texto ou imagens se achar que ajudam a dar contexto. ')} Para que eu possa te ajudar da melhor forma, conte-me um pouco mais sobre o principal desafio que você está enfrentando, a dor que sente no seu negócio, ou a área específica em que você gostaria de inovar ou receber sugestões."

        **EXPLORAÇÃO DO PROBLEMA/OPORTUNIDADE (SE NECESSÁRIO):**
        - Após a primeira descrição do usuário, se precisar de mais clareza (e considerando o contexto de arquivos, se houver), faça UMA ou DUAS perguntas abertas para aprofundar, como:
              - "Interessante. Para eu entender melhor a dimensão disso, [faça uma pergunta específica sobre o que ele disse ou o contexto do arquivo]?"
              - "Quais são os principais obstáculos ou dificuldades que você enfrenta atualmente em relação a isso?"
        - Após o usuário responder, ou se ele já deu um bom contexto (especialmente se forneceu arquivos), diga:
          "Entendido. Com base no que você me contou sobre [resuma brevemente o problema/dor/objetivo do usuário, mencionando se informações de arquivos foram consideradas], vou gerar algumas ideias e sugestões para você, aplicando princípios de marketing e administração para encontrar soluções eficazes."
        - ENTÃO, gere de 3 a 5 ideias ou abordagens distintas e criativas. Para cada ideia:
              a. Dê um **Nome ou Título Curto e Chamativo**.
              b. **Descreva a Ideia:** Explique o conceito de forma clara e concisa (1-3 frases).
              c. **Benefício Principal:** Destaque o principal benefício ou solução que essa ideia traria.
              d. **Primeiro Passo Simples (Opcional, mas bom):** Se apropriado, sugira um primeiro passo muito pequeno e prático que o usuário poderia dar para começar a explorar essa ideia.

        **DISCUSSÃO E REFINAMENTO:**
        - Após apresentar as ideias, PERGUNTE: "O que você achou dessas primeiras sugestões? Alguma delas te inspira ou parece particularmente promissora para o seu caso? Gostaria de explorar alguma delas com mais detalhes, ou talvez refinar o foco para gerarmos mais alternativas?"
        """
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

    if area_chave == "calculo_precos":
        st.session_state.last_uploaded_image_info_pricing = None
        st.session_state.processed_image_id_pricing = None
    elif area_chave == "gerador_ideias":
        st.session_state.uploaded_file_info_ideias_for_prompt = None
        st.session_state.processed_file_id_ideias = None

def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state:
        st.session_state[chat_display_key] = []

    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]):
            st.markdown(msg_info["content"])

    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v6_merged_v2") # Nova chave

    if prompt_usuario:
        st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"):
            st.markdown(prompt_usuario)

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

    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Marketing Digital com IA (Guia)": "marketing_guiado",
        "Elaborar Plano de Negócios com IA": "plano_negocios",
        "Cálculo de Preços Inteligente": "calculo_precos",
        "Gerador de Ideias para Negócios": "gerador_ideias"
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"

    for nome_menu_init, chave_secao_init in opcoes_menu.items():
        if chave_secao_init and chave_secao_init != "marketing_guiado" and f"chat_display_{chave_secao_init}" not in st.session_state :
            st.session_state[f"chat_display_{chave_secao_init}"] = []

    if 'start_marketing_form' not in st.session_state: st.session_state.start_marketing_form = False
    if 'last_uploaded_image_info_pricing' not in st.session_state: st.session_state.last_uploaded_image_info_pricing = None
    if 'processed_image_id_pricing' not in st.session_state: st.session_state.processed_image_id_pricing = None
    if 'user_input_processed_pricing' not in st.session_state: st.session_state.user_input_processed_pricing = False
    if 'uploaded_file_info_ideias_for_prompt' not in st.session_state: st.session_state.uploaded_file_info_ideias_for_prompt = None
    if 'processed_file_id_ideias' not in st.session_state: st.session_state.processed_file_id_ideias = None
    if 'user_input_processed_ideias' not in st.session_state: st.session_state.user_input_processed_ideias = False

    # Controle de re-inicialização de chat
    if 'previous_area_selecionada_for_chat_init' not in st.session_state:
        st.session_state['previous_area_selecionada_for_chat_init'] = None


    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v18_final', # Nova chave
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada: # Mudança de aba
        st.session_state.area_selecionada = area_selecionada_label
        # Limpar estados específicos de marketing ao sair da seção de marketing
        if area_selecionada_label != "Marketing Digital com IA (Guia)":
            for key in list(st.session_state.keys()): # Iterar sobre uma cópia das chaves
                if key.startswith("generated_") and key.endswith("_new"):
                    del st.session_state[key]
                if "_all_social_checkbox_ui_v3" in key: # Limpar estado do "selecionar todos"
                    st.session_state[key] = False
        st.rerun() # Forçar rerun para atualizar a interface e lógica de inicialização de chat

    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    # Inicializar chat para seções conversacionais se necessário (após o rerun da seleção de aba)
    if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
        if st.session_state.area_selecionada != st.session_state.get('previous_area_selecionada_for_chat_init_processed'):
            chat_display_key_nav = f"chat_display_{current_section_key}"
            msg_inicial_nav = ""
            memoria_agente_nav = None
            if current_section_key == "plano_negocios":
                msg_inicial_nav = "Olá! Sou seu Assistente PME Pro. Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!"
                memoria_agente_nav = agente.memoria_plano_negocios
            elif current_section_key == "calculo_precos":
                msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começar, você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?"
                memoria_agente_nav = agente.memoria_calculo_precos
            elif current_section_key == "gerador_ideias":
                msg_inicial_nav = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Conte-me um pouco sobre um desafio, uma dor ou uma área que você gostaria de inovar."
                memoria_agente_nav = agente.memoria_gerador_ideias
            
            if msg_inicial_nav and memoria_agente_nav:
                inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
            st.session_state['previous_area_selecionada_for_chat_init_processed'] = st.session_state.area_selecionada


    if current_section_key == "pagina_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para explorar as ferramentas disponíveis.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo Assistente PME Pro' width='200'></div>", unsafe_allow_html=True)
        st.markdown("---")

        num_botoes_funcionais = len(opcoes_menu) -1
        if num_botoes_funcionais > 0 :
            num_cols_render = min(num_botoes_funcionais, 4)
            cols_botoes_pg_inicial = st.columns(num_cols_render)
            btn_idx_pg_inicial = 0
            for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                if chave_secao_btn_pg != "pagina_inicial":
                    col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                    button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" para ")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" (Guia)","")
                    if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v11_final", use_container_width=True): # Chave atualizada
                        st.session_state.area_selecionada = nome_menu_btn_pg
                        st.rerun() # Força o rerun para que a lógica de inicialização de chat no topo seja acionada
                    btn_idx_pg_inicial +=1
            st.balloons()

    elif current_section_key == "marketing_guiado":
        agente.marketing_digital_guiado()

    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")
        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou diga 'Crie meu plano de negócios'", agente.conversar_plano_de_negocios)
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v7_final"): # Chave atualizada
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar seu plano de negócios! Se você gostaria de criar um plano de negócios, pode me dizer 'sim' ou 'vamos começar'!", agente.memoria_plano_negocios)
            st.rerun()

    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Vamos definir os melhores preços para seus produtos ou serviços!")

        uploaded_image = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v8_final") # Chave atualizada
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
        if current_image_context:
                kwargs_preco_chat['descricao_imagem_contexto'] = current_image_context

        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou descreva o produto/serviço", agente.calcular_precos_interativo, **kwargs_preco_chat)

        if 'user_input_processed_pricing' in st.session_state and st.session_state.user_input_processed_pricing:
            if st.session_state.get('last_uploaded_image_info_pricing'):
                    st.session_state.last_uploaded_image_info_pricing = None
            st.session_state.user_input_processed_pricing = False

        if st.sidebar.button("Reiniciar Cálculo de Preços", key="btn_reset_precos_v8_final"): # Chave atualizada
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar um novo cálculo de preços! Você quer precificar um produto que você COMPRA E REVENDE, ou um produto/serviço que você MESMO PRODUZ/CRIA?", agente.memoria_calculo_precos)
            st.rerun()

    elif current_section_key == "gerador_ideias":
        st.header("💡 Gerador de Ideias para seu Negócio com IA")
        st.caption("Descreva seus desafios ou áreas onde busca inovação, e vamos encontrar soluções juntos!")

        uploaded_files_ideias_ui = st.file_uploader(
            "Envie arquivos com informações (.txt, .png, .jpg):",
            type=["txt", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="ideias_file_uploader_v3_final" # Chave atualizada
        )

        contexto_para_ia_ideias_local = None
        if uploaded_files_ideias_ui:
            current_file_signature = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias_ui]))
            if st.session_state.get('processed_file_id_ideias') != current_file_signature or not st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                text_contents_ui = []
                image_info_ui = []
                for uploaded_file_item in uploaded_files_ideias_ui:
                    try:
                        if uploaded_file_item.type == "text/plain":
                            file_content_ui = uploaded_file_item.read().decode("utf-8")
                            text_contents_ui.append(f"Conteúdo do arquivo de texto '{uploaded_file_item.name}':\n{file_content_ui[:2000]}...")
                        elif uploaded_file_item.type in ["image/png", "image/jpeg"]:
                            st.image(Image.open(uploaded_file_item), caption=f"Imagem: {uploaded_file_item.name}", width=100)
                            image_info_ui.append(f"O usuário também carregou uma imagem chamada '{uploaded_file_item.name}'.")
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo '{uploaded_file_item.name}': {e}")

                full_context_ui = ""
                if text_contents_ui: full_context_ui += "\n\n--- CONTEÚDO DE ARQUIVOS DE TEXTO ---\n" + "\n\n".join(text_contents_ui)
                if image_info_ui: full_context_ui += "\n\n--- INFORMAÇÃO SOBRE IMAGENS CARREGADAS ---\n" + "\n".join(image_info_ui)

                if full_context_ui:
                    st.session_state.uploaded_file_info_ideias_for_prompt = full_context_ui.strip()
                    contexto_para_ia_ideias_local = st.session_state.uploaded_file_info_ideias_for_prompt
                    st.info("Arquivo(s) pronto(s) para serem considerados no próximo diálogo.")
                else:
                    st.session_state.uploaded_file_info_ideias_for_prompt = None
                st.session_state.processed_file_id_ideias = current_file_signature
            else:
                contexto_para_ia_ideias_local = st.session_state.get('uploaded_file_info_ideias_for_prompt')

        kwargs_ideias_chat_ui = {}
        if contexto_para_ia_ideias_local:
            kwargs_ideias_chat_ui['contexto_arquivos'] = contexto_para_ia_ideias_local

        exibir_chat_e_obter_input(current_section_key, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat_ui)

        if 'user_input_processed_ideias' in st.session_state and st.session_state.user_input_processed_ideias:
            st.session_state.user_input_processed_ideias = False

        if st.sidebar.button("Nova Sessão de Ideias", key="btn_reset_ideias_v4_final"): # Chave atualizada
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar uma nova busca por ideias! Conte-me sobre um novo desafio, dor ou área para inovar.", agente.memoria_gerador_ideias)
            st.rerun()
else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")   
