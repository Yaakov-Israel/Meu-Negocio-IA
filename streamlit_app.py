import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import google.generativeai as genai

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Assistente PME Marketing IA", layout="wide", initial_sidebar_state="expanded")

# --- Carregar API Key e Configurar Modelo ---
GOOGLE_API_KEY = None
llm = None

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada nos Segredos (Secrets) do Streamlit.")
    st.info("Adicione sua GOOGLE_API_KEY aos Segredos do seu app no painel do Streamlit Community Cloud.")
    st.stop()
except FileNotFoundError:
    st.error("🚨 ERRO: Arquivo de Segredos (secrets.toml) não encontrado para desenvolvimento local.")
    st.info("Crie um arquivo .streamlit/secrets.toml com sua GOOGLE_API_KEY ou configure nos Segredos do Streamlit Cloud.")
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

# --- Definição do Super Agente (mantendo a classe, mas usaremos só uma função dela agora) ---
class SuperAgentePequenasEmpresas:
    def __init__(self, llm_model):
        if llm_model is None:
            st.error("❌ Erro crítico: Agente sem modelo LLM.")
            st.stop()
        self.llm = llm_model
        self.system_message_template = """
        Você é o "Assistente PME Pro", um super especialista em Marketing Digital com IA para pequenas empresas.
        Seu objetivo é guiar o usuário a criar uma estratégia de marketing digital eficaz,
        fazendo perguntas pertinentes e fornecendo um plano de ação claro e prático.
        """

    def _criar_chain(self, area_especifica_prompt=""): # Renomeado para não conflitar
        prompt_msgs = [ # Renomeado para não conflitar
            SystemMessagePromptTemplate.from_template(self.system_message_template + "\n" + area_especifica_prompt),
            HumanMessagePromptTemplate.from_template("{solicitacao_usuario}")
        ]
        chat_prompt_obj = ChatPromptTemplate.from_messages(prompt_msgs) # Renomeado para não conflitar
        return LLMChain(llm=self.llm, prompt=chat_prompt_obj, verbose=False)

    def marketing_digital_guiado(self): # Removido o parâmetro, pois o formulário coletará tudo
        st.header("🚀 Marketing Digital Inteligente para sua Empresa")
        st.markdown("Bem-vindo! Vamos criar juntos uma estratégia de marketing digital eficaz usando o poder da IA.")

        with st.form(key='marketing_form_guiado_v2'): # Nova key para o form
            st.markdown("##### 📋 Conte-nos sobre seu Negócio e Objetivos")
            publico_alvo = st.text_input("1. Quem você quer alcançar? (Descreva seu público-alvo):", key="mdg_publico_v2")
            produto_servico = st.text_input("2. Qual produto ou serviço principal você oferece?:", key="mdg_produto_v2")
            objetivo_campanha = st.selectbox("3. Qual o principal objetivo com esta ação de marketing digital?",
                                             ["", "Aumentar vendas online", "Gerar mais contatos (leads)",
                                              "Fortalecer o reconhecimento da minha marca", "Aumentar o engajamento com clientes"],
                                             key="mdg_objetivo_v2", help="Pense no resultado mais importante que você busca.")

            st.markdown("---")
            st.markdown("##### ✉️ Sua Mensagem e Diferencial")
            mensagem_principal = st.text_area("4. Qual mensagem chave você quer que seus clientes recebam sobre seu negócio?:", key="mdg_mensagem_v2")
            diferencial = st.text_input("5. O que torna seu produto/serviço especial ou diferente da concorrência?:", key="mdg_diferencial_v2")

            st.markdown("---")
            st.markdown("##### 🖼️ Ideias para Conteúdo Visual (Opcional)")
            descricao_imagem = st.text_input("6. Se você imagina uma imagem, como ela seria? (ou cole uma URL de referência):", key="mdg_img_v2")
            descricao_video = st.text_input("7. E se fosse um vídeo, qual seria a ideia principal?:", key="mdg_video_v2")

            st.markdown("---")
            st.markdown("##### 💰 Outras Informações")
            orcamento_ideia = st.text_input("8. Você tem alguma ideia de orçamento para esta ação (Ex: baixo, até R$X, etc.)?:", key="mdg_orcamento_v2")

            redes_sociais_opcoes_dict = {
                "Não tenho certeza, preciso de sugestão": "Sugestão da IA",
                "Instagram": "Instagram", "Facebook": "Facebook", "TikTok": "TikTok",
                "LinkedIn": "LinkedIn", "WhatsApp Business": "WhatsApp",
                "E-mail Marketing": "E-mail Marketing", "Google Meu Negócio / Anúncios Google": "Google",
                "Outra / Abordagem Integrada": "Integrada"
            }
            rede_social_alvo_label = st.selectbox("9. Você já tem um canal digital principal em mente ou gostaria de uma sugestão?",
                                                options=list(redes_sociais_opcoes_dict.keys()), key="mdg_canal_label_v2")
            rede_social_alvo = redes_sociais_opcoes_dict[rede_social_alvo_label]

            submit_button = st.form_submit_button(label='Gerar Meu Guia de Marketing Digital com IA 🚀')

        if submit_button:
            if not all([publico_alvo, produto_servico, objetivo_campanha, mensagem_principal, diferencial]):
                st.warning("Por favor, preencha pelo menos os campos sobre Público, Produto/Serviço, Objetivo, Mensagem e Diferencial.")
            else:
                prompt_para_llm = f"""
                Sou o dono de uma pequena empresa e preciso de um guia prático para 'colocar meu negócio para funcionar com IA', começando pelo Marketing Digital.
                Com base nas informações que forneci, atue como um consultor especialista em Marketing Digital e IA para PMEs.

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

                Por favor, forneça um guia detalhado e acionável, incluindo:
                1. Uma breve análise da situação e potencial com base nos dados.
                2. Se pedi sugestão de canal, qual(is) canal(is) digital(is) você recomendaria e um forte porquê para cada um? Se já escolhi um, como maximizar seu uso com IA?
                3. Estratégias de Conteúdo Chave utilizando IA: Que tipos de conteúdo (posts, artigos, vídeos curtos, e-mails) posso criar para atrair meu público neste(s) canal(is)? Dê 2-3 exemplos de TÍTULOS ou IDEIAS DE POSTS específicos para meu negócio.
                4. Ferramentas de IA Práticas: Sugira 1-2 ferramentas de IA (idealmente gratuitas ou de baixo custo no início) que podem me ajudar diretamente na criação desses conteúdos ou na otimização de campanhas.
                5. Primeiros Passos Imediatos: Quais os 2-3 primeiros passos concretos que devo tomar para começar a implementar essa estratégia de marketing digital com IA?
                6. Métrica Chave de Sucesso: Qual a métrica mais importante para eu acompanhar o sucesso inicial desta iniciativa?

                O tom deve ser de um consultor parceiro, prático, encorajador e usar uma linguagem clara e acessível para um dono de pequena empresa que está começando a usar IA no marketing.
                """
                with st.spinner("O Assistente PME Pro está preparando seu guia personalizado... 🧠💡"):
                    # Usando _criar_chain com um prompt de área específico para este contexto.
                    chain = self._criar_chain("Consultor especialista em Marketing Digital com IA para PMEs, respondendo a um formulário.")
                    resposta_llm = chain.run({"solicitacao_usuario": prompt_para_llm})

                st.markdown("### 💡 Seu Guia Personalizado de Marketing Digital com IA:")
                st.markdown(resposta_llm)

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
    }

    if 'area_selecionada' not in st.session_state:
        st.session_state.area_selecionada = "Página Inicial"

    area_selecionada_sidebar = st.sidebar.radio(
        "Como posso te ajudar hoje?",
        options=list(mapa_funcoes_streamlit.keys()),
        key='sidebar_selection_v3', # Nova key para garantir atualização do estado
        index=list(mapa_funcoes_streamlit.keys()).index(st.session_state.area_selecionada) if st.session_state.area_selecionada in mapa_funcoes_streamlit else 0
    )

    if area_selecionada_sidebar != st.session_state.area_selecionada:
        st.session_state.area_selecionada = area_selecionada_sidebar
        st.rerun()

    if st.session_state.area_selecionada == "Página Inicial":
        st.title("🌟 Bem-vindo ao Assistente PME Pro! 🌟")
        st.markdown("""
        Estou aqui para te ajudar a integrar a Inteligência Artificial no dia a dia da sua pequena ou média empresa.
        Nosso foco inicial é transformar seu marketing digital!

        ⬅️ Utilize o menu à esquerda para selecionar a opção **"Marketing Digital IA (Guiado)"** e vamos começar.
        """)
        st.balloons()
    elif st.session_state.area_selecionada == "Marketing Digital IA (Guiado)":
        agente.marketing_digital_guiado() # A função gerencia sua própria UI com st.form

else:
    st.error("🚨 O Assistente PME Pro não pôde ser iniciado. Verifique a configuração da API Key do Google no painel de Segredos (Secrets) do Streamlit Cloud e se o modelo LLM está acessível.")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido por Yaakov com seu Assistente PME Pro")
