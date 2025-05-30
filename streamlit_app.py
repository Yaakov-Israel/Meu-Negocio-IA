import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth # NOVA IMPORTAÇÃO

# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- INÍCIO DA SEÇÃO DE AUTENTICAÇÃO FIREBASE ---
try:
    # Tenta carregar a configuração do Firebase dos segredos
    firebase_config = st.secrets["firebase_config"]
    
    # Inicializa o objeto de autenticação
    # Você pode adicionar um nome para o cookie e uma chave se quiser personalizar,
    # mas para começar, apenas a configuração do Firebase é suficiente.
    # Exemplo com cookie (se você criar uma seção [cookie_auth_firebase] nos seus segredos):
    # auth = st_auth.Authenticate(
    # firebase_config,
    # st.secrets["cookie_auth_firebase"]["name"],
    # st.secrets["cookie_auth_firebase"]["key"],
    # st.secrets["cookie_auth_firebase"]["expiry_days"],
    # )
    #
    # Para um início mais simples, focando apenas no login:
    auth = st_auth.Authenticate(config=firebase_config)

except KeyError as e:
    st.error(f"🚨 ERRO: Configuração '[firebase_config]' não encontrada nos Segredos (Secrets) do Streamlit. Detalhe: {e}")
    st.info("Adicione a seção [firebase_config] com todas as chaves (apiKey, authDomain, etc.) aos Segredos do seu app no painel do Streamlit Community Cloud.")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO ao inicializar o autenticador Firebase: {e}")
    st.stop()

# Renderiza o widget de login/registro e obtém o status
# O widget em si tem opções para "Login", "Register", "Forgot Password"
# e login com provedores (Google, se configurado e o componente suportar diretamente)
auth.login() # Isso vai renderizar o formulário de login e processar os dados

# Verificando o status da autenticação
if not st.session_state.get("authentication_status"):
    # Se não estiver autenticado, pode mostrar uma mensagem ou apenas deixar o formulário de login visível.
    # O próprio auth.login() já mostra o formulário, então não precisamos adicionar muito aqui
    # a menos que queira uma mensagem customizada.
    # st.info("Por favor, faça login ou registre-se para acessar o Assistente PME Pro.")
    st.stop() # Impede a execução do restante do app se não estiver logado

# Se chegou aqui, o usuário está autenticado
st.sidebar.success(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if auth.logout("Logout", "sidebar"): # Adiciona botão de logout na sidebar
    # A função logout retorna True se o botão foi clicado e o logout foi bem-sucedido
    # O próprio componente deve lidar com a limpeza do session_state relacionado à autenticação
    st.success("Logout realizado com sucesso!")
    st.experimental_rerun() # Força o re-run para voltar à tela de login

# --- FIM DA SEÇÃO DE AUTENTICAÇÃO FIREBASE ---


# O restante do seu código do app SÓ RODA SE O USUÁRIO ESTIVER AUTENTICADO
# (Devido ao st.stop() acima se não estiver autenticado)

# --- Carregar API Key e Configurar Modelo LLM ---
GOOGLE_API_KEY = None
llm_model_instance = None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError: # Este erro já foi tratado acima se firebase_config também estiver faltando
    if not firebase_config: # Só mostra se o erro da API key for o único
        st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
        st.info("Adicione sua GOOGLE_API_KEY aos Segredos do seu app no painel do Streamlit Community Cloud.")
        st.stop()
# A exceção FileNotFoundError é menos provável no Cloud, mas mantida por segurança
except FileNotFoundError: 
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        st.error("🚨 ERRO: Chave API não encontrada nos Segredos do Streamlit nem como variável de ambiente.")
        st.info("Configure GOOGLE_API_KEY nos Segredos do Streamlit Cloud ou defina como variável de ambiente local.")
        st.stop()

if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
    # Se firebase_config estava presente mas GOOGLE_API_KEY não, este erro será mostrado.
    # Se ambos faltarem, o erro do firebase_config (ou do auth init) aparecerá primeiro.
    if firebase_config: # Só mostra se o erro da API key é o problema principal agora
      st.error("🚨 ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
      st.stop()
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                 temperature=0.75,
                                                 google_api_key=GOOGLE_API_KEY,
                                                 convert_system_message_to_human=True) # Mantido por enquanto
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!") # Isso só aparecerá se o LLM iniciar após o login
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique sua chave API, se a 'Generative Language API' está ativa no Google Cloud e suas cotas.")
        st.stop()

# --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (Objetivos e Output) ---
# (Seu código de _marketing_get_objective_details, _marketing_display_output_options, etc. permanece aqui)
# ... seu código de funções de marketing ...
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = "_v15_final" 
    details["objective"] = st.text_area(
        f"Qual o principal objetivo com est(e/a) {type_of_creation}?",
        key=f"{section_key}_obj_new{key_suffix}" 
    )
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience_new{key_suffix}")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product_new{key_suffix}")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message_new{key_suffix}")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp_new{key_suffix}")
    details["style_tone"] = st.selectbox(
        "Qual o tom/estilo da comunicação?",
        ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"),
        key=f"{section_key}_tone_new{key_suffix}"
    )
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra_new{key_suffix}")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    key_suffix = "_v15_final"
    st.download_button(
        label="📥 Baixar Conteúdo Gerado",
        data=generated_content.encode('utf-8'),
        file_name=f"{file_name_prefix}_{section_key}_new.txt",
        mime="text/plain",
        key=f"download_{section_key}_new{key_suffix}"
    )
    cols_actions = st.columns(2)
    with cols_actions[0]:
        if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn_new{key_suffix}"):
            st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
            st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
    with cols_actions[1]:
        if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn_new{key_suffix}"):
            st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

