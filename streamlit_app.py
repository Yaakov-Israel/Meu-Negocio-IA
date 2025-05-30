import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- Variáveis Globais ---
auth_handler = None # Renomeado para clareza
firebase_secrets_ok = False
llm_model = None # Renomeado para clareza

# --- Bloco de Autenticação Firebase ---
try:
    # Verifica se as seções de segredos existem
    if "firebase_config" not in st.secrets or "cookie_firebase" not in st.secrets:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seções [firebase_config] ou [cookie_firebase] não encontradas nos Segredos.")
        st.info("Verifique os segredos no Streamlit Cloud: firebase_config (com apiKey, authDomain, etc.) e cookie_firebase (com name, key, expiry_days).")
        st.stop()

    firebase_creds = st.secrets["firebase_config"]
    cookie_creds = st.secrets["cookie_firebase"]

    # Validação das chaves essenciais dentro dos segredos
    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k in required_firebase_keys:
        if k not in firebase_creds:
            raise KeyError(f"Chave '{k}' ausente na seção [firebase_config] dos segredos.")
    
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k in required_cookie_keys:
        if k not in cookie_creds:
            raise KeyError(f"Chave '{k}' ausente na seção [cookie_firebase] dos segredos.")

    # Inicialização correta do FirebaseAuth com argumentos nomeados
    auth_handler = st_auth.FirebaseAuth(
        api_key=firebase_creds["apiKey"],
        auth_domain=firebase_creds["authDomain"],
        database_url=firebase_creds["databaseURL"],
        project_id=firebase_creds["projectId"],
        storage_bucket=firebase_creds["storageBucket"],
        messaging_sender_id=firebase_creds["messagingSenderId"],
        app_id=firebase_creds["appId"],
        cookie_name=cookie_creds["name"],
        cookie_key=cookie_creds["key"], # A biblioteca espera 'cookie_key'
        cookie_expiry_days=int(cookie_creds["expiry_days"]),
        debug_logs=False # Mantenha False em produção
    )
    firebase_secrets_ok = True

except KeyError as e: # Captura KeyErrors específicos dos segredos
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: {e}")
    st.info("Verifique se todas as chaves necessárias estão presentes e corretas nas seções [firebase_config] e [cookie_firebase] dos seus Segredos no Streamlit Cloud.")
    st.stop()
except Exception as e: # Captura outros erros de inicialização
    st.error(f"🚨 ERRO FATAL ao inicializar o autenticador Firebase: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

if not auth_handler:
    st.error("Falha crítica: Objeto de autenticação Firebase não pôde ser inicializado. Verifique os logs.")
    st.stop()

# --- Processo de Login ---
# O método login() da biblioteca streamlit-firebase-auth (oom-bell)
# renderiza os campos de login/registro e gerencia o estado.
auth_handler.login() # Esta chamada irá mostrar os botões de login/registro

# Verifica o status da autenticação.
# Se não estiver autenticado, interrompe o script aqui.
# A tela de login já terá sido exibida pela chamada auth_handler.login() acima.
if not st.session_state.get("authentication_status"):
    # st.info("Por favor, faça login ou registre-se para continuar.") # O widget de login já é a indicação
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if auth_handler.logout("Logout", "sidebar"): # O método logout() também lida com o rerun.
    # Limpar estados de sessão específicos do app ao fazer logout, se necessário
    keys_to_clear_on_logout = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_logout in keys_to_clear_on_logout:
        # Usando um sufixo consistente para as chaves de sessão relacionadas às funcionalidades
        if key_logout.startswith(("chat_display_", "memoria_", "generated_", "_fbauth_v5")): 
            if key_logout in st.session_state: # Verifica se a chave existe antes de deletar
                del st.session_state[key_logout]
    st.experimental_rerun() 

# --- Inicialização do Modelo de Linguagem (LLM) do Google (APÓS LOGIN) ---
try:
    google_api_key_from_secrets = st.secrets["GOOGLE_API_KEY"]
    if not google_api_key_from_secrets or not google_api_key_from_secrets.strip():
        st.error("🚨 ERRO: GOOGLE_API_KEY configurada nos segredos está vazia.")
        st.stop()
    
    genai.configure(api_key=google_api_key_from_secrets)
    llm_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                 temperature=0.75,
                                 google_api_key=google_api_key_from_secrets,
                                 convert_system_message_to_human=True)
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
    st.stop()
