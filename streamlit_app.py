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
llm_model = None 

# --- Bloco de Autenticação Firebase ---
# Os componentes st_auth.login_button() e st_auth.logout_button()
# lerão as configurações das seções [firebase_config] e [cookie_firebase]
# diretamente de st.secrets.

try:
    # Apenas uma verificação para garantir que os segredos existem e dar um feedback melhor
    if "firebase_config" not in st.secrets or \
       "cookie_firebase" not in st.secrets or \
       "GOOGLE_API_KEY" not in st.secrets:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Uma ou mais seções/chaves ([firebase_config], [cookie_firebase], GOOGLE_API_KEY) não foram encontradas nos Segredos do Streamlit Cloud.")
        st.info("Verifique se todas as chaves como 'apiKey', 'authDomain', etc., estão em [firebase_config]; 'name', 'key', 'expiry_days' em [cookie_firebase]; e GOOGLE_API_KEY diretamente.")
        st.stop()
    
    # Verifica chaves específicas dentro de firebase_config
    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k_fb in required_firebase_keys:
        if k_fb not in st.secrets["firebase_config"]:
            st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Chave '{k_fb}' ausente na seção [firebase_config] dos segredos.")
            st.stop()
    
    # Verifica chaves específicas dentro de cookie_firebase
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k_ck in required_cookie_keys:
        if k_ck not in st.secrets["cookie_firebase"]:
            st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Chave '{k_ck}' ausente na seção [cookie_firebase] dos segredos.")
            st.stop()

except KeyError as e: # Captura KeyErrors específicos dos segredos
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: A chave específica {e} não foi encontrada.")
    st.info("Por favor, verifique a estrutura e o nome das chaves nos seus Segredos no Streamlit Cloud.")
    st.stop()