# --- HANDLER FUNCTIONS ---
# CORREÇÃO DOS BUGS NAS CHAVES key_for_select_all_...
def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
    with st.spinner("🤖 A IA está criando seu post... Aguarde!"):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil. Sua tarefa é criar um post otimizado e engajador para as seguintes plataformas e objetivos. Considere as informações de suporte se fornecidas. Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes. Seja conciso e direto ao ponto, adaptando a linguagem para cada plataforma se necessário, mas mantendo a mensagem central. Se multiplas plataformas forem selecionadas, gere uma versão base e sugira pequenas adaptações para cada uma se fizer sentido, ou indique que o post pode ser usado de forma similar.",
            f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
            f"**Produto/Serviço Principal:** {details_dict['product_service']}",
            f"**Público-Alvo:** {details_dict['target_audience']}",
            f"**Objetivo do Post:** {details_dict['objective']}",
            f"**Mensagem Chave:** {details_dict['key_message']}",
            f"**Proposta Única de Valor (USP):** {details_dict['usp']}",
            f"**Tom/Estilo:** {details_dict['style_tone']}",
            f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
        ] 
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_post_content_new = ai_response.content

def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
    if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
    if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
    with st.spinner("🧠 A IA está elaborando seu plano de campanha..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um estrategista de marketing digital experiente, focado em PMEs no Brasil. Desenvolva um plano de campanha de marketing conciso e acionável com base nas informações fornecidas. O plano deve incluir: 1. Conceito da Campanha (Tema Central). 2. Sugestões de Conteúdo Chave para cada plataforma selecionada. 3. Um cronograma geral sugerido (Ex: Semana 1 - Teaser, Semana 2 - Lançamento, etc.). 4. Métricas chave para acompanhar o sucesso. Considere as informações de suporte, se fornecidas.",
            f"**Nome da Campanha:** {campaign_specifics['name']}",
            f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
            f"**Produto/Serviço Principal da Campanha:** {details_dict['product_service']}",
            f"**Público-Alvo da Campanha:** {details_dict['target_audience']}",
            f"**Objetivo Principal da Campanha:** {details_dict['objective']}",
            f"**Mensagem Chave da Campanha:** {details_dict['key_message']}",
            f"**USP do Produto/Serviço na Campanha:** {details_dict['usp']}",
            f"**Tom/Estilo da Campanha:** {details_dict['style_tone']}",
            f"**Duração Estimada:** {campaign_specifics['duration']}",
            f"**Orçamento Aproximado (se informado):** {campaign_specifics['budget']}",
            f"**KPIs mais importantes:** {campaign_specifics['kpis']}",
            f"**Informações Adicionais/CTA da Campanha:** {details_dict['extra_info']}"
        ] 
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt))
        st.session_state.generated_campaign_content_new = ai_response.content

def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
    if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
    with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages de alta conversão, com foco em PMEs no Brasil. Baseado nos detalhes fornecidos, crie uma estrutura detalhada e sugestões de texto (copy) para cada seção de uma landing page. Inclua seções como: Cabeçalho (Headline, Sub-headline), Problema/Dor, Apresentação da Solução/Produto, Benefícios Chave, Prova Social (Depoimentos), Oferta Irresistível, Chamada para Ação (CTA) clara e forte, Garantia (se aplicável), FAQ. Considere as informações de suporte, se fornecidas.",
            f"**Objetivo da Landing Page:** {lp_details['purpose']}",
            f"**Público-Alvo (Persona):** {lp_details['target_audience']}",
            f"**Oferta Principal:** {lp_details['main_offer']}",
            f"**Principais Benefícios/Transformações da Oferta:** {lp_details['key_benefits']}",
            f"**Chamada para Ação (CTA) Principal:** {lp_details['cta']}",
            f"**Preferências Visuais/Referências (se houver):** {lp_details['visual_prefs']}"
        ]
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_lp_content_new = generated_content

