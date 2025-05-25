import streamlit as st
import os
import google.generativeai as genai # Adicionado aqui, mas a configuração ainda precisa ser feita por você

# --- Configuração Inicial do Modelo Gemini (Exemplo) ---
# Substitua pela sua chave de API e configuração do modelo.
# Esta seção é um placeholder. VOCÊ PRECISA CONFIGURAR SUA CHAVE DE API.

# GOOGLE_API_KEY = "SUA_CHAVE_API_AQUI" # Descomente e cole sua chave aqui ou use variáveis de ambiente
# if 'gemini_model' not in st.session_state:
#     try:
#         api_key_to_use = os.getenv("GOOGLE_API_KEY") if not GOOGLE_API_KEY else GOOGLE_API_KEY # Prioriza a chave no código se preenchida
#
#         if api_key_to_use:
#             genai.configure(api_key=api_key_to_use)
#             model = genai.GenerativeModel(
#                 model_name="gemini-1.5-pro-latest", # Ou seu modelo preferido
#                 # generation_config=generation_config, # Se tiver config específica
#                 # safety_settings=safety_settings # Se tiver config específica
#             )
#             st.session_state.gemini_model = model
#             st.session_state.gemini_model_initialized = True
#             # st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!") # Feedback opcional
#         else:
#             st.sidebar.error("🔑 Chave da API do Google não configurada. A IA não funcionará.")
#             st.session_state.gemini_model_initialized = False
#             # st.stop() # Para a execução se a chave for crucial e não encontrada
#
#     except Exception as e:
#         st.error(f"❌ Erro ao inicializar o modelo Gemini: {e}")
#         st.session_state.gemini_model_initialized = False
#         st.stop() # Para a execução se a inicialização falhar

# --- Placeholder para a chamada à API do Gemini ---
def call_gemini_api(prompt_text, user_files_info=None):
    """
    Placeholder para a chamada real à API do Gemini.
    Substitua esta função pela sua implementação de chamada ao Gemini.
    """
    # Verifique se o modelo foi inicializado (simulação)
    # if not st.session_state.get('gemini_model_initialized', False) and not st.session_state.get('gemini_model'):
    #     st.error("Modelo Gemini não inicializado. Verifique a configuração da API Key.")
    #     return "Erro: Modelo não inicializado."

    st.markdown("---")
    st.write("ℹ️ **Informação para Desenvolvimento (Placeholder):**")
    st.write("**Prompt Enviado para IA (resumido):**")
    st.text_area("Prompt:", prompt_text[:1000] + "..." if len(prompt_text) > 1000 else prompt_text, height=150, key=f"prompt_debug_{hash(prompt_text)}")
    if user_files_info:
        st.write("**Arquivos Considerados (simulado):**")
        for file_info in user_files_info:
            st.write(f"- {file_info['name']} ({file_info['type']})")
    st.markdown("---")

    # Simulação de resposta da IA
    # Na implementação real, você usaria algo como:
    # if st.session_state.get('gemini_model'):
    # try:
    #       response = st.session_state.gemini_model.generate_content(prompt_text)
    #       return response.text
    #     except Exception as e:
    #         st.error(f"Erro na chamada ao Gemini: {e}")
    #         return f"Erro ao gerar resposta da IA: {e}"
    # else:
    #     return "Modelo não disponível para gerar resposta."

    if "criar post" in prompt_text.lower():
        return f"Conteúdo do post gerado pela IA com base no prompt:\n{prompt_text[:200]}...\n\n[Aqui viria o post completo, hashtags, emojis, etc.]"
    elif "criar campanha" in prompt_text.lower():
        return f"Plano de campanha gerado pela IA:\n{prompt_text[:200]}...\n\n[Aqui viria o plano detalhado, calendário de conteúdo, ideias de criativos, etc.]"
    elif "landing page" in prompt_text.lower():
        return f"Sugestões para Landing Page geradas pela IA:\n{prompt_text[:200]}...\n\n[Estrutura da LP, textos, CTAs, sugestões de design, etc.]"
    elif "criar site" in prompt_text.lower():
        return f"Ideias e estrutura para Site geradas pela IA:\n{prompt_text[:200]}...\n\n[Páginas, seções, conteúdo sugerido, conceito de design, etc.]"
    elif "encontre seu cliente" in prompt_text.lower():
        return f"Análise de público-alvo gerada pela IA:\n{prompt_text[:200]}...\n\n[Perfil do cliente, sugestões de segmentação, melhores canais, etc.]"
    elif "conheça a concorrência" in prompt_text.lower():
        return f"Análise de concorrência gerada pela IA:\n{prompt_text[:200]}...\n\n[Relatório dos concorrentes, pontos fortes/fracos, oportunidades, etc.]"
    return "Resposta simulada da IA para: " + prompt_text[:100] + "..."

