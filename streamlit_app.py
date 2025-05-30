import streamlit as st
import os
# Imports para Langchain e Google Generative AI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage # Adicionado AIMessage para consistência da memória
import google.generativeai as genai
# Import para manipulação de imagem
from PIL import Image

# Tenta importar as funções específicas da biblioteca de autenticação Firebase
try:
    from streamlit_firebase_auth import login_button, logout_button
    # A classe FirebaseAuth não é necessária para o fluxo básico de login/logout
    # quando os segredos são lidos automaticamente pelos componentes.
except ImportError:
    st.error("🚨 ERRO CRÍTICO AO IMPORTAR: O módulo 'streamlit_firebase_auth' não foi encontrado.")
    st.info("Verifique se 'streamlit-firebase-auth' (com a versão correta, ex: '==1.0.5') está no seu arquivo requirements.txt e se o Streamlit Cloud conseguiu instalá-lo. Confira os logs de build da aplicação.")
    st.stop()
except Exception as e_initial_import:
    st.error(f"🚨 ERRO INESPERADO NA IMPORTAÇÃO INICIAL DA AUTENTICAÇÃO: {type(e_initial_import).__name__} - {e_initial_import}")
    st.exception(e_initial_import)
    st.stop()

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- Variáveis Globais e Verificação de Segredos ---
llm_model = None 
firebase_secrets_valid = False # Flag para verificar se os segredos do Firebase estão OK

try:
    # Verifica se as seções de segredos existem
    if "firebase_config" not in st.secrets or \
       "cookie_firebase" not in st.secrets or \
       "GOOGLE_API_KEY" not in st.secrets:
        missing_secrets = []
        if "firebase_config" not in st.secrets: missing_secrets.append("[firebase_config]")
        if "cookie_firebase" not in st.secrets: missing_secrets.append("[cookie_firebase]")
        if "GOOGLE_API_KEY" not in st.secrets: missing_secrets.append("GOOGLE_API_KEY")
        st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Seção(ões)/chave(s) de segredos ausente(s): {', '.join(missing_secrets)}.")
        st.info("Verifique os segredos no Streamlit Cloud: [firebase_config] (com apiKey, authDomain, etc.), [cookie_firebase] (com name, key, expiry_days) e GOOGLE_API_KEY devem estar presentes.")
        st.stop()

    firebase_creds_check = st.secrets["firebase_config"]
    cookie_creds_check = st.secrets["cookie_firebase"]

    # Validação das chaves essenciais dentro dos segredos
    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k_fb_check in required_firebase_keys:
        if k_fb_check not in firebase_creds_check: 
            raise KeyError(f"Chave '{k_fb_check}' ausente na seção [firebase_config] dos segredos.")
    
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k_ck_check in required_cookie_keys:
        if k_ck_check not in cookie_creds_check: 
            raise KeyError(f"Chave '{k_ck_check}' ausente na seção [cookie_firebase] dos segredos.")
    
    firebase_secrets_valid = True 

except KeyError as e_key: # Captura KeyErrors específicos dos segredos
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: A chave esperada {e_key} não foi encontrada.")
    st.info("Por favor, verifique cuidadosamente a estrutura e o nome das chaves nas suas seções [firebase_config] e [cookie_firebase] nos Segredos do Streamlit Cloud.")
    st.stop()
except Exception as e_secrets_init: # Captura outros erros durante a verificação dos segredos
    st.error(f"🚨 ERRO FATAL durante a verificação inicial dos segredos: {type(e_secrets_init).__name__} - {e_secrets_init}")
    st.exception(e_secrets_init)
    st.stop()

if not firebase_secrets_valid: # Segurança adicional
    st.error("Validação dos segredos do Firebase falhou de forma inesperada. O aplicativo não pode prosseguir.")
    st.stop()

# --- Interface de Login/Logout ---
# Usar sufixos de versão para chaves de widget para ajudar a evitar conflitos de estado
login_widget_key_v8 = "login_btn_fbauth_v8"
logout_widget_key_v8 = "logout_btn_fbauth_v8"

