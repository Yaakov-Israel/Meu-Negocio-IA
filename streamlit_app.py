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
# (Esta seção é idêntica à da nossa versão funcional de autenticação)
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False

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
except AttributeError as e_attr: 
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr}"
except Exception as e_general: 
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general}"

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    # Tenta mostrar o traceback se 'e_general' ou 'e_attr' estiverem definidos
    current_exception = locals().get('e_general', locals().get('e_attr', Exception(error_message_firebase_init)))
    st.exception(current_exception)
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
        # Verifica se o token ainda é válido e atualiza infos do usuário se necessário
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None) # Limpa flag de erro ao autenticar
    except Exception as e_session: 
        error_message_session_check = "Sessão inválida ou expirada."
        try:
            error_details_str = e_session.args[0] if len(e_session.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\"")) # Tenta normalizar para JSON
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
            else: 
                error_message_session_check = f"Erro ao verificar sessão ({api_error_message}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError): # AttributeError adicionado
            error_message_session_check = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session)}"
        
        st.session_state.user_session_pyrebase = None 
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state: 
            st.sidebar.warning(error_message_session_check)
            st.session_state.auth_error_shown = True
        
        if not st.session_state.get('running_rerun_after_auth_fail_main_v2', False): # Nova chave de controle de rerun
            st.session_state.running_rerun_after_auth_fail_main_v2 = True
            st.rerun()
        else:
            st.session_state.pop('running_rerun_after_auth_fail_main_v2', None)

if 'running_rerun_after_auth_fail_main_v2' in st.session_state and st.session_state.running_rerun_after_auth_fail_main_v2:
    st.session_state.pop('running_rerun_after_auth_fail_main_v2', None)
    # Evita renderizar o resto se estivermos em um rerun forçado por falha de autenticação
# --- Interface do Usuário Condicional e Lógica Principal do App ---
KEY_SUFFIX_APP_GLOBAL = "_v22_final_app" # Novo sufixo global para esta versão

