import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Pro", layout="wide", initial_sidebar_state="expanded")

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm = None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Adicione sua GOOGLE_API_KEY aos Segredos do seu app no painel do Streamlit Community Cloud.")
    st.stop()
except FileNotFoundError: # Para desenvolvimento local
    # Tenta carregar de uma variável de ambiente se st.secrets falhar (útil para dev local sem secrets.toml)
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        st.error("🚨 ERRO: Chave API não encontrada nos Segredos do Streamlit nem como variável de ambiente.")
        st.info("Configure GOOGLE_API_KEY nos Segredos do Streamlit Cloud ou defina como variável de ambiente local.")
        st.stop()

if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
    st.error("🚨 ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
    st.stop()
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                     temperature=0.7,
                                     google_api_key=GOOGLE_API_KEY,
                                     convert_system_message_to_human=True)
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique sua chave API, se a 'Generative Language API' está ativa no Google Cloud e suas cotas.")
        st.stop()

# --- Definição do Super Agente (agora com múltiplas personas/funções) ---
class AssistentePMEPro:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model

    def _criar_cadeia_conversacional(self, system_message, memoria_conversa):
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name="historico_chat"), # Nome genérico para a memória
            HumanMessagePromptTemplate.from_template("{input_usuario}")
        ])
        return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_conversa, verbose=False)

    def marketing_digital_guiado(self):
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Vamos criar juntos uma estratégia de marketing digital eficaz usando o poder da IA.")

        if 'start_marketing_form' not in st.session_state:
            st.session_state.start_marketing_form = False

        if not st.session_state.start_marketing_form:
            if st.button("Sim, quero criar minha estratégia de Marketing Digital!", key="btn_start_marketing_form"):
                st.session_state.start_marketing_form = True
                st.rerun()
            return

        with st.form(key='marketing_form_guiado_v4'):
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar?", key="mdg_publico_v4")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?", key="mdg_produto_v4")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing?",
                                             ["", "Aumentar vendas online", "Gerar mais contatos (leads)",
                                              "Fortalecer o reconhecimento da marca", "Aumentar o engajamento"],
                                             key="mdg_objetivo_v4")
            st.markdown("---")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer comunicar?", key="mdg_mensagem_v4")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial?", key="mdg_diferencial_v4")
            st.markdown("---")
            descricao_imagem = st.text_input("6. Ideia para imagem (opcional):", key="mdg_img_v4")
            descricao_video = st.text_input("7. Ideia para vídeo (opcional):", key="mdg_video_v4")
            orcamento_ideia = st.text_input("8. Ideia de orçamento para esta ação (opcional):", key="mdg_orcamento_v4")
            redes_opcoes = { "Não tenho certeza, preciso de sugestão": "Sugestão da IA", "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok", "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp", "E-mail Marketing": "E-mail Marketing", "Google Ads": "Google", "Integrada": "Integrada"}
            rede_social_alvo_label = st.selectbox("9. Canal digital principal ou pedir sugestão?", options=list(redes_opcoes.keys()), key="mdg_canal_v4")
            rede_social_alvo = redes_opcoes[rede_social_alvo_label]
            submit_button = st.form_submit_button(label='Gerar Meu Guia de Marketing com IA 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial]):
                st.warning("Por favor, preencha os campos sobre Público, Produto/Serviço, Objetivo, Mensagem e Diferencial.")
            else:
                system_message_marketing = """
                Você é o "Assistente PME Pro", um consultor especialista em Marketing Digital com IA para pequenas empresas.
                Seu objetivo é guiar o usuário a criar uma estratégia de marketing digital eficaz,
                baseado nos melhores princípios de marketing e nas capacidades da IA.
                """
                prompt_llm_marketing = f"""
                Sou o dono de uma pequena empresa e pedi um guia prático para Marketing Digital com IA.
                Minhas informações:
                - Público-Alvo: {publico_alvo}
                - Produto/Serviço: {produto_servico}
                - Diferencial: {diferencial}
                - Objetivo: {objetivo_campanha}
                - Mensagem Chave: {mensagem_principal}
                - Imagem: {descricao_imagem or "N/A"}
                - Vídeo: {descricao_video or "N/A"}
                - Orçamento: {orcamento_ideia or "N/A"}
                - Canal: {rede_social_alvo}

                Forneça um GUIA ESTRATÉGICO E PRÁTICO, incluindo:
                1. Diagnóstico Rápido e Oportunidade com IA.
                2. Canal(is) Prioritário(s) (com justificativa se pedi sugestão, ou como otimizar o escolhido com IA).
                3. Estratégias de Conteúdo Inteligente: Tipos de conteúdo, como IA pode ajudar (ideias, rascunhos), 2 exemplos de TÍTULOS/POSTS para meu negócio.
                4. Ferramenta de IA Recomendada (Gratuita/Baixo Custo): UMA ferramenta e como ajudaria.
                5. Primeiros 3 Passos Acionáveis para usar IA no marketing.
                6. Métrica Chave de Sucesso Inicial.
                Tom: Mentor experiente, prático, encorajador. Linguagem clara. Foco em plano inicial acionável.
                """
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing... 💡"):
                    # Usando uma cadeia simples para esta funcionalidade baseada em formulário
                    resposta_llm = self.llm.invoke(system_message_marketing + "\n\n" + prompt_llm_marketing).content
                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)

    def conversar_plano_de_negocios(self, input_usuario, memoria_conversa):
        system_message_plano = """
        Você é o "Assistente PME Pro", um consultor de negócios especialista em IA.
        Sua tarefa é ajudar um empreendedor a ESBOÇAR um PLANO DE NEGÓCIOS.
        Inicie a conversa perguntando sobre o ramo de atuação, se ainda não souber.
        Faça perguntas UMA DE CADA VEZ para coletar informações essenciais para as seções de um plano de negócios simples:
        1. Sumário Executivo (Nome da empresa, missão, visão, objetivos principais - colete isso aos poucos).
        2. Descrição da Empresa (O que faz, mercado-alvo, diferencial).
        3. Produtos/Serviços.
        4. Plano de Marketing e Vendas (Como vai alcançar clientes).
        5. Plano Operacional (Como vai funcionar no dia a dia).
        6. Plano Financeiro (Estimativas iniciais, como vai ganhar dinheiro - de forma simples).
        Quando o usuário disser "sim" para criar o plano ou der um comando inicial, sua PRIMEIRA pergunta DEVE SER: "Perfeito! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"
        Se ele responder, continue com perguntas para as outras seções.
        Após coletar algumas informações chave (ex: ramo, nome, produto, público), você pode perguntar: "Com as informações que temos, gostaria que eu tentasse montar um primeiro esboço do seu plano de negócios com as seções principais?"
        Se ele disser sim, gere um esboço com as seções que puder preencher.
        Mantenha a conversa fluindo naturalmente.
        """
        # A memória é gerenciada externamente e passada para a cadeia
        cadeia = self._criar_cadeia_conversacional(system_message_plano, memoria_conversa)
        resposta_ai = cadeia.predict(input_usuario=input_usuario)
        return resposta_ai