except Exception as e: # Captura outros erros de inicialização
    st.error(f"🚨 ERRO FATAL durante a verificação inicial dos segredos: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

# --- Interface de Login/Logout ---
# Esses botões usam os st.secrets internamente para configuração.
# O estado da autenticação é gerenciado em st.session_state['authentication_status'] pela biblioteca.
st_auth.login_button(key="login_button_fbauth_v6") # Adicionada uma chave única

if not st.session_state.get("authentication_status"):
    # st.info("Por favor, faça login ou registre-se para continuar.") # O widget já serve como indicação
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if st_auth.logout_button(key="logout_button_fbauth_v6"): # Chave única
    keys_to_clear = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_to_del in keys_to_clear:
        if key_to_del.startswith(("chat_display_", "memoria_", "generated_", "_fbauth_v6")): 
            if key_to_del in st.session_state:
                del st.session_state[key_to_del]
    st.experimental_rerun()

# --- Inicialização do Modelo de Linguagem (LLM) do Google (APÓS LOGIN) ---
try:
    google_api_key_from_secrets = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=google_api_key_from_secrets)
    llm_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                 temperature=0.75,
                                 google_api_key=google_api_key_from_secrets,
                                 convert_system_message_to_human=True)
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
    key_suffix = f"_{section_key}_fbauth_v6" 
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
    key_suffix = f"_{section_key}_fbauth_v6"
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
        st.error(f"Erro ao invocar LLM para {session_state_output_key}: {e_invoke}")
        st.session_state[session_state_output_key] = "Ocorreu um erro ao gerar o conteúdo."


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_passed_in): # Nome do parâmetro alterado para clareza
        self.llm = llm_passed_in
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v6', ConversationBufferMemory(memory_key="hist_plano_fb_v6", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v6', ConversationBufferMemory(memory_key="hist_precos_fb_v6", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v6', ConversationBufferMemory(memory_key="hist_ideias_fb_v6", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key_placeholder="historico_chat"):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=memory_key_placeholder),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria, verbose=False) # verbose=False é melhor para produção
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        
        mkt_action_key = "main_marketing_action_fbauth_v6" # Chave atualizada
        opcoes_marketing = ("Selecione uma opção...", "1 - Criar post para redes sociais ou e-mail",
                            "2 - Criar campanha de marketing completa", "3 - Criar estrutura e conteúdo para landing page",
                            "4 - Criar estrutura e conteúdo para site com IA", "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)",
                            "6 - Conhecer a concorrência (Análise Competitiva)")
        
        st.session_state.setdefault(f"{mkt_action_key}_index", 0)

        def on_mkt_radio_change_v6(): # Callback atualizado
            selection = st.session_state[mkt_action_key]
            st.session_state[f"{mkt_action_key}_index"] = mkt_opcoes.index(selection) if selection in mkt_opcoes else 0
        
        mkt_acao_selecionada = st.radio("O que você quer fazer em marketing digital?", mkt_opcoes,
                                       index=st.session_state[f"{mkt_action_key}_index"], 
                                       key=mkt_action_key, on_change=on_mkt_radio_change_v6)
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
            with st.form("post_form_v6", clear_on_submit=True):
                details_post = _marketing_get_objective_details("post_v6_creator", "post")
                st.subheader("Plataformas Desejadas:")
                sel_all_post_key = "post_sel_all_v6"
                sel_all_post_val = st.checkbox("Selecionar Todas", key=sel_all_post_key)
                cols_post_plats = st.columns(2)
                current_form_selections_post = {} # Para pegar os valores do form no momento do submit
                
                for i, (p_name, p_sfx) in enumerate(platforms_config.items()):
                    with cols_post_plats[i % 2]:
                        cb_key = f"post_plat_{p_sfx}_v6"
                        # O valor do checkbox individual é usado se "Selecionar Todos" não estiver marcado.
                        # Se "Selecionar Todos" estiver, todos são marcados.
                        current_form_selections_post[p_name] = st.checkbox(p_name, value=sel_all_post_val or st.session_state.get(cb_key, False), key=cb_key)
                
                submit_post = st.form_submit_button("💡 Gerar Post!")

            if submit_post:
                # Determina as plataformas selecionadas com base nos valores do form no momento do submit
                selected_plats_post_final = []
                if st.session_state[sel_all_post_key]: # Se "Selecionar Todos" estava marcado no submit
                    selected_plats_post_final = platform_names
                else:
                    for p_name, p_sfx in platforms_config.items():
                        if st.session_state[f"post_plat_{p_sfx}_v6"]: # Checa o estado de cada checkbox
                             selected_plats_post_final.append(p_name)
                
                if not selected_plats_post_final:
                    st.warning("Selecione ao menos uma plataforma.")
                else:
                    with st.spinner("🤖 Criando post..."):
                        _marketing_generic_handler(
                            "Crie um texto de post engajador e otimizado para as plataformas e objetivos abaixo:", 
                            details_post, self.llm, "generated_post_content_v6", selected_platforms_list=selected_plats_post_final
                        )
            if "generated_post_content_v6" in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_v6, "post_out_v6", "post_ia")
        
        # ... (Lógica para outras seções de marketing como "Criar campanha", etc. precisa ser adicionada/adaptada aqui)
        # Lembre-se de usar chaves únicas para forms e session_state (ex: _v6)

    # --- Métodos de Chat para as Outras Seções ---
    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", um consultor de negócios experiente especializado em auxiliar Pequenas e Médias Empresas (PMEs) no Brasil a desenvolverem planos de negócios robustos e estratégicos. Guie o usuário interativamente, fazendo perguntas pertinentes, oferecendo insights e ajudando a estruturar cada seção do plano."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v6")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
            return resposta_ai_obj.get('text', "Desculpe, não consegui processar seu pedido para o plano de negócios.")
        except Exception as e_invoke_plano:
            st.error(f"Erro na conversação do plano de negócios: {e_invoke_plano}")
            return "Ocorreu um erro ao processar sua solicitação."

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_base_calc = f"O usuário está buscando ajuda para precificar um produto/serviço e forneceu a seguinte informação inicial: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_base_calc = f"Considerando a imagem '{descricao_imagem_contexto}', {prompt_base_calc}"
        system_message_precos = f"Você é o \"Assistente PME Pro\", especialista em precificação para PMEs. {prompt_base_calc} Faça perguntas para obter custos, margem desejada, análise de concorrência e público-alvo para sugerir uma estratégia de precificação."
        cadeia = self._criar_cadeia_conversacional(system_message_precos, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v6")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
            return resposta_ai_obj.get('text', "Desculpe, não consegui processar seu pedido de cálculo de preços.")
        except Exception as e_invoke_precos:
            st.error(f"Erro no cálculo de preços: {e_invoke_precos}")
            return "Ocorreu um erro ao processar sua solicitação de cálculo de preços."

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_base_ideias = f"O usuário busca ideias de negócios e informou: '{input_usuario}'."
        if contexto_arquivos:
            prompt_base_ideias = f"Considerando os seguintes arquivos e contextos: {contexto_arquivos}\n\n{prompt_base_ideias}"
        system_message_ideias = f"Você é o \"Assistente PME Pro\", um consultor de negócios criativo e especialista em IA. {prompt_base_ideias} Gere ideias inovadoras e práticas, considerando tendências de mercado e o perfil do PME."
        cadeia = self._criar_cadeia_conversacional(system_message_ideias, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v6")
        try:
            resposta_ai_obj = cadeia.invoke({"input_usuario": input_usuario})
            return resposta_ai_obj.get('text', "Desculpe, não consegui gerar ideias no momento.")
        except Exception as e_invoke_ideias:
            st.error(f"Erro na geração de ideias: {e_invoke_ideias}")
            return "Ocorreu um erro ao processar sua solicitação de ideias."

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_chave, msg_inicial, memoria):
    key_display = f"chat_display_{area_chave}_fbauth_v6" # Chave única para o estado do chat
    st.session_state[key_display] = [{"role": "assistant", "content": msg_inicial}]
    if memoria:
        memoria.clear()
        if hasattr(memoria.chat_memory, 'add_ai_message'): memoria.chat_memory.add_ai_message(msg_inicial)
        elif hasattr(memoria.chat_memory, 'messages'): memoria.chat_memory.messages = [AIMessage(content=msg_inicial)]
    # Limpar contextos de upload específicos da área
    if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v6', None)
    elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v6', None)

def exibir_chat_e_obter_input_global(area_chave, placeholder, funcao_agente, **kwargs_agente):
    key_display = f"chat_display_{area_chave}_fbauth_v6"
    key_input = f"chat_input_{area_chave}_fbauth_v6"
    st.session_state.setdefault(key_display, [])
    
    for msg in st.session_state[key_display]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt_usuario_chat := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt_usuario_chat})
        with st.chat_message("user"): st.markdown(prompt_usuario_chat)
        
        local_kwargs_agente_chat = kwargs_agente.copy()
        if area_chave == "calculo_precos":
            if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v6'):
                local_kwargs_agente_chat['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v6')
        elif area_chave == "gerador_ideias":
            if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v6'):
                local_kwargs_agente_chat['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v6')
            
        with st.spinner("Assistente PME Pro processando... 🤔"):
            resposta_assistente_chat = funcao_agente(input_usuario=prompt_usuario_chat, **local_kwargs_agente_chat)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente_chat})
        
        if area_chave == "calculo_precos": st.session_state.pop(f'last_uploaded_image_info_pricing_fbauth_v6', None) # Limpa após uso
        elif area_chave == "gerador_ideias": st.session_state.pop(f'uploaded_file_info_ideias_for_prompt_fbauth_v6', None) # Limpa após uso
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v6' not in st.session_state and llm_model: 
    st.session_state.agente_pme_fbauth_v6 = AssistentePMEPro(llm_passed_in=llm_model)
