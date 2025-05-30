import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image
import streamlit_firebase_auth as st_auth # Biblioteca correta para autenticação Firebase

# --- Configuração da Página e Inicialização de Variáveis Essenciais ---
st.set_page_config(
    page_title="Assistente PME Pro",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀"
)

auth_object = None # Renomeado para evitar confusão com o módulo st_auth
firebase_config_ok = False
llm = None # Renomeado para clareza

# --- Bloco de Autenticação Firebase ---
try:
    firebase_creds = st.secrets["firebase_config"]
    cookie_creds = st.secrets["cookie_firebase"]
    
    # Usando FirebaseAuth conforme descoberto
    auth_object = st_auth.FirebaseAuth( 
        config=firebase_creds.to_dict() if hasattr(firebase_creds, 'to_dict') else dict(firebase_creds), 
        cookie_name=cookie_creds["name"],
        key=cookie_creds["key"],
        cookie_expiry_days=int(cookie_creds["expiry_days"])
    )
    firebase_config_ok = True

except KeyError as e:
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO: Chave '{e}' não encontrada nos Segredos. Verifique [firebase_config] e [cookie_firebase].")
    st.stop()
except Exception as e:
    st.error(f"🚨 ERRO FATAL ao inicializar o autenticador Firebase: {type(e).__name__} - {e}")
    st.exception(e)
    st.stop()

if not auth_object:
    st.error("Falha crítica: Objeto de autenticação Firebase não pôde ser inicializado.")
    st.stop()

# --- Processo de Login ---
auth_object.login() 

if not st.session_state.get("authentication_status"):
    st.info("Por favor, faça login ou registre-se para continuar.") # Mensagem mais amigável
    st.stop() 

# --- Conteúdo do Aplicativo (Visível Apenas Após Login Bem-Sucedido) ---
st.sidebar.write(f"Bem-vindo, {st.session_state.get('username', 'Usuário')}!")
if auth_object.logout("Logout", "sidebar"):
    keys_to_clear = [k for k in st.session_state if k not in ['authentication_status', 'username', 'user_info', 'logout']]
    for key_to_del in keys_to_clear:
        if key_to_del.startswith(("chat_display_", "memoria_", "generated_", "_fbauth_")):
            del st.session_state[key_to_del]
    st.experimental_rerun()

# --- Inicialização do Modelo de Linguagem (LLM) do Google ---
try:
    google_api_key_secret = st.secrets["GOOGLE_API_KEY"]
    if not google_api_key_secret or not google_api_key_secret.strip():
        st.error("🚨 ERRO: GOOGLE_API_KEY configurada nos segredos está vazia.")
        st.stop()
    
    genai.configure(api_key=google_api_key_secret)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", # gemini-1.5-pro é mais poderoso
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
    st.error("🚨 Modelo LLM não pôde ser inicializado.")
    st.stop()

# --- Funções Auxiliares para a Seção de Marketing ---
def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
    st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
    details = {}
    key_suffix = f"_{section_key}_fbauth_v2" 
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
    key_suffix = f"_{section_key}_fbauth_v2"
    st.download_button(label="📥 Baixar Conteúdo Gerado", 
                       data=generated_content.encode('utf-8'), 
                       file_name=f"{file_name_prefix}{key_suffix}.txt", 
                       mime="text/plain", 
                       key=f"download{key_suffix}")