# --- Funções Auxiliares de UI ---
def display_social_media_options(section_key, all_option_text="Selecionar Todas as Plataformas Acima"):
    st.subheader("Plataformas Desejadas:")
    platforms_options = {
        "Instagram": f"{section_key}_insta", "Facebook": f"{section_key}_fb", "X (Twitter)": f"{section_key}_x",
        "WhatsApp": f"{section_key}_wpp", "TikTok": f"{section_key}_tt", "Kwai": f"{section_key}_kwai",
        "YouTube (descrição/roteiro)": f"{section_key}_yt",
        "E-mail Marketing (lista própria)": f"{section_key}_email_own",
        "E-mail Marketing (Campanha Google Ads)": f"{section_key}_email_google"
    }
    cols = st.columns(2)
    selected_platforms_map = {}
    platform_keys = list(platforms_options.keys())

    for i, platform_name in enumerate(platform_keys):
        col_index = i % 2
        with cols[col_index]:
            selected_platforms_map[platform_name] = st.checkbox(platform_name, key=platforms_options[platform_name])

    # O checkbox "Selecionar Todas" precisa de uma lógica mais elaborada com callbacks ou st.form para refletir imediatamente na UI.
    # Por simplicidade, ele definirá o estado que será lido no processamento.
    if st.checkbox(all_option_text, key=f"{section_key}_all_social"):
        # Esta lógica de "selecionar todos" aqui é para quando o form for submetido.
        # A UI dos checkboxes individuais não será atualizada dinamicamente por este checkbox sem callbacks.
        for platform_name in platform_keys:
            selected_platforms_map[platform_name] = True


    actual_selected_platforms = [p for p, is_selected in selected_platforms_map.items() if is_selected]
    # Se "Selecionar Todas" foi marcado, sobrescreve
    if selected_platforms_map.get(all_option_text, False) or st.session_state.get(f"{section_key}_all_social", False): # Verifica o estado do checkbox "Selecionar Todas"
         actual_selected_platforms = platform_keys


    if any(p in actual_selected_platforms for p in ["E-mail Marketing (lista própria)", "E-mail Marketing (Campanha Google Ads)"]):
        st.caption("💡 Para e-mail marketing, a IA ajudará na criação do texto, sugestões de imagens/layout e estratégia. O disparo da ação e a gestão de listas/campanhas no Google Ads requerem ferramentas externas.")
    return actual_selected_platforms

def get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    details["objective"] = st.text_area(
        f"Qual o principal objetivo com est(e/a) {type_of_creation}? (Ex: Aumentar vendas, gerar leads, divulgar evento, construir marca)",
        key=f"{section_key}_obj"
    )
    details["target_audience"] = st.text_input("Quem você quer alcançar? (Descreva seu público-alvo)", key=f"{section_key}_audience")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial ou diferente da concorrência (USP)?", key=f"{section_key}_usp")
    details["style_tone"] = st.selectbox(
        "Qual o tom/estilo da comunicação?",
        ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"),
        key=f"{section_key}_tone"
    )
    details["extra_info"] = st.text_area("Alguma informação adicional, promoção específica, ou call-to-action (CTA) principal que devemos incluir?", key=f"{section_key}_extra")
    return details

def display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)

    st.download_button(
        label="📥 Baixar Conteúdo Gerado",
        data=generated_content.encode('utf-8'),
        file_name=f"{file_name_prefix}_{section_key}.txt",
        mime="text/plain",
        key=f"download_{section_key}"
    )

    cols_actions = st.columns(2)
    with cols_actions[0]:
        if st.button("🔗 Simular Compartilhamento", key=f"{section_key}_share_btn"):
            st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
            st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
    with cols_actions[1]:
        if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn"):
            st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

