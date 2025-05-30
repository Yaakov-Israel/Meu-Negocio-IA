import streamlit as st
import os
# Imports para Langchain e Google Generative AI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage 
import google.generativeai as genai
# Import para manipulação de imagem
from PIL import Image

# Tenta importar as funções específicas da biblioteca de autenticação Firebase
try:
    from streamlit_firebase_auth import login_button, logout_button
except ImportError:
    st.error("🚨 ERRO CRÍTICO AO IMPORTAR: O módulo 'streamlit_firebase_auth' não foi encontrado.")
    st.info(f"Verifique se 'streamlit-firebase-auth==1.0.5' (ou a versão configurada) está no seu arquivo requirements.txt e se o Streamlit Cloud conseguiu instalá-lo sem erros nos logs de build. Um 'Reboot' pode ser necessário, ou até deletar e recriar o app se a conexão com o GitHub estiver com problemas.")
    st.stop()
except Exception as e_initial_import_main:
    st.error(f"🚨 ERRO INESPERADO NA IMPORTAÇÃO DA AUTENTICAÇÃO: {type(e_initial_import_main).__name__} - {e_initial_import_main}")
    st.exception(e_initial_import_main)
    st.stop()

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- Variáveis Globais e Verificação de Segredos ---
llm_model_global = None 
firebase_secrets_are_valid = False

try:
    if "firebase_config" not in st.secrets or \
       "cookie_firebase" not in st.secrets or \
       "GOOGLE_API_KEY" not in st.secrets:
        missing = []
        if "firebase_config" not in st.secrets: missing.append("'[firebase_config]'")
        if "cookie_firebase" not in st.secrets: missing.append("'[cookie_firebase]'")
        if "GOOGLE_API_KEY" not in st.secrets: missing.append("'GOOGLE_API_KEY'")
        st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: Seção(ões)/chave(s) ausente(s): {', '.join(missing)}.")
        st.stop()

    firebase_creds_check = st.secrets["firebase_config"]
    cookie_creds_check = st.secrets["cookie_firebase"]

    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k_fb in required_firebase_keys:
        if k_fb not in firebase_creds_check or not firebase_creds_check[k_fb]: # Verifica também se a chave não está vazia
            raise KeyError(f"Chave '{k_fb}' ausente ou vazia na seção [firebase_config] dos segredos.")
    
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k_ck in required_cookie_keys:
        if k_ck not in cookie_creds_check or not cookie_creds_check[k_ck]: # Verifica também se a chave não está vazia
             if k_ck == "expiry_days" and cookie_creds_check.get(k_ck) == 0: # expiry_days pode ser 0
                 pass
             else:
                raise KeyError(f"Chave '{k_ck}' ausente ou vazia na seção [cookie_firebase] dos segredos.")
    
    if not st.secrets["GOOGLE_API_KEY"].strip():
        raise ValueError("A chave 'GOOGLE_API_KEY' está vazia nos segredos.")

    firebase_secrets_are_valid = True 
except (KeyError, ValueError) as e_secrets_val: 
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: {e_secrets_val}.")
    st.info("Por favor, verifique cuidadosamente a estrutura, o nome e os valores das chaves nas suas seções [firebase_config], [cookie_firebase] e GOOGLE_API_KEY nos Segredos do Streamlit Cloud. Nenhuma chave essencial deve estar vazia.")
    st.stop()
except Exception as e_secrets_init_main: 
    st.error(f"🚨 ERRO FATAL durante a verificação inicial dos segredos: {type(e_secrets_init_main).__name__} - {e_secrets_init_main}")
    st.exception(e_secrets_init_main)
    st.stop()

if not firebase_secrets_are_valid:
    st.error("Validação dos segredos falhou. O aplicativo não pode prosseguir.")
    st.stop()

# --- Interface de Login/Logout ---
login_widget_key_v9 = "login_btn_fbauth_v9_final"
logout_widget_key_v9 = "logout_btn_fbauth_v9_final"

login_button(key=login_widget_key_v9) 

