import streamlit as st
import os 
import json 
import pyrebase 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image # Para o logo na sidebar

# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀" 
)
# O st.title() será definido dentro das seções para ser dinâmico.
# --- Inicialização do Firebase ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False
auth_exception_object = None # Para armazenar o objeto de exceção para st.exception

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]

        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
        else:
            if 'firebase_app_instance' not in st.session_state: 
                st.session_state.firebase_app_instance = pyrebase.initialize_app(plain_firebase_config_dict)
            
            firebase_app = st.session_state.firebase_app_instance
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_success_message_shown' not in st.session_state and not st.session_state.get('user_session_pyrebase'):
                 st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                 st.session_state.firebase_init_success_message_shown = True

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb}"
    auth_exception_object = e_attr_fb
except Exception as e_general_fb: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb}"
    auth_exception_object = e_general_fb

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object and ('st' in locals() or 'st' in globals()):
        st.exception(auth_exception_object)
    st.stop()

if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None) 
    except Exception as e_session: 
        error_message_session_check = "Sessão inválida ou expirada."
        try:
            error_details_str = e_session.args[0] if len(e_session.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\"")) 
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check = f"Erro ao verificar sessão ({api_error_message}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): 
            error_message_session_check = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session)}"
        
        st.session_state.user_session_pyrebase = None 
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state: 
            st.sidebar.warning(error_message_session_check)
            st.session_state.auth_error_shown = True
        
        # Controle de rerun para evitar loops infinitos
        session_rerun_key = 'running_rerun_after_auth_fail_v3' # Nova chave para esta versão
        if not st.session_state.get(session_rerun_key, False):
            st.session_state[session_rerun_key] = True
            st.rerun()
        else:
            st.session_state.pop(session_rerun_key, None)

# Limpeza da flag de rerun se ela existir e o código continuar
session_rerun_key_check = 'running_rerun_after_auth_fail_v3'
if session_rerun_key_check in st.session_state and st.session_state[session_rerun_key_check]:
    st.session_state.pop(session_rerun_key_check, None)
    # Se um rerun foi forçado, pode ser necessário parar a execução aqui
    # para evitar que o resto da UI seja renderizado incorretamente antes do rerun.
    # No entanto, o rerun deve acontecer antes de chegar aqui na próxima execução.
    # Se a flag ainda estiver aqui, é uma situação estranha, mas vamos limpá-la.
# --- Interface do Usuário Condicional e Lógica Principal do App ---
# Usaremos o sufixo de chave do seu código original (_v20_final) onde apropriado
# para a lógica do aplicativo, e chaves distintas para a autenticação.
APP_KEY_SUFFIX = "_v20_final" # Suffix do seu código original para as funcionalidades