except Exception as e:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
    st.stop()

if not llm_model:
    st.error("🚨 Modelo LLM não pôde ser inicializado. O aplicativo não pode continuar.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    # Usando um sufixo de versão para as chaves para facilitar o reset de estado se a estrutura do form mudar
    key_suffix = f"_{section_key}_fbauth_v5" 
    details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"obj{key_suffix}")
    details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"audience{key_suffix}")
    details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"product{key_suffix}")
    details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"message{key_suffix}")
    details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"usp{key_suffix}")
    details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", 
                                        ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", 
                                         "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), 
                                        key=f"tone{key_suffix}")
    details["extra_info"] = st.text_area("Alguma informação adicional/CTA (Chamada para Ação)?", key=f"extra{key_suffix}")
    return details

def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
    st.subheader("🎉 Resultado da IA e Próximos Passos:")
    st.markdown(generated_content)
    key_suffix = f"_{section_key}_fbauth_v5"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=str(generated_content).encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, current_llm, session_state_output_key, 
                               uploaded_files_info=None, campaign_specifics=None, selected_platforms_list=None):
    prompt_parts = [prompt_instruction]
    if selected_platforms_list:
        prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
    
    # Adiciona detalhes do _marketing_get_objective_details
    if details_dict:
        if details_dict.get("objective"): prompt_parts.append(f"**Objetivo:** {details_dict['objective']}")
        if details_dict.get("target_audience"): prompt_parts.append(f"**Público-Alvo:** {details_dict['target_audience']}")
        if details_dict.get("product_service"): prompt_parts.append(f"**Produto/Serviço Principal:** {details_dict['product_service']}")
        if details_dict.get("key_message"): prompt_parts.append(f"**Mensagem Chave:** {details_dict['key_message']}")
        if details_dict.get("usp"): prompt_parts.append(f"**USP:** {details_dict['usp']}")
        if details_dict.get("style_tone"): prompt_parts.append(f"**Tom/Estilo:** {details_dict['style_tone']}")
        if details_dict.get("extra_info"): prompt_parts.append(f"**Informações Adicionais/CTA:** {details_dict['extra_info']}")
    
    # Adiciona detalhes específicos da campanha, se houver
    if campaign_specifics:
        if campaign_specifics.get("name"): prompt_parts.append(f"**Nome da Campanha:** {campaign_specifics['name']}")
        if campaign_specifics.get("duration"): prompt_parts.append(f"**Duração Estimada:** {campaign_specifics['duration']}")
        if campaign_specifics.get("budget"): prompt_parts.append(f"**Orçamento Aproximado:** {campaign_specifics['budget']}")
        if campaign_specifics.get("kpis"): prompt_parts.append(f"**KPIs:** {campaign_specifics['kpis']}")
    
    # Não estamos usando uploaded_files_info nesta versão, mas mantido para referência
    # if uploaded_files_info: prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
    
    final_prompt_str = "\n\n".join(filter(None, prompt_parts)) # Filtra strings vazias
    
    try:
        ai_response = current_llm.invoke([HumanMessage(content=final_prompt_str)])
        st.session_state[session_state_output_key] = ai_response.content
    except Exception as e_invoke:
        st.error(f"Erro ao invocar LLM para {session_state_output_key}: {e_invoke}")
        st.session_state[session_state_output_key] = "Ocorreu um erro ao gerar o conteúdo."


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_passed):
        self.llm = llm_passed
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v5', ConversationBufferMemory(memory_key="hist_plano_fb_v5", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v5', ConversationBufferMemory(memory_key="hist_precos_fb_v5", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v5', ConversationBufferMemory(memory_key="hist_ideias_fb_v5", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key_placeholder="historico_chat"):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria, verbose=False)
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        
        mkt_action_key = "main_marketing_action_fbauth_v5"
        mkt_opcoes = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                      "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                      "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                      "6 - Conhecer a concorrência (Análise Competitiva)")
        
        st.session_state.setdefault(f"{mkt_action_key}_index", 0)

        def on_mkt_radio_change_v5():
            selection = st.session_state[mkt_action_key]
            st.session_state[f"{mkt_action_key}_index"] = mkt_opcoes.index(selection) if selection in mkt_opcoes else 0
        
        mkt_acao_selecionada = st.radio("O que você quer fazer em marketing digital?", mkt_opcoes,
                                       index=st.session_state[f"{mkt_action_key}_index"], 
                                       key=mkt_action_key, on_change=on_mkt_radio_change_v5)
        st.markdown("---")
        
        platforms_config = { 
            "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", 
            "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
            "E-mail Marketing (lista própria)": "email_own", 
            "E-mail Marketing (Campanha Google Ads)": "email_google"
        }
        platform_names = list(platforms_config.keys())

        if mkt_acao_selecionada == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            with st.form("post_form_v5", clear_on_submit=True):
                details_post = _marketing_get_objective_details("post_v5_creator", "post")
                st.subheader("Plataformas Desejadas:")
                sel_all_post_key = "post_sel_all_v5"
                sel_all_post_val = st.checkbox("Selecionar Todas", key=sel_all_post_key)
                cols_post_plats = st.columns(2)
                selected_plats_post = []
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_post_plats[i % 2]:
                        cb_key = f"post_plat_{p_sfx}_v5"
                        if st.checkbox(p_name, value=sel_all_post_val, key=cb_key):
                            selected_plats_post.append(p_name)
                
                submit_post = st.form_submit_button("💡 Gerar Post!")
            if submit_post:
                if not selected_plats_post and sel_all_post_val: selected_plats_post = platform_names # Se "todos" está marcado, mas a lista está vazia
                elif not selected_plats_post and not sel_all_post_val: st.warning("Selecione ao menos uma plataforma."); st.stop()

                _marketing_generic_handler(
                    "Crie um texto de post engajador e otimizado para as plataformas e objetivos abaixo.", 
                    details_post, self.llm, "generated_post_content_v5", selected_platforms_list=selected_plats_post
                )
            if "generated_post_content_v5" in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_v5, "post_out_v5", "post_ia")

        elif mkt_acao_selecionada == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            with st.form("campaign_form_v5", clear_on_submit=True):
                camp_specifics = {}
                camp_specifics["name"] = st.text_input("Nome da Campanha:", key="camp_name_v5")
                details_camp = _marketing_get_objective_details("camp_v5_creator", "campanha")
                st.subheader("Plataformas Desejadas:")
                sel_all_camp_key = "camp_sel_all_v5"
                sel_all_camp_val = st.checkbox("Selecionar Todas", key=sel_all_camp_key)
                cols_camp_plats = st.columns(2)
                selected_plats_camp = []
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_camp_plats[i % 2]:
                        cb_key_camp = f"camp_plat_{p_sfx}_v5"
                        if st.checkbox(p_name, value=sel_all_camp_val, key=cb_key_camp):
                            selected_plats_camp.append(p_name)

                camp_specifics["duration"] = st.text_input("Duração Estimada:", key="camp_duration_v5")
                camp_specifics["budget"] = st.text_input("Orçamento Aproximado (opcional):", key="camp_budget_v5")
                camp_specifics["kpis"] = st.text_area("KPIs mais importantes:", key="camp_kpis_v5")
                submit_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_camp:
                if not selected_plats_camp and sel_all_camp_val: selected_plats_camp = platform_names
                elif not selected_plats_camp and not sel_all_camp_val: st.warning("Selecione ao menos uma plataforma."); st.stop()

                _marketing_generic_handler(
                    "Desenvolva um plano de campanha de marketing conciso e acionável:", 
                    details_camp, self.llm, "generated_campaign_content_v5", 
                    campaign_specifics=camp_specifics, selected_platforms_list=selected_plats_camp
                )
            if "generated_campaign_content_v5" in st.session_state:
                _marketing_display_output_options(st.session_state.generated_campaign_content_v5, "camp_out_v5", "campanha_ia")
        
        # Adicione as outras opções de marketing aqui (Landing Page, Site, etc.)
        # seguindo o mesmo padrão, usando chaves únicas para forms e session_state.

    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente focado em PMEs no Brasil. Guie o usuário interativamente para desenvolver seções de um plano de negócios."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v5")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
            return resposta_ai_obj.get('text', "Desculpe, não consegui processar seu pedido.")
        except Exception as e:
            st.error(f"Erro na conversação do plano de negócios: {e}")
            return "Ocorreu um erro ao processar sua solicitação."

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_base = f"O usuário está buscando ajuda para precificar um produto/serviço e forneceu a seguinte informação: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_base = f"Considerando a imagem '{descricao_imagem_contexto}', {prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", especialista em precificação para PMEs. {prompt_base}. Faça perguntas para obter custos, margem desejada, análise de concorrência e público-alvo para sugerir uma estratégia de precificação."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v5")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario}) # Passa o input do usuário para a cadeia
            return resposta_ai_obj.get('text', "Desculpe, não consegui processar seu pedido de cálculo de preços.")
        except Exception as e:
            st.error(f"Erro no cálculo de preços: {e}")
            return "Ocorreu um erro ao processar sua solicitação de cálculo de preços."

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_base = f"O usuário busca ideias de negócios e informou: '{input_usuario}'."
        if contexto_arquivos:
            prompt_base = f"Considerando os seguintes arquivos e contextos: {contexto_arquivos}\n\n{prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", um consultor de negócios criativo e especialista em IA. {prompt_base}. Gere ideias inovadoras e práticas, considerando tendências de mercado e o perfil do PME."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v5")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario}) # Passa o input do usuário para a cadeia
            return resposta_ai_obj.get('text', "Desculpe, não consegui gerar ideias no momento.")
        except Exception as e:
            st.error(f"Erro na geração de ideias: {e}")
            return "Ocorreu um erro ao processar sua solicitação de ideias."

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_chave, msg_inicial, memoria):
    key_display = f"chat_display_{area_chave}_fbauth_v5" # Chave única para o estado do chat
    st.session_state[key_display] = [{"role": "assistant", "content": msg_inicial}]
    if memoria:
        memoria.clear()
        if hasattr(memoria.chat_memory, 'add_ai_message'): memoria.chat_memory.add_ai_message(msg_inicial)
        elif hasattr(memoria.chat_memory, 'messages'): memoria.chat_memory.messages = [AIMessage(content=msg_inicial)]
    # Limpar contextos de upload específicos da área
    if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v5', None)
    elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v5', None)