if not st.session_state.get("authentication_status"):
    st.stop() 

# --- Conteúdo do Aplicativo (Após Login) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!") # 'username' é populado pela biblioteca
if logout_button(key=logout_widget_key_v9):
    # Limpeza de chaves de sessão específicas do app
    keys_to_clear_v9 = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    # Definindo sufixo único para esta versão para chaves de sessão
    app_specific_key_suffix_v9 = "_fbauth_v9" 
    
    for key_to_delete_v9 in keys_to_clear_v9:
        if key_to_delete_v9.startswith(("chat_display_", "memoria_", "generated_")) or \
           app_specific_key_suffix_v9 in key_to_delete_v9: # Limpa chaves com o sufixo específico
            if key_to_delete_v9 in st.session_state:
                del st.session_state[key_to_delete_v9]
    st.experimental_rerun() 

# --- Inicialização do LLM ---
try:
    google_api_key_val = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=google_api_key_val)
    llm_model_global = ChatGoogleGenerativeAI(model="gemini-1.5-flash", 
                                 temperature=0.75,
                                 google_api_key=google_api_key_val,
                                 convert_system_message_to_human=True)
except Exception as e_llm_main:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {type(e_llm_main).__name__} - {e_llm_main}")
    st.stop()

if not llm_model_global:
    st.error("🚨 Modelo LLM não pôde ser inicializado. O aplicativo não pode carregar funcionalidades principais.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    key_suffix = f"_{section_key}_fbauth_v9_mkt" 
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
    key_suffix = f"_{section_key}_fbauth_v9_mkt"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=str(generated_content).encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, current_llm, session_state_output_key, 
                               campaign_specifics=None, selected_platforms_list=None): # Removido uploaded_files_info se não usado
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
    except Exception as e_invoke_mkt:
        st.error(f"Erro ao invocar LLM ({session_state_output_key}): {type(e_invoke_mkt).__name__} - {e_invoke_mkt}")
        st.session_state[session_state_output_key] = "Ocorreu um erro ao gerar o conteúdo."

