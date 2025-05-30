import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image

# Tenta importar as funções específicas da biblioteca de autenticação
try:
    from streamlit_firebase_auth import login_button, logout_button, FirebaseAuth
except ImportError:
    st.error("🚨 ERRO CRÍTICO: Não foi possível importar 'streamlit_firebase_auth'. Verifique se está no requirements.txt e se foi instalado corretamente.")
    st.stop()

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- Variáveis Globais ---
llm_model = None 
firebase_secrets_ok = False # Flag para verificar se os segredos do Firebase estão OK

# --- Bloco de Verificação de Segredos e Inicialização Firebase (se necessário para backend) ---
try:
    if "firebase_config" not in st.secrets or \
       "cookie_firebase" not in st.secrets or \
       "GOOGLE_API_KEY" not in st.secrets:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seções/chaves cruciais ([firebase_config], [cookie_firebase], GOOGLE_API_KEY) não encontradas nos Segredos.")
        st.stop()

    firebase_creds = st.secrets["firebase_config"]
    cookie_creds = st.secrets["cookie_firebase"]

    required_firebase_keys = ["apiKey", "authDomain", "databaseURL", "projectId", "storageBucket", "messagingSenderId", "appId"]
    for k_fb in required_firebase_keys:
        if k_fb not in firebase_creds:
            raise KeyError(f"Chave '{k_fb}' ausente na seção [firebase_config] dos segredos.")
    
    required_cookie_keys = ["name", "key", "expiry_days"]
    for k_ck in required_cookie_keys:
        if k_ck not in cookie_creds:
            raise KeyError(f"Chave '{k_ck}' ausente na seção [cookie_firebase] dos segredos.")
    
    firebase_secrets_ok = True 
    # Nota: A instanciação de FirebaseAuth() não é necessária para usar login_button/logout_button
    # se a biblioteca estiver configurada para ler dos segredos automaticamente para esses componentes.
    # auth_handler = FirebaseAuth(...) # Removido pois causava o TypeError anterior

except KeyError as e:
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: {e}")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO FATAL durante a configuração inicial: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

if not firebase_secrets_ok: # Se a verificação dos segredos falhou
    st.error("Configuração de segredos do Firebase está incompleta. O aplicativo não pode prosseguir.")
    st.stop()

# --- Interface de Login/Logout ---
# Estas funções devem usar os st.secrets internamente.
login_key_suffix = "_fbauth_v7_login" # Sufixo para garantir chaves únicas
logout_key_suffix = "_fbauth_v7_logout"

login_button(key=f"loginbtn{login_key_suffix}")

if not st.session_state.get("authentication_status"):
    st.info("Por favor, faça login ou registre-se para continuar.")
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if logout_button(key=f"logoutbtn{logout_key_suffix}"):
    keys_to_clear = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_to_del in keys_to_clear:
        if key_to_del.startswith(("chat_display_", "memoria_", "generated_", "_fbauth_v7")): 
            if key_to_del in st.session_state:
                del st.session_state[key_to_del]
    st.experimental_rerun() 