# A função login_button usa os st.secrets internamente para configuração.
login_button(key=login_widget_key_v8) # Streamlit_firebase_auth cria o widget de login aqui

# Verifica o status da autenticação.
# Se não estiver autenticado, o st.stop() abaixo interromperá a execução do restante do script.
# A tela de login já terá sido exibida pela chamada login_button() acima.
if not st.session_state.get("authentication_status"):
    # st.info("Por favor, faça login ou registre-se para continuar.") # Opcional, o widget já é a indicação
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if logout_button(key=logout_widget_key_v8):
    # Limpar estados de sessão específicos do app ao fazer logout
    keys_to_clear_on_logout_v8 = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_to_delete_v8 in keys_to_clear_on_logout_v8:
        # Sufixo v8 para chaves de sessão para garantir que são as desta versão
        if key_to_delete_v8.startswith(("chat_display_v8_", "memoria_v8_", "generated_v8_", "_fbauth_v8")) or \
           key_to_delete_v8.startswith("main_marketing_action_fbauth_v8") or \
           key_to_delete_v8.startswith("post_sel_all_v8") or \
           key_to_delete_v8.startswith("post_plat_") or \
           key_to_delete_v8.startswith("camp_sel_all_v8") or \
           key_to_delete_v8.startswith("camp_plat_"):
            if key_to_delete_v8 in st.session_state: # Checa se a chave existe antes de deletar
                del st.session_state[key_to_delete_v8]
    st.experimental_rerun() 

# --- Inicialização do Modelo de Linguagem (LLM) do Google ---
try:
    google_api_key_value = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=google_api_key_value)
    llm_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", # Ou gemini-1.5-pro para mais capacidade
                                 temperature=0.75,
                                 google_api_key=google_api_key_value,
                                 convert_system_message_to_human=True)
except Exception as e_llm_init:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {type(e_llm_init).__name__} - {e_llm_init}")
    st.stop()