def _marketing_generic_handler(prompt_instruction, details_dict, llm_model, session_state_key, uploaded_files_info=None, campaign_specifics=None, selected_platforms_list=None):
    prompt_parts = [prompt_instruction]
    if selected_platforms_list:
        prompt_parts.append(f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.")
    if details_dict:
        for key, value in details_dict.items():
            if value: # Adiciona apenas se tiver valor
                prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    if campaign_specifics:
        for key, value in campaign_specifics.items():
            if value:
                prompt_parts.append(f"**{key.replace('_', ' ').capitalize()}:** {value}")
    if uploaded_files_info:
        prompt_parts.append(f"**Informações de Arquivos de Suporte:** {', '.join([f['name'] for f in uploaded_files_info])}.")
    
    final_prompt = "\n\n".join(prompt_parts)
    
    try:
        # Langchain ChatGoogleGenerativeAI espera uma lista de mensagens ou um prompt simples
        # Para prompts complexos, é melhor construir uma HumanMessage.
        ai_response = llm_model.invoke([HumanMessage(content=final_prompt)])
        st.session_state[session_state_key] = ai_response.content
    except Exception as e:
        st.error(f"Erro ao invocar LLM para {session_state_key}: {e}")
        st.session_state[session_state_key] = "Ocorreu um erro ao gerar o conteúdo."

# --- Classe Principal do Aplicativo e suas Funcionalidades ---
class AssistentePMEPro:
    def __init__(self, llm_instance):
        self.llm = llm_instance
        self.memoria_plano_negocios = st.session_state.setdefault('memoria_plano_negocios_fbauth_v2', ConversationBufferMemory(memory_key="hist_plano_fb_v2", return_messages=True))
        self.memoria_calculo_precos = st.session_state.setdefault('memoria_calculo_precos_fbauth_v2', ConversationBufferMemory(memory_key="hist_precos_fb_v2", return_messages=True))
        self.memoria_gerador_ideias = st.session_state.setdefault('memoria_gerador_ideias_fbauth_v2', ConversationBufferMemory(memory_key="hist_ideias_fb_v2", return_messages=True))

    def _criar_cadeia_conversacional(self, system_message, memoria, memory_key="historico_chat"):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=memory_key),
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt, memory=memoria, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Interativo com IA")
        st.caption("Seu copiloto para criar estratégias, posts, campanhas e mais!")
        st.markdown("---")
        
        main_action_key = "main_marketing_action_fbauth_v2"
        opcoes_marketing = ("Selecione...", "Criar post", "Criar campanha", "Estrutura landing page", 
                              "Estrutura site", "Análise de Público-Alvo", "Análise Competitiva")
        
        st.session_state.setdefault(f"{main_action_key}_index", 0)

        def on_marketing_radio_change():
            st.session_state[f"{main_action_key}_index"] = opcoes_marketing.index(st.session_state[main_action_key])

        main_action = st.radio("O que você quer fazer em marketing digital?", opcoes_marketing,
                               index=st.session_state[f"{main_action_key}_index"], 
                               key=main_action_key, on_change=on_marketing_radio_change)
        st.markdown("---")

        if main_action == "Criar post":
            with st.form("post_form_fbauth_v2", clear_on_submit=True):
                details = _marketing_get_objective_details("post", "post")
                # Adicionar seleção de plataformas aqui se necessário
                submitted = st.form_submit_button("Gerar Post")
            if submitted:
                with st.spinner("🤖 Criando post..."):
                    _marketing_generic_handler(
                        "Crie um texto para post com base nos seguintes detalhes:", 
                        details, self.llm, "generated_post_content_new_v2"
                    )
            if "generated_post_content_new_v2" in st.session_state:
                _marketing_display_output_options(st.session_state.generated_post_content_new_v2, "post_out_v2", "post_ia")
        
        # Adicionar outras seções de marketing (campanha, landing page, etc.) de forma similar...

    def conversar_plano_de_negocios(self, input_usuario):
        system_message = "Você é o \"Assistente PME Pro\", consultor de negócios experiente..."
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_plano_negocios, memory_key_placeholder="hist_plano_fb_v2")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def calcular_precos_interativo(self, input_usuario, descricao_imagem_contexto=None):
        prompt_base = f"O usuário busca ajuda para precificar: '{input_usuario}'."
        if descricao_imagem_contexto:
            prompt_base = f"Contexto visual da imagem '{descricao_imagem_contexto}'.\n{prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", especialista em precificação... {prompt_base}"
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_calculo_precos, memory_key_placeholder="hist_precos_fb_v2")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

    def gerar_ideias_para_negocios(self, input_usuario, contexto_arquivos=None):
        prompt_base = f"O usuário busca ideias de negócios e diz: '{input_usuario}'."
        if contexto_arquivos:
            prompt_base = f"Considerando os arquivos/contextos: {contexto_arquivos}\n{prompt_base}"
        system_message = f"Você é o \"Assistente PME Pro\", consultor de negócios criativo... {prompt_base}"
        cadeia = self._criar_cadeia_conversacional(system_message, self.memoria_gerador_ideias, memory_key_placeholder="hist_ideias_fb_v2")
        resposta = cadeia.invoke({"input_usuario": input_usuario})
        return resposta.get('text', str(resposta))

def inicializar_ou_resetar_chat_global(area_chave, msg_inicial, memoria):
    key_display = f"chat_display_{area_chave}_fbauth_v2"
    st.session_state[key_display] = [{"role": "assistant", "content": msg_inicial}]
    if memoria:
        memoria.clear()
        if hasattr(memoria.chat_memory, 'add_ai_message'): memoria.chat_memory.add_ai_message(msg_inicial)
        elif hasattr(memoria.chat_memory, 'messages'): memoria.chat_memory.messages = [AIMessage(content=msg_inicial)]
    # Limpar contextos de upload específicos da área
    if area_chave == "calculo_precos": st.session_state.pop('last_uploaded_image_info_pricing_fbauth_v2', None)
    elif area_chave == "gerador_ideias": st.session_state.pop('uploaded_file_info_ideias_for_prompt_fbauth_v2', None)