def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
    if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
    with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um arquiteto de informação e web designer experiente, focado em criar sites eficazes para PMEs no Brasil. Desenvolva uma proposta de estrutura de site (mapa do site com principais páginas e seções dentro de cada página) e sugestões de conteúdo chave para cada seção. Considere as informações de suporte, se fornecidas.",
            f"**Tipo de Negócio/Empresa:** {site_details['business_type']}",
            f"**Principal Objetivo do Site:** {site_details['main_purpose']}",
            f"**Público-Alvo Principal:** {site_details['target_audience']}",
            f"**Páginas Essenciais Desejadas:** {site_details['essential_pages']}",
            f"**Principais Produtos/Serviços/Diferenciais a serem destacados:** {site_details['key_features']}",
            f"**Personalidade da Marca:** {site_details['brand_personality']}",
            f"**Preferências Visuais/Referências (se houver):** {site_details['visual_references']}"
        ]
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_site_content_new = generated_content

def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
    if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
    with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
        prompt_parts = [
             "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado para PMEs no Brasil. Sua tarefa é realizar uma análise completa do público-alvo com base nas informações fornecidas e gerar um relatório detalhado com os seguintes itens: 1. Persona Detalhada (Nome fictício, Idade, Profissão, Dores, Necessidades, Sonhos, Onde busca informação). 2. Sugestões de Canais de Marketing mais eficazes para alcançar essa persona. 3. Sugestões de Mensagens Chave e Ângulos de Comunicação que ressoem com essa persona. 4. Se 'Deep Research' estiver ativado, inclua insights adicionais sobre comportamento online, tendências e micro-segmentos. Considere as informações de suporte, se fornecidas.",
            f"**Produto/Serviço ou Campanha para Análise:** {client_details['product_campaign']}",
            f"**Localização Geográfica (Cidade(s), Região):** {client_details['location']}",
            f"**Verba Aproximada para Ação/Campanha (se aplicável):** {client_details['budget']}",
            f"**Faixa Etária e Gênero Predominante (se souber):** {client_details['age_gender']}",
            f"**Principais Interesses, Hobbies, Dores, Necessidades do Público Desejado:** {client_details['interests']}",
            f"**Canais de Marketing que já utiliza ou considera:** {client_details['current_channels']}",
            f"**Nível de Pesquisa:** {'Deep Research Ativado (análise mais aprofundada)' if client_details['deep_research'] else 'Pesquisa Padrão'}"
        ]
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_client_analysis_new = generated_content

def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
    if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
    with st.spinner("🔬 A IA está analisando a concorrência..."):
        prompt_parts = [
            "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em análise de mercado para PMEs no Brasil. Com base nas informações do negócio do usuário e da lista de concorrentes, elabore um relatório breve e útil. Para cada concorrente listado (ou os principais, se a lista for longa), analise os 'Aspectos para Análise' selecionados. Destaque os pontos fortes e fracos de cada um em relação a esses aspectos e, ao final, sugira 2-3 oportunidades ou diferenciais que o negócio do usuário pode explorar. Considere as informações de suporte, se fornecidas.",
            f"**Negócio do Usuário (para comparação):** {competitor_details['your_business']}",
            f"**Concorrentes (nomes, sites, redes sociais, se possível):** {competitor_details['competitors_list']}",
            f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"
        ]
        if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
        final_prompt = "\n\n".join(prompt_parts)
        ai_response = llm.invoke(HumanMessage(content=final_prompt)); generated_content = ai_response.content
        st.session_state.generated_competitor_analysis_new = generated_content