if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    
    # Inicialização do LLM (SÓ SE AUTENTICADO)
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None

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
            if 'llm_init_success_sidebar_shown' not in st.session_state:
                st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
                st.session_state.llm_init_success_sidebar_shown = True
        except Exception as e_llm_init:
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm_init}")
            st.stop()

    if llm_model_instance:
        # --- FUNÇÕES AUXILIARES PARA MARKETING DIGITAL (Objetivos e Output) ---
        def _marketing_get_objective_details(section_key_local, type_of_creation="post/campanha"):
            st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
            details = {}
            details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key_local}_obj{KEY_SUFFIX_APP_GLOBAL}")
            details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key_local}_audience{KEY_SUFFIX_APP_GLOBAL}")
            details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key_local}_product{KEY_SUFFIX_APP_GLOBAL}")
            details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key_local}_message{KEY_SUFFIX_APP_GLOBAL}")
            details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key_local}_usp{KEY_SUFFIX_APP_GLOBAL}")
            details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key_local}_tone{KEY_SUFFIX_APP_GLOBAL}")
            details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key_local}_extra{KEY_SUFFIX_APP_GLOBAL}")
            return details

        def _marketing_display_output_options(generated_content, section_key_local, file_name_prefix="conteudo_gerado"):
            st.subheader("🎉 Resultado da IA e Próximos Passos:")
            st.markdown(generated_content)
            st.download_button(label="📥 Baixar Conteúdo Gerado", data=generated_content.encode('utf-8'), file_name=f"{file_name_prefix}_{section_key_local}{KEY_SUFFIX_APP_GLOBAL}.txt", mime="text/plain", key=f"download_{section_key_local}{KEY_SUFFIX_APP_GLOBAL}")
            cols_actions = st.columns(2)
            with cols_actions[0]:
                if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key_local}_share_btn{KEY_SUFFIX_APP_GLOBAL}"):
                    st.success("Conteúdo pronto para ser copiado e compartilhado!")
            with cols_actions[1]:
                if st.button("🗓️ Simular Agendamento", key=f"{section_key_local}_schedule_btn{KEY_SUFFIX_APP_GLOBAL}"):
                    st.info("Agendamento simulado.")

        def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
            # (Lógica da função como antes, usando KEY_SUFFIX_APP_GLOBAL para session_state e widget keys)
            if not selected_platforms_list: st.warning("Por favor, selecione pelo menos uma plataforma."); return
            if not details_dict["objective"]: st.warning("Por favor, descreva o objetivo do post."); return
            with st.spinner("🤖 A IA está criando seu post..."):
                prompt_parts = [
                    "**Instrução para IA:** Você é um especialista em copywriting para PMEs no Brasil...",
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                    f"**Produto/Serviço Principal:** {details_dict['product_service']}",
                    f"**Público-Alvo:** {details_dict['target_audience']}",
                    f"**Objetivo do Post:** {details_dict['objective']}",
                    f"**Mensagem Chave:** {details_dict['key_message']}",
                    f"**Proposta Única de Valor (USP):** {details_dict['usp']}",
                    f"**Tom/Estilo:** {details_dict['style_tone']}",
                    f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
                ] 
                if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_post_content{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content

        def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
            if not selected_platforms_list: st.warning("Selecione plataforma(s)."); return
            if not details_dict["objective"]: st.warning("Descreva o objetivo."); return
            with st.spinner("🧠 Plano de campanha em elaboração..."):
                prompt_parts = [
                    "**Instrução para IA:** Estrategista de marketing digital para PMEs no Brasil. Plano de campanha conciso...",
                    f"**Nome da Campanha:** {campaign_specifics['name']}",
                    f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                     # ... (completar com todas as chaves de details_dict e campaign_specifics)
                    f"**Produto/Serviço Principal:** {details_dict['product_service']}",
                    f"**Público-Alvo:** {details_dict['target_audience']}",
                    f"**Objetivo:** {details_dict['objective']}",
                    f"**Mensagem Chave:** {details_dict['key_message']}",
                    f"**USP:** {details_dict['usp']}",
                    f"**Tom/Estilo:** {details_dict['style_tone']}",
                    f"**Duração:** {campaign_specifics['duration']}",
                    f"**Orçamento:** {campaign_specifics['budget']}",
                    f"**KPIs:** {campaign_specifics['kpis']}",
                    f"**Informações Adicionais/CTA:** {details_dict['extra_info']}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_campaign_content{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content
        
        def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
            if not lp_details["purpose"] or not lp_details["main_offer"] or not lp_details["cta"]: st.warning("Preencha objetivo, oferta e CTA."); return
            with st.spinner("🎨 Estrutura da landing page..."):
                prompt_parts = [
                    "**Instrução para IA:** Especialista UX/UI e copy para LPs de alta conversão (PMEs Brasil)...",
                    f"**Objetivo LP:** {lp_details['purpose']}",
                    f"**Público-Alvo:** {lp_details['target_audience']}",
                    f"**Oferta Principal:** {lp_details['main_offer']}",
                    f"**Benefícios Chave:** {lp_details['key_benefits']}",
                    f"**CTA Principal:** {lp_details['cta']}",
                    f"**Preferências Visuais:** {lp_details['visual_prefs']}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_lp_content{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content

        def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
            if not site_details["business_type"] or not site_details["main_purpose"]: st.warning("Informe tipo de negócio e objetivo."); return
            with st.spinner("🛠️ Arquitetura do site..."):
                prompt_parts = [
                    "**Instrução para IA:** Arquiteto de informação e web designer (PMEs Brasil). Estrutura de site e conteúdo chave...",
                    f"**Tipo de Negócio:** {site_details['business_type']}",
                    f"**Objetivo do Site:** {site_details['main_purpose']}",
                    f"**Público-Alvo:** {site_details['target_audience']}",
                    f"**Páginas Essenciais:** {site_details['essential_pages']}",
                    f"**Diferenciais:** {site_details['key_features']}",
                    f"**Personalidade da Marca:** {site_details['brand_personality']}",
                    f"**Referências Visuais:** {site_details['visual_references']}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_site_content{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content

        def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
            if not client_details["product_campaign"]: st.warning("Descreva produto/campanha."); return
            with st.spinner("🕵️ Análise de público-alvo..."):
                prompt_parts = [
                    "**Instrução para IA:** 'Agente Detetive de Clientes' (PMEs Brasil). Persona detalhada, canais, mensagens...",
                    f"**Produto/Campanha:** {client_details['product_campaign']}",
                    f"**Localização:** {client_details['location']}",
                    f"**Verba:** {client_details['budget']}",
                    f"**Idade/Gênero:** {client_details['age_gender']}",
                    f"**Interesses/Dores:** {client_details['interests']}",
                    f"**Canais Atuais:** {client_details['current_channels']}",
                    f"**Nível Pesquisa:** {'Deep Research' if client_details['deep_research'] else 'Padrão'}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_client_analysis{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content

        def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
            if not competitor_details["your_business"] or not competitor_details["competitors_list"]: st.warning("Descreva seu negócio e concorrentes."); return
            with st.spinner("🔬 Análise de concorrência..."):
                prompt_parts = [
                    "**Instrução para IA:** 'Agente de Inteligência Competitiva' (PMEs Brasil). Análise de concorrentes, pontos fortes/fracos, oportunidades...",
                    f"**Seu Negócio:** {competitor_details['your_business']}",
                    f"**Concorrentes:** {competitor_details['competitors_list']}",
                    f"**Aspectos para Análise:** {', '.join(competitor_details['aspects_to_analyze'])}"
                ]
                if uploaded_files_info: prompt_parts.append(f"**Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
                final_prompt = "\n\n".join(prompt_parts)
                ai_response = llm.invoke(HumanMessage(content=final_prompt))
                st.session_state[f'generated_competitor_analysis{KEY_SUFFIX_APP_GLOBAL}'] = ai_response.content

        # --- Classe do Agente (AssistentePMEPro) ---
        class AssistentePMEPro:
            def __init__(self, llm_passed_model):
                if llm_passed_model is None: st.error("Erro: LLM não fornecido ao AssistentePMEPro."); st.stop()
                self.llm = llm_passed_model
                # Inicializa memórias com sufixo global para unicidade
                for mem_key in ["plano_negocios", "calculo_precos", "gerador_ideias"]:
                    session_key = f'memoria_{mem_key}{KEY_SUFFIX_APP_GLOBAL}'
                    if session_key not in st.session_state:
                        st.session_state[session_key] = ConversationBufferMemory(memory_key=f"historico_chat_{mem_key}{KEY_SUFFIX_APP_GLOBAL}", return_messages=True)
                self.memoria_plano_negocios = st.session_state[f'memoria_plano_negocios{KEY_SUFFIX_APP_GLOBAL}']
                self.memoria_calculo_precos = st.session_state[f'memoria_calculo_precos{KEY_SUFFIX_APP_GLOBAL}']
                self.memoria_gerador_ideias = st.session_state[f'memoria_gerador_ideias{KEY_SUFFIX_APP_GLOBAL}']

            def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
                # O placeholder real usado na memória é definido na inicialização da memória
                actual_memory_key = memoria_especifica.memory_key
                prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(system_message_content),
                    MessagesPlaceholder(variable_name=actual_memory_key), 
                    HumanMessagePromptTemplate.from_template("{input_usuario}")
                ])
                return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

            def marketing_digital_guiado(self):
                st.header("🚀 Marketing Digital Interativo com IA")
                # (Restante da sua lógica de marketing_digital_guiado, usando KEY_SUFFIX_APP_GLOBAL para todas as chaves de widget e session_state)
                # ... (código omitido por brevidade, mas você deve colar o seu aqui, adaptando as chaves) ...
                # Exemplo de adaptação de chave:
                # main_action_key = f"main_marketing_action_choice{KEY_SUFFIX_APP_GLOBAL}"
                # ...
                # if 'generated_post_content' + KEY_SUFFIX_APP_GLOBAL in st.session_state:
                #    _marketing_display_output_options(st.session_state['generated_post_content' + KEY_SUFFIX_APP_GLOBAL], "post_output" + KEY_SUFFIX_APP_GLOBAL, "post_ia")
                st.info("Seção de Marketing Digital Guiado em construção aqui.")


            def conversar_plano_de_negocios(self, input_usuario):
                system_message_plano = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente especializado em auxiliar Pequenas e Médias Empresas (PMEs) no Brasil a desenvolverem planos de negócios robustos e estratégicos. Seu objetivo é guiar o usuário através das seções de um plano de negócios, fazendo perguntas pertinentes, oferecendo insights e ajudando a estruturar as ideias. Mantenha um tom profissional, encorajador e prático."
                cadeia = self._criar_cadeia_conversacional(system_message_plano, self.memoria_plano_negocios, memory_key_placeholder_base=f"historico_chat_plano{KEY_SUFFIX_APP_GLOBAL}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
                prompt_content_calc = f"O usuário está buscando ajuda para precificar um produto/serviço e forneceu a seguinte informação inicial: '{input_usuario}'."
                if descricao_imagem_contexto: prompt_content_calc = f"{descricao_imagem_contexto}\n\n{prompt_content_calc}"
                system_message_precos = f"""Você é o "Assistente PME Pro", um especialista em estratégias de precificação para PMEs no Brasil. {prompt_content_calc} Comece fazendo perguntas claras e objetivas para entender os custos (fixos e variáveis), o valor percebido pelo cliente, os preços da concorrência e os objetivos de margem de lucro do usuário. Guie-o passo a passo no processo de cálculo, sugerindo métodos como markup, margem de contribuição ou precificação baseada em valor, conforme apropriado."""
                cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder_base=f"historico_chat_precos{KEY_SUFFIX_APP_GLOBAL}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base nas informações que forneci (incluindo a descrição e a imagem, se houver), quais seriam os próximos passos ou perguntas para definirmos o preço?"}) 
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

            def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
                prompt_content_ideias = f"O usuário busca ideias criativas e viáveis para seu negócio (ou um novo negócio) e descreve seu desafio ou ponto de partida como: '{input_usuario}'."
                if contexto_arquivos: prompt_content_ideias = f"Adicionalmente, o usuário forneceu o seguinte contexto a partir de arquivos:\n{contexto_arquivos}\n\n{prompt_content_ideias}"
                system_message_ideias = f"""Você é o "Assistente PME Pro", um consultor de negócios altamente criativo e com visão de mercado, focado em PMEs no Brasil. {prompt_content_ideias} Faça perguntas exploratórias para entender melhor as paixões, habilidades, recursos disponíveis e o mercado de interesse do usuário. Com base nisso, gere 3-5 ideias de negócios ou inovações distintas e acionáveis, cada uma com uma breve justificativa e potenciais primeiros passos. Priorize ideias com potencial de crescimento e alinhadas com tendências atuais."""
                cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder_base=f"historico_chat_ideias{KEY_SUFFIX_APP_GLOBAL}")
                resposta_ai_obj = cadeia.invoke({"input_usuario": "Com base no que descrevi e nos arquivos (se houver), quais ideias inovadoras você sugere?"})
                return resposta_ai_obj['text'] if isinstance(resposta_ai_obj, dict) and 'text' in resposta_ai_obj else str(resposta_ai_obj)

        # --- Funções Utilitárias de Chat (adaptadas para usar KEY_SUFFIX_APP_GLOBAL) ---
        def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
            chat_display_key = f"chat_display_{area_chave}{KEY_SUFFIX_APP_GLOBAL}"
            st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
            if memoria_agente_instancia:
                memoria_agente_instancia.clear()
                memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
            
            if area_chave == "calculo_precos": 
                st.session_state.pop(f'last_uploaded_image_info_{area_chave}{KEY_SUFFIX_APP_GLOBAL}', None)
                st.session_state.pop(f'processed_image_id_{area_chave}{KEY_SUFFIX_APP_GLOBAL}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{KEY_SUFFIX_APP_GLOBAL}', None)
            elif area_chave == "gerador_ideias": 
                st.session_state.pop(f'uploaded_file_info_{area_chave}_for_prompt{KEY_SUFFIX_APP_GLOBAL}', None)
                st.session_state.pop(f'processed_file_id_{area_chave}{KEY_SUFFIX_APP_GLOBAL}', None)
                st.session_state.pop(f'user_input_processed_{area_chave}{KEY_SUFFIX_APP_GLOBAL}', None)

        def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
            chat_display_key = f"chat_display_{area_chave}{KEY_SUFFIX_APP_GLOBAL}"
            if chat_display_key not in st.session_state: st.session_state[chat_display_key] = [] 
            for msg_info in st.session_state[chat_display_key]:
                with st.chat_message(msg_info["role"]): st.markdown(msg_info["content"])
            prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{KEY_SUFFIX_APP_GLOBAL}")
            if prompt_usuario:
                st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
                with st.chat_message("user"): st.markdown(prompt_usuario)
                if area_chave in ["calculo_precos", "gerador_ideias"]: st.session_state[f'user_input_processed_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'] = True
                with st.spinner("Assistente PME Pro processando..."):
                    resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
                st.rerun()
        
        def _sidebar_clear_button(label, memoria, section_key): 
            if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key}{KEY_SUFFIX_APP_GLOBAL}_clear"):
                msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
                if section_key == "calculo_precos": msg_inicial = "Ok, vamos recomeçar o cálculo de preços! Descreva seu produto ou serviço."
                elif section_key == "gerador_ideias": msg_inicial = "Ok, vamos recomeçar a geração de ideias! Qual o seu ponto de partida?"
                inicializar_ou_resetar_chat(section_key, msg_inicial, memoria) 
                st.rerun()

        def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj): 
            descricao_imagem_para_ia = None
            processed_image_id_key = f'processed_image_id_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'
            last_uploaded_info_key = f'last_uploaded_image_info_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'
            user_input_processed_key = f'user_input_processed_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'

            if uploaded_image_obj is not None:
                if st.session_state.get(processed_image_id_key) != uploaded_image_obj.file_id: # Usar file_id para unicidade
                    try:
                        img_pil = Image.open(uploaded_image_obj); st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                        descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                        st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                        st.session_state[processed_image_id_key] = uploaded_image_obj.file_id
                        st.info(f"Imagem '{uploaded_image_obj.name}' pronta.")
                    except Exception as e: st.error(f"Erro ao processar imagem: {e}"); st.session_state[last_uploaded_info_key] = None; st.session_state[processed_image_id_key] = None
                else: descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
            kwargs_chat = {}
            ctx_img_prox_dialogo = st.session_state.get(last_uploaded_info_key)
            if ctx_img_prox_dialogo and not st.session_state.get(user_input_processed_key, False): kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
            exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
            if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
                if st.session_state.get(last_uploaded_info_key): st.session_state[last_uploaded_info_key] = None
                st.session_state[user_input_processed_key] = False

        def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
            contexto_para_ia_local = None
            processed_file_id_key = f'processed_file_id_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'
            uploaded_info_key = f'uploaded_file_info_{area_chave}_for_prompt{KEY_SUFFIX_APP_GLOBAL}'
            user_input_processed_key = f'user_input_processed_{area_chave}{KEY_SUFFIX_APP_GLOBAL}'

            if uploaded_files_objs:
                current_file_signature = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id}" for f in uploaded_files_objs])) # Adicionar file_id
                if st.session_state.get(processed_file_id_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                    text_contents, image_info = [], []
                    for f_item in uploaded_files_objs:
                        try:
                            if f_item.type == "text/plain": text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...")
                            elif f_item.type in ["image/png","image/jpeg"]: st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100); image_info.append(f"Imagem '{f_item.name}'.")
                        except Exception as e: st.error(f"Erro ao processar '{f_item.name}': {e}")
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
        if 'agente_pme' not in st.session_state or not isinstance(st.session_state.agente_pme, AssistentePMEPro):
            st.session_state.agente_pme = AssistentePMEPro(llm_passed_model=llm_model_instance)
        agente = st.session_state.agente_pme
        
        # --- Lógica de Navegação Principal (Sidebar) ---
        opcoes_menu = { 
            "Página Inicial": "pagina_inicial", 
            "Marketing Digital com IA (Guia)": "marketing_guiado",
            "Elaborar Plano de Negócios com IA": "plano_negocios", 
            "Cálculo de Preços Inteligente": "calculo_precos",
            "Gerador de Ideias para Negócios": "gerador_ideias"
        }
        radio_key_sidebar_main = f'sidebar_selection{KEY_SUFFIX_APP_GLOBAL}_main'
        
        if 'area_selecionada' not in st.session_state or st.session_state.area_selecionada not in opcoes_menu:
            st.session_state.area_selecionada = "Página Inicial" # Define o padrão
        
        # Determina o índice do radio button
        try:
            current_radio_index = list(opcoes_menu.keys()).index(st.session_state.area_selecionada)
        except ValueError:
            current_radio_index = 0 # Default para "Página Inicial" se a chave não for encontrada
            st.session_state.area_selecionada = list(opcoes_menu.keys())[0]

        area_selecionada_label = st.sidebar.radio(
            "Como posso te ajudar hoje?", 
            options=list(opcoes_menu.keys()), 
            key=radio_key_sidebar_main, 
            index=current_radio_index
        )

        if area_selecionada_label != st.session_state.area_selecionada:
            st.session_state.area_selecionada = area_selecionada_label
            # Limpar estados específicos de seções ao mudar de seção, se necessário
            if area_selecionada_label != "Marketing Digital com IA (Guia)":
                # Adapte esta lógica de limpeza conforme necessário
                keys_to_clear_on_nav = [k for k in st.session_state if k.startswith('generated_') or k.startswith('post_platform_') or k.startswith('campaign_platform_')]
                for key_clear_nav in keys_to_clear_on_nav:
                    st.session_state.pop(key_clear_nav, None)
            st.rerun() 

        current_section_key = opcoes_menu.get(st.session_state.area_selecionada)
        
        # Inicializar chats quando a seção é selecionada pela primeira vez ou mudada
        if current_section_key not in ["pagina_inicial", "marketing_guiado"]:
            chat_init_flag_key = f'previous_area_selecionada_for_chat_init{KEY_SUFFIX_APP_GLOBAL}'
            chat_display_key_specific = f"chat_display_{current_section_key}{KEY_SUFFIX_APP_GLOBAL}"
            if st.session_state.area_selecionada != st.session_state.get(chat_init_flag_key) or \
               chat_display_key_specific not in st.session_state or \
               not st.session_state[chat_display_key_specific]:
                
                msg_inicial_nav, memoria_agente_nav = "", None
                if current_section_key == "plano_negocios": msg_inicial_nav, memoria_agente_nav = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia.", agente.memoria_plano_negocios
                elif current_section_key == "calculo_precos": msg_inicial_nav, memoria_agente_nav = "Olá! Para calcular preços, descreva seu produto/serviço. Pode enviar uma imagem.", agente.memoria_calculo_precos
                elif current_section_key == "gerador_ideias": msg_inicial_nav, memoria_agente_nav = "Olá! Buscando ideias? Descreva seu desafio ou envie arquivos de contexto.", agente.memoria_gerador_ideias
                
                if msg_inicial_nav and memoria_agente_nav is not None:
                    inicializar_ou_resetar_chat(current_section_key, msg_inicial_nav, memoria_agente_nav)
                st.session_state[chat_init_flag_key] = st.session_state.area_selecionada

        # --- SELEÇÃO E EXIBIÇÃO DA SEÇÃO ATUAL ---
        if current_section_key == "pagina_inicial":
            st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p>Use o menu à esquerda para navegar pelas ferramentas.</p></div>", unsafe_allow_html=True)
            st.markdown("---")
            # Logo foi removido daqui conforme seu feedback, pois já existe na sidebar.
            # Se quiser adicionar algo visual aqui, pode ser um st.image genérico ou ícones.
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
                        if col_para_botao_pg.button(button_label_pg, key=f"btn_goto_{chave_secao_btn_pg}{KEY_SUFFIX_APP_GLOBAL}", use_container_width=True, help=f"Ir para {nome_menu_btn_pg}"):
                            st.session_state.area_selecionada = nome_menu_btn_pg
                            # Atualiza o índice do radio button da sidebar ao clicar no botão da página inicial
                            try: st.session_state[f'{radio_key_sidebar_main}_index'] = list(opcoes_menu.keys()).index(nome_menu_btn_pg)
                            except ValueError: pass # Se o nome não for encontrado, não faz nada (deve ser encontrado)
                            st.rerun()
                        btn_idx_pg_inicial +=1
        
        elif current_section_key == "marketing_guiado": 
            agente.marketing_digital_guiado()
        elif current_section_key == "plano_negocios": 
            st.header("📝 Elaborando seu Plano de Negócios com IA")
            exibir_chat_e_obter_input(current_section_key, "Sua resposta ou próxima seção do plano...", agente.conversar_plano_de_negocios)
            _sidebar_clear_button("Plano", agente.memoria_plano_negocios, current_section_key)
        elif current_section_key == "calculo_precos": 
            st.header("💲 Cálculo de Preços Inteligente com IA")
            uploaded_image_preco = st.file_uploader("Imagem do produto (opcional):", type=["png","jpg","jpeg"],key=f"preco_img{KEY_SUFFIX_APP_GLOBAL}")
            _handle_chat_with_image("calculo_precos", "Descreva produto/custos...", agente.calcular_precos_interativo, uploaded_image_preco)
            _sidebar_clear_button("Preços", agente.memoria_calculo_precos, current_section_key)
        elif current_section_key == "gerador_ideias": 
            st.header("💡 Gerador de Ideias para seu Negócio com IA")
            uploaded_files_ideias = st.file_uploader("Arquivos de contexto (opcional):",type=["txt","png","jpg","jpeg"],accept_multiple_files=True,key=f"ideias_files{KEY_SUFFIX_APP_GLOBAL}")
            _handle_chat_with_files("gerador_ideias", "Descreva seu desafio...", agente.gerar_ideias_para_negocios, uploaded_files_ideias)
            _sidebar_clear_button("Ideias", agente.memoria_gerador_ideias, current_section_key)

    else: 
        st.error("🚨 O Assistente PME Pro não pôde ser iniciado devido a um problema com o modelo LLM.")
        st.info("Verifique a API Key do Google e a configuração do modelo nos segredos.")

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else: 
    st.session_state.pop('auth_error_shown', None) 
    st.title("🔑 Bem-vindo ao Assistente PME Pro") 
    st.sidebar.subheader("Login / Registro")
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=f"app_auth_action_choice{KEY_SUFFIX_APP_GLOBAL}_else")

    if auth_action_choice == "Login":
        with st.sidebar.form(f"app_login_form{KEY_SUFFIX_APP_GLOBAL}_else"):
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
                    except Exception as e:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: error_message_login = f"Erro no login: {api_error_message}"
                        except: pass
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form(f"app_register_form{KEY_SUFFIX_APP_GLOBAL}_else"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try: pb_auth_client.send_email_verification(user['idToken']); st.sidebar.info("Email de verificação enviado.")
                        except Exception as verify_email_error: st.sidebar.caption(f"Nota: Envio de email de verificação falhou: {verify_email_error}")
                    except Exception as e:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message: error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message: error_message_register = f"Erro no registro: {api_error_message}"
                        except: error_message_register = f"Erro no registro: {str(e)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: 
        st.info("Faça login ou registre-se na barra lateral para usar o Assistente PME Pro.")
        # Logo da tela de login (se a pasta 'images' estiver correta)
        LOGO_PATH_UNAUTH = "images/logo-pme-ia.png" 
        FALLBACK_LOGO_URL_UNAUTH = "https://i.imgur.com/7IIYxq1.png"
        try:
            st.image(LOGO_PATH_UNAUTH, width=200)
        except Exception:
            st.image(FALLBACK_LOGO_URL_UNAUTH, width=200, caption="Logo (Fallback)")

# Rodapé da Sidebar (sempre visível)
st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini Pro")