# --- Classe Principal do Aplicativo ---
class AssistentePMEPro:
    def __init__(self, llm_instance_for_class):
        self.llm = llm_instance_for_class
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v9', ConversationBufferMemory(memory_key="hist_plano_fb_v9", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v9', ConversationBufferMemory(memory_key="hist_precos_fb_v9", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v9', ConversationBufferMemory(memory_key="hist_ideias_fb_v9", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message_template, memoria_obj, memory_key_placeholder="hist_conversa_v9_placeholder"):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message_template),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria_obj, verbose=False)
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        
        mkt_action_key = "main_marketing_action_fbauth_v9" # Sufixo de versão
        opcoes_mkt_list = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                            "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                            "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                            "6 - Conhecer a concorrência (Análise Competitiva)")
        st.session_state.setdefault(f"{mkt_action_key}_index", 0)
        def on_mkt_radio_change(): st.session_state[f"{mkt_action_key}_index"] = mkt_opcoes_list.index(st.session_state[mkt_action_key])
        mkt_acao_selecionada = st.radio("O que você quer fazer em marketing digital?", mkt_opcoes_list,
                                       index=st.session_state[f"{mkt_action_key}_index"], 
                                       key=mkt_action_key, on_change=on_mkt_radio_change)
        st.markdown("---")
        
        platforms_config = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp" } # Simplificado para exemplo
        platform_names = list(platforms_config.keys())

        if mkt_acao_selecionada == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            form_key_post = "post_form_v9_mkt"
            output_key_post = "generated_post_content_v9_mkt"
            with st.form(form_key_post, clear_on_submit=True):
                details_post = _marketing_get_objective_details("post_creator_v9", "post")
                st.subheader("Plataformas Desejadas:")
                select_all_key_post = f"post_sel_all_{form_key_post}"
                select_all_val_post = st.checkbox("Selecionar Todas", key=select_all_key_post)
                cols_plats_post = st.columns(min(len(platforms_config), 2)) # No máximo 2 colunas
                current_plat_selections_post = {}
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_plats_post[i % len(cols_plats_post)]:
                        cb_key_plat_post = f"post_plat_{p_sfx}_{form_key_post}"
                        current_plat_selections_post[p_name] = st.checkbox(p_name, value=select_all_val_post, key=cb_key_plat_post)
                submitted_post = st.form_submit_button("💡 Gerar Post!")
            if submitted_post:
                final_selected_plats_post = [p for p,isSelected in current_plat_selections_post.items() if st.session_state[f"post_plat_{platforms_config[p]}_{form_key_post}"]]
                if st.session_state[select_all_key_post]: final_selected_plats_post = platform_names
                if not final_selected_plats_post: st.warning("Selecione ao menos uma plataforma.")
                else:
                    _marketing_generic_handler("Crie um texto de post...", details_post, self.llm, output_key_post, selected_platforms_list=final_selected_plats_post)
            if output_key_post in st.session_state:
                _marketing_display_output_options(st.session_state[output_key_post], "post_out_v9_mkt", "post_ia")

        elif mkt_acao_selecionada == "2 - Criar campanha de marketing completa":
             st.subheader("🌍 Planejador de Campanhas de Marketing com IA")
             form_key_campanha = "campaign_form_v9_mkt"
             output_key_campanha = "generated_campaign_content_v9_mkt"
             with st.form(form_key_campanha, clear_on_submit=True):
                camp_specifics_data = {}
                camp_specifics_data["name"] = st.text_input("Nome da Campanha:", key=f"camp_name_{form_key_campanha}")
                details_campanha = _marketing_get_objective_details("camp_creator_v9", "campanha")
                st.subheader("Plataformas Desejadas:")
                sel_all_camp_key = f"camp_sel_all_{form_key_campanha}"
                sel_all_camp_val = st.checkbox("Selecionar Todas", key=sel_all_camp_key)
                cols_camp_plats = st.columns(min(len(platforms_config), 2))
                current_plat_selections_camp = {}
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_camp_plats[i % len(cols_camp_plats)]:
                        cb_key_camp_plat = f"camp_plat_{p_sfx}_{form_key_campanha}"
                        current_plat_selections_camp[p_name] = st.checkbox(p_name, value=sel_all_camp_val, key=cb_key_camp_plat)
                camp_specifics_data["duration"] = st.text_input("Duração Estimada:", key=f"camp_duration_{form_key_campanha}")
                camp_specifics_data["budget"] = st.text_input("Orçamento Aproximado (opcional):", key=f"camp_budget_{form_key_campanha}")
                camp_specifics_data["kpis"] = st.text_area("KPIs mais importantes:", key=f"camp_kpis_{form_key_campanha}")
                submitted_campanha = st.form_submit_button("🚀 Gerar Plano de Campanha!")
             if submitted_campanha:
                final_selected_plats_camp = [p for p,isSelected in current_plat_selections_camp.items() if st.session_state[f"camp_plat_{platforms_config[p]}_{form_key_campanha}"]]
                if st.session_state[sel_all_camp_key]: final_selected_plats_camp = platform_names
                if not final_selected_plats_camp: st.warning("Selecione ao menos uma plataforma.")
                else:
                    _marketing_generic_handler("Crie um plano de campanha...", details_campanha, self.llm, output_key_campanha, 
                                               campaign_specifics=camp_specifics_data, selected_platforms_list=final_selected_plats_camp)
             if output_key_campanha in st.session_state:
                _marketing_display_output_options(st.session_state[output_key_campanha], "camp_out_v9_mkt", "campanha_ia")
        
        # ... (Implementar o restante das opções de marketing: Landing Page, Site, Cliente, Concorrência)
        # ... Lembre-se de usar sufixos _v9 ou _vX_mkt para todas as chaves de form e session_state ...

        elif mkt_acao_selecionada_v8 == "Selecione uma opção...": # Correção para v8 aqui, já que foi copiado
            st.info("👋 Bem-vindo à seção interativa de Marketing Digital com IA! Escolha uma das opções acima para começar.")
            # LOGO_PATH_MKT = "images/logo-pme-ia.png" 
            # if os.path.exists(LOGO_PATH_MKT): st.image(LOGO_PATH_MKT, caption="Assistente PME Pro", width=200)
            # else: st.image(IMGUR_FALLBACK_APP, caption="Assistente PME Pro (Logo Padrão)", width=200)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v9")
        try: resp = cadeia.invoke({"input_usuario": input_usuario}); return resp.get('text', "Erro")
        except Exception as e: return f"Erro: {e}"

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt = f"Usuário pede ajuda para precificar: '{input_usuario}'."
        if descricao_imagem_contexto: prompt = f"Imagem: '{descricao_imagem_contexto}'. {prompt}"
        system_message = f"Você é especialista em precificação. {prompt} Faça perguntas para obter custos, margem, etc."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v9")
        try: resp = cadeia.invoke({"input_usuario": input_usuario}); return resp.get('text', "Erro")
        except Exception as e: return f"Erro: {e}"

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt = f"Usuário busca ideias: '{input_usuario}'."
        if contexto_arquivos: prompt = f"Contexto: {contexto_arquivos}\n{prompt}"
        system_message = f"Você é um consultor criativo. {prompt} Gere 3-5 ideias inovadoras."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v9")
        try: resp = cadeia.invoke({"input_usuario": input_usuario}); return resp.get('text', "Erro")
        except Exception as e: return f"Erro: {e}"

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_key, msg_inicial, memoria):
    chat_key = f"chat_display_v9_{area_key}"
    st.session_state[chat_key] = [{"role": "assistant", "content": msg_inicial}]
    if memoria: 
        memoria.clear()
        memoria.chat_memory.messages = [AIMessage(content=msg_inicial)] # Atualizado para AIMessage
    if area_key == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v9', None)
    elif area_key == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v9', None)