# --- Inicialização do Modelo de Linguagem (LLM) do Google ---
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
    key_suffix = f"_{section_key}_fbauth_v7" 
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
    key_suffix = f"_{section_key}_fbauth_v7"
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
    def __init__(self, llm_instance):
        self.llm = llm_instance
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v7', ConversationBufferMemory(memory_key="hist_plano_fb_v7", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v7', ConversationBufferMemory(memory_key="hist_precos_fb_v7", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v7', ConversationBufferMemory(memory_key="hist_ideias_fb_v7", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key_placeholder="historico_chat"):
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
        platforms_config = { "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x"} # etc.
        platform_names = list(platforms_config.keys())

        if mkt_acao_selecionada == "1 - Criar post para redes sociais ou e-mail":
            st.subheader("✨ Criador de Posts com IA")
            with st.form("post_form_v7", clear_on_submit=True):
                details_post = _marketing_get_objective_details("post_v7_creator", "post")
                # ... (Lógica de seleção de plataformas como antes) ...
                submit_post = st.form_submit_button("💡 Gerar Post!")
            if submit_post:
                # ... (Lógica para pegar plataformas selecionadas) ...
                _marketing_generic_handler("Crie um texto de post...", details_post, self.llm, "generated_post_v7", selected_platforms_list=["Instagram"]) # Exemplo
            if "generated_post_v7" in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_v7, "post_out_v7", "post_ia")
        # ... (Restante das seções de marketing)

    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", consultor de negócios..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v7")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        # ... (lógica como antes) ...
        system_message = f"Você é o \"Assistente PME Pro\", especialista em precificação..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v7")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        # ... (lógica como antes) ...
        system_message = f"Você é o \"Assistente PME Pro\", consultor criativo..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v7")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

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
    if prompt_usuario := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"): st.markdown(prompt_usuario)
        with st.spinner("Processando..."):
            resposta_assistente = funcao_agente(input_usuario=prompt_usuario, **kwargs_agente)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente})
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v7' not in st.session_state and llm_model: 
    st.session_state.agente_pme_fbauth_v7 = AssistentePMEPro(llm_instance=llm_model)
agente_principal = st.session_state.get('agente_pme_fbauth_v7')

LOGO_PATH_APP = "images/logo-pme-ia.png" 
IMGUR_FALLBACK_APP = "https://i.imgur.com/7IIYxq1.png"
if os.path.exists(LOGO_PATH_APP): st.sidebar.image(LOGO_PATH_APP, width=150)
else: st.sidebar.image(IMGUR_FALLBACK_APP, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu_principais = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_labels_principais = list(opcoes_menu_principais.keys())
radio_key_menu_principal = 'main_selection_fbauth_v7'

st.session_state.setdefault(f'{radio_key_menu_principal}_index', 0)
st.session_state.setdefault('secao_selecionada_app_v7', opcoes_labels_principais[st.session_state[f'{radio_key_menu_principal}_index']])

def on_main_radio_change_v7():
    st.session_state.secao_selecionada_app_v7 = st.session_state[radio_key_menu_principal]
    st.session_state[f'{radio_key_menu_principal}_index'] = opcoes_labels_principais.index(st.session_state[radio_key_menu_principal])
    st.session_state.previous_secao_selecionada_app_v7 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels_principais, key=radio_key_menu_principal, 
                 index=st.session_state[f'{radio_key_menu_principal}_index'], on_change=on_main_radio_change_v7)

chave_secao_renderizar = opcoes_menu_principais.get(st.session_state.secao_selecionada_app_v7)