agente_principal_app = st.session_state.get('agente_pme_fbauth_v6')

LOGO_PATH_APP = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_LOGO_APP = "https://i.imgur.com/7IIYxq1.png"

if os.path.exists(LOGO_PATH_APP): st.sidebar.image(LOGO_PATH_APP, width=150)
else: st.sidebar.image(IMGUR_FALLBACK_LOGO_APP, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_sidebar = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"
}
opcoes_labels_sidebar = list(opcoes_menu_sidebar.keys())
radio_key_sidebar_main = 'main_selection_fbauth_v6' # Chave única para o radio principal

st.session_state.setdefault(f'{radio_key_sidebar_main}_index', 0)
st.session_state.setdefault('secao_selecionada_app_atual_v6', opcoes_labels_sidebar[st.session_state[f'{radio_key_sidebar_main}_index']])

def on_main_radio_change_v6():
    st.session_state.secao_selecionada_app_atual_v6 = st.session_state[radio_key_sidebar_main]
    st.session_state[f'{radio_key_sidebar_main}_index'] = opcoes_labels_sidebar.index(st.session_state[radio_key_sidebar_main])
    if st.session_state.secao_selecionada_app_atual_v6 != "Marketing Digital com IA":
         for k_clear in list(st.session_state.keys()): 
            if k_clear.startswith(("generated_", "_cb_fbauth_v6", "main_marketing_action_fbauth_v6")):
                if k_clear in st.session_state: del st.session_state[k_clear]
    st.session_state.previous_secao_selecionada_app_v6 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels_sidebar, key=radio_key_sidebar_main, 
                 index=st.session_state[f'{radio_key_sidebar_main}_index'], on_change=on_main_radio_change_v6)