def exibir_chat_e_obter_input_global(area_key, placeholder, func_agente, **kwargs_agente):
    chat_key_display = f"chat_display_v9_{area_key}"
    chat_key_input = f"chat_input_v9_{area_key}"
    st.session_state.setdefault(chat_key_display, [])
    for msg in st.session_state[chat_key_display]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt_usr := st.chat_input(placeholder, key=chat_key_input):
        st.session_state[chat_key_display].append({"role": "user", "content": prompt_usr})
        with st.chat_message("user"): st.markdown(prompt_usr)
        
        current_kwargs = kwargs_agente.copy()
        if area_key == "calculo_precos" and st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v9'):
            current_kwargs['descricao_imagem_contexto'] = st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v9', None)
        elif area_key == "gerador_ideias" and st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v9'):
            current_kwargs['contexto_arquivos'] = st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v9', None)
            
        with st.spinner("Processando..."):
            resp_agent = func_agente(input_usuario=prompt_usr, **current_kwargs)
        st.session_state[chat_key_display].append({"role": "assistant", "content": resp_agent})
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v9' not in st.session_state and llm_model_global: 
    st.session_state.agente_pme_fbauth_v9 = AssistentePMEPro(llm_instance_for_class=llm_model_global)
agente_principal_app = st.session_state.get('agente_pme_fbauth_v9')

LOGO_PATH_SIDEBAR = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_SIDEBAR = "https://i.imgur.com/7IIYxq1.png"
if os.path.exists(LOGO_PATH_SIDEBAR): st.sidebar.image(LOGO_PATH_SIDEBAR, width=150)
else: st.sidebar.image(IMGUR_FALLBACK_SIDEBAR, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_sidebar_map = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_labels_sidebar_list = list(opcoes_menu_sidebar_map.keys())
radio_key_sidebar_main_v9 = 'main_selection_fbauth_v9' 

st.session_state.setdefault(f'{radio_key_sidebar_main_v9}_index', 0)
st.session_state.setdefault('secao_selecionada_app_v9', opcoes_labels_sidebar_list[st.session_state[f'{radio_key_sidebar_main_v9}_index']])

def on_main_radio_change_v9_sidebar_cb():
    st.session_state.secao_selecionada_app_v9 = st.session_state[radio_key_sidebar_main_v9]
    st.session_state[f'{radio_key_sidebar_main_v9}_index'] = opcoes_labels_sidebar_list.index(st.session_state[radio_key_sidebar_main_v9])
    st.session_state.previous_secao_selecionada_app_v9 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels_sidebar_list, key=radio_key_sidebar_main_v9, 
                 index=st.session_state[f'{radio_key_sidebar_main_v9}_index'], on_change=on_main_radio_change_v9_sidebar_cb)