if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    
    # Inicialização do LLM (SÓ SE AUTENTICADO)
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None
    llm_init_exception = None

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada ou vazia nos Segredos do Streamlit.")
        st.stop()
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash", # ou gemini-pro
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
            if 'llm_init_success_sidebar_shown_main_app' not in st.session_state: # Chave única
                st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
                st.session_state.llm_init_success_sidebar_shown_main_app = True
        except Exception as e_llm:
            llm_init_exception = e_llm # Armazena a exceção
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm}")
            # Não vamos dar st.stop() aqui ainda, para permitir que o resto da UI de logout etc. funcione.
            # A verificação de llm_model_instance abaixo cuidará disso.

    # --- SEU CÓDIGO DO APLICATIVO ASSISTENTE PME PRO ---
    if llm_model_instance:
        # --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (Objetivos e Output) ---
        # (Vou usar as suas funções exatamente como você forneceu)
        def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
            # Usando APP_KEY_SUFFIX (que é "_v20_final" do seu código)
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj{APP_KEY_SUFFIX}")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{APP_KEY_SUFFIX}")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{APP_KEY_SUFFIX}")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{APP_KEY_SUFFIX}")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{APP_KEY_SUFFIX}")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone{APP_KEY_SUFFIX}")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{APP_KEY_SUFFIX}")
            return details

        def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key}{APP_KEY_SUFFIX}.txt", mime="text/plain", key=f"download_{section_key}{APP_KEY_SUFFIX}")
            cols_actions = st.columns(2)
            with cols_actions[0]:
                if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn{APP_KEY_SUFFIX}"):
                    st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
                    st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
            with cols_actions[1]:
                if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn{APP_KEY_SUFFIX}"):
                    st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

        # --- HANDLER FUNCTIONS (do seu código) ---
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
                st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

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
                st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

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
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

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
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

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
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

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
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content # Chave de session_state atualizada

        # --- Classe do Agente (AssistentePMEPro) (do seu código) ---
        class AssistentePMEPro:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None:
                    st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
                    st.stop() 
                self.llm = llm_passed_model
                # Usando APP_KEY_SUFFIX para chaves de memória
                if f'memoria_plano_negocios{APP_KEY_SUFFIX}' not in st.session_state:
                    st.session_state[f'memoria_plano_negocios{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_plano{APP_KEY_SUFFIX}", return_messages=True)
                if f'memoria_calculo_precos{APP_KEY_SUFFIX}' not in st.session_state:
                    st.session_state[f'memoria_calculo_precos{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_precos{APP_KEY_SUFFIX}", return_messages=True)
                if f'memoria_gerador_ideias{APP_KEY_SUFFIX}' not in st.session_state:
                    st.session_state[f'memoria_gerador_ideias{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_ideias{APP_KEY_SUFFIX}", return_messages=True)
                
                self.memoria_plano_negocios = st.session_state[f'memoria_plano_negocios{APP_KEY_SUFFIX}']
                self.memoria_calculo_precos = st.session_state[f'memoria_calculo_precos{APP_KEY_SUFFIX}']
                self.memoria_gerador_ideias = st.session_state[f'memoria_gerador_ideias{APP_KEY_SUFFIX}']

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
                actual_memory_key = memoria_especifica.memory_key # Usa a memory_key da instância de memória
                prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(system_message_content),
                    MessagesPlaceholder(variable_name=actual_memory_key),
                    HumanMessagePromptTemplate.from_template("{input_usuario}")
                ])
                return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

            def marketing_digital_guiado(self):
                st.header("🚀 Marketing Digital Interativo com IA")
                st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
                st.markdown("---")

                marketing_files_info_for_prompt_local = [] 
                with st.sidebar: 
                    # Este file_uploader já estava na sua versão, vou manter o sufixo dele se não conflitar
                    # Mas idealmente, deveria usar APP_KEY_SUFFIX
                    st.subheader("📎 Suporte para Marketing") # Esta subheader pode ser movida para o corpo principal se preferir
                    uploaded_marketing_files = st.file_uploader(
                        "Upload de arquivos de CONTEXTO para Marketing (opcional):", 
                        accept_multiple_files=True,
                        type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'], 
                        key=f"marketing_files_uploader{APP_KEY_SUFFIX}" # Aplicando sufixo
                    )
                    if uploaded_marketing_files:
                        temp_marketing_files_info = []
                        for up_file in uploaded_marketing_files:
                            temp_marketing_files_info.append({"name": up_file.name, "type": up_file.type, "size": up_file.size})
                        if temp_marketing_files_info:
                            marketing_files_info_for_prompt_local = temp_marketing_files_info 
                            st.success(f"{len(uploaded_marketing_files)} arquivo(s) de contexto carregado(s)!")
                            with st.expander("Ver arquivos de contexto"):
                                for finfo in marketing_files_info_for_prompt_local:
                                    st.write(f"- {finfo['name']} ({finfo['type']})")
                    # st.markdown("---") # Removendo este divisor da sidebar, o layout principal do app já tem um

                main_action_key = f"main_marketing_action_choice{APP_KEY_SUFFIX}" # Aplicando sufixo
                opcoes_menu_marketing_dict = { 
                    "Selecione uma opção...": 0,
                    "1 - Criar post para redes sociais ou e-mail": 1,
                    "2 - Criar campanha de marketing completa": 2,
                    "3 - Criar estrutura e conteúdo para landing page": 3,
                    "4 - Criar estrutura e conteúdo para site com IA": 4,
                    "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)": 5,
                    "6 - Conhecer a concorrência (Análise Competitiva)": 6
                }
                opcoes_radio_marketing = list(opcoes_menu_marketing_dict.keys())
                
                # Gerenciamento do índice do radio button
                radio_index_key = f"{main_action_key}_index"
                if radio_index_key not in st.session_state:
                    st.session_state[radio_index_key] = 0

                def update_marketing_radio_index_on_change(): # Função de callback precisa existir
                    st.session_state[radio_index_key] = opcoes_radio_marketing.index(st.session_state[main_action_key])

                main_action = st.radio(
                    "Olá! O que você quer fazer agora em marketing digital?",
                    opcoes_radio_marketing,
                    index=st.session_state[radio_index_key], 
                    key=main_action_key,
                    on_change=update_marketing_radio_index_on_change # Corrigido para on_change
                )
                st.markdown("---")
                
                platforms_config_options = { 
                    "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", 
                    "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
                    "E-mail Marketing (lista própria)": "email_own", 
                    "E-mail Marketing (Campanha Google Ads)": "email_google"
                }

                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com IA")
                    with st.form(f"post_creator_form{APP_KEY_SUFFIX}"):
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_post = f"post_select_all{APP_KEY_SUFFIX}"
                        select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_post)
                        cols_post = st.columns(2); selected_platforms_post_ui = []
                        for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                            col_index = i % 2
                            platform_key = f"post_platform_{platform_suffix}{APP_KEY_SUFFIX}" 
                            with cols_post[col_index]:
                                if st.checkbox(platform_name, key=platform_key, value=select_all_post_checked):
                                    selected_platforms_post_ui.append(platform_name)
                                if "E-mail Marketing" in platform_name and st.session_state.get(platform_key): 
                                    st.caption("💡 Para e-mail marketing, considere segmentar sua lista e personalizar a saudação.")
                        post_details = _marketing_get_objective_details(f"post{APP_KEY_SUFFIX}", "post") # Usando section_key mais simples
                        submit_button_pressed_post = st.form_submit_button("💡 Gerar Post!")
                    if submit_button_pressed_post:
                        _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, selected_platforms_post_ui, self.llm)
                    if f'generated_post_content_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        _marketing_display_output_options(st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'], f"post_output{APP_KEY_SUFFIX}", "post_ia")

                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
                    with st.form(f"campaign_creator_form{APP_KEY_SUFFIX}"):
                        campaign_name = st.text_input("Nome da Campanha:", key=f"campaign_name{APP_KEY_SUFFIX}")
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_camp = f"campaign_select_all{APP_KEY_SUFFIX}"
                        select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_camp)
                        cols_camp = st.columns(2); selected_platforms_camp_ui = []
                        for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                            col_index = i % 2
                            platform_key = f"campaign_platform_{platform_suffix}{APP_KEY_SUFFIX}"
                            with cols_camp[col_index]:
                                if st.checkbox(platform_name, key=platform_key, value=select_all_camp_checked):
                                    selected_platforms_camp_ui.append(platform_name)
                        campaign_details_obj = _marketing_get_objective_details(f"campaign{APP_KEY_SUFFIX}", "campanha")
                        campaign_duration = st.text_input("Duração Estimada:", key=f"campaign_duration{APP_KEY_SUFFIX}")
                        campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key=f"campaign_budget{APP_KEY_SUFFIX}")
                        specific_kpis = st.text_area("KPIs mais importantes:", key=f"campaign_kpis{APP_KEY_SUFFIX}")
                        submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")
                    if submit_button_pressed_camp:
                        campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration, "budget": campaign_budget_approx, "kpis": specific_kpis}
                        _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, selected_platforms_camp_ui, self.llm)
                    if f'generated_campaign_content_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        _marketing_display_output_options(st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'], f"campaign_output{APP_KEY_SUFFIX}", "campanha_ia")
                
                elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                    st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
                    with st.form(f"landing_page_form{APP_KEY_SUFFIX}"):
                        lp_purpose = st.text_input("Principal objetivo da landing page:", key=f"lp_purpose{APP_KEY_SUFFIX}")
                        lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key=f"lp_audience{APP_KEY_SUFFIX}")
                        lp_main_offer = st.text_area("Oferta principal e irresistível:", key=f"lp_offer{APP_KEY_SUFFIX}")
                        lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key=f"lp_benefits{APP_KEY_SUFFIX}")
                        lp_cta = st.text_input("Chamada para ação (CTA) principal:", key=f"lp_cta{APP_KEY_SUFFIX}")
                        lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key=f"lp_visual{APP_KEY_SUFFIX}")
                        submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")
                    if submitted_lp:
                        lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                        _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details_dict, self.llm)
                    if f'generated_lp_content_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                        st.markdown(st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'])
                        st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'].encode('utf-8'), file_name=f"landing_page_sugestoes_ia{APP_KEY_SUFFIX}.txt", mime="text/plain", key=f"download_lp{APP_KEY_SUFFIX}") 

                elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                    st.subheader("🏗️ Arquiteto de Sites com IA")
                    with st.form(f"site_creator_form{APP_KEY_SUFFIX}"): 
                        site_business_type = st.text_input("Tipo do seu negócio/empresa:", key=f"site_biz_type{APP_KEY_SUFFIX}")
                        site_main_purpose = st.text_area("Principal objetivo do seu site:", key=f"site_purpose{APP_KEY_SUFFIX}")
                        site_target_audience = st.text_input("Público principal do site:", key=f"site_audience{APP_KEY_SUFFIX}")
                        site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key=f"site_pages{APP_KEY_SUFFIX}")
                        site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key=f"site_features{APP_KEY_SUFFIX}")
                        site_brand_personality = st.text_input("Personalidade da sua marca:", key=f"site_brand{APP_KEY_SUFFIX}")
                        site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key=f"site_visual_ref{APP_KEY_SUFFIX}")
                        submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site!")
                    if submitted_site:
                        site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                        _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details_dict, self.llm)
                    if f'generated_site_content_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                        st.markdown(st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'])
                        st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'].encode('utf-8'), file_name=f"site_sugestoes_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_site{APP_KEY_SUFFIX}")

                elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                    st.subheader("🎯 Decodificador de Clientes com IA")
                    with st.form(f"find_client_form{APP_KEY_SUFFIX}"):
                        fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key=f"fc_campaign{APP_KEY_SUFFIX}")
                        fc_location = st.text_input("Cidade(s) ou região de alcance:", key=f"fc_location{APP_KEY_SUFFIX}")
                        fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key=f"fc_budget{APP_KEY_SUFFIX}")
                        fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key=f"fc_age_gender{APP_KEY_SUFFIX}")
                        fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key=f"fc_interests{APP_KEY_SUFFIX}")
                        fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key=f"fc_channels{APP_KEY_SUFFIX}")
                        fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key=f"fc_deep{APP_KEY_SUFFIX}")
                        submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente!")
                    if submitted_fc:
                        client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                        _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details_dict, self.llm)
                    if f'generated_client_analysis_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                        st.markdown(st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'])
                        st.download_button(label="📥 Baixar Análise de Público",data=st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'].encode('utf-8'), file_name=f"analise_publico_alvo_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_client_analysis{APP_KEY_SUFFIX}")
                
                elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                    st.subheader("🧐 Radar da Concorrência com IA")
                    with st.form(f"competitor_analysis_form{APP_KEY_SUFFIX}"):
                        ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key=f"ca_your_biz{APP_KEY_SUFFIX}")
                        ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key=f"ca_competitors{APP_KEY_SUFFIX}")
                        ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"ca_aspects{APP_KEY_SUFFIX}")
                        submitted_ca = st.form_submit_button("📡 Analisar Concorrentes!")
                    if submitted_ca:
                        competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                        _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details_dict, self.llm)
                    if f'generated_competitor_analysis_new{APP_KEY_SUFFIX}' in st.session_state: # Usando chave de session_state correta
                        st.subheader("📊 Análise da Concorrência e Insights:")
                        st.markdown(st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'])
                        st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'].encode('utf-8'), file_name=f"analise_concorrencia_ia{APP_KEY_SUFFIX}.txt",mime="text/plain",key=f"download_competitor_analysis{APP_KEY_SUFFIX}")

                elif main_action == "Selecione uma opção...":
                    st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
                    # Usando o caminho corrigido para o logo local aqui também
                    LOGO_PATH_MARKETING_WELCOME = "images/logo-pme-ia.png"
                    FALLBACK_LOGO_MARKETING_WELCOME = "https://i.imgur.com/7IIYxq1.png"
                    try:
                        st.image(LOGO_PATH_MARKETING_WELCOME, caption="Assistente PME Pro", width=200)
                    except Exception:
                        st.image(FALLBACK_LOGO_MARKETING_WELCOME, caption="Assistente PME Pro (Fallback)", width=200)
            
            # Demais métodos da classe AssistentePMEPro (conversar_plano_de_negocios, etc.)
            # com as adaptações de memory_key e outras chaves para APP_KEY_SUFFIX

        # --- Funções Utilitárias de Chat (do seu código, adaptando chaves para APP_KEY_SUFFIX) ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}" # Usando APP_KEY_SUFFIX
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                    memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
                     # Para ConversationBufferMemory, a forma correta pode ser adicionar diretamente à lista messages
                    memoria_agente_instancia.chat_memory.messages.clear() # Limpa primeiro
                    memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
            # Limpando chaves específicas de upload
            if area_chave == "calculo_precos": 
                st.session_state.pop(f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)
            elif area_chave == "gerador_ideias": 
                st.session_state.pop(f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}" # Usando APP_KEY_SUFFIX
            if chat_display_key not in st.session_state: 
                st.session_state[chat_display_key] = [] 
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): 
                    st.markdown(msg_info["content"])
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{APP_KEY_SUFFIX}") # Usando APP_KEY_SUFFIX
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                if area_chave in ["calculo_precos", "gerador_ideias"]: st.session_state[f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'] = True # Usando APP_KEY_SUFFIX
                with st.spinner("Assistente PME Pro está processando... 🤔"):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()
        
        def _sidebar_clear_button(label, memoria, section_key): # Removido key_suffix_version, usará APP_KEY_SUFFIX
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key}{APP_KEY_SUFFIX}_clear"): # Usando APP_KEY_SUFFIX
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key == "calculo_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços! Descreva seu produto ou serviço."
                elif section_key == "gerador_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias! Qual o seu ponto de partida?"
                inicializar_ou_resetar_chat(section_key, msg_inicial, memoria) 
                st.rerun()

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj): # Removido key_suffix_version
            # Usando APP_KEY_SUFFIX implicitamente nas chaves de session_state
            descricao_imagem_para_ia = None
            processed_image_id_key = f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}'
            last_uploaded_info_key = f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}'
            user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'

            if uploaded_image_obj is not None:
                # Usar uploaded_image_obj.file_id para garantir unicidade se o mesmo nome de arquivo for reenviado
                if st.session_state.get(processed_image_id_key) != uploaded_image_obj.file_id:
                    try:
                        img_pil = Image.open(uploaded_image_obj); st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                        st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                        st.session_state[processed_image_id_key] = uploaded_image_obj.file_id # Armazenar file_id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo.")
                    except Exception as e_img_proc: st.error(f"Erro ao processar imagem: {e_img_proc}"); st.session_state[last_uploaded_info_key] = None; st.session_state[processed_image_id_key] = None
                else: descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
            kwargs_chat = {}
            ctx_img_prox_dialogo = st.session_state.get(last_uploaded_info_key)
            if ctx_img_prox_dialogo and not st.session_state.get(user_input_processed_key, False): kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
            if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
                if st.session_state.get(last_uploaded_info_key): st.session_state[last_uploaded_info_key] = None
                st.session_state[user_input_processed_key] = False

        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs): # Removido key_suffix_version
            # Usando APP_KEY_SUFFIX implicitamente nas chaves de session_state
            contexto_para_ia_local = None
            processed_file_id_key = f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}'
            uploaded_info_key = f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}'
            user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'

            if uploaded_files_objs: # uploaded_files_objs é uma lista de UploadedFile
                current_file_signature = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id}" for f in uploaded_files_objs])) # Usar file_id
                if st.session_state.get(processed_file_id_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                    text_contents, image_info = [], []
                    for f_item in uploaded_files_objs:
                        try:
                            if f_item.type == "text/plain": text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...") # Limita o tamanho para contexto
                            elif f_item.type in ["image/png","image/jpeg"]: st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100); image_info.append(f"Imagem '{f_item.name}'.")
                        except Exception as e_file_proc: st.error(f"Erro ao processar '{f_item.name}': {e_file_proc}")
                    full_ctx_str = ("\n\n--- TEXTO DOS ARQUIVOS ---\n" + "\n\n".join(text_contents) if text_contents else "") + \
                                   ("\n\n--- IMAGENS FORNECIDAS ---\n" + "\n".join(image_info) if image_info else "")
                    if full_ctx_str.strip(): st.session_state[uploaded_info_key] = full_ctx_str.strip(); contexto_para_ia_local = st.session_state[uploaded_info_key]; st.info("Arquivo(s) de contexto pronto(s).")
                    else: st.session_state[uploaded_info_key] = None
                    st.session_state[processed_file_id_key] = current_file_signature
                else: contexto_para_ia_local = st.session_state.get(uploaded_info_key)
            kwargs_chat = {}
            if contexto_para_ia_local and not st.session_state.get(user_input_processed_key, False): kwargs_chat['contexto_arquivos'] = contexto_para_ia_local
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
            if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
                if st.session_state.get(uploaded_info_key): st.session_state[uploaded_info_key] = None
                st.session_state[user_input_processed_key] = False

        # --- Instanciação do Agente ---
        if 'agente_pme' not in st.session_state or not isinstance(st.session_state.agente_pme, AssistentePMEPro) or st.session_state.agente_pme.llm != llm_model_instance : # Adicionada verificação do llm
            st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme
        
        # --- Interface da Sidebar (após login) ---
        st.sidebar.write(f"Logado como: {display_email}")
        if st.sidebar.button("Logout", key=f"main_app_logout{APP_KEY_SUFFIX}"): # Usando APP_KEY_SUFFIX
            st.session_state.user_session_pyrebase = None
            # Limpeza de chaves de sessão
            st.session_state.pop('firebase_init_success_message_shown', None)
            st.session_state.pop('firebase_app_instance', None) 
            st.session_state.pop('llm_init_success_sidebar_shown_main_app', None)
            # Limpar chaves específicas do app (usando APP_KEY_SUFFIX e prefixos comuns)
            keys_to_clear_on_logout = [k for k in st.session_state if APP_KEY_SUFFIX in k or k.startswith('memoria_') or k.startswith('chat_display_') or k.startswith('generated_') or k.startswith('post_') or k.startswith('campaign_')]
            keys_to_clear_on_logout.append('agente_pme')
            keys_to_clear_on_logout.append('area_selecionada') # Chave de navegação principal
            for key_to_clear in keys_to_clear_on_logout: 
                st.session_state.pop(key_to_clear, None)
            st.rerun()

        # Logo da Sidebar (Corrigido para usar try-except)
        LOGO_PATH_SIDEBAR_APP = "images/logo-pme-ia.png" # Certifique-se que é 'images'
        FALLBACK_LOGO_URL_SIDEBAR_APP = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.sidebar.image(LOGO_PATH_SIDEBAR_APP, width=150)
        except Exception:
            st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR_APP, width=150, caption="Logo (Fallback)")

        st.sidebar.title("Assistente PME Pro")
        st.sidebar.markdown("IA para seu Negócio Decolar!")
        st.sidebar.markdown("---")

        # --- Lógica de Navegação Principal (Sidebar) (do seu código) ---
        opcoes_menu = {
            "Página Inicial": "pagina_inicial", 
            "Marketing Digital com IA (Guia)": "marketing_guiado",
            "Elaborar Plano de Negócios com IA": "plano_negocios", 
            "Cálculo de Preços Inteligente": "calculo_precos",
            "Gerador de Ideias para Negócios": "gerador_ideias"
        }
        radio_key_sidebar_main = f'sidebar_selection{APP_KEY_SUFFIX}_main' # Usando APP_KEY_SUFFIX
        
        if 'area_selecionada' not in st.session_state or st.session_state.area_selecionada not in opcoes_menu:
            st.session_state.area_selecionada = "Página Inicial"
        
        # Gerenciamento do índice do radio button para persistência
        radio_index_key_nav = f'{radio_key_sidebar_main}_index'
        if radio_index_key_nav not in st.session_state:
            try:
                st.session_state[radio_index_key_nav] = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)
            except ValueError: # Caso 'area_selecionada' seja inválida
                st.session_state[radio_index_key_nav] = 0
                st.session_state.area_selecionada = list(opcoes_menu.keys())[0]
        
        def update_main_radio_index_on_change_app(): # Nome da função de callback atualizado
             st.session_state[radio_index_key_nav] = list(opcoes_menu.keys()).index(st.session_state[radio_key_sidebar_main])

        area_selecionada_label = st.sidebar.radio(
            "Como posso te ajudar hoje?", 
            options=list(opcoes_menu.keys()), 
            key=radio_key_sidebar_main, 
            index=st.session_state[radio_index_key_nav], # Usando a chave de índice correta
            on_change=update_main_radio_index_on_change_app # Callback corrigido
        )

        if area_selecionada_label != st.session_state.area_selecionada:
            st.session_state.area_selecionada = area_selecionada_label
            # Limpar estados de marketing se sair da seção
            if area_selecionada_label != "Marketing Digital com IA (Guia)":
                keys_to_clear_marketing_nav = [k for k in st.session_state if k.startswith(f"generated_") and APP_KEY_SUFFIX in k or k.startswith(f"post_{APP_KEY_SUFFIX}") or k.startswith(f"campaign_{APP_KEY_SUFFIX}")]
                for key_clear_nav_mkt in keys_to_clear_marketing_nav:
                    st.session_state.pop(key_clear_nav_mkt, None)
            st.rerun() 

        current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
        
        # Inicializar chats quando a seção é selecionada pela primeira vez ou mudada
        if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
            chat_init_flag_key_app = f'previous_area_selecionada_for_chat_init{APP_KEY_SUFFIX}' # Usando APP_KEY_SUFFIX
            chat_display_key_specific_app = f"chat_display_{current_section_key}{APP_KEY_SUFFIX}" # Usando APP_KEY_SUFFIX
            
            # Verifica se precisa reinicializar o chat
            needs_chat_reset = False
            if st.session_state.area_selecionada != st.session_state.get(chat_init_flag_key_app):
                needs_chat_reset = True
            elif chat_display_key_specific_app not in st.session_state:
                needs_chat_reset = True
            elif not st.session_state.get(chat_display_key_specific_app): # Se a lista de chat estiver vazia
                needs_chat_reset = True

            if needs_chat_reset:
                msg_inicial_nav, memoria_agente_nav = "", None
                if current_section_key == "plano_negocios": msg_inicial_nav, memoria_agente_nav = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia.", agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav, memoria_agente_nav = "Olá! Para calcular preços, descreva seu produto/serviço. Pode enviar uma imagem.", agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav, memoria_agente_nav = "Olá! Buscando ideias? Descreva seu desafio ou envie arquivos de contexto.", agente.memoria_gerador_ideias
                
                if msg_inicial_nav and memoria_agente_nav is not None:
                    inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
                st.session_state[chat_init_flag_key_app] = st.session_state.area_selecionada


        # --- SELEÇÃO E EXIBIÇÃO DA SEÇÃO ATUAL (do seu código) ---
        if current_section_key == "pagina_inicial":
            st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
            st.markdown("---")
            # LOGO DA PÁGINA INICIAL REMOVIDO CONFORME SEU PEDIDO
            st.markdown("---")
            
            num_botoes_funcionais = len(opcoes_menu) -1 
            if num_botoes_funcionais > 0 :
                num_cols_render = min(num_botoes_funcionais, 3) 
                cols_botoes_pg_inicial = st.columns(num_cols_render)
                btn_idx_pg_inicial = 0
                for nome_menu_btn_pg, chave_secao_btn_pg in opcoes_menu.items():
                    if chave_secao_btn_pg != "pagina_inicial":
                        col_para_botao_pg = cols_botoes_pg_inicial[btn_idx_pg_inicial % num_cols_render]
                        button_label_pg = nome_menu_btn_pg.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                        if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}{APP_KEY_SUFFIX}", use_container_width=True, help=f"Ir para {nome_menu_btn_pg}"): # Usando APP_KEY_SUFFIX
                            st.session_state.area_selecionada = nome_menu_btn_pg
                            try: # Atualiza o índice do radio button da sidebar
                                st.session_state[radio_index_key_nav] = list(opcoes_menu.keys()).index(nome_menu_btn_pg)
                            except ValueError: pass
                            st.rerun()
                        btn_idx_pg_inicial +=1
                st.balloons()

        elif current_section_key == "marketing_guiado": 
            agente.marketing_digital_guiado() # Certifique-se que as chaves internas usam APP_KEY_SUFFIX
        elif current_section_key == "plano_negocios": 
            st.header("📝 Elaborando seu Plano de Negócios com IA")
            st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
            exibir_chat_e_obter_input(current_section_key, "Sua resposta ou próxima seção do plano...", agente.conversar_plano_de_negocios)
            _sidebar_clear_button("Plano", agente.memoria_plano_negocios, current_section_key) # APP_KEY_SUFFIX usado internamente
        elif current_section_key == "calculo_precos": 
            st.header("💲 Cálculo de Preços Inteligente com IA")
            st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
            uploaded_image_calc = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key=f"preco_img{APP_KEY_SUFFIX}") # Usando APP_KEY_SUFFIX
            _handle_chat_with_image("calculo_precos", "Descreva o produto/serviço, custos, etc.", agente.calcular_precos_interativo, uploaded_image_calc) # APP_KEY_SUFFIX usado internamente
            _sidebar_clear_button("Preços", agente.memoria_calculo_precos, current_section_key) # APP_KEY_SUFFIX usado internamente
        elif current_section_key == "gerador_ideias": 
            st.header("💡 Gerador de Ideias para seu Negócio com IA")
            st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
            uploaded_files_ideias_ui = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"ideias_file_uploader{APP_KEY_SUFFIX}") # Usando APP_KEY_SUFFIX
            _handle_chat_with_files("gerador_ideias", "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, uploaded_files_ideias_ui) # APP_KEY_SUFFIX usado internamente
            _sidebar_clear_button("Ideias", agente.memoria_gerador_ideias, current_section_key) # APP_KEY_SUFFIX usado internamente
    
    else: # Se llm_model_instance não foi inicializado
        st.error("🚨 O Assistente PME Pro não pôde ser iniciado.")
        st.info("Isso pode ter ocorrido devido a um problema com a chave da API do Google ou ao contatar os serviços do Google Generative AI.")
        if llm_init_exception: # Mostra a exceção específica se disponível
            st.exception(llm_init_exception)


# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: 
    st.session_state.pop('auth_error_shown', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") # Título da aplicação na tela de login

    # Forms de Login/Registro na Sidebar
    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key = "app_auth_choice_pyrebase" # Chave única para o radio da autenticação
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key)

    if auth_action_choice == "Login":
        with st.sidebar.form("app_login_form_pyrebase"): # Chave única para o form de login
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None) # Para não mostrar novamente após login
                        st.rerun()
                    except Exception as e_login:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str = e_login.args[0] if len(e_login.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: error_message_login = f"Erro no login: {api_error_message}"
                        except: pass # Ignora erros de parsing da mensagem de erro do Firebase, usa a genérica
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("app_register_form_pyrebase"): # Chave única para o form de registro
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: # Tenta enviar email de verificação
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_local: # Renomeada variável de exceção
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_local}")
                    except Exception as e_register:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e_register.args[0] if len(e_register.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message:
                                error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except: # Ignora erros de parsing, usa mensagem genérica + str(e)
                             error_message_register = f"Erro no registro: {str(e_register)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    # Conteúdo da página de login (quando não autenticado)
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        # Logo da tela de login (Corrigido para usar try-except)
        LOGO_PATH_LOGIN_UNAUTH = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN_UNAUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN_UNAUTH, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN_UNAUTH, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