if not llm_model: # Checagem final após o try-except
    st.error("🚨 Modelo LLM não pôde ser inicializado. O aplicativo não pode carregar funcionalidades principais.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    # Usar um sufixo de versão para as chaves para facilitar o reset de estado se a estrutura do form mudar
    key_suffix = f"_{section_key}_fbauth_v8_mkt" 
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
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
    key_suffix = f"_{section_key}_fbauth_v8_mkt"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=str(generated_content).encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, current_llm_instance, session_state_output_key, 
                               campaign_specifics=None, selected_platforms_list=None):
    prompt_parts = [prompt_instruction]
    if selected_platforms_list: prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
    if details_dict:
        for key, value in details_dict.items():
            if value: prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    if campaign_specifics:
        for key, value in campaign_specifics.items():
            if value: prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    
    final_prompt_str = "\n\n".join(filter(None, prompt_parts))
    
    try:
        ai_response = current_llm_instance.invoke([HumanMessage(content=final_prompt_str)])
        st.session_state[session_state_output_key] = ai_response.content
    except Exception as e_invoke_mkt_generic:
        st.error(f"Erro ao invocar LLM para '{session_state_output_key}': {type(e_invoke_mkt_generic).__name__} - {e_invoke_mkt_generic}")
        st.session_state[session_state_output_key] = "Ocorreu um erro ao gerar o conteúdo. Verifique os logs do app."


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_to_use_in_class): # Nome do parâmetro alterado
        self.llm = llm_to_use_in_class
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v8', ConversationBufferMemory(memory_key="hist_plano_fb_v8", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v8', ConversationBufferMemory(memory_key="hist_precos_fb_v8", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v8', ConversationBufferMemory(memory_key="hist_ideias_fb_v8", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message_template, memoria_obj, memory_key_placeholder="hist_conversa_v8_placeholder"):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_template),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria_obj, verbose=False)
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        
        mkt_action_key_v8 = "main_marketing_action_fbauth_v8" # Sufixo v8
        opcoes_mkt_v8 = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                         "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                         "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                         "6 - Conhecer a concorrência (Análise Competitiva)")
        
        st.session_state.setdefault(f"{mkt_action_key_v8}_index", 0)

        def on_mkt_radio_change_v8_cb(): # Callback com sufixo v8
            selection = st.session_state[mkt_action_key_v8]
            st.session_state[f"{mkt_action_key_v8}_index"] = mkt_opcoes_v8.index(selection) if selection in mkt_opcoes_v8 else 0
        
        mkt_acao_selecionada_v8 = st.radio("O que você quer fazer em marketing digital?", mkt_opcoes_v8,
                                           index=st.session_state[f"{mkt_action_key_v8}_index"], 
                                           key=mkt_action_key_v8, on_change=on_mkt_radio_change_v8_cb)
        st.markdown("---")
        
        platforms_config_mkt = { 
            "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp", 
            "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
            "E-mail Marketing (lista própria)": "email_own", 
            "E-mail Marketing (Campanha Google Ads)": "email_google"
        }
        platform_names_mkt = list(platforms_config_mkt.keys())

        if mkt_acao_selecionada_v8 == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            form_key = "post_form_v8"
            output_key = "generated_post_content_v8"
            with st.form(form_key, clear_on_submit=True): # clear_on_submit para resetar o form após envio
                details = _marketing_get_objective_details("post_creator_v8", "post")
                st.subheader("Plataformas Desejadas:")
                select_all_key = f"post_sel_all_{form_key}"
                select_all_val = st.checkbox("Selecionar Todas as Plataformas", key=select_all_key)
                cols_plats = st.columns(2)
                current_plat_selections = {}
                for i, (p_name, p_sfx) in enumerate(platforms_config_mkt.items()):
                    with cols_plats[i % 2]:
                        cb_key_plat = f"post_plat_{p_sfx}_{form_key}"
                        current_plat_selections[p_name] = st.checkbox(p_name, value=select_all_val, key=cb_key_plat)
                submitted = st.form_submit_button("💡 Gerar Post!")
            if submitted:
                final_selected_plats = [p for p,isSelected in current_plat_selections.items() if isSelected or select_all_val]
                if not final_selected_plats : final_selected_plats = platform_names_mkt if select_all_val else [] # Garante que se "todos" está marcado, todos são pegos

                if not final_selected_plats: st.warning("Por favor, selecione ao menos uma plataforma.")
                else:
                    _marketing_generic_handler("Crie um texto de post...", details, self.llm, output_key, selected_platforms_list=final_selected_plats)
            if output_key in st.session_state:
                _marketing_display_output_options(st.session_state[output_key], "post_out_v8", "post_ia")

        elif mkt_acao_selecionada_v8 == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            form_key_c = "campaign_form_v8"
            output_key_c = "generated_campaign_content_v8"
            with st.form(form_key_c, clear_on_submit=True):
                camp_specifics = {}
                camp_specifics["name"] = st.text_input("Nome da Campanha:", key=f"camp_name_{form_key_c}")
                details_c = _marketing_get_objective_details("camp_creator_v8", "campanha")
                # ... (lógica de seleção de plataforma como acima) ...
                camp_specifics["duration"] = st.text_input("Duração Estimada:", key=f"camp_duration_{form_key_c}")
                camp_specifics["budget"] = st.text_input("Orçamento Aproximado (opcional):", key=f"camp_budget_{form_key_c}")
                camp_specifics["kpis"] = st.text_area("KPIs mais importantes:", key=f"camp_kpis_{form_key_c}")
                submitted_c = st.form_submit_button("🚀 Gerar Plano de Campanha!")
            if submitted_c:
                # ... (lógica para pegar plataformas selecionadas) ...
                _marketing_generic_handler("Crie um plano de campanha...", details_c, self.llm, output_key_c, campaign_specifics=camp_specifics, selected_platforms_list=["Instagram", "Facebook"]) # Exemplo
            if output_key_c in st.session_state:
                _marketing_display_output_options(st.session_state[output_key_c], "camp_out_v8", "campanha_ia")
        
        # As outras seções de marketing (Landing Page, Site, Cliente Ideal, Concorrência) seguem um padrão similar.
        # Lembre-se de usar chaves únicas para forms e st.session_state para cada uma.
        # Por exemplo, para Landing Page:
        elif mkt_acao_selecionada_v8 == "3 - Criar estrutura e conteúdo para landing page":
            st.subheader("📄 Gerador de Estrutura para Landing Pages com IA")
            form_key_lp = "lp_form_v8"
            output_key_lp = "generated_lp_content_v8"
            with st.form(form_key_lp, clear_on_submit=False): # clear_on_submit=False pode ser melhor para LPs
                lp_details_form = {}
                lp_details_form["purpose"] = st.text_input("Principal objetivo da landing page:", key=f"lp_purpose_{form_key_lp}")
                lp_details_form["target_audience"] = st.text_input("Para quem é esta landing page? (Persona)", key=f"lp_audience_{form_key_lp}")
                lp_details_form["main_offer"] = st.text_area("Oferta principal e irresistível:", key=f"lp_offer_{form_key_lp}")
                lp_details_form["key_benefits"] = st.text_area("3-5 principais benefícios/transformações:", key=f"lp_benefits_{form_key_lp}")
                lp_details_form["cta"] = st.text_input("Chamada para ação (CTA) principal:", key=f"lp_cta_{form_key_lp}")
                lp_details_form["visual_prefs"] = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key=f"lp_visual_{form_key_lp}")
                submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP!")
            if submitted_lp:
                _marketing_generic_handler("Crie uma estrutura detalhada e conteúdo para uma landing page com base nos seguintes detalhes:", 
                                           lp_details_form, self.llm, output_key_lp)
            if output_key_lp in st.session_state:
                _marketing_display_output_options(st.session_state[output_key_lp], "lp_out_v8", "landing_page_ia")

        elif mkt_acao_selecionada_v8 == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            # LOGO_PATH_MKT_WELCOME = "images/logo-pme-ia.png" # Idealmente, esta imagem está no repo do APP
            # if os.path.exists(LOGO_PATH_MKT_WELCOME): st.image(LOGO_PATH_MKT_WELCOME, width=200)
            # else: st.image(IMGUR_FALLBACK, width=200, caption="Logo Padrão")


    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente especializado em auxiliar Pequenas e Médias Empresas (PMEs) no Brasil a desenvolverem planos de negócios robustos e estratégicos. Guie o usuário interativamente, fazendo perguntas pertinentes, oferecendo insights e ajudando a estruturar cada seção do plano."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v8")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui processar o pedido para o plano de negócios.")
        except Exception as e: return f"Erro ao gerar resposta para plano de negócios: {e}"

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_base_calc = f"O usuário está buscando ajuda para precificar um produto/serviço. Informação inicial: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_base_calc = f"Considerando a imagem '{descricao_imagem_contexto}', {prompt_base_calc}"
        system_message_precos = f"Você é o \"Assistente PME Pro\", especialista em precificação para PMEs. {prompt_base_calc} Seu objetivo é guiar o usuário, fazendo perguntas sobre custos (fixos e variáveis), margem de lucro desejada, análise de concorrência (preços praticados, diferenciais), e o público-alvo para então sugerir uma estratégia de precificação e um possível preço ou faixa de preço. Seja prático e didático."
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v8")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui processar o pedido de cálculo de preços.")
        except Exception as e: return f"Erro ao gerar resposta para cálculo de preços: {e}"

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_base_ideias = f"O usuário busca ideias de negócios e informou: '{input_usuario}'."
        if contexto_arquivos:
            prompt_base_ideias = f"Considerando os seguintes arquivos e contextos: {contexto_arquivos}\n\n{prompt_base_ideias}"
        system_message_ideias = f"Você é o \"Assistente PME Pro\", um consultor de negócios altamente criativo e especialista em IA. {prompt_base_ideias} Gere 3 a 5 ideias de negócios inovadoras e práticas, detalhando brevemente cada uma, considerando tendências de mercado e o perfil de uma Pequena ou Média Empresa no Brasil. Para cada ideia, sugira um nome criativo, um público-alvo inicial e um diferencial chave."
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v8")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui gerar ideias no momento.")
        except Exception as e: return f"Erro ao gerar resposta para ideias de negócios: {e}"

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_key_chat, msg_inicial_chat, memoria_chat):
    chat_display_key_chat_v8 = f"chat_display_v8_{area_key_chat}" # Sufixo v8
    st.session_state[chat_display_key_chat_v8] = [{"role": "assistant", "content": msg_inicial_chat}]
    if memoria_chat:
        memoria_chat.clear()
        # Adiciona a mensagem inicial à memória da LLMChain
        if hasattr(memoria_chat.chat_memory, 'add_ai_message'): 
             memoria_chat.chat_memory.add_ai_message(msg_inicial_chat)
        elif hasattr(memoria_chat.chat_memory, 'messages') and isinstance(memoria_chat.chat_memory.messages, list):
             # Garante que a lista seja de BaseMessage (AIMessage para assistente)
             memoria_chat.chat_memory.messages = [AIMessage(content=msg_inicial_chat)]
    # Limpar contextos de upload específicos da área
    if area_key_chat == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v8', None)
    elif area_key_chat == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v8', None)