# --- Classe do Agente (AssistentePMEPro) ---
class AssistentePMEPro:
    def __init__(self, llm_passed_model):
        if llm_passed_model is None:
            st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
            st.stop()
        self.llm = llm_passed_model
        # Inicializa memórias para cada chat
        if 'memoria_plano_negocios' not in st.session_state:
            st.session_state.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat_plano", return_messages=True)
        if 'memoria_calculo_precos' not in st.session_state:
            st.session_state.memoria_calculo_precos = ConversationBufferMemory(memory_key="historico_chat_precos", return_messages=True)
        if 'memoria_gerador_ideias' not in st.session_state:
            st.session_state.memoria_gerador_ideias = ConversationBufferMemory(memory_key="historico_chat_ideias", return_messages=True)
        
        self.memoria_plano_negocios = st.session_state.memoria_plano_negocios
        self.memoria_calculo_precos = st.session_state.memoria_calculo_precos
        self.memoria_gerador_ideias = st.session_state.memoria_gerador_ideias


    def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder="historico_chat"):
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

        marketing_files_info_for_prompt = [] # Este deve ser local para a função
        with st.sidebar: 
            st.subheader("📎 Suporte para Marketing")
            uploaded_marketing_files = st.file_uploader(
                "Upload para Marketing (opcional):",
                accept_multiple_files=True,
                type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx', 'mp4', 'mov'],
                key="marketing_files_uploader_v15_final" 
            )
            if uploaded_marketing_files:
                temp_marketing_files_info = []
                for up_file in uploaded_marketing_files:
                    temp_marketing_files_info.append({"name": up_file.name, "type": up_file.type, "size": up_file.size})
                if temp_marketing_files_info:
                    marketing_files_info_for_prompt = temp_marketing_files_info # Atribui aqui
                    st.success(f"{len(uploaded_marketing_files)} arquivo(s) de marketing carregado(s)!")
                    with st.expander("Ver arquivos de marketing"):
                        for finfo in marketing_files_info_for_prompt:
                            st.write(f"- {finfo['name']} ({finfo['type']})")
            st.markdown("---")

        main_action_key = "main_marketing_action_choice_v15_final"
        main_action = st.radio(
            "Olá! O que você quer fazer agora em marketing digital?",
            ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
             "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
             "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
             "6 - Conhecer a concorrência (Análise Competitiva)"),
            index=0, key=main_action_key
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
            with st.form("post_creator_form_v15_final"):
                st.subheader(" Plataformas Desejadas:")
                
                key_select_all_post = f"post_v15_select_all" # Definido aqui
                select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_post)
                
                cols_post = st.columns(2)
                keys_for_platforms_post = {} 
                has_email_option_post = False
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                    col_index = i % 2
                    platform_key = f"post_v15_platform_{platform_suffix}" 
                    keys_for_platforms_post[platform_name] = platform_key
                    with cols_post[col_index]:
                        st.checkbox(platform_name, key=platform_key, value=select_all_post_checked) # Propaga o valor do "select all"
                    if "E-mail Marketing" in platform_name: has_email_option_post = True
                if has_email_option_post: st.caption("💡 Para e-mail marketing, considere segmentar sua lista e personalizar a saudação.")

                post_details = _marketing_get_objective_details("post_v15", "post")
                submit_button_pressed_post = st.form_submit_button("💡 Gerar Post!")

            if submit_button_pressed_post:
                actual_selected_platforms = []
                if select_all_post_checked: # Usa o valor do checkbox diretamente
                    actual_selected_platforms = platform_names_available_list
                else:
                    for p_name, p_key in keys_for_platforms_post.items():
                        if st.session_state.get(p_key, False):
                            actual_selected_platforms.append(p_name)
                _marketing_handle_criar_post(marketing_files_info_for_prompt, post_details, actual_selected_platforms, self.llm)

            if 'generated_post_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_new, "post_v15", "post_ia")

        elif main_action == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            with st.form("campaign_creator_form_v15_final"):
                campaign_name = st.text_input("Nome da Campanha:", key="campaign_name_new_v15")
                st.subheader(" Plataformas Desejadas:")

                key_select_all_camp = f"campaign_v15_select_all" # Definido aqui
                select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_camp)

                cols_camp = st.columns(2)
                keys_for_platforms_camp = {}
                has_email_option_camp = False
                for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                    col_index = i % 2
                    platform_key = f"campaign_v15_platform_{platform_suffix}"
                    keys_for_platforms_camp[platform_name] = platform_key
                    with cols_camp[col_index]:
                        st.checkbox(platform_name, key=platform_key, value=select_all_camp_checked) # Propaga o valor
                    if "E-mail Marketing" in platform_name: has_email_option_camp = True
                if has_email_option_camp: st.caption("💡 Para e-mail marketing, defina bem seus segmentos e personalize as mensagens.")
                
                campaign_details_obj = _marketing_get_objective_details("campaign_v15", "campanha")
                campaign_duration = st.text_input("Duração Estimada:", key="campaign_duration_new_v15")
                campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key="campaign_budget_new_v15")
                specific_kpis = st.text_area("KPIs mais importantes:", key="campaign_kpis_new_v15")
                submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_button_pressed_camp:
                actual_selected_platforms_camp = []
                if select_all_camp_checked: # Usa o valor do checkbox diretamente
                    actual_selected_platforms_camp = platform_names_available_list
                else:
                    for p_name, p_key in keys_for_platforms_camp.items():
                        if st.session_state.get(p_key, False):
                            actual_selected_platforms_camp.append(p_name)
                
                campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration,
                                           "budget": campaign_budget_approx, "kpis": specific_kpis}
                _marketing_handle_criar_campanha(marketing_files_info_for_prompt, campaign_details_obj, campaign_specifics_dict, actual_selected_platforms_camp, self.llm)

            if 'generated_campaign_content_new' in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_new, "campaign_v15", "campanha_ia")
        
        elif main_action == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            with st.form("landing_page_form_new_v15"):
                lp_purpose = st.text_input("Principal objetivo da landing page:", key="lp_purpose_new_v15")
                lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key="lp_audience_new_v15")
                lp_main_offer = st.text_area("Oferta principal e irresistível:", key="lp_offer_new_v15")
                lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key="lp_benefits_new_v15")
                lp_cta = st.text_input("Chamada para ação (CTA) principal:", key="lp_cta_new_v15")
                lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key="lp_visual_new_v15")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")
            if submitted_lp:
                lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                _marketing_handle_criar_landing_page(marketing_files_info_for_prompt, lp_details_dict, self.llm)
            if 'generated_lp_content_new' in st.session_state:
                st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                st.markdown(st.session_state.generated_lp_content_new)
                st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state.generated_lp_content_new.encode('utf-8'), file_name="landing_page_sugestoes_ia_new.txt", mime="text/plain", key="download_lp_new_v15") 

        elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
            st.subheader("🏗️ Arquiteto de Sites com IA")
            with st.form("site_creator_form_new_v15"): 
                site_business_type = st.text_input("Tipo do seu negócio/empresa:", key="site_biz_type_new_v15")
                site_main_purpose = st.text_area("Principal objetivo do seu site:", key="site_purpose_new_v15")
                site_target_audience = st.text_input("Público principal do site:", key="site_audience_new_v15")
                site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key="site_pages_new_v15")
                site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key="site_features_new_v15")
                site_brand_personality = st.text_input("Personalidade da sua marca:", key="site_brand_new_v15")
                site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key="site_visual_ref_new_v15")
                submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")
            if submitted_site:
                site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                _marketing_handle_criar_site(marketing_files_info_for_prompt, site_details_dict, self.llm)
            if 'generated_site_content_new' in st.session_state:
                st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                st.markdown(st.session_state.generated_site_content_new)
                st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state.generated_site_content_new.encode('utf-8'), file_name="site_sugestoes_ia_new.txt", mime="text/plain",key="download_site_new_v15")

        elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
            st.subheader("🎯 Decodificador de Clientes com IA")
            with st.form("find_client_form_new_v15"):
                fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key="fc_campaign_new_v15")
                fc_location = st.text_input("Cidade(s) ou região de alcance:", key="fc_location_new_v15")
                fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key="fc_budget_new_v15")
                fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key="fc_age_gender_new_v15")
                fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key="fc_interests_new_v15")
                fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key="fc_channels_new_v15")
                fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key="fc_deep_new_v15")
                submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")
            if submitted_fc:
                client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                _marketing_handle_encontre_cliente(marketing_files_info_for_prompt, client_details_dict, self.llm)
            if 'generated_client_analysis_new' in st.session_state:
                st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                st.markdown(st.session_state.generated_client_analysis_new)
                st.download_button(label="📥 Baixar Análise de Público",data=st.session_state.generated_client_analysis_new.encode('utf-8'), file_name="analise_publico_alvo_ia_new.txt", mime="text/plain",key="download_client_analysis_new_v15")
        
        elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
            st.subheader("🧐 Radar da Concorrência com IA")
            with st.form("competitor_analysis_form_new_v15"):
                ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key="ca_your_biz_new_v15")
                ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key="ca_competitors_new_v15")
                ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key="ca_aspects_new_v15")
                submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")
            if submitted_ca:
                competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt, competitor_details_dict, self.llm)
            if 'generated_competitor_analysis_new' in st.session_state:
                st.subheader("📊 Análise da Concorrência e Insights:")
                st.markdown(st.session_state.generated_competitor_analysis_new)
                st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state.generated_competitor_analysis_new.encode('utf-8'), file_name="analise_concorrencia_ia_new.txt",mime="text/plain",key="download_competitor_analysis_new_v15")

        elif main_action == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            logo_url_marketing_welcome = "https://i.imgur.com/7IIYxq1.png" # Manteve o link da imagem anterior
            st.image(logo_url_marketing_welcome, caption="Assistente PME Pro", width=200)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..." # Exemplo, prompt completo omitido
        cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder="historico_chat_plano")
        resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_content = f"O usuário pergunta sobre cálculo de preços: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_content = f"{descricao_imagem_contexto}\n\n{prompt_content}"
        
        system_message_precos = f"""Você é o "Assistente PME Pro", especialista em precificação com IA... {prompt_content}""" # Exemplo, prompt completo omitido
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="historico_chat_precos")
        # Para o cálculo de preços, a "entrada do usuário" já está no system_message_precos
        # Podemos passar um input_usuario mais genérico ou uma confirmação.
        # Ou ajustar _criar_cadeia_conversacional para não exigir {input_usuario} se o prompt for construído dinamicamente.
        # Por simplicidade agora, vamos assumir que o prompt_usuario complementa.
        resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base nisso, quais são suas recomendações de preço?"}) 
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_content = f"O usuário busca ideias de negócios e diz: '{input_usuario}'."
        if contexto_arquivos:
            prompt_content = f"Considerando os seguintes arquivos e contextos fornecidos pelo usuário:\n{contexto_arquivos}\n\n{prompt_content}"

        system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios especialista em IA... {prompt_content}""" # Exemplo
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="historico_chat_ideias")
        resposta_ai_obj = cadeia.invoke({"input_usuario": "Quais ideias você sugere com base nisso?"})
        return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

# --- Funções Utilitárias de Chat ---
def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
    chat_display_key = f"chat_display_{area_chave}"
    st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
    if memoria_agente_instancia:
        memoria_agente_instancia.clear()
        # Adiciona a mensagem inicial à memória para que a IA tenha o contexto de início
        if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
            memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
        elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
             memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))

    # Resetar estados específicos da seção ao reiniciar o chat
    if area_chave == "calculo_precos": 
        st.session_state.last_uploaded_image_info_pricing = None
        st.session_state.processed_image_id_pricing = None
        st.session_state.user_input_processed_pricing = False # Garante que não tentará limpar na próxima renderização sem novo input
    elif area_chave == "gerador_ideias": 
        st.session_state.uploaded_file_info_ideias_for_prompt = None
        st.session_state.processed_file_id_ideias = None
        st.session_state.user_input_processed_ideias = False


def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
    chat_display_key = f"chat_display_{area_chave}"
    if chat_display_key not in st.session_state: 
        # Se o chat não foi inicializado por alguma razão (ex: navegação direta sem passar pela inicialização),
        # pode ser necessário adicionar uma mensagem padrão ou forçar a inicialização.
        # Por ora, vamos assumir que inicializar_ou_resetar_chat foi chamado.
        st.session_state[chat_display_key] = [] 

    for msg_info in st.session_state[chat_display_key]:
        with st.chat_message(msg_info["role"]): 
            st.markdown(msg_info["content"])
    
    prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}_v15_final")
    
    if prompt_usuario:
        st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"): 
            st.markdown(prompt_usuario)
        
        # Marcar que o input do usuário foi processado para seções específicas
        if area_chave == "calculo_precos": st.session_state.user_input_processed_pricing = True
        elif area_chave == "gerador_ideias": st.session_state.user_input_processed_ideias = True
            
        with st.spinner("Assistente PME Pro está processando... 🤔"):
            resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
        st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
        st.rerun()

# --- Interface Principal Streamlit (APÓS LOGIN BEM-SUCEDIDO) ---
# Esta parte só será executada se llm_model_instance for definido E o usuário estiver autenticado
if llm_model_instance: # Garante que o LLM foi carregado antes de tentar usar o agente
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
    agente = st.session_state.agente_pme

    # LOGO E TÍTULO DA SIDEBAR (Só aparecem após login, dentro da área protegida)
    URL_DO_SEU_LOGO = "https://i.imgur.com/7IIYxq1.png" # Considere usar a logo local: "images/logo-pme-ia.png"
    st.sidebar.image(URL_DO_SEU_LOGO, width=150) # Ajuste o tamanho se necessário
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
    
    # Assegura que as chaves de chat display existem antes do radio button
    for nome_menu_init, chave_secao_init in opcoes_menu.items():
        if f"chat_display_{chave_secao_init}" not in st.session_state:
            st.session_state[f"chat_display_{chave_secao_init}"] = []
    
    if 'previous_area_selecionada_for_chat_init_processed_v15' not in st.session_state:
        st.session_state['previous_area_selecionada_for_chat_init_processed_v15'] = None

    # Atualiza o índice do radio button para refletir a seleção atual em st.session_state
    current_selection_index = 0 # Padrão para "Página Inicial"
    if st.session_state.area_selecionada in opcoes_menu:
        current_selection_index = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)

    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?", 
        options=list(opcoes_menu.keys()), 
        key='sidebar_selection_v25_final', 
        index=current_selection_index
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        # Lógica para limpar o estado de marketing ao sair dessa seção
        if area_selecionada_label != "Marketing Digital com IA (Guia)":
            for key_to_clear in list(st.session_state.keys()):
                if key_to_clear.startswith("generated_") and key_to_clear.endswith("_new"):
                    del st.session_state[key_to_clear]
                # Limpa estado dos checkboxes de plataforma também
                if key_to_clear.startswith("post_v15_platform_") or \
                   key_to_clear.startswith("campaign_v15_platform_") or \
                   key_to_clear == "post_v15_select_all" or \
                   key_to_clear == "campaign_v15_select_all":
                    if st.session_state.get(key_to_clear) is not None:
                        del st.session_state[key_to_clear]
        st.rerun()

    current_section_key = opcoes_menu.get(st.session_state.area_selecionada)

    # Lógica de inicialização de chat para seções conversacionais
    if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
        # Se a área mudou E não é uma das que não precisa de reset de chat na navegação
        if st.session_state.area_selecionada != st.session_state.get('previous_area_selecionada_for_chat_init_processed_v15'):
            chat_display_key_nav = f"chat_display_{current_section_key}"
            # Inicializa ou reseta o chat se ele não existir ou estiver vazio
            if chat_display_key_nav not in st.session_state or not st.session_state[chat_display_key_nav]:
                msg_inicial_nav = ""
                memoria_agente_nav = None
                if current_section_key == "plano_negocios": 
                    msg_inicial_nav = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia de negócio, seus principais produtos/serviços, e quem você imagina como seus clientes."
                    memoria_agente_nav = agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": 
                    msg_inicial_nav = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começarmos, por favor, descreva o produto ou serviço para o qual você gostaria de ajuda para precificar. Se tiver uma imagem, pode enviá-la também."
                    memoria_agente_nav = agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": 
                    msg_inicial_nav = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Você pode me descrever um desafio, uma área que quer inovar, ou simplesmente pedir sugestões. Se tiver algum arquivo de contexto (texto ou imagem), pode enviar também."
                    memoria_agente_nav = agente.memoria_gerador_ideias
                
                if msg_inicial_nav and memoria_agente_nav is not None: # Verifica se memoria_agente_nav não é None
                    inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
            # Atualiza a área processada para evitar re-inicializações desnecessárias no mesmo rerun
            st.session_state['previous_area_selecionada_for_chat_init_processed_v15'] = st.session_state.area_selecionada


    if current_section_key == "pagina_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        # Usando a mesma logo da landing page, mas idealmente uma versão local
        # Se a logo da landing page está em 'images/logo-pme-ia.png' no repo da LANDING PAGE,
        # para o app Streamlit, você precisaria ter essa imagem no repo do APP STREAMLIT
        # ou usar uma URL pública. Vou manter o Imgur por enquanto, mas o ideal é padronizar.
        st.markdown(f"<div style='text-align: center;'><img src='{URL_DO_SEU_LOGO}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        num_botoes_funcionais = len(opcoes_menu) -1 # Exclui "Página Inicial"
        if num_botoes_funcionais > 0 :
            # Organiza os botões em colunas, tentando não exceder 3 ou 4 colunas
            num_cols_render = min(num_botoes_funcionais, 3) 
            cols_botoes_pg_inicial = st.columns(num_cols_render)
            btn_idx_pg_inicial = 0
            for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                if chave_secao_btn_pg != "pagina_inicial":
                    col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                    # Simplifica o label do botão
                    button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                    if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}_v15_final", use_container_width=True, help=f"Ir para {nome_menu_btn_pg}"):
                        st.session_state.area_selecionada = nome_menu_btn_pg
                        st.rerun()
                    btn_idx_pg_inicial +=1
            st.balloons()

    elif current_section_key == "marketing_guiado": 
        agente.marketing_digital_guiado()
    elif current_section_key == "plano_negocios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias. Forneça o máximo de detalhes possível.")
        exibir_chat_e_obter_input(current_section_key, "Sua resposta ou próxima seção do plano...", agente.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Histórico do Plano", key="btn_reset_plano_v15_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos recomeçar o seu Plano de Negócios. Sobre qual aspecto você gostaria de falar primeiro?", agente.memoria_plano_negocios)
            st.rerun()
    elif current_section_key == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar. O assistente te guiará na definição de preços.")
        uploaded_image = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_img_uploader_v15_final")
        
        descricao_imagem_para_ia = None 
        if uploaded_image is not None:
            if st.session_state.get('processed_image_id_pricing') != uploaded_image.id:
                try:
                    img_pil = Image.open(uploaded_image) 
                    st.image(img_pil, caption=f"Imagem: {uploaded_image.name}", width=150)
                    descricao_imagem_para_ia = f"O usuário carregou uma imagem chamada '{uploaded_image.name}'. Considere esta informação visualmente e contextualmente."
                    st.session_state.last_uploaded_image_info_pricing = descricao_imagem_para_ia
                    st.session_state.processed_image_id_pricing = uploaded_image.id
                    st.info(f"Imagem '{uploaded_image.name}' pronta para ser considerada no próximo diálogo.")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {e}")
                    st.session_state.last_uploaded_image_info_pricing = None
                    st.session_state.processed_image_id_pricing = None
            else: 
                 descricao_imagem_para_ia = st.session_state.get('last_uploaded_image_info_pricing')

        kwargs_preco_chat = {}
        # Usa a descrição da imagem que foi definida nesta renderização OU da sessão se o input do usuário ainda não foi processado para ela
        # A ideia é que a descrição da imagem seja enviada JUNTO com o input do usuário que se refere a ela.
        contexto_imagem_para_proximo_dialogo = st.session_state.get('last_uploaded_image_info_pricing')
        if contexto_imagem_para_proximo_dialogo and not st.session_state.get('user_input_processed_pricing', False):
            kwargs_preco_chat['descricao_imagem_contexto'] = contexto_imagem_para_proximo_dialogo
        
        exibir_chat_e_obter_input(current_section_key, "Descreva o produto/serviço, custos, etc.", agente.calcular_precos_interativo, **kwargs_preco_chat)
        
        if 'user_input_processed_pricing' in st.session_state and st.session_state.user_input_processed_pricing:
            if st.session_state.get('last_uploaded_image_info_pricing'): 
                st.session_state.last_uploaded_image_info_pricing = None # Limpa para que não seja enviado novamente sem uma nova imagem ou novo contexto de input
            st.session_state.user_input_processed_pricing = False

        if st.sidebar.button("🗑️ Limpar Histórico de Preços", key="btn_reset_precos_v15_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar um novo cálculo de preços! Descreva seu produto ou serviço.", agente.memoria_calculo_precos)
            st.rerun()

    elif current_section_key == "gerador_ideias":
        st.header("💡 Gerador de Ideias para seu Negócio com IA")
        st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
        uploaded_files_ideias_ui = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key="ideias_file_uploader_v15_final")
        
        contexto_para_ia_ideias_local = None
        if uploaded_files_ideias_ui:
            current_file_signature = "-".join(sorted([f"{f.name}-{f.size}" for f in uploaded_files_ideias_ui]))
            if st.session_state.get('processed_file_id_ideias') != current_file_signature or not st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                text_contents_ui = []
                image_info_ui = []
                image_objects_for_prompt = [] # Para o futuro, se o modelo puder aceitar objetos de imagem diretamente com Langchain

                for uploaded_file_item in uploaded_files_ideias_ui:
                    try:
                        if uploaded_file_item.type == "text/plain": 
                            text_contents_ui.append(f"Conteúdo do arquivo de texto '{uploaded_file_item.name}':\n{uploaded_file_item.read().decode('utf-8')[:3000]}...") # Limita para não sobrecarregar
                        elif uploaded_file_item.type in ["image/png", "image/jpeg"]: 
                            st.image(Image.open(uploaded_file_item), caption=f"Contexto Visual: {uploaded_file_item.name}", width=100)
                            image_info_ui.append(f"Uma imagem chamada '{uploaded_file_item.name}' foi fornecida como contexto visual.")
                            # Se o modelo e Langchain suportarem, poderíamos tentar passar a imagem:
                            # image_objects_for_prompt.append(Image.open(uploaded_file_item))
                    except Exception as e: st.error(f"Erro ao processar o arquivo '{uploaded_file_item.name}': {e}")
                
                full_context_ui_str = ""
                if text_contents_ui: full_context_ui_str += "\n\n--- CONTEÚDO TEXTUAL DOS ARQUIVOS ---\n" + "\n\n".join(text_contents_ui)
                if image_info_ui: full_context_ui_str += "\n\n--- DESCRIÇÃO DAS IMAGENS FORNECIDAS ---\n" + "\n".join(image_info_ui)
                
                if full_context_ui_str: 
                    st.session_state.uploaded_file_info_ideias_for_prompt = full_context_ui_str.strip()
                    contexto_para_ia_ideias_local = st.session_state.uploaded_file_info_ideias_for_prompt
                    st.info("Arquivo(s) de contexto pronto(s) para o próximo diálogo.")
                else: 
                    st.session_state.uploaded_file_info_ideias_for_prompt = None
                st.session_state.processed_file_id_ideias = current_file_signature
            else: 
                contexto_para_ia_ideias_local = st.session_state.get('uploaded_file_info_ideias_for_prompt')
        
        kwargs_ideias_chat_ui = {}
        if contexto_para_ia_ideias_local and not st.session_state.get('user_input_processed_ideias', False) : 
            kwargs_ideias_chat_ui['contexto_arquivos'] = contexto_para_ia_ideias_local
        
        exibir_chat_e_obter_input(current_section_key, "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, **kwargs_ideias_chat_ui)
        
        if 'user_input_processed_ideias' in st.session_state and st.session_state.user_input_processed_ideias:
            if st.session_state.get('uploaded_file_info_ideias_for_prompt'):
                 st.session_state.uploaded_file_info_ideias_for_prompt = None # Limpa para não reenviar sem novo upload/contexto
            st.session_state.user_input_processed_ideias = False

        if st.sidebar.button("🗑️ Limpar Histórico de Ideias", key="btn_reset_ideias_v15_final"):
            inicializar_ou_resetar_chat(current_section_key, "Ok, vamos começar uma nova sessão de geração de ideias! Qual o seu ponto de partida?", agente.memoria_gerador_ideias)
            st.rerun()

else: # Se llm_model_instance não foi definido (ex: falha na API key)
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM nas configurações.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com IA Gemini 2.5 pro")
