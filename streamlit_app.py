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
    # FirebaseAuth pode não ser necessário se usarmos apenas os botões e st.secrets
except ImportError:
    st.error("🚨 ERRO CRÍTICO: Não foi possível importar 'streamlit_firebase_auth'.")
    st.info("Verifique se 'streamlit-firebase-auth==1.0.6' está no seu requirements.txt e se foi instalado corretamente pelo Streamlit Cloud.")
    st.info("Tente dar 'Reboot' no app no Streamlit Cloud. Se o erro persistir, pode haver um problema com a instalação do pacote no ambiente.")
    st.stop()
except Exception as e_import:
    st.error(f"🚨 ERRO INESPERADO DURANTE IMPORTAÇÃO: {type(e_import).__name__} - {e_import}")
    st.exception(e_import)
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
firebase_secrets_ok = False

try:
    if "firebase_config" not in st.secrets or \
       "cookie_firebase" not in st.secrets or \
       "GOOGLE_API_KEY" not in st.secrets:
        missing = []
        if "firebase_config" not in st.secrets: missing.append("[firebase_config]")
        if "cookie_firebase" not in st.secrets: missing.append("[cookie_firebase]")
        if "GOOGLE_API_KEY" not in st.secrets: missing.append("GOOGLE_API_KEY")
        st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Seção(ões)/chave(s) {', '.join(missing)} não encontrada(s) nos Segredos.")
        st.stop()

    firebase_creds = st.secrets["firebase_config"]
    cookie_creds = st.secrets["cookie_firebase"]

    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k_fb in required_firebase_keys:
        if k_fb not in firebase_creds: raise KeyError(f"Chave '{k_fb}' ausente em [firebase_config]")
    
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k_ck in required_cookie_keys:
        if k_ck not in cookie_creds: raise KeyError(f"Chave '{k_ck}' ausente em [cookie_firebase]")
    
    firebase_secrets_ok = True 
except KeyError as e:
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: {e}. Verifique o nome e a presença das chaves.")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO FATAL na verificação dos segredos: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

if not firebase_secrets_ok: # Dupla checagem
    st.error("Falha na validação dos segredos do Firebase. App interrompido.")
    st.stop()

# --- Interface de Login/Logout ---
# Sufixo para garantir chaves únicas para os widgets em diferentes execuções/versões
widget_key_suffix = "_fbauth_v7_widget" 

# A função login_button usa os segredos configurados em st.secrets automaticamente
login_button(key=f"loginbtn{widget_key_suffix}") # Fornecendo uma chave única

if not st.session_state.get("authentication_status"):
    # A biblioteca já mostra os campos de login/registro. 
    # Podemos adicionar uma mensagem se quisermos, mas não é estritamente necessário.
    # st.info("Por favor, faça login ou registre-se para usar o Assistente PME Pro.")
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if logout_button(key=f"logoutbtn{widget_key_suffix}"): # Fornecendo uma chave única
    # Limpar estados de sessão específicos do app ao fazer logout
    keys_to_clear = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_to_del in keys_to_clear:
        # Usando um sufixo consistente e mais específico para as chaves de sessão
        if key_to_del.startswith(("chat_display_v7_", "memoria_v7_", "generated_v7_", "_fbauth_v7")): 
            if key_to_del in st.session_state:
                del st.session_state[key_to_del]
    st.experimental_rerun() 

# --- Inicialização do Modelo de Linguagem (LLM) do Google ---
try:
    google_api_key_from_secrets = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=google_api_key_from_secrets)
    llm_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", # Considere gemini-1.5-pro para mais capacidade
                                 temperature=0.75,
                                 google_api_key=google_api_key_from_secrets,
                                 convert_system_message_to_human=True)
except Exception as e:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
    st.stop()