def exibir_chat_e_obter_input_global(area_key_chat, placeholder_chat, func_agente_chat, **kwargs_agente_chat):
    chat_display_key_chat_v8 = f"chat_display_v8_{area_key_chat}"
    chat_input_key_v8 = f"chat_input_v8_{area_key_chat}"
    st.session_state.setdefault(chat_display_key_chat_v8, [])
    
    for msg_item_chat in st.session_state[chat_display_key_chat_v8]:
        with st.chat_message(msg_item_chat["role"]): st.markdown(msg_item_chat["content"])
    
    if user_prompt_from_chat := st.chat_input(placeholder_chat, key=chat_input_key_v8):
        st.session_state[chat_display_key_chat_v8].append({"role": "user", "content": user_prompt_from_chat})
        with st.chat_message("user"): st.markdown(user_prompt_from_chat)
        
        local_kwargs_for_agente = kwargs_agente_chat.copy()
        if area_key_chat == "calculo_precos":
            if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v8'):
                local_kwargs_for_agente['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v8')
        elif area_key_chat == "gerador_ideias":
            if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v8'):
                local_kwargs_for_agente['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v8')
            
        with st.spinner("Assistente PME Pro processando... 🤔"):
            resposta_do_assistente = func_agente_chat(input_usuario=user_prompt_from_chat, **local_kwargs_for_agente)
        st.session_state[chat_display_key_chat_v8].append({"role": "assistant", "content": resposta_do_assistente})
        
        # Limpa contextos de upload após uso para não persistirem para a próxima mensagem no mesmo chat
        if area_key_chat == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v8', None) 
        elif area_key_chat == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v8', None)
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v8' not in st.session_state and llm_model: 
    st.session_state.agente_pme_fbauth_v8 = AssistentePMEPro(llm_to_use_in_class=llm_model)