def exibir_chat_e_obter_input_global(area_chave, placeholder, funcao_agente, **kwargs_agente):
    key_display = f"chat_display_{area_chave}_fbauth_v5"
    key_input = f"chat_input_{area_chave}_fbauth_v5"
    st.session_state.setdefault(key_display, [])
    
    for msg in st.session_state[key_display]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt_usuario := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"): st.markdown(prompt_usuario)
        
        # Prepara kwargs para a função do agente
        local_kwargs_agente = kwargs_agente.copy()
        if area_chave == "calculo_precos":
            if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v5'):
                local_kwargs_agente['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v5')
        elif area_chave == "gerador_ideias":
            if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v5'):
                local_kwargs_agente['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v5')
            
        with st.spinner("Assistente PME Pro processando... 🤔"):
            resposta_assistente = funcao_agente(input_usuario=prompt_usuario, **local_kwargs_agente)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente})
        
        # Limpa contextos de upload após uso para não persistirem para a próxima mensagem no mesmo chat
        if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v5', None)
        elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v5', None)
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v5' not in st.session_state and llm_model: 
    st.session_state.agente_pme_fbauth_v5 = AssistentePMEPro(llm_passed=llm_model)
agente_principal = st.session_state.get('agente_pme_fbauth_v5')

LOGO_FILE_PATH = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_URL = "https://i.imgur.com/7IIYxq1.png"

