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
        
        session_rerun_key = 'running_rerun_after_auth_fail_v3' 
        if not st.session_state.get(session_rerun_key, False):
            st.session_state[session_rerun_key] = True
            st.rerun()
        else:
            st.session_state.pop(session_rerun_key, None)

session_rerun_key_check = 'running_rerun_after_auth_fail_v3'
if session_rerun_key_check in st.session_state and st.session_state[session_rerun_key_check]:
    st.session_state.pop(session_rerun_key_check, None)
# --- Interface do Usuário Condicional e Lógica Principal do App ---
APP_KEY_SUFFIX = "_v20_final" # Suffix do seu código original para as funcionalidades

if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None
    llm_init_exception = None 

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada ou vazia nos Segredos do Streamlit.")
        st.stop() 
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash", 
                                                       temperature=0.75,
                                                       google_api_key=GOOGLE_API_KEY,
                                                       convert_system_message_to_human=True)
            if 'llm_init_success_sidebar_shown_main_app' not in st.session_state:
                st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
                st.session_state.llm_init_success_sidebar_shown_main_app = True
        except Exception as e_llm:
            llm_init_exception = e_llm 
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm}")
            
    if llm_model_instance:
        # --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (Objetivos e Output) ---
        def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
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
                st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = ai_response.content

        # ***** FUNÇÃO _marketing_handle_criar_campanha COM DEBUG LINE *****
        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo da campanha."); return
            with st.spinner("🧠 A IA está elaborando seu plano de campanha..."): # Spinner correto
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
                
                # ***** LINHA DE DEBUG INSERIDA AQUI *****
                st.expander("🔍 Debug: Ver Prompt da Campanha Enviado para IA").write(final_prompt)
                # ***** FIM DA LINHA DE DEBUG *****
                
                # Dentro da função _marketing_handle_criar_campanha:
# ... (todo o código que monta a lista `prompt_parts` vem antes daqui) ...
            
            if uploaded_files_info: 
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
            
            final_prompt = "\n\n".join(prompt_parts) # Esta linha monta o prompt original
            
            # Sua linha de debug original (MANTENHA para ver o prompt original que seria enviado)
            st.expander("🔍 Debug: Ver Prompt ORIGINAL da Campanha Enviado para IA").write(final_prompt) 
            
            # ---- INÍCIO DO BLOCO DE TESTE SIMPLES DE PROMPT ----
            # (Este bloco substitui as linhas originais de 'llm.invoke' e 'st.session_state' para a campanha)
            
            test_prompt_content = "Por favor, escreva uma frase curta sobre marketing para pequenas empresas no Brasil."
            
            # Adicionando um novo expander para o prompt de teste, para não confundir com o original
            st.expander("🧪 Debug: Ver Prompt DE TESTE Sendo Enviado").write(f"USANDO PROMPT DE TESTE: {test_prompt_content}") 
            
            try:
                ai_response_test = llm.invoke(HumanMessage(content=test_prompt_content)) # Usando o prompt de teste
                # Se o teste funcionar, vamos guardar a resposta em uma chave de session_state diferente
                st.session_state[f'generated_campaign_content_TEST{APP_KEY_SUFFIX}'] = ai_response_test.content
                st.success("🎉 Teste de prompt simples FUNCIONOU! A IA respondeu.") 
                st.write("Resposta do teste:")
                st.write(ai_response_test.content) # Mostra a resposta do teste
            except ValueError as e_val_test: # Captura especificamente ValueError
                st.error(f"😥 ERRO (ValueError) no teste de prompt simples: {e_val_test}")
                # Tenta mostrar a mensagem completa do ValueError
                st.text_area("Detalhe do ValueError (para copiar):", str(e_val_test), height=150)
            except Exception as e_test_invoke: # Captura outras exceções
                st.error(f"😥 ERRO GERAL no teste de prompt simples: {e_test_invoke}")
                st.text_area("Detalhe do Erro Geral (para copiar):", str(e_test_invoke), height=150)
            # ---- FIM DO BLOCO DE TESTE SIMPLES DE PROMPT ----

        # Aqui termina a função _marketing_handle_criar_campanha

