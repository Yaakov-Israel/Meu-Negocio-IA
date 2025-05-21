import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import google.generativeai as genai # SDK direta do Google também é necessária para configurar a chave

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Gaon da IA - Super Agente PME", layout="wide", initial_sidebar_state="expanded")

# --- Carregar API Key e Configurar Modelo ---
# Esta é a forma correta de carregar a API Key no Streamlit Cloud
# Você precisará configurar um "Secret" no Streamlit Cloud chamado GOOGLE_API_KEY
GOOGLE_API_KEY = None
llm = None # Inicializa llm como None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError: # Chave não encontrada nos secrets do Streamlit
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Por favor, adicione sua GOOGLE_API_KEY aos Segredos do seu aplicativo no painel do Streamlit Community Cloud.")
    st.stop() # Interrompe a execução se a chave não for encontrada
except FileNotFoundError: # Para desenvolvimento local se o .streamlit/secrets.toml não existir
    st.error("🚨 ERRO: Arquivo de Segredos (secrets.toml) não encontrado para desenvolvimento local.")
    st.info("Crie um arquivo .streamlit/secrets.toml com sua GOOGLE_API_KEY ou configure-a nos Segredos do Streamlit Cloud.")
    st.stop()


if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
    st.error("🚨 ERRO: GOOGLE_API_KEY não foi carregada ou está vazia.")
    st.stop()
else:
    try:
        # Configura a chave para a SDK do google-generativeai (usada por LangChain indiretamente)
        genai.configure(api_key=GOOGLE_API_KEY)

        # Inicializa o modelo LLM usando LangChain
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                     temperature=0.7,
                                     google_api_key=GOOGLE_API_KEY, # Passa a chave explicitamente
                                     convert_system_message_to_human=True)
        st.sidebar.success("✅ Modelo LLM (Gemini) inicializado!")
    except Exception as e:
        st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e}")
        st.info("Verifique se sua chave API é válida, se a 'Generative Language API' está ativa no seu projeto Google Cloud e se há cotas disponíveis.")
        st.stop()


