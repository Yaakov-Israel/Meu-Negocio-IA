import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth # Renomeado de volta para st_auth por consistência

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

# --- Bloco de Autenticação Firebase (Simplificado) ---
# A biblioteca streamlit-firebase-auth lida com a maior parte da configuração
# através dos widgets de login/logout e dos segredos.

# Inicializa o objeto de autenticação da biblioteca.
# Ele usará os segredos do Streamlit para as configurações do Firebase.
# As chaves específicas como apiKey, authDomain, etc., DEVEM estar na seção [firebase_config] dos seus segredos.
# As chaves do cookie (name, key, expiry_days) DEVEM estar na seção [cookie_firebase] dos seus segredos.
try:
    # Apenas instanciamos. A configuração é pega dos segredos pela biblioteca.
    # O construtor de FirebaseAuth da oom-bell não aceita os argumentos de config do cliente diretamente.
    # Ele é mais para o lado do admin (verificar tokens, etc.).
    # O widget de login é que usa os segredos.
    
    # Vamos tentar a estrutura que a biblioteca realmente expõe para o fluxo de login.
    # A biblioteca `streamlit-firebase-auth` (oom-bell) usa o `login_button` para o fluxo.
    # Não precisamos instanciar `FirebaseAuth` antes de chamar o login_button.
    # O login_button e o logout_button são os pontos de entrada principais.

    # Verificação se os segredos existem (para feedback ao usuário)
    if "firebase_config" not in st.secrets or "cookie_firebase" not in st.secrets:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seções [firebase_config] ou [cookie_firebase] não encontradas nos Segredos.")
        st.info("Certifique-se de que os segredos estão corretamente configurados no Streamlit Cloud.")
        st.stop()
    
    # A inicialização do objeto Authenticate da biblioteca é feita internamente
    # pelos seus componentes de UI quando os segredos estão disponíveis.

except Exception as e:
    st.error(f"🚨 ERRO FATAL durante a configuração inicial da autenticação: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()


# --- Processo de Login ---
# O widget de login/logout da biblioteca `streamlit-firebase-auth` (oom-bell)
# lida com a interface e o estado da sessão.
# Ele espera que as configurações do Firebase e do cookie estejam nos segredos do Streamlit.

login_successful = st_auth.login_button(
    #label="Login / Registrar com Google", # Exemplo de customização do label
    #class_name="minha-classe-css-customizada" # Exemplo
)
# A variável 'login_successful' será True se o login for bem-sucedido,
# False se falhar, e None se o usuário ainda não interagiu.
# O estado da autenticação também é gerenciado em st.session_state['authentication_status'] pela biblioteca.

if not st.session_state.get("authentication_status"):
    st.info("Por favor, utilize o botão acima para fazer login ou registrar-se.")
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!") # 'username' é populado pela biblioteca

# Botão de Logout
# O logout_button também lida com a lógica de limpar a sessão e o cookie.
st_auth.logout_button(
    #label="Sair do Aplicativo", # Exemplo de customização
    #class_name="minha-classe-css-logout" # Exemplo
)
# Após o logout, a biblioteca deve definir authentication_status como False e a página será recarregada.

# --- Inicialização do Modelo de Linguagem (LLM) do Google (APÓS LOGIN) ---
llm = None
try:
    google_api_key_secret = st.secrets["GOOGLE_API_KEY"]
    if not google_api_key_secret or not google_api_key_secret.strip():
        st.error("🚨 ERRO: GOOGLE_API_KEY configurada nos segredos está vazia.")
        st.stop()
    
    genai.configure(api_key=google_api_key_secret)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                 temperature=0.75,
                                 google_api_key=google_api_key_secret,
                                 convert_system_message_to_human=True)
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos.")
    st.stop()
except Exception as e:
    st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
    st.stop()

if not llm:
    st.error("🚨 Modelo LLM não pôde ser inicializado. O aplicativo não pode continuar.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing (como antes) ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = f"_{section_key}_fbauth_v4" 
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
    key_suffix = f"_{section_key}_fbauth_v4"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=str(generated_content).encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, llm_model, session_state_key, uploaded_files_info=None, campaign_specifics=None, selected_platforms_list=None):
    prompt_parts = [prompt_instruction]
    # ... (lógica de construção do prompt como antes) ...
    if selected_platforms_list: prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
    if details_dict:
        for key, value in details_dict.items():
            if value: prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    if campaign_specifics:
        for key, value in campaign_specifics.items():
            if value: prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    
    final_prompt = "\n\n".join(prompt_parts)
    
    try:
        ai_response = llm_model.invoke([HumanMessage(content=final_prompt)])
        st.session_state[session_state_key] = ai_response.content
    except Exception as e:
        st.error(f"Erro ao invocar LLM para {session_state_key}: {e}")
        st.session_state[session_state_key] = "Ocorreu um erro ao gerar o conteúdo."


# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_instance_passed):
        self.llm = llm_instance_passed
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v4', ConversationBufferMemory(memory_key="hist_plano_fb_v4", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v4', ConversationBufferMemory(memory_key="hist_precos_fb_v4", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v4', ConversationBufferMemory(memory_key="hist_ideias_fb_v4", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key="historico_chat"):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=memory_key),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria, verbose=False)
        
    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        # ... (Restante da função marketing_digital_guiado como antes, adaptando chaves se necessário)
        main_action_key = "main_marketing_action_fbauth_v4"
        opcoes_marketing = ("Selecione uma opção...", "Criar post para redes sociais ou e-mail",
                                     "Criar campanha de marketing completa", "Criar estrutura e conteúdo para landing page",
                                     "Criar estrutura e conteúdo para site com IA", "Encontrar meu cliente ideal (Análise de Público-Alvo)",
                                     "Conhecer a concorrência (Análise Competitiva)")
        st.session_state.setdefault(f"{main_action_key}_index", 0)
        def on_mkt_radio_change(): st.session_state[f"{main_action_key}_index"] = opcoes_marketing.index(st.session_state[main_action_key])
        main_action = st.radio("Marketing Digital:", opcoes_marketing, index=st.session_state[f"{main_action_key}_index"], key=main_action_key, on_change=on_mkt_radio_change)
        # ... (Implementar a lógica para cada ação de marketing como na versão anterior do código) ...


    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", consultor de negócios..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v4")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_text = f"Usuário pergunta sobre preços: '{input_usuario}'."
        if descricao_imagem_contexto: prompt_text = f"Contexto da imagem '{descricao_imagem_contexto}'.\n{prompt_text}"
        system_message = f"Você é o \"Assistente PME Pro\", especialista em precificação... {prompt_text}"
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v4")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_text = f"Usuário busca ideias: '{input_usuario}'."
        if contexto_arquivos: prompt_text = f"Contexto dos arquivos: {contexto_arquivos}\n{prompt_text}"
        system_message = f"Você é o \"Assistente PME Pro\", consultor criativo... {prompt_text}"
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v4")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

# --- Funções Globais de Chat e Interface ---
def inicializar_ou_resetar_chat_global(area_chave, msg_inicial, memoria):
    key_display = f"chat_display_{area_chave}_fbauth_v4"
    st.session_state[key_display] = [{"role": "assistant", "content": msg_inicial}]
    if memoria:
        memoria.clear()
        if hasattr(memoria.chat_memory, 'add_ai_message'): memoria.chat_memory.add_ai_message(msg_inicial)
        elif hasattr(memoria.chat_memory, 'messages'): memoria.chat_memory.messages = [AIMessage(content=msg_inicial)]

def exibir_chat_e_obter_input_global(area_chave, placeholder, funcao_agente, **kwargs_agente):
    key_display = f"chat_display_{area_chave}_fbauth_v4"
    key_input = f"chat_input_{area_chave}_fbauth_v4"
    st.session_state.setdefault(key_display, [])
    for msg in st.session_state[key_display]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.spinner("Processando..."):
            resposta_assistente = funcao_agente(input_usuario=prompt, **kwargs_agente)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente})
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_fbauth_v4' not in st.session_state and llm: 
    st.session_state.agente_pme_fbauth_v4 = AssistentePMEPro(llm_instance=llm)
agente_app = st.session_state.get('agente_pme_fbauth_v4')

LOGO_PATH = "images/logo-pme-ia.png" 
IMGUR_FALLBACK = "https://i.imgur.com/7IIYxq1.png"
if os.path.exists(LOGO_PATH): st.sidebar.image(LOGO_PATH, width=150)
else: st.sidebar.image(IMGUR_FALLBACK, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado",
    "Elaborar Plano de Negócios": "plano_negocios", 
    "Cálculo de Preços": "calculo_precos",
    "Gerador de Ideias": "gerador_ideias"}
opcoes_labels = list(opcoes_menu.keys())
radio_key = 'main_selection_fbauth_v4'

st.session_state.setdefault(f'{radio_key}_index', 0)
st.session_state.setdefault('area_selecionada_v4', opcoes_labels[st.session_state[f'{radio_key}_index']])

def on_main_radio_change_v4():
    st.session_state.area_selecionada_v4 = st.session_state[radio_key]
    st.session_state[f'{radio_key}_index'] = opcoes_labels.index(st.session_state[radio_key])
    st.session_state.previous_area_selecionada_v4 = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", options=opcoes_labels, key=radio_key, 
                 index=st.session_state[f'{radio_key}_index'], on_change=on_main_radio_change_v4)

secao_key_atual = opcoes_menu.get(st.session_state.area_selecionada_v4)

if agente_app:
    # ... (Lógica de inicialização de chat para seções como antes, usando as novas chaves com _v4) ...
    if secao_key_atual == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao Assistente PME Pro!</h1>...</div>", unsafe_allow_html=True)
        # ... (Restante da página inicial como antes) ...
    elif secao_key_atual == "mkt_guiado": 
        agente_app.marketing_digital_guiado()
    elif secao_key_atual == "plano_negocios":
        st.header("📝 Plano de Negócios com IA")
        exibir_chat_e_obter_input_global(secao_key_atual, "Sua ideia...", agente_app.conversar_plano_de_negocios)
        # ... (botão de limpar como antes, com chave _v4) ...
    elif secao_key_atual == "calc_precos":
        st.header("💲 Cálculo de Preços com IA")
        # ... (lógica de upload e chat como antes, com chaves _v4) ...
        exibir_chat_e_obter_input_global(secao_key_atual, "Descreva produto/custos...", agente_app.calcular_precos_interativo)
    elif secao_key_atual == "gerador_ideias":
        st.header("💡 Gerador de Ideias com IA")
        # ... (lógica de upload e chat como antes, com chaves _v4) ...
        exibir_chat_e_obter_input_global(secao_key_atual, "Descreva seu desafio...", agente_app.gerar_ideias_para_negocios)
else:
    if not firebase_config_ok: st.error("Configuração do Firebase falhou.")
    elif not llm: st.error("Modelo LLM não inicializado.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