chave_secao_render_atual = opcoes_menu_sidebar_map.get(st.session_state.secao_selecionada_app_v9)

if agente_principal_app: 
    if chave_secao_render_atual not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_v9 != st.session_state.get('previous_secao_selecionada_app_v9'):
            msg_inicial_chat_secao = ""
            memoria_chat_secao = None
            if chave_secao_render_atual == "plano_negocios": 
                msg_inicial_chat_secao = "Olá! Vamos detalhar seu plano de negócios?"
                memoria_chat_secao = agente_principal_app.memoria_plano_negocios
            elif chave_secao_render_atual == "calculo_precos": 
                msg_inicial_chat_secao = "Pronto para calcular preços? Descreva seu produto/serviço."
                memoria_chat_secao = agente_principal_app.memoria_calculo_precos
            elif chave_secao_render_atual == "gerador_ideias": 
                msg_inicial_chat_secao = "Buscando inspiração? Qual seu desafio ou área de interesse?"
                memoria_chat_secao = agente_principal_app.memoria_gerador_ideias
            if msg_inicial_chat_secao and memoria_chat_secao: 
                inicializar_ou_resetar_chat_global(chave_secao_render_atual, msg_inicial_chat_secao, memoria_chat_secao)
            st.session_state.previous_secao_selecionada_app_v9 = st.session_state.secao_selecionada_app_v9

    if chave_secao_render_atual == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        # ... (Conteúdo da página inicial como antes)
        st.markdown("---")
        logo_pg_inicial_v9 = LOGO_PATH_APP if os.path.exists(LOGO_PATH_APP) else IMGUR_FALLBACK_APP
        st.markdown(f"<div style='text-align: center;'><img src='{logo_pg_inicial_v9}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        # Botões de navegação
    elif chave_secao_render_atual == "mkt_guiado": 
        agente_principal_app.marketing_digital_guiado()
    elif chave_secao_render_atual == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        exibir_chat_e_obter_input_global(chave_secao_render_atual, "Detalhes do seu negócio...", agente_principal_app.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v9"):
            inicializar_ou_resetar_chat_global(chave_secao_render_atual, "Plano de negócios reiniciado.", agente_principal_app.memoria_plano_negocios); st.rerun()
    elif chave_secao_render_atual == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        # ... (lógica de upload e chat como antes, com chaves _v9) ...
        exibir_chat_e_obter_input_global(chave_secao_render_atual, "Descreva produto/custos...", agente_principal_app.calcular_precos_interativo)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v9"):
            inicializar_ou_resetar_chat_global(chave_secao_render_atual, "Cálculo de preços reiniciado.", agente_principal_app.memoria_calculo_precos); st.rerun()
    elif chave_secao_render_atual == "gerador_ideias":
        st.header("💡 Gerador de Ideias para Negócios com IA")
        # ... (lógica de upload e chat como antes, com chaves _v9) ...
        exibir_chat_e_obter_input_global(chave_secao_render_atual, "Descreva seu desafio...", agente_principal_app.gerar_ideias_para_negocios)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v9"):
            inicializar_ou_resetar_chat_global(chave_secao_render_atual, "Geração de ideias reiniciada.", agente_principal_app.memoria_gerador_ideias); st.rerun()
else:
    if not firebase_secrets_valid: pass 
    elif not llm_model_global and st.session_state.get("authentication_status"): 
        st.error("O LLM não foi inicializado. Verifique a GOOGLE_API_KEY.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