agente_principal_instancia = st.session_state.get('agente_pme_fbauth_v8')

LOGO_PATH_APP = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_APP = "https://i.imgur.com/7IIYxq1.png"
if os.path.exists(LOGO_PATH_APP): st.sidebar.image(LOGO_PATH_APP, width=150)
else: st.sidebar.image(IMGUR_FALLBACK_APP, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_sidebar_principal = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_labels_sidebar_principal = list(opcoes_menu_sidebar_principal.keys())
radio_key_sidebar_v8 = 'main_selection_fbauth_v8' 

st.session_state.setdefault(f'{radio_key_sidebar_v8}_index', 0)
st.session_state.setdefault('secao_selecionada_app_v8', opcoes_labels_sidebar_principal[st.session_state[f'{radio_key_sidebar_v8}_index']])

def on_main_radio_change_v8_sidebar():
    st.session_state.secao_selecionada_app_v8 = st.session_state[radio_key_sidebar_v8]
    st.session_state[f'{radio_key_sidebar_v8}_index'] = opcoes_labels_sidebar_principal.index(st.session_state[radio_key_sidebar_v8])
    st.session_state.previous_secao_selecionada_app_v8 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels_sidebar_principal, key=radio_key_sidebar_v8, 
                 index=st.session_state[f'{radio_key_sidebar_v8}_index'], on_change=on_main_radio_change_v8_sidebar)

