import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Inteligente", layout="wide", initial_sidebar_state="expanded")

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm = None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Por favor, adicione sua GOOGLE_API_KEY aos Segredos do seu aplicativo no painel do Streamlit Community Cloud.")
    st.stop()
except FileNotFoundError:
    st.error("🚨 ERRO: Arquivo de Segredos (secrets.toml) não encontrado para desenvolvimento local.")
    st.info("Crie um arquivo .streamlit/secrets.toml com sua GOOGLE_API_KEY ou configure-a nos Segredos do Streamlit Cloud.")
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
        st.info("Verifique se sua chave API é válida, se a 'Generative Language API' está ativa no seu projeto Google Cloud e se há cotas disponíveis.")
        st.stop()

# --- Definição do Super Agente ---
class SuperAgentePequenasEmpresas:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Tentativa de inicializar o agente sem um modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message_template = """
        Você é o "Assistente PME Pro", um super especialista em trazer soluções inovadoras de IA
        para serem aplicadas em pequenas empresas. Sua comunicação deve ser objetiva, sucinta,
        prática e focada em resolver as dores do usuário, guiando-o passo a passo quando necessário.
        """ # Adicionado "guiando-o passo a passo"

    def _criar_chain(self, area_especifica_prompt=""):
        prompt_template_msgs = [
            SystemMessagePromptTemplate.from_template(self.system_message_template + "\n" + area_especifica_prompt),
            HumanMessagePromptTemplate.from_template("{solicitacao_usuario}")
        ]
        chat_prompt = ChatPromptTemplate.from_messages(prompt_template_msgs)
        return LLMChain(llm=self.llm, prompt=chat_prompt, verbose=False)

    # Mantendo outras funções do agente, mesmo que não estejam no menu agora, para expansão futura
    def responder_pergunta_geral(self, solicitacao_usuario):
        chain = self._criar_chain("Seu foco é fornecer uma visão geral e conselhos práticos.")
        return chain.run({"solicitacao_usuario": solicitacao_usuario})

    # ... (todas as outras funções de gestao_financeira, planejamento_financeiro, etc., podem ser mantidas aqui para uso futuro)
    # ... (para economizar espaço aqui, vou omiti-las, mas elas estariam no seu código original)

    def marketing_digital_guiado(self, solicitacao_inicial_contexto=""):
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("""
        Bem-vindo ao nosso guia para impulsionar sua empresa no mundo digital com Inteligência Artificial!
        Vamos criar juntos uma estratégia de marketing digital eficaz.
        """)

        # Poderíamos adicionar aqui a interação inicial "vamos colocar sua empresa no mundo da IA? Resposta: sim."
        # Por enquanto, vamos direto ao formulário.
        
        with st.form(key='marketing_form_guiado'):
            st.markdown("##### Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar? (Descreva seu público-alvo):", key="mdg_publico")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?:", key="mdg_produto")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing digital?",
                                             ["", "Aumentar vendas online", "Gerar mais contatos (leads)", 
                                              "Fortalecer o reconhecimento da minha marca", "Aumentar o engajamento com clientes"], 
                                             key="mdg_objetivo", help="Pense no resultado mais importante que você busca.")
            
            st.markdown("---")
            st.markdown("##### Sua Mensagem e Diferencial")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer que seus clientes recebam sobre seu negócio?:", key="mdg_mensagem")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial ou diferente da concorrência?:", key="mdg_diferencial")
            
            st.markdown("---")
            st.markdown("##### Ideias para Conteúdo Visual (Opcional)")
            descricao_imagem = st.text_input("6. Se você imagina uma imagem, como ela seria? (ou cole uma URL de referência):", key="mdg_img")
            descricao_video = st.text_input("7. E se fosse um vídeo, qual seria a ideia principal?:", key="mdg_video")
            
            st.markdown("---")
            st.markdown("##### Outras Informações")
            orcamento_ideia = st.text_input("8. Você tem alguma ideia de orçamento para esta ação (Ex: baixo, até R$X, etc.)?:", key="mdg_orcamento")
            
            rede_social_opcoes_dict = {
                "Não tenho certeza, preciso de sugestão": "Sugestão da IA",
                "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok",
                "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp",
                "E-mail Marketing": "E-mail Marketing", "Google Meu Negócio / Anúncios Google": "Google",
                "Outra / Abordagem Integrada": "Integrada"
            }
            rede_social_alvo_label = st.selectbox("9. Você já tem um canal digital principal em mente ou gostaria de uma sugestão?",
                                                options=list(redes_sociais_opcoes_dict.keys()), key="mdg_canal_label")
            rede_social_alvo = redes_sociais_opcoes_dict[rede_social_alvo_label]

            submit_button = st.form_submit_button(label='Me Ajude a Estruturar Minha Estratégia de Marketing Digital com IA! 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial]):
                st.warning("Por favor, preencha pelo menos os campos sobre Público, Produto/Serviço, Objetivo, Mensagem e Diferencial.")
            else:
                prompt_para_llm = f"""
                Sou o dono de uma pequena empresa e preciso de ajuda para 'colocar meu negócio para funcionar com IA', começando pelo Marketing Digital.
                Com base nas informações que forneci, atue como um consultor especialista em Marketing Digital e IA para PMEs.
                Guie-me com um plano de ação prático e sugestões.

                Informações sobre meu negócio e objetivos:
                - Público-Alvo: {publico_alvo}
                - Produto/Serviço Principal: {produto_servico}
                - Principal Diferencial: {diferencial}
                - Objetivo Principal com Marketing Digital: {objetivo_campanha}
                - Mensagem Chave: {mensagem_principal}
                - Ideia para Imagem (se houver): {descricao_imagem if descricao_imagem else "Não especificado"}
                - Ideia para Vídeo (se houver): {descricao_video if descricao_video else "Não especificado"}
                - Orçamento Estimado (se houver): {orcamento_ideia if orcamento_ideia else "Não especificado"}
                - Canal Digital em Mente ou Pedido de Sugestão: {rede_social_alvo}

                Por favor, forneça:
                1.  Uma análise concisa da situação com base nos dados fornecidos.
                2.  Se pedi sugestão de canal, qual(is) canal(is) digital(is) você recomendaria e por quê? Se já escolhi um, como otimizá-lo?
                3.  Principais Estratégias de Conteúdo com IA: Que tipo de conteúdo posso criar (posts, vídeos, artigos) usando IA para atrair meu público neste(s) canal(is)? Dê 2-3 exemplos de ideias de posts/conteúdo.
                4.  Ferramentas de IA Úteis: Sugira 1-2 ferramentas de IA (podem ser gratuitas ou de baixo custo) que podem me ajudar na criação de conteúdo, análise de resultados ou automação de marketing.
                5.  Primeiros Passos Acionáveis: Quais os 2-3 primeiros passos que devo tomar para começar a implementar essa estratégia?
                6.  Métrica Chave: Qual a métrica mais importante para eu acompanhar o sucesso inicial?

                Seja prático, encorajador e use uma linguagem acessível para um dono de pequena empresa.
                O objetivo é me dar um ponto de partida claro para usar IA no meu marketing.
                """
                with st.spinner("O Assistente PME Pro está elaborando seu guia de marketing digital com IA..."):
                    resposta_llm = self._criar_chain("Consultor de Marketing Digital e IA para PMEs.").run({"solicitacao_usuario": prompt_para_llm})
                
                st.markdown("### 💡 Seu Guia de Marketing Digital com IA:")
                st.markdown(resposta_llm)
                
                # Guarda no histórico (opcional, mas bom para referência)
                if "Marketing Digital IA (Guiado)" not in st.session_state.chat_history:
                    st.session_state.chat_history["Marketing Digital IA (Guiado)"] = []
                # Adicionando um resumo do input e a resposta
                input_summary = f"Público: {publico_alvo}, Produto: {produto_servico}, Objetivo: {objetivo_campanha}"
                st.session_state.chat_history["Marketing Digital IA (Guiado)"].append({"role": "user", "content": f"Solicitação de Guia de Marketing (Resumo): {input_summary}"})
                st.session_state.chat_history["Marketing Digital IA (Guiado)"].append({"role": "assistant", "content": resposta_llm})


# --- Interface Principal Streamlit ---
if llm: 
    agente = SuperAgentePequenasEmpresas(llm_model=llm)

    st.sidebar.image("https://i.imgur.com/rGkzKxN.png", width=100) 
    st.sidebar.title("Assistente PME Pro") 
    st.sidebar.markdown("Soluções de IA para sua pequena empresa.")
    st.sidebar.markdown("---")

    # MENU SIMPLIFICADO
    mapa_funcoes_streamlit = {
        "Página Inicial": None,
        "Marketing Digital IA (Guiado)": agente.marketing_digital_guiado,
        # "Pergunta Geral Rápida": agente.responder_pergunta_geral # Poderia adicionar se quiser uma opção de chat genérico
    }
    
    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"
    # O chat_history agora é mais simples, pois temos menos áreas
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {area: [] for area in mapa_funcoes_streamlit}

    area_selecionada_sidebar = st.sidebar.radio(
        "Como posso te ajudar hoje?", # Texto do menu alterado
        options=list(mapa_funcoes_streamlit.keys()),
        key='sidebar_selection_v2', # Nova key para evitar conflito se o estado antigo persistir
        index=list(mapa_funcoes_streamlit.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in mapa_funcoes_streamlit else 0
    )

    if area_selecionada_sidebar != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_sidebar
        if st.session_state.area_selecionada not in st.session_state.chat_history: # Garante que nova área tenha histórico
            st.session_state.chat_history[st.session_state.area_selecionada] = []
        st.rerun() 
    
    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟") 
        st.markdown("""
        Estou aqui para te ajudar a integrar a Inteligência Artificial no dia a dia da sua pequena ou média empresa. 
        Vamos começar transformando seu marketing digital?
        
        ⬅️ Use o menu à esquerda para selecionar a opção "Marketing Digital IA (Guiado)".
        """)
        st.balloons()
    elif st.session_state.area_selecionada == "Marketing Digital IA (Guiado)":
        agente.marketing_digital_guiado() # A função agora gerencia sua própria UI com st.form
        
        # Exibe o histórico, se houver, para esta funcionalidade
        if st.session_state.chat_history[st.session_state.area_selecionada]:
            st.markdown("---")
            st.markdown("#### Histórico de Guias Gerados:")
            for item in reversed(st.session_state.chat_history[st.session_state.area_selecionada]):
                if item["role"] == "assistant": # Mostra as respostas do assistente
                    with st.expander("Ver Guia Anterior", expanded=False):
                        st.markdown(item["content"])
    # Se você adicionar "Pergunta Geral Rápida" de volta ao menu, precisará de um elif para ela aqui.
    # Exemplo:
    # elif st.session_state.area_selecionada == "Pergunta Geral Rápida":
    # st.header("Pergunta Geral Rápida")
    # # (lógica de chat aqui, similar à versão anterior, mas usando st.session_state.chat_history[st.session_state.area_selecionada])
    # # ...

else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a configuração da API Key do Google no painel de Segredos (Secrets) do Streamlit Cloud e se o modelo LLM está acessível.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