if not llm_model: # Checagem final
    st.error("🚨 Modelo LLM não pôde ser inicializado. O aplicativo não pode carregar funcionalidades principais.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = f"_{section_key}_fbauth_v7_mkt" 
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
    key_suffix = f"_{section_key}_fbauth_v7_mkt"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=str(generated_content).encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, current_llm, session_state_output_key, 
                               uploaded_files_info=None, campaign_specifics=None, selected_platforms_list=None):
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
        ai_response = current_llm.invoke([HumanMessage(content=final_prompt_str)])
        st.session_state[session_state_output_key] = ai_response.content
    except Exception as e_invoke:
        st.error(f"Erro ao invocar LLM ({session_state_output_key}): {type(e_invoke).__name__} - {e_invoke}")
        st.session_state[session_state_output_key] = "Ocorreu um erro ao gerar o conteúdo."


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_instance): # Renomeado para clareza
        self.llm = llm_instance
        # Sufixos v7 para evitar conflitos de estado de memória
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v7', ConversationBufferMemory(memory_key="hist_plano_fb_v7", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v7', ConversationBufferMemory(memory_key="hist_precos_fb_v7", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v7', ConversationBufferMemory(memory_key="hist_ideias_fb_v7", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key_placeholder="historico_chat_placeholder_v7"): # Placeholder único
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria, verbose=False)
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        
        mkt_action_key = "main_marketing_action_fbauth_v7"
        opcoes_marketing = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                            "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                            "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                            "6 - Conhecer a concorrência (Análise Competitiva)")
        
        st.session_state.setdefault(f"{mkt_action_key}_index", 0)

        def on_mkt_radio_change_v7():
            selection = st.session_state[mkt_action_key]
            st.session_state[f"{mkt_action_key}_index"] = mkt_opcoes.index(selection) if selection in mkt_opcoes else 0
        
        mkt_acao_selecionada = st.radio("O que você quer fazer em marketing digital?", mkt_opcoes,
                                       index=st.session_state[f"{mkt_action_key}_index"], 
                                       key=mkt_action_key, on_change=on_mkt_radio_change_v7)
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
            form_key_post = "post_form_v7"
            session_key_output_post = "generated_post_content_v7"
            with st.form(form_key_post, clear_on_submit=True):
                details_post = _marketing_get_objective_details("post_creator_v7", "post")
                st.subheader("Plataformas Desejadas:")
                sel_all_post_key = f"post_sel_all_{form_key_post}"
                sel_all_post_val = st.checkbox("Selecionar Todas", key=sel_all_post_key, value=st.session_state.get(sel_all_post_key, False))
                
                cols_post_plats = st.columns(2)
                form_plat_selections_post = {}
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_post_plats[i % 2]:
                        cb_key = f"post_plat_{p_sfx}_{form_key_post}"
                        form_plat_selections_post[p_name] = st.checkbox(p_name, value=sel_all_post_val or st.session_state.get(cb_key,False) , key=cb_key)
                
                submit_post = st.form_submit_button("💡 Gerar Post!")

            if submit_post:
                selected_plats_post_final = []
                if st.session_state[sel_all_post_key]:
                    selected_plats_post_final = platform_names
                else:
                    for p_name, p_sfx in platforms_config.items():
                        if st.session_state[f"post_plat_{p_sfx}_{form_key_post}"]:
                             selected_plats_post_final.append(p_name)
                
                if not selected_plats_post_final: st.warning("Selecione ao menos uma plataforma.")
                else:
                    _marketing_generic_handler(
                        "Crie um texto de post engajador e otimizado para as plataformas e objetivos abaixo:", 
                        details_post, self.llm, session_key_output_post, selected_platforms_list=selected_plats_post_final
                    )
            if session_key_output_post in st.session_state:
                _marketing_display_output_options(st.session_state[session_key_output_post], "post_out_v7", "post_ia")

        elif mkt_acao_selecionada == "2 - Criar campanha de marketing completa":
            st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
            form_key_camp = "campaign_form_v7"
            session_key_output_camp = "generated_campaign_content_v7"
            with st.form(form_key_camp, clear_on_submit=True):
                camp_specifics_form = {}
                camp_specifics_form["name"] = st.text_input("Nome da Campanha:", key=f"camp_name_{form_key_camp}")
                details_camp = _marketing_get_objective_details("camp_creator_v7", "campanha")
                st.subheader("Plataformas Desejadas:")
                sel_all_camp_key = f"camp_sel_all_{form_key_camp}"
                sel_all_camp_val = st.checkbox("Selecionar Todas", key=sel_all_camp_key, value=st.session_state.get(sel_all_camp_key, False))
                cols_camp_plats = st.columns(2)
                form_plat_selections_camp = {}
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_camp_plats[i % 2]:
                        cb_key_camp = f"camp_plat_{p_sfx}_{form_key_camp}"
                        form_plat_selections_camp[p_name] = st.checkbox(p_name, value=sel_all_camp_val or st.session_state.get(cb_key_camp, False), key=cb_key_camp)
                
                camp_specifics_form["duration"] = st.text_input("Duração Estimada:", key=f"camp_duration_{form_key_camp}")
                camp_specifics_form["budget"] = st.text_input("Orçamento Aproximado (opcional):", key=f"camp_budget_{form_key_camp}")
                camp_specifics_form["kpis"] = st.text_area("KPIs mais importantes:", key=f"camp_kpis_{form_key_camp}")
                submit_camp = st.form_submit_button("🚀 Gerar Plano de Campanha!")

            if submit_camp:
                selected_plats_camp_final = []
                if st.session_state[sel_all_camp_key]: selected_plats_camp_final = platform_names
                else:
                    for p_name, p_sfx in platforms_config.items():
                        if st.session_state[f"camp_plat_{p_sfx}_{form_key_camp}"]: selected_plats_camp_final.append(p_name)
                if not selected_plats_camp_final: st.warning("Selecione ao menos uma plataforma.")
                else:
                    _marketing_generic_handler(
                        "Desenvolva um plano de campanha de marketing conciso e acionável:", 
                        details_camp, self.llm, session_key_output_camp, 
                        campaign_specifics=camp_specifics_form, selected_platforms_list=selected_plats_camp_final
                    )
            if session_key_output_camp in st.session_state:
                _marketing_display_output_options(st.session_state[session_key_output_camp], "camp_out_v7", "campanha_ia")
        
        # Adicionar as outras opções de marketing (Landing Page, Site, etc.) aqui, seguindo o padrão.
        elif mkt_acao_selecionada == "Selecione uma opção...":
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            # ... (código da imagem da logo)

    # --- Métodos de Chat para as Outras Seções ---
    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..." # Manter prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v7")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui processar o pedido para o plano de negócios.")
        except Exception as e: return f"Erro ao gerar resposta: {e}"

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_base = f"Usuário pede ajuda para precificar: '{input_usuario}'."
        if descricao_imagem_contexto: prompt_base = f"Contexto da imagem '{descricao_imagem_contexto}'.\n{prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", especialista em precificação. {prompt_base} Faça perguntas para obter custos, margem, etc." # Manter prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v7")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui processar o pedido de cálculo de preços.")
        except Exception as e: return f"Erro ao gerar resposta: {e}"

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_base = f"Usuário busca ideias: '{input_usuario}'."
        if contexto_arquivos: prompt_base = f"Contexto dos arquivos: {contexto_arquivos}\n{prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", consultor criativo. {prompt_base} Gere ideias inovadoras." # Manter prompt completo
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v7")
        try:
            resposta = cadeia.invoke({"input_usuario": input_usuario})
            return resposta.get('text', "Desculpe, não consegui gerar ideias.")
        except Exception as e: return f"Erro ao gerar resposta: {e}"

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_chave, msg_inicial, memoria):
    key_display = f"chat_display_{area_chave}_fbauth_v7"
    st.session_state[key_display] = [{"role": "assistant", "content": msg_inicial}]
    if memoria:
        memoria.clear()
        if hasattr(memoria.chat_memory, 'add_ai_message'): memoria.chat_memory.add_ai_message(msg_inicial)
        elif hasattr(memoria.chat_memory, 'messages'): memoria.chat_memory.messages = [AIMessage(content=msg_inicial)]