def exibir_chat_e_obter_input_global(area_chave, placeholder, funcao_agente, **kwargs_agente):
    key_display = f"chat_display_{area_chave}_fbauth_v2"
    key_input = f"chat_input_{area_chave}_fbauth_v2"
    
    for msg in st.session_state.get(key_display, []):
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt := st.chat_input(placeholder, key=key_input):
        st.session_state[key_display].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("Assistente PME Pro processando... 🤔"):
            resposta_assistente = funcao_agente(input_usuario=prompt, **kwargs_agente)
        st.session_state[key_display].append({"role": "assistant", "content": resposta_assistente})
        
        # Limpar contextos de upload após uso
        if area_chave == "calculo_precos": st.session_state.pop('last_uploaded_image_info_pricing_fbauth_v2', None)
        elif area_chave == "gerador_ideias": st.session_state.pop('uploaded_file_info_ideias_for_prompt_fbauth_v2', None)
        st.rerun()

# --- Lógica Principal da Interface Streamlit ---
if 'agente_pme_v2' not in st.session_state and llm: # Garante que o LLM está pronto
    st.session_state.agente_pme_v2 = AssistentePMEPro(llm_instance=llm)
agente_app = st.session_state.get('agente_pme_v2')

LOGO_PATH = "images/logo-pme-ia.png" 
IMGUR_FALLBACK = "https://i.imgur.com/7IIYxq1.png"

if os.path.exists(LOGO_PATH): st.sidebar.image(LOGO_PATH, width=150)
else: st.sidebar.image(IMGUR_FALLBACK, width=150, caption="Logo Padrão")

st.sidebar.title("Assistente PME Pro")
st.sidebar.markdown("IA para seu Negócio Decolar!")
st.sidebar.markdown("---")

opcoes_menu = {
    "Página Inicial": "pg_inicial", 
    "Marketing Digital com IA": "mkt_guiado", # Nome mais curto
    "Elaborar Plano de Negócios": "plano_neg", 
    "Cálculo de Preços": "calc_precos",
    "Gerador de Ideias": "gerador_ideias"
}
opcoes_labels = list(opcoes_menu.keys())
radio_key_sidebar = 'main_selection_fbauth_v2'

st.session_state.setdefault(f'{radio_key_sidebar}_index', 0)
st.session_state.setdefault('area_selecionada_app', opcoes_labels[st.session_state[f'{radio_key_sidebar}_index']])


def on_main_radio_change():
    st.session_state.area_selecionada_app = st.session_state[radio_key_sidebar]
    st.session_state[f'{radio_key_sidebar}_index'] = opcoes_labels.index(st.session_state[radio_key_sidebar])
    if st.session_state.area_selecionada_app != "Marketing Digital com IA":
         for k in list(st.session_state.keys()): # Itera sobre cópia para poder deletar
            if k.startswith(("generated_", "_cb_fbauth", "main_marketing_action_fbauth_v2")):
                del st.session_state[k]
    st.session_state.previous_area_selecionada_app = None 
    st.experimental_rerun()

st.sidebar.radio("Como posso te ajudar hoje?", 
                 options=opcoes_labels, 
                 key=radio_key_sidebar, 
                 index=st.session_state[f'{radio_key_sidebar}_index'],
                 on_change=on_main_radio_change)

secao_atual = opcoes_menu.get(st.session_state.area_selecionada_app)