# --- Definição do Super Agente (a mesma classe do Colab) ---
class SuperAgentePequenasEmpresas:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Tentativa de inicializar o agente sem um modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message_template = """
        Você é o "Gaon da IA", um super especialista em trazer soluções inovadoras de IA
        para serem aplicadas em pequenas empresas. Sua comunicação deve ser objetiva, sucinta,
        prática e focada em resolver as dores do usuário.
        """

    def _criar_chain(self, area_especifica_prompt=""):
        prompt_template_msgs = [
            SystemMessagePromptTemplate.from_template(self.system_message_template + "\n" + area_especifica_prompt),
            HumanMessagePromptTemplate.from_template("{solicitacao_usuario}")
        ]
        chat_prompt = ChatPromptTemplate.from_messages(prompt_template_msgs)
        return LLMChain(llm=self.llm, prompt=chat_prompt, verbose=False)

    def responder_pergunta_geral(self, solicitacao_usuario):
        chain = self._criar_chain("Seu foco é fornecer uma visão geral e conselhos práticos.")
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def gestao_financeira(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Gestão Financeira. Detalhe aspectos como fluxo de caixa, contas a pagar/receber, e conciliação bancária."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def planejamento_financeiro(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Planejamento Financeiro. Forneça orientações claras, passos práticos e sugestões de ferramentas/templates."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def controle_de_custos(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Controle de Custos. Apresente estratégias para identificar, analisar e reduzir custos fixos e variáveis."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def precificacao(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Precificação de Produtos/Serviços. Explique métodos como markup, margem de contribuição e precificação baseada em valor."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def acesso_a_credito(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Acesso a Crédito. Descreva opções de crédito para pequenas empresas e como se preparar para solicitar."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def obrigacoes_fiscais(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Obrigações Fiscais (Simples Nacional, MEI, etc.). Forneça um panorama geral e a importância de um contador."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def controle_de_estoque(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Controle de Estoque. Discuta métodos como Curva ABC, PEPS, UEPS e a importância do inventário."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def recursos_humanos(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Recursos Humanos para Pequenas Empresas. Aborde temas como recrutamento, seleção, treinamento e legislação básica."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def gerenciamento_de_frequencia(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Gerenciamento de Frequência de Funcionários. Sugira ferramentas ou métodos para controle de ponto e gestão de horas."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def marketing_e_vendas(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Marketing e Vendas. Apresente estratégias fundamentais de marketing offline e online, e técnicas de vendas."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    def conquista_de_clientes(self, solicitacao_usuario):
        prompt_especifico = "Foco Atual: Conquista de Clientes. Detalhe funil de vendas, prospecção, e estratégias para atrair novos clientes."
        chain = self._criar_chain(prompt_especifico)
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    # Função marketing_digital adaptada para Streamlit com st.form
    def marketing_digital(self, solicitacao_inicial_contexto=""): 
        st.subheader("Assistente de Criação de Campanha de Marketing Digital")
        st.write("Para te ajudar a criar uma campanha, preciso de algumas informações.")
        if solicitacao_inicial_contexto and isinstance(solicitacao_inicial_contexto, str) and solicitacao_inicial_contexto.strip():
            st.info(f"Contexto inicial da sua solicitação: '{solicitacao_inicial_contexto}'")

        with st.form(key='marketing_form'):
            publico_alvo = st.text_input("1. Qual é o público-alvo da sua campanha? (Descreva idade, interesses, localização, etc.):", key="md_publico")
            produto_servico = st.text_input("2. Qual produto ou serviço específico você quer promover nesta campanha?:", key="md_produto")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo desta campanha?",
                                             ["", "Aumentar vendas", "Gerar leads", "Reconhecimento da marca", "Engajamento"], key="md_objetivo")
            mensagem_principal = st.text_area("4. Qual é a mensagem central ou o principal apelo que você quer comunicar?:", key="md_mensagem")
            diferencial = st.text_input("5. Qual o principal diferencial do seu produto/serviço que deve ser destacado?:", key="md_diferencial")
            
            st.markdown("---")
            st.markdown("##### Elementos de Mídia (Descreva suas ideias)")
            descricao_imagem = st.text_input("6. Imagem: Descreva a imagem principal (ou cole uma URL de referência):", key="md_img")
            descricao_video = st.text_input("7. Vídeo: Descreva o conceito do vídeo (ou cole uma URL):", key="md_video")
            
            st.markdown("---")
            orcamento_ideia = st.text_input("8. Você tem uma ideia de orçamento para esta campanha (Ex: baixo, R$100-R$500, alto)?:", key="md_orcamento")
            
            st.markdown("---")
            st.markdown("##### Canais")
            redes_sociais_opcoes_dict = {
                "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok",
                "LinkedIn": "LinkedIn", "Twitter / X": "Twitter / X", "WhatsApp": "WhatsApp",
                "E-mail Marketing": "E-mail Marketing", "Google Ads (Pesquisa/Display)": "Google Ads",
                "Outra / Abordagem Integrada": "Integrada"
            }
            rede_social_alvo_label = st.selectbox("9. Para qual canal ou rede social principal esta campanha seria direcionada?",
                                                options=list(redes_sociais_opcoes_dict.keys()), key="md_canal_label")
            rede_social_alvo = redes_sociais_opcoes_dict[rede_social_alvo_label]

            submit_button = st.form_submit_button(label='Gerar Sugestão de Campanha 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial, rede_social_alvo]):
                st.warning("Por favor, preencha todos os campos obrigatórios para a campanha (Público, Produto, Objetivo, Mensagem, Diferencial, Canal).")
            else:
                prompt_para_llm = f"""
                Contexto Inicial do Usuário sobre Marketing Digital: {solicitacao_inicial_contexto if solicitacao_inicial_contexto else "N/A"}
                Crie uma sugestão de campanha de marketing digital detalhada e prática com base nas seguintes informações fornecidas pelo usuário:
                - Público-Alvo: {publico_alvo}
                - Produto/Serviço: {produto_servico}
                - Principal Diferencial: {diferencial}
                - Objetivo Principal: {objetivo_campanha}
                - Mensagem Principal: {mensagem_principal}
                - Ideia para Imagem: {descricao_imagem if descricao_imagem else "Não especificado"}
                - Ideia para Vídeo: {descricao_video if descricao_video else "Não especificado"}
                - Orçamento Estimado: {orcamento_ideia if orcamento_ideia else "Não especificado"}
                - Canal Principal Alvo: {rede_social_alvo}

                A sugestão deve incluir:
                1. Nome/Tema Criativo.
                2. Estratégia de Conteúdo para '{rede_social_alvo}' (2-3 exemplos de posts/anúncios, CTAs, formatos).
                3. Sugestões de Segmentação (se anúncios pagos).
                4. Hashtags Estratégicas.
                5. KPIs para medir sucesso.
                6. Cronograma Sugerido Simples.
                7. Dicas Adicionais Práticas para '{rede_social_alvo}'.
                Seja criativo, prático e forneça um plano acionável. Tom encorajador e especializado.
                """
                with st.spinner("O Gaon da IA está elaborando sua campanha de marketing..."):
                    resposta_llm = self._criar_chain("Assistente de Criação de Campanhas de Marketing Digital.").run({"solicitacao_usuario": prompt_para_llm})
                
                if "Marketing Digital (Criar Campanha)" not in st.session_state.chat_history:
                    st.session_state.chat_history["Marketing Digital (Criar Campanha)"] = []
                st.session_state.chat_history["Marketing Digital (Criar Campanha)"].append({"role": "assistant", "type": "campaign_suggestion", "content": resposta_llm})
                
                st.markdown("### 💡 Sugestão de Campanha de Marketing Digital:")
                st.markdown(resposta_llm)
        # A função não precisa retornar nada aqui, pois manipula a UI diretamente


# --- Interface Principal Streamlit ---
if llm: # Só continua se o LLM foi carregado com sucesso
    agente = SuperAgentePequenasEmpresas(llm_model=llm)

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100) # Você pode trocar por seu logo
    st.sidebar.title("Gaon da IA para PMEs")
    st.sidebar.markdown("Seu assistente inteligente para negócios!")
    st.sidebar.markdown("---")

    mapa_funcoes_streamlit = {
        "Página Inicial": None, # Opção inicial
        "Gestão Financeira": agente.gestao_financeira,
        "Planejamento Financeiro": agente.planejamento_financeiro,
        "Controle de Custos": agente.controle_de_custos,
        "Precificação": agente.precificacao,
        "Acesso a Crédito": agente.acesso_a_credito,
        "Obrigações Fiscais": agente.obrigacoes_fiscais,
        "Controle de Estoque": agente.controle_de_estoque,
        "Recursos Humanos": agente.recursos_humanos,
        "Gerenciamento de Frequência": agente.gerenciamento_de_frequencia,
        "Marketing e Vendas (Geral)": agente.marketing_e_vendas,
        "Conquista de Clientes": agente.conquista_de_clientes,
        "Marketing Digital (Criar Campanha)": agente.marketing_digital,
        "Pergunta Geral": agente.responder_pergunta_geral
    }
    
    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    if 'chat_history' not in st.session_state:
        # Inicializa como um dicionário vazio para armazenar históricos por área
        st.session_state.chat_history = {} 

    # Inicializa o histórico de chat para a área selecionada, se ainda não existir
    if st.session_state.area_selecionada not in st.session_state.chat_history:
        st.session_state.chat_history[st.session_state.area_selecionada] = []
        
    area_selecionada_sidebar = st.sidebar.radio(
        "Escolha uma área de atuação:",
        options=list(mapa_funcoes_streamlit.keys()),
        key='sidebar_selection',
        index=list(mapa_funcoes_streamlit.keys()).index(st.session_state.area_selecionada)
    )

    if area_selecionada_sidebar != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_sidebar
        # Se a área mudou, garante que o histórico para a nova área exista
        if st.session_state.area_selecionada not in st.session_state.chat_history:
            st.session_state.chat_history[st.session_state.area_selecionada] = []
        st.rerun() # Força o rerender da página para atualizar a UI e o contexto do chat
    
    # --- Área de Conteúdo Principal ---
    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Gaon da IA para PMEs! 🌟")
        st.markdown("Sou seu assistente inteligente, pronto para ajudar a otimizar a gestão do seu negócio.")
        st.markdown("Utilize o menu à esquerda para selecionar uma área e começar.")
        st.balloons()
    elif st.session_state.area_selecionada == "Marketing Digital (Criar Campanha)":
        # A função marketing_digital agora usa st.form e gerencia sua própria UI.
        # Um contexto inicial pode vir de uma interação anterior no chat, se desejado.
        contexto_marketing = "" 
        # Se houver mensagens no histórico de "Marketing Digital" e a última for do usuário, podemos usá-la.
        # Mas para um formulário, geralmente não passamos o último input do chat diretamente.
        # A função em si coleta os dados.
        agente.marketing_digital(solicitacao_inicial_contexto=contexto_marketing)
        
        # Exibir histórico de sugestões de campanha, se houver (apenas as respostas do assistente)
        if st.session_state.chat_history[st.session_state.area_selecionada]:
            st.markdown("---")
            st.markdown("#### Histórico de Sugestões de Campanha:")
            # Mostra apenas as respostas do assistente que são sugestões de campanha
            for item in reversed(st.session_state.chat_history[st.session_state.area_selecionada]):
                if item["role"] == "assistant" and item.get("type") == "campaign_suggestion":
                    with st.expander("Ver Sugestão Anterior", expanded=False):
                        st.markdown(item["content"])
    else:
        st.header(f"Assistência em: {st.session_state.area_selecionada}")

        # Exibe o histórico de chat da área selecionada
        for mensagem in st.session_state.chat_history[st.session_state.area_selecionada]:
            with st.chat_message(mensagem["role"]):
                st.markdown(mensagem["content"])

        prompt_usuario = st.chat_input(f"Qual sua dúvida ou solicitação sobre {st.session_state.area_selecionada}?")

        if prompt_usuario:
            st.session_state.chat_history[st.session_state.area_selecionada].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"):
                st.markdown(prompt_usuario)

            with st.spinner("O Gaon da IA está pensando... 🧠"):
                try:
                    funcao_agente = mapa_funcoes_streamlit[st.session_state.area_selecionada]
                    if funcao_agente: 
                        resposta_agente = funcao_agente(prompt_usuario)
                        st.session_state.chat_history[st.session_state.area_selecionada].append({"role": "assistant", "content": resposta_agente})
                        with st.chat_message("assistant"):
                            st.markdown(resposta_agente)
                    # Não precisa de 'else' aqui, pois a Página Inicial é tratada separadamente e Marketing Digital também.
                except Exception as e:
                    erro_msg = f"Desculpe, ocorreu um erro ao processar sua solicitação: {e}"
                    st.error(erro_msg)
                    st.session_state.chat_history[st.session_state.area_selecionada].append({"role": "assistant", "content": erro_msg})
else:
    st.error("🚨 O Gaon da IA não pôde ser iniciado. Verifique a configuração da API Key do Google no painel de Segredos (Secrets) do Streamlit Cloud e se o modelo LLM está acessível.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com o Gaon da IA")