# --- Interface Principal Streamlit ---
if llm:
    if 'agente_pme' not in st.session_state:
        st.session_state.agente_pme = AssistentePMEPro(llm_model=llm)
    agente = st.session_state.agente_pme

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100)
    st.sidebar.title("Assistente PME Pro")
    st.sidebar.markdown("IA para seu Negócio Decolar!")
    st.sidebar.markdown("---")

    opcoes_menu = {
        "Página Inicial": "pagina_inicial",
        "Marketing Digital com IA (Guia)": "marketing_guiado",
        "Elaborar Plano de Negócios": "plano_negocios"
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"

    # Inicializar memórias e históricos de chat no session_state
    if "memoria_plano_negocios" not in st.session_state:
        st.session_state.memoria_plano_negocios = ConversationBufferMemory(memory_key="historico_chat", return_messages=True)
    if "chat_display_plano_negocios" not in st.session_state:
        st.session_state.chat_display_plano_negocios = []


    area_selecionada_label = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(opcoes_menu.keys()),
        key='sidebar_selection_v7',
        index=list(opcoes_menu.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in opcoes_menu else 0
    )

    if area_selecionada_label != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_label
        # Não resetar o formulário de marketing ou o chat do plano de negócios ao trocar de aba
        # O estado do formulário é gerenciado por st.form e o chat do plano por sua própria memória/display list
        st.rerun()


    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("Sou seu parceiro de IA pronto para ajudar sua pequena ou média empresa a crescer e se organizar melhor.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Quero um Guia de Marketing Digital com IA!", key="btn_goto_marketing"):
                st.session_state.area_selecionada = "Marketing Digital com IA (Guia)"
                st.session_state.start_marketing_form = False # Garante que o botão de início do form apareça
                st.rerun()
        with col2:
            if st.button("📝 Quero Esboçar meu Plano de Negócios com IA!", key="btn_goto_plano"):
                st.session_state.area_selecionada = "Elaborar Plano de Negócios"
                # Se o chat do plano de negócios estiver vazio, adiciona a primeira mensagem da IA
                if not st.session_state.chat_display_plano_negocios:
                     st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Olá! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?"}]
                     st.session_state.memoria_plano_negocios.chat_memory.add_ai_message("Olá! Para começarmos a esboçar seu plano de negócios, qual é o seu ramo de atuação principal?")
                st.rerun()
        st.balloons()

    elif st.session_state.area_selecionada == "Marketing Digital com IA (Guia)":
        agente.marketing_digital_guiado()

    elif st.session_state.area_selecionada == "Elaborar Plano de Negócios":
        st.header("📝 Elaborando seu Plano de Negócios com IA")
        st.caption("Converse comigo para construirmos seu plano passo a passo.")

        # Exibir histórico da conversa do plano de negócios
        for msg_info in st.session_state.chat_display_plano_negocios:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])

        prompt_usuario_plano = st.chat_input("Sua resposta ou diga 'Crie meu plano de negócios'")

        if prompt_usuario_plano:
            st.session_state.chat_display_plano_negocios.append({"role": "user", "content": prompt_usuario_plano})
            with st.chat_message("user"):
                st.markdown(prompt_usuario_plano)

            with st.spinner("Assistente PME Pro está processando... 🤔"):
                # A memória é passada para a função e atualizada pela LLMChain
                resposta_ai_plano = agente.conversar_plano_de_negocios(prompt_usuario_plano, st.session_state.memoria_plano_negocios)

            st.session_state.chat_display_plano_negocios.append({"role": "assistant", "content": resposta_ai_plano})
            with st.chat_message("assistant"):
                st.markdown(resposta_ai_plano)
        
        if st.sidebar.button("Reiniciar Plano de Negócios", key="btn_reset_plano_v2"):
            st.session_state.chat_display_plano_negocios = [{"role": "assistant", "content": "Ok, vamos recomeçar seu plano de negócios! Qual é o seu ramo de atuação principal?"}]
            st.session_state.memoria_plano_negocios.clear()
            st.session_state.memoria_plano_negocios.chat_memory.add_ai_message("Ok, vamos recomeçar seu plano de negócios! Qual é o seu ramo de atuação principal?")
            st.rerun()

else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a API Key e o modelo LLM.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