# --- Seção Principal de Marketing Digital ---
def marketing_digital_section():
    st.header("🚀 Marketing Digital com IA")
    st.caption("Seu copiloto para criar estratégias de marketing digital eficazes!")
    st.markdown("---")

    with st.sidebar:
        st.header("📎 Material de Suporte")
        st.caption("Envie arquivos para contextualizar a IA na criação das suas ações de marketing.")
        uploaded_files = st.file_uploader(
            "Upload de imagens, textos, planilhas, vídeos:",
            accept_multiple_files=True,
            type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx', 'mp4', 'mov'],
            key="marketing_files_uploader"
        )
        user_files_info = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                user_files_info.append({"name": uploaded_file.name, "type": uploaded_file.type, "size": uploaded_file.size})
            st.success(f"{len(uploaded_files)} arquivo(s) carregado(s) com sucesso!")
            with st.expander("Ver arquivos carregados"):
                for file_info in user_files_info:
                    st.write(f"- {file_info['name']} ({file_info['type']})")
        st.markdown("---")
        st.info("A IA poderá usar o nome e tipo dos arquivos para entender o contexto. Para análise de conteúdo de texto, a implementação da chamada ao Gemini precisará ler e enviar o texto do arquivo.")

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
        index=0,
        key="main_marketing_action_choice"
    )
    st.markdown("---")

    if main_action == "1 - Criar post para redes sociais ou e-mail":
        st.subheader("✨ Criador de Posts com IA")
        with st.form("post_creator_form"):
            selected_platforms = display_social_media_options("post")
            post_details = get_objective_details("post", "post")
            submitted_post = st.form_submit_button("💡 Gerar Post!")

        if submitted_post:
            if not selected_platforms:
                st.warning("Por favor, selecione pelo menos uma plataforma.")
            elif not post_details["objective"]:
                st.warning("Por favor, descreva o objetivo do post.")
            else:
                with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um especialista em copywriting e marketing digital criando um post para pequenas empresas.",
                        f"**Plataformas Alvo:** {', '.join(selected_platforms)}.",
                        f"**Objetivo do Post:** {post_details['objective']}",
                        f"**Público-Alvo:** {post_details['target_audience']}",
                        f"**Produto/Serviço Promovido:** {post_details['product_service']}",
                        f"**Mensagem Chave:** {post_details['key_message']}",
                        f"**Diferencial (USP):** {post_details['usp']}",
                        f"**Tom/Estilo:** {post_details['style_tone']}",
                        f"**Informações Adicionais/CTA:** {post_details['extra_info']}",
                        "**Tarefa:**",
                        "1. Gere o conteúdo do post. Se múltiplas plataformas foram selecionadas, forneça uma versão base com dicas de adaptação para cada uma, ou versões ligeiramente diferentes se a natureza da plataforma exigir (ex: WhatsApp mais direto, E-mail com Assunto e corpo).",
                        "2. Inclua sugestões de 3-5 hashtags relevantes e populares, se aplicável.",
                        "3. Sugira 2-3 emojis apropriados para o tom e conteúdo.",
                        "4. Se for para e-mail, crie um Assunto (Subject Line) chamativo e o corpo do e-mail.",
                        "5. Se for para YouTube/TikTok/Kwai, forneça um roteiro breve ou ideias principais para um vídeo curto (até 1 minuto), incluindo sugestões para o visual e áudio.",
                        "6. Se o usuário enviou arquivos de suporte, mencione como eles podem ser usados (ex: 'use a imagem [nome_arquivo_imagem] como principal' ou 'baseie-se nos dados da planilha [nome_arquivo_planilha]')."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_post_content = generated_content

        if 'generated_post_content' in st.session_state:
            display_output_options(st.session_state.generated_post_content, "post", "post_ia")

    elif main_action == "2 - Criar campanha de marketing completa":
        st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
        with st.form("campaign_creator_form"):
            campaign_name = st.text_input("Nome da Campanha (para sua organização):", key="campaign_name")
            selected_platforms_camp = display_social_media_options("campaign")
            campaign_details = get_objective_details("campaign", "campanha")
            campaign_duration = st.text_input("Duração Estimada da Campanha (Ex: 1 semana, 1 mês, lançamento pontual):", key="campaign_duration")
            campaign_budget_approx = st.text_input("Orçamento Aproximado para Impulsionamento (opcional, ex: R$500):", key="campaign_budget")
            specific_kpis = st.text_area(
                "Quais Indicadores Chave de Performance (KPIs) são mais importantes para esta campanha?",
                placeholder="Ex: Nº de vendas diretas, % de aumento em leads, custo por clique (CPC) alvo, taxa de engajamento.",
                key="campaign_kpis"
            )
            submitted_campaign = st.form_submit_button("🚀 Gerar Plano de Campanha!")

        if submitted_campaign:
            if not selected_platforms_camp:
                st.warning("Selecione ao menos uma plataforma para a campanha.")
            elif not campaign_details["objective"]:
                st.warning("Descreva o objetivo principal da campanha.")
            else:
                with st.spinner("🧠 A IA está elaborando seu plano de campanha... Isso pode levar um momento."):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um estrategista de marketing digital sênior, criando um plano de campanha completo e acionável para uma pequena empresa.",
                        f"**Nome da Campanha:** {campaign_name}",
                        f"**Plataformas Envolvidas:** {', '.join(selected_platforms_camp)}.",
                        f"**Duração Estimada:** {campaign_duration}",
                        f"**Orçamento para Impulsionamento (Referência):** {campaign_budget_approx}",
                        f"**Objetivo Principal da Campanha:** {campaign_details['objective']}",
                        f"**Público-Alvo Detalhado:** {campaign_details['target_audience']}",
                        f"**Produto/Serviço Central:** {campaign_details['product_service']}",
                        f"**Mensagem Chave Central:** {campaign_details['key_message']}",
                        f"**Principal Diferencial (USP):** {campaign_details['usp']}",
                        f"**Tom/Estilo Geral da Campanha:** {campaign_details['style_tone']}",
                        f"**KPIs Principais:** {specific_kpis}",
                        f"**Informações Adicionais/CTA Principal:** {campaign_details['extra_info']}",
                        "**Tarefa:** Elabore um plano de campanha que inclua:",
                        "1.  **Conceito Criativo Central:** Uma ideia ou tema que unifique a campanha.",
                        "2.  **Estrutura da Campanha:** Fases sugeridas (ex: Teaser, Lançamento, Sustentação, Última Chamada), se aplicável à duração.",
                        "3.  **Mix de Conteúdo por Plataforma:** Sugestões de 3-5 tipos diferentes de posts/ações para CADA plataforma selecionada (Ex: para Instagram: 1x Reels, 2x Carrossel, 3x Stories interativos. Para E-mail: 1x E-mail de anúncio, 1x E-mail de benefícios, 1x E-mail de prova social).",
                        "4.  **Sugestões de Criativos:** Ideias para visuais, vídeos, textos principais para alguns dos conteúdos chave.",
                        "5.  **Mini Calendário Editorial:** Um esboço de como distribuir os conteúdos ao longo da duração da campanha.",
                        "6.  **Estratégia de Hashtags (se aplicável).**",
                        "7.  **Recomendações para Impulsionamento:** Onde alocar o orçamento (se informado), que tipo de público impulsionar.",
                        "8.  **Como Mensurar os KPIs:** Sugestões de métricas específicas a acompanhar por plataforma.",
                        "9.  **Dicas de Otimização:** O que observar durante a campanha para fazer ajustes.",
                        "Se o usuário enviou arquivos de suporte, integre informações relevantes deles no plano."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_campaign_content = generated_content
        if 'generated_campaign_content' in st.session_state:
            display_output_options(st.session_state.generated_campaign_content, "campaign", "campanha_ia")

    elif main_action == "3 - Criar estrutura e conteúdo para landing page":
        st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
        st.caption("Crie uma Landing Page (LP) focada em conversão. A IA vai te ajudar com a estrutura e o copy.")
        with st.form("landing_page_form"):
            lp_purpose = st.text_input("Qual o principal objetivo da sua landing page? (Ex: Capturar leads para ebook, vender produto X, inscrição em webinar)", key="lp_purpose")
            lp_target_audience = st.text_input("Para quem é esta landing page? (Descreva a persona)", key="lp_audience")
            lp_main_offer = st.text_area("Qual é a oferta principal e irresistível da landing page?", key="lp_offer")
            lp_key_benefits = st.text_area("Quais são os 3-5 principais benefícios ou transformações que sua oferta proporciona?", placeholder="Use bullet points ou frases curtas.", key="lp_benefits")
            lp_cta = st.text_input("Qual é a chamada para ação (CTA) principal? (Ex: Baixar Ebook Grátis, Comprar Agora com Desconto, Quero me Inscrever)", key="lp_cta")
            lp_visual_prefs = st.text_input("Você tem alguma preferência de cores, estilo visual ou sites de referência para a LP? (Opcional)", key="lp_visual")
            submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da Landing Page!")

        if submitted_lp:
            if not lp_purpose or not lp_main_offer or not lp_cta:
                st.warning("Por favor, preencha o objetivo, a oferta principal e o CTA da landing page.")
            else:
                with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um especialista em UX/UI e copywriting, focado em criar landing pages de alta conversão para pequenas empresas.",
                        f"**Objetivo da Landing Page:** {lp_purpose}",
                        f"**Público-Alvo (Persona):** {lp_target_audience}",
                        f"**Oferta Principal:** {lp_main_offer}",
                        f"**Principais Benefícios da Oferta:** {lp_key_benefits}",
                        f"**Chamada para Ação (CTA) Principal:** {lp_cta}",
                        f"**Preferências Visuais/Referências:** {lp_visual_prefs}",
                        "**Tarefa:** Crie uma estrutura detalhada e sugestões de conteúdo (copy) para esta landing page. O resultado deve incluir:",
                        "1.  **Título Principal (Headline):** Sugira 2-3 variações de headlines magnéticas e focadas no benefício.",
                        "2.  **Subtítulo:** Um subtítulo que complemente a headline e reforce a proposta de valor.",
                        "3.  **Seção de Abertura/Problema:** Como introduzir o problema que a oferta resolve ou a oportunidade que ela apresenta.",
                        "4.  **Seção da Solução/Oferta:** Apresentação clara da oferta, destacando seus componentes.",
                        "5.  **Seção de Benefícios:** Detalhar os benefícios listados, talvez usando ícones (sugerir quais).",
                        "6.  **Seção de Prova Social:** Onde e como incluir depoimentos, estudos de caso, números de clientes, logos de parceiros (sugerir o que seria ideal).",
                        "7.  **Seção de CTA:** Reforçar o CTA principal e talvez um CTA secundário. Sugerir texto para o botão.",
                        "8.  **Elementos Adicionais (Opcional):** Sugerir se faria sentido incluir FAQ, Garantia, Selos de Segurança, etc.",
                        "9.  **Tom de Voz e Estilo de Copy:** Recomendações para o texto ser persuasivo para a persona indicada.",
                        "10. **Sugestões de Layout/Design:** Descrever brevemente como as seções poderiam ser organizadas visualmente e que tipo de imagens/ícones seriam mais eficazes (sem gerar a imagem, apenas descrever).",
                        "Se o usuário enviou arquivos de suporte, sugira como integrá-los (ex: 'usar a logo [nome_arquivo_logo.png] no cabeçalho')."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_lp_content = generated_content

        if 'generated_lp_content' in st.session_state:
            st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
            st.markdown(st.session_state.generated_lp_content)
            st.download_button(
                label="📥 Baixar Sugestões da Landing Page",
                data=st.session_state.generated_lp_content.encode('utf-8'),
                file_name="landing_page_sugestoes_ia.txt",
                mime="text/plain",
                key="download_lp"
            )

    elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
        st.subheader("🏗️ Arquiteto de Sites com IA")
        st.caption("Defina a base do seu site institucional ou e-commerce. A IA ajudará com páginas, seções e conteúdo inicial.")
        with st.form("site_creator_form"):
            site_business_type = st.text_input("Qual o tipo do seu negócio/empresa? (Ex: Loja de roupas, consultoria de TI, restaurante, profissional liberal)", key="site_biz_type")
            site_main_purpose = st.text_area("Qual o principal objetivo do seu site? (Ex: Vender produtos online, apresentar serviços e gerar orçamentos, ser um portfólio, construir autoridade com blog)", key="site_purpose")
            site_target_audience = st.text_input("Quem é o público principal que você quer atrair para o seu site?", key="site_audience")
            site_essential_pages = st.text_area("Quais páginas você considera essenciais para o seu site? (Ex: Home, Sobre Nós, Serviços/Produtos, Contato, Blog, FAQ, Loja)", key="site_pages", placeholder="Home, Sobre, Serviços, Contato")
            site_key_features = st.text_area("Quais são seus principais produtos, serviços ou diferenciais que o site deve destacar?", key="site_features")
            site_brand_personality = st.text_input("Como você descreveria a personalidade da sua marca? (Ex: Moderna e inovadora, tradicional e confiável, amigável e acessível, sofisticada e premium)", key="site_brand")
            site_visual_references = st.text_input("Tem alguma preferência de cores, estilo visual ou sites que você admira como referência? (Opcional)", key="site_visual_ref")
            submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")

        if submitted_site:
            if not site_business_type or not site_main_purpose:
                st.warning("Por favor, informe o tipo de negócio e o objetivo principal do site.")
            else:
                with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um arquiteto de informação e web designer conceitual, ajudando uma pequena empresa a planejar a estrutura e conteúdo de seu novo site.",
                        f"**Tipo de Negócio:** {site_business_type}",
                        f"**Objetivo Principal do Site:** {site_main_purpose}",
                        f"**Público-Alvo Principal:** {site_target_audience}",
                        f"**Páginas Essenciais Sugeridas pelo Usuário:** {site_essential_pages}",
                        f"**Principais Produtos/Serviços/Diferenciais a Destacar:** {site_key_features}",
                        f"**Personalidade da Marca:** {site_brand_personality}",
                        f"**Preferências Visuais/Referências:** {site_visual_references}",
                        "**Tarefa:** Desenvolva uma proposta de estrutura e conteúdo para o site. A proposta deve incluir:",
                        "1.  **Mapa do Site Sugerido:** Liste todas as páginas recomendadas (considerando as sugeridas pelo usuário e adicionando outras se crucial para o tipo de negócio/objetivo).",
                        "2.  **Para cada Página Principal (Home, Sobre, Serviços/Produtos, Contato, e 1-2 outras chave):**",
                        "    a.  **Objetivo Específico da Página.**",
                        "    b.  **Principais Seções/Blocos de Conteúdo dentro da página.** (Ex: Na Home: Hero section, Apresentação breve, Chamada para principais serviços, Depoimentos, CTA).",
                        "    c.  **Sugestões de Textos (Copy) para as seções mais importantes de cada página.**",
                        "    d.  **Tipos de Imagens ou Elementos Visuais recomendados para cada seção** (descrever, não gerar).",
                        "    e.  **Call-to-Actions (CTAs) relevantes para a página.**",
                        "3.  **Conceito Geral para o Design e Layout:** Com base na personalidade da marca e público, sugira um estilo (ex: minimalista, vibrante, corporativo) e como a navegação principal poderia funcionar.",
                        "4.  **Sugestão de Slogan/Tagline para o Site (opcional).**",
                        "5.  **Considerações sobre SEO On-Page:** Breves dicas de como otimizar o conteúdo das páginas para mecanismos de busca (palavras-chave, títulos).",
                        "Se o usuário enviou arquivos de suporte, sugira como incorporá-los (ex: 'a seção 'Nossa História' na página 'Sobre Nós' pode usar informações do arquivo [nome_arquivo_historia.docx]')."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para referência contextual):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_site_content = generated_content

        if 'generated_site_content' in st.session_state:
            st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
            st.markdown(st.session_state.generated_site_content)
            st.download_button(
                label="📥 Baixar Sugestões do Site",
                data=st.session_state.generated_site_content.encode('utf-8'),
                file_name="site_sugestoes_ia.txt",
                mime="text/plain",
                key="download_site"
            )

    elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
        st.subheader("🎯 Decodificador de Clientes com IA")
        st.caption("Entenda profundamente quem é seu cliente ideal e onde encontrá-lo. A IA simulará pesquisas e análises.")
        with st.form("find_client_form"):
            fc_product_campaign = st.text_area("Descreva brevemente o produto, serviço ou campanha para o qual você quer encontrar o cliente ideal:", key="fc_campaign")
            fc_location = st.text_input("Cidade(s) ou região de alcance principal da sua ação/negócio:", key="fc_location")
            fc_budget = st.text_input("Qual sua verba aproximada para esta ação/campanha? (Opcional, ex: R$300, R$1000)", key="fc_budget")
            fc_age_gender = st.text_input("Faixa etária e gênero predominante do público (Ex: 25-45 anos, ambos; 30-50 anos, mulheres):", key="fc_age_gender")
            fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades ou comportamentos do seu público-alvo:", key="fc_interests", placeholder="Ex: Amantes de café artesanal, preocupados com sustentabilidade, buscam soluções rápidas para X...")
            fc_current_channels = st.text_area("Quais canais de marketing você já utiliza ou considera para alcançar esse público?", key="fc_channels", placeholder="Ex: Instagram, Google Ads, Feiras locais")
            fc_deep_research = st.checkbox("Habilitar 'Deep Research' (A IA fará uma análise mais aprofundada, simulando pesquisa extensiva)", key="fc_deep")
            submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")

        if submitted_fc:
            if not fc_product_campaign:
                st.warning("Por favor, descreva o produto/serviço ou campanha.")
            else:
                with st.spinner("🕵️ A IA está investigando seu público-alvo... Isso pode levar alguns segundos."):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado. Sua missão é ajudar uma pequena empresa a encontrar e entender seu público-alvo exato.",
                        f"**Produto/Serviço/Campanha em Foco:** {fc_product_campaign}",
                        f"**Localização Principal:** {fc_location}",
                        f"**Verba de Marketing (Referência):** {fc_budget}",
                        f"**Faixa Etária e Gênero (Informado):** {fc_age_gender}",
                        f"**Interesses/Dores/Necessidades (Informado):** {fc_interests}",
                        f"**Canais Atuais/Considerados:** {fc_current_channels}",
                        f"**Nível de Pesquisa Solicitado:** {'Deep Research Ativado' if fc_deep_research else 'Pesquisa Padrão'}",
                        "**Tarefa:** Realize uma análise completa e forneça um relatório sobre o público-alvo ideal. O relatório deve incluir:",
                        "1.  **Definição da Persona Principal (e secundária, se aplicável):** Nome fictício, idade, gênero, ocupação, renda aproximada (se inferível), principais desafios, objetivos, como o produto/serviço do usuário ajuda.",
                        "2.  **Segmentação Detalhada para Anúncios:** Sugestões de interesses, comportamentos, dados demográficos para plataformas como Facebook/Instagram Ads e Google Ads.",
                        "3.  **Melhores Canais para Alcance:** Com base na persona e oferta, quais são os canais online e offline mais eficazes (incluindo redes sociais, blogs, fóruns, eventos, etc.).",
                        "4.  **Estratégia de Conteúdo para Atrair:** Que tipo de conteúdo essa persona consome e valoriza?",
                        "5.  **Melhor CPC/CPA Estimado (se possível inferir com base na verba e mercado).**",
                        "6.  **Sugestão de Impulsionamento:** Qual rede/canal priorizar para impulsionar e como configurar o público, considerando a verba (se informada).",
                        "**Se 'Deep Research' estiver ativo:**",
                        "   a.  **Insights Adicionais:** Comportamentos de compra, influenciadores que seguem, objeções comuns à compra, linguagem que utilizam.",
                        "   b.  **Simulação de Pesquisa Google:** Mencione 'Com base em tendências de busca no Google para [termos relevantes]...' ou 'Dados de mercado para [segmento] indicam que...'.",
                        "   c.  **Oportunidades Não Óbvias:** Nichos ou subgrupos dentro do público-alvo que podem ser explorados.",
                        "O objetivo é fornecer as melhores configurações de público-alvo possíveis dentro da verba do usuário, viabilizando vendas e otimizando o investimento."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para contexto sobre o negócio do usuário):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_client_analysis = generated_content

        if 'generated_client_analysis' in st.session_state:
            st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
            st.markdown(st.session_state.generated_client_analysis)
            st.download_button(
                label="📥 Baixar Análise de Público",
                data=st.session_state.generated_client_analysis.encode('utf-8'),
                file_name="analise_publico_alvo_ia.txt",
                mime="text/plain",
                key="download_client_analysis"
            )

    elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
        st.subheader("🧐 Radar da Concorrência com IA")
        st.caption("Analise seus concorrentes para identificar pontos fortes, fracos e oportunidades para o seu negócio.")
        with st.form("competitor_analysis_form"):
            ca_your_business = st.text_area("Descreva brevemente seu próprio negócio/produto para que a IA possa fazer uma comparação relevante:", key="ca_your_biz")
            ca_competitors_list = st.text_area("Liste seus principais concorrentes. Se possível, inclua nomes, sites ou perfis de redes sociais:", key="ca_competitors", placeholder="Ex: Concorrente Alfa (sitealfa.com, @alfa_insta), Empresa Beta (lojabeta.com.br), Dr. Gama (instagama.com/drgama)")
            ca_aspects_to_analyze = st.multiselect(
                "Quais aspectos da concorrência você gostaria que a IA analisasse principalmente?",
                [
                    "Presença Online (qualidade do site, atividade nas redes sociais)",
                    "Tipos de Conteúdo que publicam (temas, formatos)",
                    "Comunicação e Tom de Voz",
                    "Pontos Fortes Percebidos",
                    "Pontos Fracos ou Brechas Percebidas",
                    "Estratégia de Preços (se publicamente observável)",
                    "Engajamento do Público (comentários, curtidas - se observável)",
                    "Diferenciais Competitivos deles"
                ],
                default=["Presença Online (qualidade do site, atividade nas redes sociais)", "Pontos Fortes Percebidos", "Pontos Fracos ou Brechas Percebidas"],
                key="ca_aspects"
            )
            submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")

        if submitted_ca:
            if not ca_your_business or not ca_competitors_list:
                st.warning("Por favor, descreva seu negócio e liste pelo menos um concorrente.")
            else:
                with st.spinner("🔬 A IA está espionando eticamente a concorrência..."):
                    prompt_parts = [
                        "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em analisar o mercado e os concorrentes de pequenas empresas.",
                        f"**Negócio do Usuário (para Ponto de Referência):** {ca_your_business}",
                        f"**Concorrentes a Serem Analisados (Informados pelo Usuário):** {ca_competitors_list}",
                        f"**Principais Aspectos para Análise:** {', '.join(ca_aspects_to_analyze)}",
                        "**Tarefa:** Elabore um relatório breve e útil sobre os concorrentes listados, focando nos aspectos solicitados. O relatório deve:",
                        "1.  **Para cada Concorrente Principal (ou os 2-3 mais relevantes se a lista for longa):**",
                        "    a.  Um resumo da análise dos aspectos selecionados (ex: 'Presença Online: Site moderno, mas pouco ativo no Instagram. Conteúdo focado em X. Ponto forte: Preço agressivo. Ponto fraco: Atendimento ao cliente parece ser uma queixa comum online.').",
                        "2.  **Comparativo Geral:**",
                        "    a.  Quais são os principais pontos fortes consolidados da concorrência no geral?",
                        "    b.  Quais são as principais fraquezas ou brechas deixadas pela concorrência que o negócio do usuário poderia explorar?",
                        "3.  **Recomendações Estratégicas para o Usuário:**",
                        "    a.  Como o usuário pode se diferenciar com base na análise?",
                        "    b.  Que ações de marketing específicas o usuário pode tomar para se posicionar melhor em relação aos concorrentes?",
                        "Seja objetivo e forneça insights acionáveis. Simule pesquisa pública sobre os concorrentes (ex: 'Uma análise do site do Concorrente Alfa mostra que...', 'Observando o Instagram da Empresa Beta, nota-se que...')."
                    ]
                    if user_files_info:
                        prompt_parts.append(f"**Arquivos de Suporte Enviados (para contexto sobre o negócio do usuário):** {', '.join([f['name'] for f in user_files_info])}.")

                    final_prompt = "\n\n".join(prompt_parts)
                    generated_content = call_gemini_api(final_prompt, user_files_info)
                    st.session_state.generated_competitor_analysis = generated_content

        if 'generated_competitor_analysis' in st.session_state:
            st.subheader("📊 Análise da Concorrência e Insights:")
            st.markdown(st.session_state.generated_competitor_analysis)
            st.download_button(
                label="📥 Baixar Análise da Concorrência",
                data=st.session_state.generated_competitor_analysis.encode('utf-8'),
                file_name="analise_concorrencia_ia.txt",
                mime="text/plain",
                key="download_competitor_analysis"
            )

    elif main_action == "Selecione uma opção...":
        st.info("👋 Bem-vindo à seção de Marketing Digital com IA! Escolha uma das opções acima para começar a impulsionar seu negócio.")
        # st.image("https://via.placeholder.com/1260x300.png/007bff/FFFFFF?Text=Marketing+Digital+com+IA", caption="Vamos criar juntos estratégias incríveis!")


    st.markdown("---")
    st.caption("Assistente PME Pro - Marketing Digital com IA")