chave_secao_ativa = opcoes_menu_sidebar.get(st.session_state.secao_selecionada_app_atual_v6)

if agente_principal_app: # Só executa se o agente (e LLM) estiverem prontos
    # Inicialização de chat para seções conversacionais
    if chave_secao_ativa not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_atual_v6 != st.session_state.get('previous_secao_selecionada_app_v6'):
            msg_inicial_para_secao = ""
            memoria_para_secao = None
            if chave_secao_ativa == "plano_negocios": 
                msg_inicial_para_secao = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios? Para começar, me conte sobre sua ideia de negócio, seus principais produtos/serviços, e quem você imagina como seus clientes."
                memoria_para_secao = agente_principal_app.memoria_plano_negocios
            elif chave_secao_ativa == "calculo_precos": 
                msg_inicial_para_secao = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Para começarmos, por favor, descreva o produto ou serviço para o qual você gostaria de ajuda para precificar. Se tiver uma imagem, pode enviá-la também."
                memoria_para_secao = agente_principal_app.memoria_calculo_precos
            elif chave_secao_ativa == "gerador_ideias": 
                msg_inicial_para_secao = "Olá! Sou o Assistente PME Pro. Estou aqui para te ajudar a ter novas ideias para o seu negócio. Você pode me descrever um desafio, uma área que quer inovar, ou simplesmente pedir sugestões."
                memoria_para_secao = agente_principal_app.memoria_gerador_ideias
            
            if msg_inicial_para_secao and memoria_para_secao: 
                inicializar_ou_resetar_chat_global(chave_secao_ativa, msg_inicial_para_secao, memoria_para_secao)
            st.session_state.previous_secao_selecionada_app_v6 = st.session_state.secao_selecionada_app_atual_v6

    # Renderização da Seção Selecionada
    if chave_secao_ativa == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        logo_pagina_inicial = LOGO_PATH_APP if os.path.exists(LOGO_PATH_APP) else IMGUR_FALLBACK_LOGO_APP
        st.markdown(f"<div style='text-align: center;'><img src='{logo_pagina_inicial}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        num_botoes_menu_inicial = len(opcoes_menu_sidebar) -1 
        if num_botoes_menu_inicial > 0 :
            num_cols_menu_inicial = min(num_botoes_menu_inicial, 3) 
            cols_menu_inicial = st.columns(num_cols_menu_inicial)
            idx_btn_menu_inicial = 0
            for nome_menu_item_btn, chave_secao_item_btn in opcoes_menu_sidebar.items():
                if chave_secao_item_btn != "pg_inicial":
                    col_do_botao = cols_menu_inicial[idx_btn_menu_inicial % num_cols_menu_inicial]
                    label_do_botao = nome_menu_item_btn.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                    if col_do_botao.button(label_do_botao, key=f"btn_goto_{chave_secao_item_btn}_fbauth_v6", use_container_width=True, help=f"Ir para {nome_menu_item_btn}"):
                        st.session_state.secao_selecionada_app_atual_v6 = nome_menu_item_btn
                        st.session_state[f'{radio_key_sidebar_main}_index'] = opcoes_labels_sidebar.index(nome_menu_item_btn)
                        st.experimental_rerun()
                    idx_btn_menu_inicial +=1
            st.balloons()

    elif chave_secao_ativa == "mkt_guiado": 
        agente_principal_app.marketing_digital_guiado()
    elif chave_secao_ativa == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
        exibir_chat_e_obter_input_global(chave_secao_ativa, "Sua ideia, produtos/serviços, clientes...", agente_principal_app.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v6"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa, "Ok, vamos recomeçar o seu Plano de Negócios.", agente_principal_app.memoria_plano_negocios)
            st.rerun()
    elif chave_secao_ativa == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
        uploaded_image_preco = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_uploader_fbauth_v6")
        kwargs_preco_chat_call = {}
        if uploaded_image_preco and st.session_state.get(f'processed_image_id_pricing_fbauth_v6') != uploaded_image_preco.file_id:
            try:
                st.image(Image.open(uploaded_image_preco), caption=f"Contexto: {uploaded_image_preco.name}", width=150)
                st.session_state[f'last_uploaded_image_info_pricing_fbauth_v6'] = f"Imagem: {uploaded_image_preco.name}"
                st.session_state[f'processed_image_id_pricing_fbauth_v6'] = uploaded_image_preco.file_id
            except Exception as e_img_calc: st.error(f"Erro ao carregar imagem: {e_img_calc}")
        if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v6'):
            kwargs_preco_chat_call['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v6')
        exibir_chat_e_obter_input_global(chave_secao_ativa, "Descreva produto/serviço, custos...", agente_principal_app.calcular_precos_interativo, **kwargs_preco_chat_call)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v6"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa, "Novo cálculo de preços. Descreva o produto/serviço.", agente_principal_app.memoria_calculo_precos)
            st.rerun()
            
    elif chave_secao_ativa == "gerador_ideias":
        st.header("💡 Gerador de Ideias para Negócios com IA")
        st.caption("Descreva um desafio ou peça ideias. Envie arquivos de contexto, se desejar.")
        uploaded_files_ideias_ctx = st.file_uploader("Arquivos de contexto (.txt, .png, .jpg):", accept_multiple_files=True, key="ideias_uploader_fbauth_v6")
        kwargs_ideias_chat_call = {}
        if uploaded_files_ideias_ctx:
            files_id_sig_ideias = "_".join(sorted([f.file_id for f in uploaded_files_ideias_ctx]))
            if st.session_state.get(f'processed_file_id_ideias_fbauth_v6') != files_id_sig_ideias:
                file_contexts_list = []
                for uploaded_file_item_ideias in uploaded_files_ideias_ctx:
                    try:
                        if uploaded_file_item_ideias.type == "text/plain":
                            file_contexts_list.append(f"Conteúdo de '{uploaded_file_item_ideias.name}':\n{uploaded_file_item_ideias.read().decode('utf-8')[:1000]}...")
                        elif uploaded_file_item_ideias.type in ["image/png", "image/jpeg"]:
                            st.image(Image.open(uploaded_file_item_ideias), caption=f"Contexto: {uploaded_file_item_ideias.name}", width=100)
                            file_contexts_list.append(f"Imagem '{uploaded_file_item_ideias.name}' fornecida.")
                    except Exception as e_file_proc_ideias: st.error(f"Erro ao processar '{uploaded_file_item_ideias.name}': {e_file_proc_ideias}")
                st.session_state[f'uploaded_file_info_ideias_for_prompt_fbauth_v6'] = "\n".join(file_contexts_list)
                st.session_state[f'processed_file_id_ideias_fbauth_v6'] = files_id_sig_ideias
                if file_contexts_list: st.info("Arquivo(s) de contexto pronto(s) para o diálogo.")
        
        if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v6'):
            kwargs_ideias_chat_call['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v6')

        exibir_chat_e_obter_input_global(chave_secao_ativa, "Descreva seu desafio ou peça ideias:", agente_principal_app.gerar_ideias_para_negocios, **kwargs_ideias_chat_call)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v6"):
            inicializar_ou_resetar_chat_global(chave_secao_ativa, "Novas ideias? Conte-me sobre seu objetivo.", agente_principal_app.memoria_gerador_ideias)
            st.rerun()
else: # Se o agente_principal_app (e consequentemente o llm_model) não foi inicializado
    if not st.session_state.get("authentication_status"):
        pass # O st_auth.login_button() e o st.stop() acima já cuidam disso.
    elif not llm_model: # Se autenticado, mas LLM falhou
        st.error("O modelo de linguagem (LLM) não pôde ser inicializado. Verifique a chave GOOGLE_API_KEY nos segredos. O aplicativo não pode carregar as funcionalidades principais.")
    # Caso genérico de falha de inicialização do agente, se necessário.
    # else:
    #    st.error("Agente principal do aplicativo não pôde ser carregado.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