if agente_app: # Procede somente se o agente (e o LLM) estiverem prontos
    if secao_atual not in ["pg_inicial", "mkt_guiado"]:
        if st.session_state.area_selecionada_app != st.session_state.get('previous_area_selecionada_app'):
            msg_inicial = ""
            memoria_corrente = None
            if secao_atual == "plano_negocios": 
                msg_inicial = "Olá! Vamos elaborar seu plano de negócios?"
                memoria_corrente = agente_app.memoria_plano_negocios
            elif secao_atual == "calc_precos": 
                msg_inicial = "Olá! Para calcular preços, descreva seu produto/serviço."
                memoria_corrente = agente_app.memoria_calculo_precos
            elif secao_atual == "gerador_ideias": 
                msg_inicial = "Olá! Buscando novas ideias? Descreva seu desafio."
                memoria_corrente = agente_app.memoria_gerador_ideias
            
            if msg_inicial and memoria_corrente: 
                inicializar_ou_resetar_chat_global(secao_atual, msg_inicial, memoria_corrente)
            st.session_state.previous_area_selecionada_app = st.session_state.area_selecionada_app

    if secao_atual == "pg_inicial":
        st.markdown("<div style='text-align: center;'><h1>🚀 Bem-vindo ao Assistente PME Pro!</h1>...</div>", unsafe_allow_html=True)
        # ... (Restante da página inicial como antes) ...
    elif secao_atual == "mkt_guiado": 
        agente_app.marketing_digital_guiado()
    elif secao_atual == "plano_negocios":
        st.header("📝 Plano de Negócios com IA")
        exibir_chat_e_obter_input_global(secao_atual, "Sua ideia...", agente_app.conversar_plano_de_negocios)
        if st.sidebar.button("🗑️ Limpar Plano", key="reset_plano_fbauth_v2"):
            inicializar_ou_resetar_chat_global(secao_atual, "Recomeçando o plano...", agente_app.memoria_plano_negocios)
            st.rerun()
    elif secao_atual == "calc_precos":
        st.header("💲 Cálculo de Preços com IA")
        # ... (lógica de upload e chat como antes, usando chaves de sessão com _fbauth_v2) ...
        uploaded_img = st.file_uploader("Imagem do produto (opcional):", type=["png", "jpg"], key="preco_uploader_fbauth_v2")
        kwargs_calc = {}
        if uploaded_img and st.session_state.get('processed_image_id_pricing_fbauth_v2') != uploaded_img.id:
            # Processar imagem...
            st.session_state.last_uploaded_image_info_pricing_fbauth_v2 = f"Imagem: {uploaded_img.name}"
            st.session_state.processed_image_id_pricing_fbauth_v2 = uploaded_img.id
        if st.session_state.get('last_uploaded_image_info_pricing_fbauth_v2'):
            kwargs_calc['descricao_imagem_contexto'] = st.session_state.last_uploaded_image_info_pricing_fbauth_v2
        exibir_chat_e_obter_input_global(secao_atual, "Descreva produto/custos...", agente_app.calcular_precos_interativo, **kwargs_calc)
        if st.sidebar.button("🗑️ Limpar Preços", key="reset_precos_fbauth_v2"):
            inicializar_ou_resetar_chat_global(secao_atual, "Novo cálculo de preços...", agente_app.memoria_calculo_precos)
            st.rerun()
            
    elif secao_atual == "gerador_ideias":
        st.header("💡 Gerador de Ideias com IA")
        # ... (lógica de upload e chat como antes, usando chaves de sessão com _fbauth_v2) ...
        uploaded_files = st.file_uploader("Arquivos de contexto (.txt, .png, .jpg):", accept_multiple_files=True, key="ideias_uploader_fbauth_v2")
        kwargs_ideias = {}
        if uploaded_files and st.session_state.get('processed_file_id_ideias_fbauth_v2') != str([f.id for f in uploaded_files]):
             # Processar arquivos...
            st.session_state.uploaded_file_info_ideias_for_prompt_fbauth_v2 = "Contexto dos arquivos..."
            st.session_state.processed_file_id_ideias_fbauth_v2 = str([f.id for f in uploaded_files])
        if st.session_state.get('uploaded_file_info_ideias_for_prompt_fbauth_v2'):
            kwargs_ideias['contexto_arquivos'] = st.session_state.uploaded_file_info_ideias_for_prompt_fbauth_v2
        exibir_chat_e_obter_input_global(secao_atual, "Descreva seu desafio...", agente_app.gerar_ideias_para_negocios, **kwargs_ideias)
        if st.sidebar.button("🗑️ Limpar Ideias", key="reset_ideias_fbauth_v2"):
            inicializar_ou_resetar_chat_global(secao_atual, "Novas ideias? Conte-me.", agente_app.memoria_gerador_ideias)
            st.rerun()
else:
    if not firebase_config_ok: # Se a configuração do Firebase falhou antes do login
        st.error("Configuração do Firebase falhou. App não pode carregar.")
    # Se o agente_app não foi inicializado (provavelmente porque llm falhou),
    # uma mensagem de erro já terá sido mostrada sobre o LLM.
    # O auth_object.login() e st.stop() já trataram o caso de não autenticado.

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov Israel com Gemini 2.5 pro")