# A próxima definição de função deve começar aqui, por exemplo:
# def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
#    # ...
        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Por favor, preencha objetivo, oferta e CTA."); return
            with st.spinner("🎨 A IA está desenhando a estrutura da sua landing page..."): # Spinner correto
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages de alta conversão, com foco em PMEs no Brasil...", # seu prompt completo
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
                st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = ai_response.content

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo do site."); return
            with st.spinner("🛠️ A IA está arquitetando a estrutura do seu site..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um arquiteto de informação e web designer experiente, focado em criar sites eficazes para PMEs no Brasil...", # seu prompt completo
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
                st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = ai_response.content

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details["product_campaign"]: st.warning("Descreva o produto/serviço ou campanha."); return
            with st.spinner("🕵️ A IA está investigando seu público-alvo..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado para PMEs no Brasil...", # seu prompt completo
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
                st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e liste concorrentes."); return
            with st.spinner("🔬 A IA está analisando a concorrência..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em análise de mercado para PMEs no Brasil...", # seu prompt completo
                    f"**Negócio do Usuário (para comparação):** {competitor_details['your_business']}",
                    f"**Concorrentes (nomes, sites, redes sociais, se possível):** {competitor_details['competitors_list']}",
                    f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content

        # --- Classe do Agente (AssistentePMEPro) ---
        class AssistentePMEPro:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None:
                    st.error("❌ Erro crítico: Agente PME Pro tentou ser inicializado sem um modelo LLM.")
                    st.stop() 
                self.llm = llm_passed_model
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
                actual_memory_key = memoria_especifica.memory_key
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
                # Lógica do File Uploader da Sidebar para Marketing (do seu código)
                with st.sidebar: 
                    sidebar_marketing_expander = st.sidebar.expander("📎 Suporte para Marketing (Upload Geral)")
                    with sidebar_marketing_expander:
                        uploaded_marketing_files_sidebar = st.file_uploader(
                            "Upload de arquivos de CONTEXTO para Marketing (opcional):", 
                            accept_multiple_files=True,
                            type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'], 
                            key=f"marketing_files_uploader{APP_KEY_SUFFIX}" 
                        )
                        if uploaded_marketing_files_sidebar:
                            temp_marketing_files_info = [{"name": up_file.name, "type": up_file.type, "size": up_file.size} for up_file in uploaded_marketing_files_sidebar]
                            if temp_marketing_files_info:
                                marketing_files_info_for_prompt_local = temp_marketing_files_info 
                                st.success(f"{len(uploaded_marketing_files_sidebar)} arquivo(s) de contexto carregado(s)!")
                                with st.expander("Ver arquivos de contexto"):
                                    for finfo in marketing_files_info_for_prompt_local: st.write(f"- {finfo['name']} ({finfo['type']})")
                
                main_action_key = f"main_marketing_action_choice{APP_KEY_SUFFIX}"
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
                radio_index_key_mkt = f"{main_action_key}_index"
                if radio_index_key_mkt not in st.session_state: st.session_state[radio_index_key_mkt] = 0
                
                current_main_action_value_mkt = st.session_state.get(main_action_key, opcoes_radio_marketing[0])
                try:
                    current_main_action_index_mkt = opcoes_radio_marketing.index(current_main_action_value_mkt)
                    if st.session_state.get(radio_index_key_mkt) != current_main_action_index_mkt : st.session_state[radio_index_key_mkt] = current_main_action_index_mkt
                except ValueError: st.session_state[radio_index_key_mkt] = 0
                
                main_action = st.radio("Olá! O que você quer fazer agora em marketing digital?", opcoes_radio_marketing, index=st.session_state[radio_index_key_mkt], key=main_action_key)
                st.markdown("---")
                platforms_config_options = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt", "E-mail Marketing (lista própria)": "email_own", "E-mail Marketing (Campanha Google Ads)": "email_google" }
                platform_names_available_list = list(platforms_config_options.keys())

                if main_action == "1 - Criar post para redes sociais ou e-mail":
                    st.subheader("✨ Criador de Posts com IA")
                    with st.form(f"post_creator_form{APP_KEY_SUFFIX}"):
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_post = f"post_select_all{APP_KEY_SUFFIX}"
                        select_all_post_checked_val = st.session_state.get(key_select_all_post, False)
                        select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", value=select_all_post_checked_val, key=key_select_all_post)
                        cols_post = st.columns(2); selected_platforms_post_keys_map = {}
                        for i, (pn, ps) in enumerate(platforms_config_options.items()):
                            pk = f"post_platform_{ps}{APP_KEY_SUFFIX}"; selected_platforms_post_keys_map[pn] = pk
                            with cols_post[i%2]: st.checkbox(pn, key=pk, value=(select_all_post_checked if st.session_state.get(key_select_all_post) else st.session_state.get(pk, False) ))
                        post_details = _marketing_get_objective_details(f"post_creator_details{APP_KEY_SUFFIX}", "post")
                        submit_post = st.form_submit_button("💡 Gerar Post!")
                    if submit_post:
                        sel_plats = platform_names_available_list if st.session_state.get(key_select_all_post, False) else [pfn for pfn, pfk in selected_platforms_post_keys_map.items() if st.session_state.get(pfk, False)]
                        _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, sel_plats, self.llm)
                    if f'generated_post_content_new{APP_KEY_SUFFIX}' in st.session_state: _marketing_display_output_options(st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'], f"post_disp{APP_KEY_SUFFIX}", "post_ia")

                elif main_action == "2 - Criar campanha de marketing completa":
                    st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
                    with st.form(f"campaign_creator_form{APP_KEY_SUFFIX}"):
                        campaign_name = st.text_input("Nome da Campanha:", key=f"campaign_name_ui{APP_KEY_SUFFIX}")
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_camp = f"campaign_select_all{APP_KEY_SUFFIX}"
                        select_all_camp_checked_val = st.session_state.get(key_select_all_camp, False)
                        select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Acima", value=select_all_camp_checked_val, key=key_select_all_camp)
                        cols_camp = st.columns(2); selected_platforms_camp_keys_map = {}
                        for i, (pn_c, ps_c) in enumerate(platforms_config_options.items()):
                            pk_c = f"campaign_platform_{ps_c}{APP_KEY_SUFFIX}"; selected_platforms_camp_keys_map[pn_c] = pk_c
                            with cols_camp[i%2]: st.checkbox(pn_c, key=pk_c, value=(select_all_camp_checked if st.session_state.get(key_select_all_camp) else st.session_state.get(pk_c, False)))
                        campaign_details_obj = _marketing_get_objective_details(f"campaign_creator_details{APP_KEY_SUFFIX}", "campanha")
                        campaign_duration = st.text_input("Duração Estimada:", key=f"campaign_duration_ui{APP_KEY_SUFFIX}")
                        campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key=f"campaign_budget_ui{APP_KEY_SUFFIX}")
                        specific_kpis = st.text_area("KPIs mais importantes:", key=f"campaign_kpis_ui{APP_KEY_SUFFIX}")
                        submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")
                    if submit_button_pressed_camp:
                        actual_selected_platforms_camp = []
                        if st.session_state.get(key_select_all_camp, False):
                            actual_selected_platforms_camp = platform_names_available_list
                        else:
                            for p_name, p_key in selected_platforms_camp_keys_map.items():
                                if st.session_state.get(p_key, False):
                                    actual_selected_platforms_camp.append(p_name)
                        campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration, "budget": campaign_budget_approx, "kpis": specific_kpis}
                        # A chamada para _marketing_handle_criar_campanha está aqui
                        _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, actual_selected_platforms_camp, self.llm)
                    if f'generated_campaign_content_new{APP_KEY_SUFFIX}' in st.session_state: _marketing_display_output_options(st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'], f"campaign_disp{APP_KEY_SUFFIX}", "campanha_ia")
                
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
                    if f'generated_lp_content_new{APP_KEY_SUFFIX}' in st.session_state:
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
                    if f'generated_site_content_new{APP_KEY_SUFFIX}' in st.session_state:
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
                    if f'generated_client_analysis_new{APP_KEY_SUFFIX}' in st.session_state:
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
                    if f'generated_competitor_analysis_new{APP_KEY_SUFFIX}' in st.session_state:
                        st.subheader("📊 Análise da Concorrência e Insights:")
                        st.markdown(st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'])
                        st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'].encode('utf-8'), file_name=f"analise_concorrencia_ia{APP_KEY_SUFFIX}.txt",mime="text/plain",key=f"download_competitor_analysis{APP_KEY_SUFFIX}")

                elif main_action == "Selecione uma opção...":
                    st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
                    LOGO_PATH_MKT_WELCOME_APP = "images/logo-pme-ia.png"
                    FALLBACK_LOGO_MKT_WELCOME_APP = "https://i.imgur.com/7IIYxq1.png"
                    try:
                        st.image(LOGO_PATH_MKT_WELCOME_APP, caption="Assistente PME Pro", width=200)
                    except Exception:
                        st.image(FALLBACK_LOGO_MKT_WELCOME_APP, caption="Assistente PME Pro (Fallback)", width=200)
            
            def conversar_plano_de_negocios(self, input_usuario):
                system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente especializado em auxiliar Pequenas e Médias Empresas (PMEs) no Brasil a desenvolverem planos de negócios robustos e estratégicos..." # Mantendo o prompt completo do seu código
                cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder_base=f"historico_chat_plano{APP_KEY_SUFFIX}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
                prompt_content_calc = f"O usuário está buscando ajuda para precificar um produto/serviço e forneceu a seguinte informação inicial: '{input_usuario}'."
                if descricao_imagem_contexto: prompt_content_calc = f"{descricao_imagem_contexto}\n\n{prompt_content_calc}"
                system_message_precos = f"""Você é o "Assistente PME Pro", um especialista em estratégias de precificação para PMEs no Brasil. {prompt_content_calc} Comece fazendo perguntas claras e objetivas para entender os custos (fixos e variáveis), o valor percebido pelo cliente, os preços da concorrência e os objetivos de margem de lucro do usuário. Guie-o passo a passo no processo de cálculo, sugerindo métodos como markup, margem de contribuição ou precificação baseada em valor, conforme apropriado."""
                cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder_base=f"historico_chat_precos{APP_KEY_SUFFIX}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base nas informações que forneci (incluindo a descrição e a imagem, se houver), quais seriam os próximos passos ou perguntas para definirmos o preço?"}) 
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
                prompt_content_ideias = f"O usuário busca ideias criativas e viáveis para seu negócio (ou um novo negócio) e descreve seu desafio ou ponto de partida como: '{input_usuario}'."
                if contexto_arquivos: prompt_content_ideias = f"Adicionalmente, o usuário forneceu o seguinte contexto a partir de arquivos:\n{contexto_arquivos}\n\n{prompt_content_ideias}"
                system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios altamente criativo e com visão de mercado, focado em PMEs no Brasil. {prompt_content_ideias} Faça perguntas exploratórias para entender melhor as paixões, habilidades, recursos disponíveis e o mercado de interesse do usuário. Com base nisso, gere 3-5 ideias de negócios ou inovações distintas e acionáveis, cada uma com uma breve justificativa e potenciais primeiros passos. Priorize ideias com potencial de crescimento e alinhadas com tendências atuais."""
                cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder_base=f"historico_chat_ideias{APP_KEY_SUFFIX}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que descrevi e nos arquivos (se houver), quais ideias inovadoras você sugere?"})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

        # --- Funções Utilitárias de Chat (do seu código, adaptando chaves para APP_KEY_SUFFIX) ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                if hasattr(memoria_agente_instancia, 'chat_memory') and hasattr(memoria_agente_instancia.chat_memory, 'messages'):
                    memoria_agente_instancia.chat_memory.messages.clear() 
                    memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
                elif hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                     memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
            
            if area_chave == "calculo_precos": 
                st.session_state.pop(f'last_uploaded_image_info_calculo_precos{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_image_id_calculo_precos{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_calculo_precos{APP_KEY_SUFFIX}', None)
            elif area_chave == "gerador_ideias": 
                st.session_state.pop(f'uploaded_file_info_gerador_ideias_for_prompt{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'processed_file_id_gerador_ideias{APP_KEY_SUFFIX}', None)
                st.session_state.pop(f'user_input_processed_gerador_ideias{APP_KEY_SUFFIX}', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
            if chat_display_key not in st.session_state: st.session_state[chat_display_key] = [] 
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{APP_KEY_SUFFIX}")
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                user_input_processed_key_chat = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'
                if area_chave in ["calculo_precos", "gerador_ideias"]: 
                    st.session_state[user_input_processed_key_chat] = True
                with st.spinner("Assistente PME Pro está processando... 🤔"):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()
        
        def _sidebar_clear_button(label, memoria, section_key): 
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key}{APP_KEY_SUFFIX}_clear"):
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key == "calculo_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços! Descreva seu produto ou serviço."
                elif section_key == "gerador_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias! Qual o seu ponto de partida?"
                inicializar_ou_resetar_chat(section_key, msg_inicial, memoria) 
                st.rerun()

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj): 
            descricao_imagem_para_ia = None
            processed_image_id_key = f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}'
            last_uploaded_info_key = f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}'
            user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'
            if uploaded_image_obj is not None:
                current_image_id = uploaded_image_obj.file_id if hasattr(uploaded_image_obj, 'file_id') else uploaded_image_obj.id
                if st.session_state.get(processed_image_id_key) != current_image_id:
                    try:
                        img_pil = Image.open(uploaded_image_obj); st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                        st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                        st.session_state[processed_image_id_key] = current_image_id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta.")
                    except Exception as e_img_proc_handle: 
                        st.error(f"Erro ao processar imagem: {e_img_proc_handle}")
                        st.session_state.pop(last_uploaded_info_key, None)
                        st.session_state.pop(processed_image_id_key, None)
                else: descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
            kwargs_chat_img = {}
            ctx_img_prox_dialogo_handle = st.session_state.get(last_uploaded_info_key)
            if ctx_img_prox_dialogo_handle and not st.session_state.get(user_input_processed_key, False): 
                kwargs_chat_img['descricao_imagem_contexto'] = ctx_img_prox_dialogo_handle
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat_img)
            if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
                st.session_state.pop(last_uploaded_info_key, None) 
                st.session_state[user_input_processed_key] = False

        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
            contexto_para_ia_local = None
            processed_file_id_key_handle = f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}'
            uploaded_info_key_handle = f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}'
            user_input_processed_key_handle = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'
            if uploaded_files_objs:
                current_file_signature_handle = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id if hasattr(f, 'file_id') else f.id}" for f in uploaded_files_objs]))
                if st.session_state.get(processed_file_id_key_handle) != current_file_signature_handle or not st.session_state.get(uploaded_info_key_handle):
                    text_contents_handle, image_info_handle = [], []
                    for f_item_handle in uploaded_files_objs:
                        try:
                            if f_item_handle.type == "text/plain": 
                                text_contents_handle.append(f"Arquivo '{f_item_handle.name}':\n{f_item_handle.read().decode('utf-8')[:3000]}...")
                            elif f_item_handle.type in ["image/png","image/jpeg"]: 
                                st.image(Image.open(f_item_handle),caption=f"Contexto: {f_item_handle.name}",width=100)
                                image_info_handle.append(f"Imagem '{f_item_handle.name}'.")
                        except Exception as e_file_proc_handle: st.error(f"Erro ao processar '{f_item_handle.name}': {e_file_proc_handle}")
                    full_ctx_str_handle = ("\n\n--- TEXTO DOS ARQUIVOS ---\n" + "\n\n".join(text_contents_handle) if text_contents_handle else "") + \
                                          ("\n\n--- IMAGENS FORNECIDAS ---\n" + "\n".join(image_info_handle) if image_info_handle else "")
                    if full_ctx_str_handle.strip(): 
                        st.session_state[uploaded_info_key_handle] = full_ctx_str_handle.strip()
                        contexto_para_ia_local = st.session_state[uploaded_info_key_handle]
                        st.info("Arquivo(s) de contexto pronto(s).")
                    else: 
                        st.session_state.pop(uploaded_info_key_handle, None)
                    st.session_state[processed_file_id_key_handle] = current_file_signature_handle
                else: 
                    contexto_para_ia_local = st.session_state.get(uploaded_info_key_handle)
            kwargs_chat_files = {}
            if contexto_para_ia_local and not st.session_state.get(user_input_processed_key_handle, False): 
                kwargs_chat_files['contexto_arquivos'] = contexto_para_ia_local
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat_files)
            if user_input_processed_key_handle in st.session_state and st.session_state[user_input_processed_key_handle]:
                st.session_state.pop(uploaded_info_key_handle, None)
                st.session_state[user_input_processed_key_handle] = False

        # --- Instanciação do Agente ---
        if 'agente_pme' not in st.session_state or \
           not isinstance(st.session_state.agente_pme, AssistentePMEPro) or \
           (hasattr(st.session_state.agente_pme, 'llm') and st.session_state.agente_pme.llm != llm_model_instance):
            st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme
        
        # --- Interface da Sidebar (após login) ---
        st.sidebar.write(f"Logado como: {display_email}")
        if st.sidebar.button("Logout", key=f"main_app_logout{APP_KEY_SUFFIX}"): 
            st.session_state.user_session_pyrebase = None
            st.session_state.pop('firebase_init_success_message_shown', None)
            st.session_state.pop('firebase_app_instance', None) 
            st.session_state.pop('llm_init_success_sidebar_shown_main_app', None)
            keys_to_clear_logout = ['agente_pme', 'area_selecionada']
            for key in list(st.session_state.keys()):
                if APP_KEY_SUFFIX in key or key.startswith('memoria_') or \
                   key.startswith('chat_display_') or key.startswith('generated_') or \
                   key.startswith('post_') or key.startswith('campaign_') or \
                   key.startswith('main_marketing_action_choice') or \
                   key.startswith('sidebar_selection') or \
                   key.startswith('previous_area_selecionada_for_chat_init'):
                    keys_to_clear_logout.append(key)
            for key_to_clear in set(keys_to_clear_logout):
                st.session_state.pop(key_to_clear, None)
            st.rerun()

        # Logo da Sidebar (Corrigido para usar try-except)
        LOGO_PATH_SIDEBAR_AUTH = "images/logo-pme-ia.png"
        FALLBACK_LOGO_URL_SIDEBAR_AUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.sidebar.image(LOGO_PATH_SIDEBAR_AUTH, width=150)
        except Exception:
            st.sidebar.image(FALLBACK_LOGO_URL_SIDEBAR_AUTH, width=150, caption="Logo (Fallback)")

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
        radio_key_sidebar_main_nav_app = f'sidebar_nav_main_app{APP_KEY_SUFFIX}' 
        if 'area_selecionada' not in st.session_state or st.session_state.area_selecionada not in opcoes_menu:
            st.session_state.area_selecionada = "Página Inicial"
        try:
            current_nav_radio_index_val = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)
        except ValueError:
            current_nav_radio_index_val = 0
            st.session_state.area_selecionada = list(opcoes_menu.keys())[0]
        
        area_selecionada_label = st.sidebar.radio(
            "Como posso te ajudar hoje?", 
            options=list(opcoes_menu.keys()), 
            key=radio_key_sidebar_main_nav_app,
            index=current_nav_radio_index_val
        )

        if area_selecionada_label != st.session_state.area_selecionada:
            st.session_state.area_selecionada = area_selecionada_label
            if area_selecionada_label != "Marketing Digital com IA (Guia)":
                keys_to_clear_mkt_nav_app_on_change = [
                    k for k in st.session_state if 
                    (k.startswith("generated_") and k.endswith(f"_new{APP_KEY_SUFFIX}")) or 
                    (f"post{APP_KEY_SUFFIX}" in k and not k.startswith("post_creator_details")) or # Evitar limpar os detalhes do form ativo
                    (f"campaign{APP_KEY_SUFFIX}" in k and not k.startswith("campaign_creator_details")) or # Evitar limpar os detalhes do form ativo
                    k == f"main_marketing_action_choice{APP_KEY_SUFFIX}_index"
                ]
                for key_clear_mkt_on_change in keys_to_clear_mkt_nav_app_on_change:
                    st.session_state.pop(key_clear_mkt_on_change, None)
            st.rerun() 

        current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
        
        if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
            chat_init_flag_key_app = f'previous_area_selecionada_for_chat_init{APP_KEY_SUFFIX}'
            chat_display_key_specific_app = f"chat_display_{current_section_key}{APP_KEY_SUFFIX}"
            needs_chat_reset_main_app_logic = False
            if st.session_state.area_selecionada != st.session_state.get(chat_init_flag_key_app): needs_chat_reset_main_app_logic = True
            elif chat_display_key_specific_app not in st.session_state: needs_chat_reset_main_app_logic = True
            elif not st.session_state.get(chat_display_key_specific_app): needs_chat_reset_main_app_logic = True
            if needs_chat_reset_main_app_logic:
                msg_inicial_nav_app, memoria_agente_nav_app = "", None
                if current_section_key == "plano_negocios": msg_inicial_nav_app, memoria_agente_nav_app = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia.", agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav_app, memoria_agente_nav_app = "Olá! Para calcular preços, descreva seu produto/serviço. Pode enviar uma imagem.", agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav_app, memoria_agente_nav_app = "Olá! Buscando ideias? Descreva seu desafio ou envie arquivos de contexto.", agente.memoria_gerador_ideias
                if msg_inicial_nav_app and memoria_agente_nav_app is not None: inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav_app, memoria_agente_nav_app)
                st.session_state[chat_init_flag_key_app] = st.session_state.area_selecionada

        # --- SELEÇÃO E EXIBIÇÃO DA SEÇÃO ATUAL ---
        if current_section_key == "pagina_inicial":
            st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
            st.markdown("---")
            # LOGO DA PÁGINA INICIAL REMOVIDO
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
                        # Usando uma chave única para os botões da página inicial
                        button_key_pg_inicial = f"btn_goto_{chave_secao_btn_pg}{APP_KEY_SUFFIX}_pg_inicial"
                        if col_para_botao_pg.button(button_label_pg, key=button_key_pg_inicial, use_container_width=True, help=f"Ir para {nome_menu_btn_pg}"):
                            st.session_state.area_selecionada = nome_menu_btn_pg
                            try: 
                                st.session_state[f'{radio_key_sidebar_main_nav_app}_index'] = list(opcoes_menu.keys()).index(nome_menu_btn_pg)
                            except ValueError: pass
                            st.rerun()
                        btn_idx_pg_inicial +=1
        
        elif current_section_key == "marketing_guiado": agente.marketing_digital_guiado()
        elif current_section_key == "plano_negocios": 
            st.header("📝 Elaborando seu Plano de Negócios com IA")
            st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
            exibir_chat_e_obter_input(current_section_key, "Sua resposta ou próxima seção do plano...", agente.conversar_plano_de_negocios)
            _sidebar_clear_button("Plano", agente.memoria_plano_negocios, current_section_key)
        elif current_section_key == "calculo_precos": 
            st.header("💲 Cálculo de Preços Inteligente com IA")
            st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
            uploaded_image_preco_app = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key=f"preco_img_uploader{APP_KEY_SUFFIX}")
            _handle_chat_with_image("calculo_precos", "Descreva o produto/serviço, custos, etc.", agente.calcular_precos_interativo, uploaded_image_preco_app)
            _sidebar_clear_button("Preços", agente.memoria_calculo_precos, current_section_key)
        elif current_section_key == "gerador_ideias": 
            st.header("💡 Gerador de Ideias para seu Negócio com IA")
            st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
            uploaded_files_ideias_app_ui = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"ideias_file_uploader{APP_KEY_SUFFIX}")
            _handle_chat_with_files("gerador_ideias", "Descreva seu desafio ou peça ideias:", agente.gerar_ideias_para_negocios, uploaded_files_ideias_app_ui)
            _sidebar_clear_button("Ideias", agente.memoria_gerador_ideias, current_section_key)
    
    else: 
        st.error("🚨 O Assistente PME Pro não pôde ser iniciado.")
        st.info("Isso pode ter ocorrido devido a um problema com a chave da API do Google ou ao contatar os serviços do Google Generative AI.")
        if llm_init_exception: 
            st.exception(llm_init_exception)

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: 
    st.session_state.pop('auth_error_shown', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 

    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key_else_final = f"app_auth_action_choice{APP_KEY_SUFFIX}_corrected_else" 
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key_else_final)

    if auth_action_choice == "Login":
        with st.sidebar.form(f"app_login_form{APP_KEY_SUFFIX}_corrected_else"): 
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None)
                        st.rerun()
                    except Exception as e_login_final_corrected:
                        error_message_login_final_corrected = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str_final_corrected = e_login_final_corrected.args[0] if len(e_login_final_corrected.args) > 0 else "{}"
                            error_data_final_corrected = json.loads(error_details_str_final_corrected.replace("'", "\""))
                            api_error_message_final_corrected = error_data_final_corrected.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message_final_corrected or "EMAIL_NOT_FOUND" in api_error_message_final_corrected or "INVALID_PASSWORD" in api_error_message_final_corrected or "USER_DISABLED" in api_error_message_final_corrected or "INVALID_EMAIL" in api_error_message_final_corrected:
                                error_message_login_final_corrected = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message_final_corrected: error_message_login_final_corrected = f"Erro no login: {api_error_message_final_corrected}"
                        except: pass 
                        st.sidebar.error(error_message_login_final_corrected)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"app_register_form{APP_KEY_SUFFIX}_corrected_else"): 
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: 
                           pb_auth_client.send_email_verification(user['idToken'])
                           st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_final_corrected: 
                           st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_final_corrected}")
                    except Exception as e_register_final_corrected:
                        error_message_register_final_corrected = "Erro no registro."
                        try:
                            error_details_str_reg_final_corrected = e_register_final_corrected.args[0] if len(e_register_final_corrected.args) > 0 else "{}"
                            error_data_reg_final_corrected = json.loads(error_details_str_reg_final_corrected.replace("'", "\""))
                            api_error_message_reg_final_corrected = error_data_reg_final_corrected.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message_reg_final_corrected:
                                error_message_register_final_corrected = "Este email já está registrado. Tente fazer login."
                            elif api_error_message_reg_final_corrected:
                                error_message_register_final_corrected = f"Erro no registro: {api_error_message_reg_final_corrected}"
                        except: 
                             error_message_register_final_corrected = f"Erro no registro: {str(e_register_final_corrected)}"
                        st.sidebar.error(error_message_register_final_corrected)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        LOGO_PATH_LOGIN_UNAUTH_APP = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_LOGIN_UNAUTH_APP = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_LOGIN_UNAUTH_APP, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_LOGIN_UNAUTH_APP, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