if agente_principal: # Só renderiza o conteúdo se o agente (e o LLM) estiverem prontos
    # Inicialização de chat para seções conversacionais
    if chave_secao_renderizar not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.secao_selecionada_app_v7 != st.session_state.get('previous_secao_selecionada_app_v7'):
            msg_inicial_secao_chat = ""
            memoria_secao_chat_atual = None
            if chave_secao_renderizar == "plano_negocios": 
                msg_inicial_secao_chat = "Olá! Sou seu Assistente PME Pro. Vamos elaborar um rascunho robusto do seu plano de negócios?"
                memoria_secao_chat_atual = agente_principal.memoria_plano_negocios
            elif chave_secao_renderizar == "calculo_precos": 
                msg_inicial_secao_chat = "Olá! Bem-vindo ao assistente de Cálculo de Preços. Descreva o produto ou serviço."
                memoria_secao_chat_atual = agente_principal.memoria_calculo_precos
            elif chave_secao_renderizar == "gerador_ideias": 
                msg_inicial_secao_chat = "Olá! Sou o Assistente PME Pro, pronto para te ajudar a ter novas ideias."
                memoria_secao_chat_atual = agente_principal.memoria_gerador_ideias
            if msg_inicial_secao_chat and memoria_secao_chat_atual: 
                inicializar_ou_resetar_chat_global(chave_secao_renderizar, msg_inicial_secao_chat, memoria_secao_chat_atual)
            st.session_state.previous_secao_selecionada_app_v7 = st.session_state.secao_selecionada_app_v7

    # Renderização da Seção Selecionada
    if chave_secao_renderizar == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao seu Assistente PME Pro!</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Sou seu parceiro de IA dedicado a impulsionar o sucesso de Pequenas e Médias Empresas.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para navegar pelas ferramentas e começar a transformar seu negócio.</p></div>", unsafe_allow_html=True)
        st.markdown("---")
        logo_para_pagina_inicial = LOGO_PATH_APP if os.path.exists(LOGO_PATH_APP) else IMGUR_FALLBACK_APP
        st.markdown(f"<div style='text-align: center;'><img src='{logo_para_pagina_inicial}' alt='Logo Assistente PME Pro' width='150'></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        num_botoes_pg_inicial_final = len(opcoes_menu_principais) -1 
        if num_botoes_pg_inicial_final > 0 :
            num_cols_pg_inicial_final = min(num_botoes_pg_inicial_final, 3) 
            cols_pg_inicial_final = st.columns(num_cols_pg_inicial_final)
            idx_btn_pg_inicial_final = 0
            for nome_menu_item, chave_secao_item in opcoes_menu_principais.items():
                if chave_secao_item != "pg_inicial":
                    col_atual = cols_pg_inicial_final[idx_btn_pg_inicial_final % num_cols_pg_inicial_final]
                    label_botao_limpo = nome_menu_item.split(" com IA")[0].split(" (Guia)")[0].replace("Elaborar ", "").replace(" Inteligente","").replace(" para Negócios","")
                    if col_atual.button(label_botao_limpo, key=f"btn_goto_{chave_secao_item}_fbauth_v7", use_container_width=True, help=f"Ir para {nome_menu_item}"):
                        st.session_state.secao_selecionada_app_v7 = nome_menu_item
                        st.session_state[f'{radio_key_menu_principal}_index'] = opcoes_labels_principais.index(nome_menu_item)
                        st.experimental_rerun()
                    idx_btn_pg_inicial_final +=1
            st.balloons()

    elif chave_secao_renderizar == "mkt_guiado": 
        agente_principal.marketing_digital_guiado()
    elif chave_secao_renderizar == "plano_negocios":
        st.header("📝 Elaborar Plano de Negócios com IA")
        st.caption("Converse com o assistente para desenvolver seções do seu plano de negócios.")
        exibir_chat_e_obter_input_global(chave_secao_renderizar, "Sua ideia, produtos/serviços, clientes...", agente_principal.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="btn_reset_plano_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_renderizar, "Ok, vamos recomeçar o seu Plano de Negócios.", agente_principal.memoria_plano_negocios)
            st.rerun()
    elif chave_secao_renderizar == "calculo_precos":
        st.header("💲 Cálculo de Preços Inteligente com IA")
        st.caption("Descreva seu produto/serviço, custos, mercado e objetivos.")
        uploaded_image_precos_v7 = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key="preco_uploader_fbauth_v7")
        kwargs_preco_chat_final = {}
        if uploaded_image_precos_v7 and st.session_state.get(f'processed_image_id_pricing_fbauth_v7') != uploaded_image_precos_v7.file_id:
            try:
                st.image(Image.open(uploaded_image_precos_v7), caption=f"Contexto: {uploaded_image_precos_v7.name}", width=150)
                st.session_state[f'last_uploaded_image_info_pricing_fbauth_v7'] = f"Imagem: {uploaded_image_precos_v7.name}"
                st.session_state[f'processed_image_id_pricing_fbauth_v7'] = uploaded_image_precos_v7.file_id
            except Exception as e: st.error(f"Erro ao carregar imagem: {e}")
        if st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v7'):
            kwargs_preco_chat_final['descricao_imagem_contexto'] = st.session_state.get(f'last_uploaded_image_info_pricing_fbauth_v7')
        exibir_chat_e_obter_input_global(chave_secao_renderizar, "Descreva produto/serviço, custos...", agente_principal.calcular_precos_interativo, **kwargs_preco_chat_final)
        if st.sidebar.button("🗑️ Limpar Preços", key="btn_reset_precos_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_renderizar, "Novo cálculo de preços. Descreva o produto/serviço.", agente_principal.memoria_calculo_precos)
            st.rerun()
            
    elif chave_secao_renderizar == "gerador_ideias":
        st.header("💡 Gerador de Ideias para Negócios com IA")
        st.caption("Descreva um desafio ou peça ideias. Envie arquivos de contexto, se desejar.")
        uploaded_files_ideias_ctx_v7 = st.file_uploader("Arquivos de contexto (.txt, .png, .jpg):", accept_multiple_files=True, key="ideias_uploader_fbauth_v7")
        kwargs_ideias_chat_final = {}
        if uploaded_files_ideias_ctx_v7:
            files_id_sig_ideias_v7 = "_".join(sorted([f.file_id for f in uploaded_files_ideias_ctx_v7]))
            if st.session_state.get(f'processed_file_id_ideias_fbauth_v7') != files_id_sig_ideias_v7:
                file_contexts_list_ideias = []
                for uploaded_file in uploaded_files_ideias_ctx_v7:
                    try:
                        if uploaded_file.type == "text/plain":
                            file_contexts_list_ideias.append(f"Conteúdo de '{uploaded_file.name}':\n{uploaded_file.read().decode('utf-8')[:1000]}...")
                        elif uploaded_file.type in ["image/png", "image/jpeg"]:
                            st.image(Image.open(uploaded_file), caption=f"Contexto: {uploaded_file.name}", width=100)
                            file_contexts_list_ideias.append(f"Imagem '{uploaded_file.name}' fornecida.")
                    except Exception as e: st.error(f"Erro ao processar '{uploaded_file.name}': {e}")
                st.session_state[f'uploaded_file_info_ideias_for_prompt_fbauth_v7'] = "\n".join(file_contexts_list_ideias)
                st.session_state[f'processed_file_id_ideias_fbauth_v7'] = files_id_sig_ideias_v7
                if file_contexts_list_ideias: st.info("Arquivo(s) de contexto pronto(s).")
        if st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v7'):
            kwargs_ideias_chat_final['contexto_arquivos'] = st.session_state.get(f'uploaded_file_info_ideias_for_prompt_fbauth_v7')
        exibir_chat_e_obter_input_global(chave_secao_renderizar, "Descreva seu desafio ou peça ideias:", agente_principal.gerar_ideias_para_negocios, **kwargs_ideias_chat_final)
        if st.sidebar.button("🗑️ Limpar Ideias", key="btn_reset_ideias_fbauth_v7"):
            inicializar_ou_resetar_chat_global(chave_secao_renderizar, "Novas ideias? Conte-me sobre seu objetivo.", agente_principal.memoria_gerador_ideias)
            st.rerun()
else:
    # Se o agente_principal (e o LLM) não foram inicializados após o login bem-sucedido, algo está errado com a inicialização do LLM.
    # O login_button e o st.stop() já cuidam da renderização antes do login.
    if st.session_state.get("authentication_status"): # Usuário está logado, mas agente falhou
        if not firebase_secrets_ok: # Isso já deveria ter parado o script, mas é uma dupla checagem
             st.error("A configuração dos segredos do Firebase está incompleta. O aplicativo não pode carregar.")
        elif not llm_model: 
             st.error("O modelo de linguagem (LLM) não foi inicializado. Verifique a chave GOOGLE_API_KEY nos segredos. O aplicativo não pode carregar as funcionalidades principais.")
        else:
             st.error("Agente principal do aplicativo não pôde ser carregado por um motivo desconhecido, mesmo com o LLM e login OK.")


st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