if __name__ == "__main__":
    st.set_page_config(page_title="PME Pro - Marketing Digital", layout="wide", initial_sidebar_state="expanded")
    
    # Bloco de inicialização do Gemini (placeholder, requer sua chave e configuração)
    # Mantenha comentado e configure conforme suas necessidades.
    # A inicialização real do 'genai' e 'model' deve ser feita aqui ou importada.
    # O código abaixo é uma sugestão de como lidar com isso.
    if 'gemini_model_initialized' not in st.session_state:
        st.session_state.gemini_model_initialized = False # Default
        # --- Exemplo de como você poderia inicializar ---
        # GOOGLE_API_KEY_FROM_CODE = "" # Coloque sua chave aqui se não usar os.getenv
        # api_key = os.getenv("GOOGLE_API_KEY") or GOOGLE_API_KEY_FROM_CODE
        # if api_key:
        #     try:
        #         genai.configure(api_key=api_key)
        #         model = genai.GenerativeModel('gemini-1.5-pro-latest') # Ou o modelo desejado
        #         st.session_state.gemini_model = model
        #         st.session_state.gemini_model_initialized = True
        #         # st.sidebar.success("Modelo Gemini pronto!") # Descomente para feedback
        #     except Exception as e:
        #         st.sidebar.error(f"Erro ao inicializar Gemini: {e}")
        #         st.session_state.gemini_model_initialized = False
        # else:
        #     st.sidebar.warning("Chave API Gemini não configurada.")
        #     st.session_state.gemini_model_initialized = False
        # Para este placeholder, vamos apenas simular que precisa ser configurado:
        if not st.session_state.gemini_model_initialized:
             st.sidebar.warning("Integração com IA (Gemini) não está ativa neste placeholder. Configure sua API Key.")


    marketing_digital_section()

    st.sidebar.markdown("---")
    st.sidebar.info("Desenvolvido por Yaakov Israel com AI Google")