def exibir_chat_e_obter_input_global(area_chave, placeholder, funcao_agente, **kwargs_agente):
    key_display = f"chat_display_{area_chave}_fbauth_v7"
    key_input = f"chat_input_{area_chave}_fbauth_v7"
    st.session_state.setdefault(key_display, [])
    for msg in st.session_state[key_display]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt_usuario_chat := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt_usuario_chat})
        with st.chat_message("user"): st.markdown(prompt_usuario_chat)
        with st.spinner("Processando..."):
            resposta_assistente_chat = funcao_agente(input_usuario=prompt_usuario_chat, **kwargs_agente)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente_chat})
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v7' not in st.session_state and llm_model: 
    st.session_state.agente_pme_fbauth_v7 = AssistentePMEPro(llm_instance=llm_model)
agente_principal = st.session_state.get('agente_pme_fbauth_v7')

LOGO_PATH = "images/logo-pme-ia.png" 
IMGUR_FALLBACK = "https://i.imgur.com/7IIYxq1.png"
if os.path.exists(LOGO_PATH): st.sidebar.image(LOGO_PATH, width=150)
else: st.sidebar.image(IMGUR_FALLBACK, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_sidebar = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_labels_sidebar = list(opcoes_menu_sidebar.keys())
radio_key_principal_sidebar = 'main_selection_fbauth_v7' # Chave única para o radio principal

st.session_state.setdefault(f'{radio_key_principal_sidebar}_index', 0)
st.session_state.setdefault('secao_selecionada_app_v7', opcoes_labels_sidebar[st.session_state[f'{radio_key_principal_sidebar}_index']])

def on_main_radio_change_v7_sidebar():
    st.session_state.secao_selecionada_app_v7 = st.session_state[radio_key_principal_sidebar]
    st.session_state[f'{radio_key_principal_sidebar}_index'] = opcoes_labels_sidebar.index(st.session_state[radio_key_principal_sidebar])
    st.session_state.previous_secao_selecionada_app_v7 = None # Força reinicialização de chat ao mudar de seção principal
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels_sidebar, key=radio_key_principal_sidebar, 
                 index=st.session_state[f'{radio_key_principal_sidebar}_index'], on_change=on_main_radio_change_v7_sidebar)