if os.path.exists(LOGO_FILE_PATH): st.sidebar.image(LOGO_FILE_PATH, width=150)
else: st.sidebar.image(IMGUR_FALLBACK_URL, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_principais_menu = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_principais_labels = list(opcoes_principais_menu.keys())
radio_key_principal = 'main_selection_fbauth_v5'

st.session_state.setdefault(f'{radio_key_principal}_index', 0)
st.session_state.setdefault('secao_selecionada_app_v5', opcoes_principais_labels[st.session_state[f'{radio_key_principal}_index']])

def on_main_radio_change_final():
    st.session_state.secao_selecionada_app_v5 = st.session_state[radio_key_principal]
    st.session_state[f'{radio_key_principal}_index'] = opcoes_principais_labels.index(st.session_state[radio_key_principal])
    if st.session_state.secao_selecionada_app_v5 != "Marketing Digital com IA":
         for k_sidebar_clear in list(st.session_state.keys()): 
            if k_sidebar_clear.startswith(("generated_", "_cb_fbauth_v5", "main_marketing_action_fbauth_v5")):
                if k_sidebar_clear in st.session_state: del st.session_state[k_sidebar_clear]
    st.session_state.previous_secao_selecionada_app_v5 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_principais_labels, key=radio_key_principal, 
                 index=st.session_state[f'{radio_key_principal}_index'], on_change=on_main_radio_change_final)