chave_secao_ativa_render = opcoes_menu_sidebar_principal.get(st.session_state.secao_selecionada_app_v8)

if agente_principal_instancia: 
    if chave_secao_ativa_render not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_v8 != st.session_state.get('previous_secao_selecionada_app_v8'):
            msg_inicial_secao_chat_render = ""
            memoria_secao_chat_atual_render = None
            if chave_secao_ativa_render == "plano_negocios": 
                msg_inicial_secao_chat_render = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia de negócio, seus principais produtos/serviços, e quem você imagina como seus clientes."
                memoria_secao_chat_atual_render = agente_principal_instancia.memoria_plano_negocios
            elif chave_secao_ativa_render == "calculo_precos": 
                msg_inicial_secao_chat_render = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começarmos, por favor, descreva o produto ou serviço para o qual você gostaria de ajuda para precificar. Se tiver uma imagem, pode enviá-la também."
                memoria_secao_chat_atual_render = agente_principal_instancia.memoria_calculo_precos
            elif chave_secao_ativa_render == "gerador_ideias": 
                msg_inicial_secao_chat_render = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Você pode me descrever um desafio, uma área que quer inovar, ou simplesmente pedir sugestões."
                memoria_secao_chat_atual_render = agente_principal_instancia.memoria_gerador_ideias
            
            if msg_inicial_secao_chat_render and memoria_secao_chat_atual_render: 
                inicializar_ou_resetar_chat_global(chave_secao_ativa_render, msg_inicial_secao_chat_render, memoria_secao_chat_atual_render)
            st.session_state.previous_secao_selecionada_app_v8 = st.session_state.secao_selecionada_app_v8

    if chave_secao_ativa_render == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        logo_pg_inicial = LOGO_PATH_APP if os.path.exists(LOGO_PATH_APP) else IMGUR_FALLBACK_APP
        st.markdown(f"<div style='text-align: center;'><img src='{logo_pg_inicial}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        num_btns_pg_inicial = len(opcoes_menu_sidebar_principal) -1 
        if num_btns_pg_inicial > 0 :
            num_cols_btns_pg_inicial = min(num_btns_pg_inicial, 3) 
            cols_btns_pg_inicial = st.columns(num_cols_btns_pg_inicial)
            idx_btn_pg_inicial = 0
            for nome_menu_item_render, chave_secao_item_render in opcoes_menu_sidebar_principal.items():
                if chave_secao_item_render != "pg_inicial":
                    col_para_btn_render = cols_btns_pg_inicial[idx_btn_pg_inicial % num_cols_btns_pg_inicial]
                    label_btn_render = nome_menu_item_render.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                    if col_para_btn_render.button(label_btn_render, key=f"btn_goto_{chave_secao_item_render}_fbauth_v8", use_container_width=True, help=f"Ir para {nome_menu_item_render}"):
                        st.session_state.secao_selecionada_app_v8 = nome_menu_item_render
                        st.session_state[f'{radio_key_principal_sidebar}_index'] = opcoes_labels_sidebar_principal.index(nome_menu_item_render)
                        st.experimental_rerun()
                    idx_btn_pg_inicial +=1
            st.balloons()

    elif chave_secao_ativa_render == "mkt_guiado": 
        agente_principal_instancia.marketing_digital_guiado()
    elif chave_secao_ativa_render == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
        exibir_chat_e_obter_input_global(chave_secao_ativa_render, "Sua ideia, produtos/serviços, clientes...", agente_principal_instancia.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v8"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa_render, "Ok, vamos recomeçar o seu Plano de Negócios.", agente_principal_instancia.memoria_plano_negocios); st.rerun()
    elif chave_secao_ativa_render == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
        uploaded_image_calc_preco = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_uploader_fbauth_v8")
        kwargs_preco_chat = {}
        if uploaded_image_calc_preco and st.session_state.get(f'processed_image_id_pricing_fbauth_v8') != uploaded_image_calc_preco.file_id:
            try:
                st.image(Image.open(uploaded_image_calc_preco), caption=f"Contexto: {uploaded_image_calc_preco.name}", width=150)
                st.session_state[f'last_uploaded_image_info_pricing_fbauth_v8'] = f"Imagem: {uploaded_image_calc_preco.name}"
                st.session_state[f'processed_image_id_pricing_fbauth_v8'] = uploaded_image_calc_preco.file_id
            except Exception as e: st.error(f"Erro ao carregar imagem: {e}")
        if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v8'):
            kwargs_preco_chat['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v8')
        exibir_chat_e_obter_input_global(chave_secao_ativa_render, "Descreva produto/serviço, custos...", agente_principal_instancia.calcular_precos_interativo, **kwargs_preco_chat)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v8"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa_render, "Novo cálculo de preços. Descreva o produto/serviço.", agente_principal_instancia.memoria_calculo_precos); st.rerun()
            
    elif chave_secao_ativa_render == "gerador_ideias":
        st.header("💡 Gerador de Ideias para Negócios com IA")
        st.caption("Descreva um desafio ou peça ideias. Envie arquivos de contexto, se desejar.")
        uploaded_files_gerador_ideias = st.file_uploader("Arquivos de contexto (.txt, .png, .jpg):", accept_multiple_files=True, key="ideias_uploader_fbauth_v8")
        kwargs_ideias_chat = {}
        if uploaded_files_gerador_ideias:
            files_id_sig_ideias_v8 = "_".join(sorted([f.file_id for f in uploaded_files_gerador_ideias])) # Usar file_id para assinatura
            if st.session_state.get(f'processed_file_id_ideias_fbauth_v8') != files_id_sig_ideias_v8:
                file_contexts_list_v8 = []
                for uploaded_file_item_v8 in uploaded_files_gerador_ideias:
                    try:
                        if uploaded_file_item_v8.type == "text/plain":
                            file_contexts_list_v8.append(f"Conteúdo de '{uploaded_file_item_v8.name}':\n{uploaded_file_item_v8.read().decode('utf-8')[:1000]}...")
                        elif uploaded_file_item_v8.type in ["image/png", "image/jpeg"]:
                            st.image(Image.open(uploaded_file_item_v8), caption=f"Contexto: {uploaded_file_item_v8.name}", width=100)
                            file_contexts_list_v8.append(f"Imagem '{uploaded_file_item_v8.name}' fornecida.")
                    except Exception as e: st.error(f"Erro ao processar '{uploaded_file_item_v8.name}': {e}")
                st.session_state[f'uploaded_file_info_ideias_for_prompt_fbauth_v8'] = "\n".join(file_contexts_list_v8)
                st.session_state[f'processed_file_id_ideias_fbauth_v8'] = files_id_sig_ideias_v8
                if file_contexts_list_v8: st.info("Arquivo(s) de contexto pronto(s).")
        
        if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v8'):
            kwargs_ideias_chat['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v8')

        exibir_chat_e_obter_input_global(chave_secao_ativa_render, "Descreva seu desafio ou peça ideias:", agente_principal_instancia.gerar_ideias_para_negocios, **kwargs_ideias_chat)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v8"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa_render, "Novas ideias? Conte-me sobre seu objetivo.", agente_principal_instancia.memoria_gerador_ideias); st.rerun()
else: # Se o agente_principal_instancia (e o llm_model) não foram inicializados
    if not firebase_secrets_valid: pass # Erro já tratado e st.stop() chamado
    elif not llm_model and st.session_state.get("authentication_status"): 
        st.error("O modelo de linguagem (LLM) não foi inicializado. Verifique a chave GOOGLE_API_KEY nos segredos. O aplicativo não pode carregar as funcionalidades principais.")
    # Se não autenticado, o st.stop() após login_button() já tratou.

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