chave_secao_render = opcoes_menu_sidebar.get(st.session_state.secao_selecionada_app_v7)

if agente_principal: 
    if chave_secao_render not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_v7 != st.session_state.get('previous_secao_selecionada_app_v7'):
            msg_inicial_secao = ""
            memoria_secao_atual = None
            if chave_secao_render == "plano_negocios": 
                msg_inicial_secao = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios?"
                memoria_secao_atual = agente_principal.memoria_plano_negocios
            elif chave_secao_render == "calculo_precos": 
                msg_inicial_secao = "Olá! Bem-vindo ao assistente de Cálculo de Preços."
                memoria_secao_atual = agente_principal.memoria_calculo_precos
            elif chave_secao_render == "gerador_ideias": 
                msg_inicial_secao = "Olá! Sou o Assistente PME Pro, pronto para te ajudar a ter novas ideias."
                memoria_secao_atual = agente_principal.memoria_gerador_ideias
            if msg_inicial_secao and memoria_secao_atual: 
                inicializar_ou_resetar_chat_global(chave_secao_render, msg_inicial_secao, memoria_secao_atual)
            st.session_state.previous_secao_selecionada_app_v7 = st.session_state.secao_selecionada_app_v7

    if chave_secao_render == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        # ... (conteúdo da página inicial)
    elif chave_secao_render == "mkt_guiado": 
        agente_principal.marketing_digital_guiado()
    elif chave_secao_render == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        exibir_chat_e_obter_input_global(chave_secao_render, "Sua ideia...", agente_principal.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Ok, vamos recomeçar o Plano.", agente_principal.memoria_plano_negocios); st.rerun()
    elif chave_secao_render == "calculo_precos":
        st.header("💲 Cálculo de Preços com IA")
        # ... (lógica de upload e chat como antes, com chaves _v7) ...
        exibir_chat_e_obter_input_global(chave_secao_render, "Descreva produto/custos...", agente_principal.calcular_precos_interativo)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Novo cálculo de preços.", agente_principal.memoria_calculo_precos); st.rerun()
    elif chave_secao_render == "gerador_ideias":
        st.header("💡 Gerador de Ideias com IA")
        # ... (lógica de upload e chat como antes, com chaves _v7) ...
        exibir_chat_e_obter_input_global(chave_secao_render, "Descreva seu desafio...", agente_principal.gerar_ideias_para_negocios)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_render, "Novas ideias? Conte-me.", agente_principal.memoria_gerador_ideias); st.rerun()
else:
    if not firebase_secrets_ok: pass # Erro já tratado
    elif not llm_model and st.session_state.get("authentication_status"): # Só mostra erro do LLM se autenticado
        st.error("O modelo de linguagem (LLM) não foi inicializado. Verifique a chave GOOGLE_API_KEY.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