chave_secao_render = opcoes_principais_menu.get(st.session_state.secao_selecionada_app_v5)

if agente_principal:
    if chave_secao_render not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_v5 != st.session_state.get('previous_secao_selecionada_app_v5'):
            msg_inicial_secao = ""
            memoria_secao_atual = None
            if chave_secao_render == "plano_negocios": 
                msg_inicial_secao = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia, produtos/serviços e clientes."
                memoria_secao_atual = agente_principal.memoria_plano_negocios
            elif chave_secao_render == "calculo_precos": 
                msg_inicial_secao = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começarmos, descreva o produto ou serviço para o qual gostaria de ajuda para precificar. Se tiver uma imagem, pode enviá-la também."
                memoria_secao_atual = agente_principal.memoria_calculo_precos
            elif chave_secao_render == "gerador_ideias": 
                msg_inicial_secao = "Olá! Sou o Assistente PME Pro, pronto para te ajudar a ter novas ideias. Descreva um desafio, uma área que quer inovar, ou simplesmente peça sugestões."
                memoria_secao_atual = agente_principal.memoria_gerador_ideias
            
            if msg_inicial_secao and memoria_secao_atual: 
                inicializar_ou_resetar_chat_global(chave_secao_render, msg_inicial_secao, memoria_secao_atual)
            st.session_state.previous_secao_selecionada_app_v5 = st.session_state.secao_selecionada_app_v5

    if chave_secao_render == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        logo_display = LOGO_FILE_PATH if os.path.exists(LOGO_FILE_PATH) else IMGUR_FALLBACK
        st.markdown(f"<div style='text-align: center;'><img src='{logo_display}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        num_botoes_pg = len(opcoes_principais_menu) -1 
        if num_botoes_pg > 0 :
            num_cols_btns_pg = min(num_botoes_pg, 3) 
            cols_btns_pg = st.columns(num_cols_btns_pg)
            idx_btn_pg = 0
            for nome_menu_item, chave_secao_item in opcoes_principais_menu.items():
                if chave_secao_item != "pg_inicial":
                    col_para_btn = cols_btns_pg[idx_btn_pg % num_cols_btns_pg]
                    label_btn_limpo = nome_menu_item.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                    if col_para_btn.button(label_btn_limpo, key=f"btn_goto_{chave_secao_item}_fbauth_v5", use_container_width=True, help=f"Ir para {nome_menu_item}"):
                        st.session_state.secao_selecionada_app_v5 = nome_menu_item
                        st.session_state[f'{radio_key_principal}_index'] = opcoes_principais_labels.index(nome_menu_item)
                        st.experimental_rerun()
                    idx_btn_pg +=1
            st.balloons()

    elif chave_secao_render == "mkt_guiado": 
        agente_principal.marketing_digital_guiado()
    elif chave_secao_render == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
        exibir_chat_e_obter_input_global(chave_secao_render, "Sua ideia, produtos/serviços, clientes...", agente_principal.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v5"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Ok, vamos recomeçar o seu Plano de Negócios.", agente_principal.memoria_plano_negocios)
            st.rerun()
    elif chave_secao_render == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
        uploaded_image = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_uploader_fbauth_v5")
        kwargs_preco_chat = {}
        if uploaded_image and st.session_state.get(f'processed_image_id_pricing_fbauth_v5') != uploaded_image.file_id: # Usar file_id para unicidade
            try:
                st.image(Image.open(uploaded_image), caption=f"Contexto: {uploaded_image.name}", width=150)
                st.session_state[f'last_uploaded_image_info_pricing_fbauth_v5'] = f"Imagem: {uploaded_image.name}"
                st.session_state[f'processed_image_id_pricing_fbauth_v5'] = uploaded_image.file_id
            except Exception as e_img_proc: st.error(f"Erro ao carregar imagem: {e_img_proc}")
        if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v5'):
            kwargs_preco_chat['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v5')
        exibir_chat_e_obter_input_global(chave_secao_render, "Descreva produto/serviço, custos...", agente_principal.calcular_precos_interativo, **kwargs_preco_chat)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v5"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Novo cálculo de preços. Descreva o produto/serviço.", agente_principal.memoria_calculo_precos)
            st.rerun()
            
    elif chave_secao_render == "gerador_ideias":
        st.header("💡 Gerador de Ideias para Negócios com IA")
        st.caption("Descreva um desafio ou peça ideias. Envie arquivos de contexto, se desejar.")
        uploaded_files_ctx = st.file_uploader("Arquivos de contexto (.txt, .png, .jpg):", accept_multiple_files=True, key="ideias_uploader_fbauth_v5")
        kwargs_ideias_chat = {}
        if uploaded_files_ctx:
            files_id_sig = "_".join(sorted([f.file_id for f in uploaded_files_ctx])) # Gera uma assinatura dos arquivos
            if st.session_state.get(f'processed_file_id_ideias_fbauth_v5') != files_id_sig:
                # Processar e armazenar contexto dos arquivos
                # Esta parte precisaria de uma lógica mais robusta para extrair texto de PDFs/DOCs se necessário
                file_contexts = []
                for uploaded_file_item in uploaded_files_ctx:
                    if uploaded_file_item.type == "text/plain":
                        file_contexts.append(f"Conteúdo de '{uploaded_file_item.name}':\n{uploaded_file_item.read().decode('utf-8')[:1000]}...")
                    elif uploaded_file_item.type in ["image/png", "image/jpeg"]:
                        st.image(Image.open(uploaded_file_item), caption=f"Contexto: {uploaded_file_item.name}", width=100)
                        file_contexts.append(f"Imagem '{uploaded_file_item.name}' fornecida.")
                st.session_state[f'uploaded_file_info_ideias_for_prompt_fbauth_v5'] = "\n".join(file_contexts)
                st.session_state[f'processed_file_id_ideias_fbauth_v5'] = files_id_sig
                if file_contexts: st.info("Arquivo(s) de contexto pronto(s) para o diálogo.")
        
        if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v5'):
            kwargs_ideias_chat['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v5')

        exibir_chat_e_obter_input_global(chave_secao_render, "Descreva seu desafio ou peça ideias:", agente_principal.gerar_ideias_para_negocios, **kwargs_ideias_chat)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v5"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Novas ideias? Conte-me sobre seu objetivo.", agente_principal.memoria_gerador_ideias)
            st.rerun()
else: # Se o agente_principal (e consequentemente o llm_model) não foi inicializado
    if not firebase_secrets_ok: # Este erro já teria parado o script antes, mas é uma checagem extra
        st.error("A configuração dos segredos do Firebase falhou. O aplicativo não pode carregar completamente.")
    elif not llm_model: # Se o llm_model não foi inicializado (erro já mostrado)
         st.error("O modelo de linguagem (LLM) não foi inicializado. Verifique a chave GOOGLE_API_KEY nos segredos. O aplicativo não pode carregar completamente.")
    # Se auth_handler.login() já fez st.stop(), nada mais será renderizado aqui até o login.

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
