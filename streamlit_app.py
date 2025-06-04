import streamlit as st
import os
import json
import pyrebase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import google.generativeai as genai
from PIL import Image # Para o logo na sidebar
import base64

# --- Função Auxiliar para Imagem em Base64 ---
def convert_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Arquivo de imagem não encontrado: {image_path}")
        return None
    except Exception as e:
        st.error(f"Erro ao converter imagem {image_path}: {e}")
        return None

# --- Configuração da Página Streamlit ---
PAGE_ICON_PATH = "images/carinha-agente-max-ia.png"
try:
    page_icon_img = Image.open(PAGE_ICON_PATH)
except FileNotFoundError:
    page_icon_img = "🤖"
    st.warning(f"Arquivo do ícone da página não encontrado: {PAGE_ICON_PATH}. Usando fallback.")

st.set_page_config(
    page_title="Max IA",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=page_icon_img
)

# --- Inicialização do Firebase ---
firebase_app = None
pb_auth_client = None
error_message_firebase_init = None
firebase_initialized_successfully = False
auth_exception_object = None

try:
    firebase_config_from_secrets = st.secrets.get("firebase_config")
    if not firebase_config_from_secrets:
        error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada ou está vazia nos Segredos."
    else:
        plain_firebase_config_dict = {k: v for k, v in firebase_config_from_secrets.items()}
        required_keys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
        missing_keys = [key for key in required_keys if key not in plain_firebase_config_dict]

        if missing_keys:
            error_message_firebase_init = f"ERRO CRÍTICO: Chaves faltando em [firebase_config] nos segredos: {', '.join(missing_keys)}"
        else:
            if 'firebase_app_instance' not in st.session_state:
                st.session_state.firebase_app_instance = pyrebase.initialize_app(plain_firebase_config_dict)

            firebase_app = st.session_state.firebase_app_instance
            pb_auth_client = firebase_app.auth()
            firebase_initialized_successfully = True
            if 'firebase_init_success_message_shown' not in st.session_state and not st.session_state.get('user_session_pyrebase'):
                st.sidebar.success("✅ Firebase SDK (Pyrebase4) inicializado!")
                st.session_state.firebase_init_success_message_shown = True

except KeyError:
    error_message_firebase_init = "ERRO CRÍTICO: A seção '[firebase_config]' não foi encontrada nos Segredos do Streamlit."
    auth_exception_object = Exception(error_message_firebase_init)
except AttributeError as e_attr_fb:
    error_message_firebase_init = f"ERRO CRÍTICO ao acessar st.secrets['firebase_config']: {e_attr_fb}"
    auth_exception_object = e_attr_fb
except Exception as e_general_fb:
    error_message_firebase_init = f"ERRO GERAL ao inicializar Pyrebase4: {e_general_fb}"
    auth_exception_object = e_general_fb

if error_message_firebase_init:
    st.error(error_message_firebase_init)
    if auth_exception_object and ('st' in locals() or 'st' in globals()):
        st.exception(auth_exception_object)
    st.stop()

if not firebase_initialized_successfully or not pb_auth_client:
    st.error("Falha crítica na inicialização do Firebase. O app não pode continuar.")
    st.stop()

# --- Lógica de Autenticação e Estado da Sessão ---
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
        st.session_state.pop('auth_error_shown', None)
    except Exception as e_session:
        error_message_session_check = "Sessão inválida ou expirada."
        try:
            error_details_str = e_session.args[0] if len(e_session.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\""))
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO_SESSAO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                error_message_session_check = "Sua sessão expirou. Por favor, faça login novamente."
            else:
                error_message_session_check = f"Erro ao verificar sessão ({api_error_message}). Faça login."
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError):
            error_message_session_check = f"Erro ao verificar sessão (parsing). Faça login. Detalhe: {str(e_session)}"

        st.session_state.user_session_pyrebase = None
        user_is_authenticated = False
        if 'auth_error_shown' not in st.session_state:
            st.sidebar.warning(error_message_session_check)
            st.session_state.auth_error_shown = True

        session_rerun_key = 'running_rerun_after_auth_fail_v3'
        if not st.session_state.get(session_rerun_key, False):
            st.session_state[session_rerun_key] = True
            st.rerun()
        else:
            st.session_state.pop(session_rerun_key, None)

session_rerun_key_check = 'running_rerun_after_auth_fail_v3'
if session_rerun_key_check in st.session_state and st.session_state[session_rerun_key_check]:
    st.session_state.pop(session_rerun_key_check, None)


# --- Interface do Usuário Condicional e Lógica Principal do App ---
APP_KEY_SUFFIX = "_v20_final"

if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None)
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")

    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    llm_model_instance = None
    llm_init_exception = None

    if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
        st.error("🚨 ERRO: Chave API 'GOOGLE_API_KEY' não encontrada ou vazia nos Segredos do Streamlit.")
        st.stop()
    else:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            llm_model_instance = ChatGoogleGenerativeAI(model="gemini-1.5-flash",
                                                        temperature=0.75,
                                                        google_api_key=GOOGLE_API_KEY,
                                                        convert_system_message_to_human=True)
            if 'llm_init_success_sidebar_shown_main_app' not in st.session_state:
                st.sidebar.success("✅ Max IA (Gemini) inicializado!")
                st.session_state.llm_init_success_sidebar_shown_main_app = True
        except Exception as e_llm:
            llm_init_exception = e_llm
            st.error(f"😥 ERRO AO INICIALIZAR O MODELO LLM DO GOOGLE: {e_llm}")

    def _marketing_get_objective_details(section_key, type_of_creation="post/campanha"):
        st.subheader(f"Detalhes para Orientar a Criação do(a) {type_of_creation.capitalize()}:")
        details = {}
        details["objective"] = st.text_area(f"Qual o principal objetivo com est(e/a) {type_of_creation}?", key=f"{section_key}_obj{APP_KEY_SUFFIX}")
        details["target_audience"] = st.text_input("Quem você quer alcançar?", key=f"{section_key}_audience{APP_KEY_SUFFIX}")
        details["product_service"] = st.text_area("Qual produto ou serviço principal você está promovendo?", key=f"{section_key}_product{APP_KEY_SUFFIX}")
        details["key_message"] = st.text_area("Qual mensagem chave você quer comunicar?", key=f"{section_key}_message{APP_KEY_SUFFIX}")
        details["usp"] = st.text_area("O que torna seu produto/serviço especial (USP)?", key=f"{section_key}_usp{APP_KEY_SUFFIX}")
        details["style_tone"] = st.selectbox("Qual o tom/estilo da comunicação?", ("Profissional e direto", "Amigável e informal", "Criativo e inspirador", "Urgente e promocional", "Engraçado e leve", "Educacional e informativo"), key=f"{section_key}_tone{APP_KEY_SUFFIX}")
        details["extra_info"] = st.text_area("Alguma informação adicional/CTA?", key=f"{section_key}_extra{APP_KEY_SUFFIX}")
        return details

    def _marketing_display_output_options(generated_content, section_key, file_name_prefix="conteudo_gerado"):
        st.subheader("🎉 Resultado da IA e Próximos Passos:")
        st.markdown(generated_content)
        
        # Botão de download (o principal suspeito do erro anterior)
        try:
            st.download_button(
                label="📥 Baixar Conteúdo Gerado",
                data=generated_content.encode('utf-8'),
                file_name=f"{file_name_prefix}_{section_key}{APP_KEY_SUFFIX}.txt",
                mime="text/plain",
                key=f"download_{section_key}{APP_KEY_SUFFIX}"
            )
        except Exception as e_download: 
            st.error(f"Erro ao tentar renderizar o botão de download: {e_download}")
            print(f"ERRO NO DOWNLOAD BUTTON: {e_download}")

        # Mantendo outros botões comentados para isolar o problema do download_button, se persistir
        # cols_actions = st.columns(2)
        # with cols_actions[0]:
        #     if st.button("🔗 Copiar para Compartilhar (Simulado)", key=f"{section_key}_share_btn{APP_KEY_SUFFIX}"):
        #         st.success("Conteúdo pronto para ser copiado e compartilhado nas suas redes ou e-mail!")
        #         st.caption("Lembre-se de adaptar para cada plataforma, se necessário.")
        # with cols_actions[1]:
        #     if st.button("🗓️ Simular Agendamento", key=f"{section_key}_schedule_btn{APP_KEY_SUFFIX}"):
        #         st.info("Agendamento simulado. Para agendamento real, use ferramentas como Meta Business Suite, Hootsuite, mLabs, ou a função de programação do seu serviço de e-mail marketing.")

    def _marketing_handle_criar_post(uploaded_files_info, details_dict, selected_platforms_list, llm):
        st.error("DEBUG: EXECUTANDO A VERSÃO CORRIGIDA DE _marketing_handle_criar_post v2") # Linha de Debug

        if not selected_platforms_list:
            st.warning("Por favor, selecione pelo menos uma plataforma.")
            st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
            return
        if not details_dict.get("objective") or not details_dict["objective"].strip():
            st.warning("Por favor, descreva o objetivo do post.")
            st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🤖 Max IA está criando seu post... Aguarde!"):
            prompt_parts = [
                "**Instrução para IA:** Você é um especialista em copywriting e marketing digital para pequenas e médias empresas no Brasil. Sua tarefa é criar um post otimizado e engajador para as seguintes plataformas e objetivos.",
                "Considere as informações de suporte se fornecidas. Gere apenas o texto do post, com sugestões de emojis e hashtags relevantes.",
                "Seja conciso e direto ao ponto, adaptando a linguagem para cada plataforma se necessário, mas mantendo a mensagem central.",
                "Se multiplas plataformas forem selecionadas, gere uma versão base e sugira pequenas adaptações para cada uma se fizer sentido, ou indique que o post pode ser usado de forma similar.",
                f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                f"**Produto/Serviço Principal:** {details_dict.get('product_service', '')}",
                f"**Público-Alvo:** {details_dict.get('target_audience', '')}",
                f"**Objetivo do Post:** {details_dict.get('objective', '')}",
                f"**Mensagem Chave:** {details_dict.get('key_message', '')}",
                f"**Proposta Única de Valor (USP):** {details_dict.get('usp', '')}",
                f"**Tom/Estilo:** {details_dict.get('style_tone', '')}",
                f"**Informações Adicionais/CTA:** {details_dict.get('extra_info', '')}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a IA está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_post_content_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para o post: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para CRIAR POST: {ve}")
                print(f"Prompt completo que causou o ValueError (CRIAR POST): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para o post: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_post_content_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR POST: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (CRIAR POST): {final_prompt}")
                return

    def _marketing_handle_criar_campanha(uploaded_files_info, details_dict, campaign_specifics, selected_platforms_list, llm):
        if not selected_platforms_list:
            st.warning("Por favor, selecione pelo menos uma plataforma para a campanha.")
            st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
            return
        if not details_dict.get("objective") or not details_dict["objective"].strip():
            st.warning("Por favor, descreva o objetivo principal da campanha.")
            st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
            return
        if not campaign_specifics.get("name") or not campaign_specifics["name"].strip():
            st.warning("Por favor, dê um nome para a campanha.")
            st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🧠 Max IA está elaborando seu plano de campanha..."):
            prompt_parts = [
                "**Instrução para IA:** Você é um estrategista de marketing digital experiente, focado em PMEs no Brasil. Desenvolva um plano de campanha de marketing conciso e acionável com base nas informações fornecidas. O plano deve incluir: 1. Conceito da Campanha (Tema Central). 2. Sugestões de Conteúdo Chave para cada plataforma selecionada. 3. Um cronograma geral sugerido (Ex: Semana 1 - Teaser, Semana 2 - Lançamento, etc.). 4. Métricas chave para acompanhar o sucesso. Considere as informações de suporte, se fornecidas.",
                f"**Nome da Campanha:** {campaign_specifics.get('name', '')}",
                f"**Plataformas Alvo:** {', '.join(selected_platforms_list)}.",
                f"**Produto/Serviço Principal da Campanha:** {details_dict.get('product_service', '')}",
                f"**Público-Alvo da Campanha:** {details_dict.get('target_audience', '')}",
                f"**Objetivo Principal da Campanha:** {details_dict.get('objective', '')}",
                f"**Mensagem Chave da Campanha:** {details_dict.get('key_message', '')}",
                f"**USP do Produto/Serviço na Campanha:** {details_dict.get('usp', '')}",
                f"**Tom/Estilo da Campanha:** {details_dict.get('style_tone', '')}",
                f"**Duração Estimada:** {campaign_specifics.get('duration', 'Não especificada')}",
                f"**Orçamento Aproximado (se informado):** {campaign_specifics.get('budget', 'Não informado')}",
                f"**KPIs mais importantes:** {campaign_specifics.get('kpis', 'Não especificados')}",
                f"**Informações Adicionais/CTA da Campanha:** {details_dict.get('extra_info', '')}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a campanha está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_campaign_content_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a campanha: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para CRIAR CAMPANHA: {ve}")
                print(f"Prompt completo que causou o ValueError (CRIAR CAMPANHA): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a campanha: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_campaign_content_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR CAMPANHA: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (CRIAR CAMPANHA): {final_prompt}")
                return

    def _marketing_handle_criar_landing_page(uploaded_files_info, lp_details, llm):
        if not lp_details.get("purpose") or not lp_details["purpose"].strip():
            st.warning("Por favor, preencha o principal objetivo da landing page.")
            st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
            return
        if not lp_details.get("main_offer") or not lp_details["main_offer"].strip():
            st.warning("Por favor, descreva a oferta principal da landing page.")
            st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
            return
        if not lp_details.get("cta") or not lp_details["cta"].strip():
            st.warning("Por favor, defina a Chamada para Ação (CTA) principal da landing page.")
            st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🎨 Max IA está desenhando a estrutura da sua landing page..."):
            prompt_parts = [
                "**Instrução para IA:** Você é um especialista em UX/UI e copywriting para landing pages de alta conversão, com foco em PMEs no Brasil. Baseado nos detalhes fornecidos, crie uma estrutura detalhada e sugestões de texto (copy) para cada seção de uma landing page. Inclua seções como: Cabeçalho (Headline, Sub-headline), Problema/Dor, Apresentação da Solução/Produto, Benefícios Chave, Prova Social (Depoimentos), Oferta Irresistível, Chamada para Ação (CTA) clara e forte, Garantia (se aplicável), FAQ. Considere as informações de suporte, se fornecidas.",
                f"**Objetivo da Landing Page:** {lp_details.get('purpose', '')}",
                f"**Público-Alvo (Persona):** {lp_details.get('target_audience', 'Não especificado')}",
                f"**Oferta Principal:** {lp_details.get('main_offer', '')}",
                f"**Principais Benefícios/Transformações da Oferta:** {lp_details.get('key_benefits', 'Não especificados')}",
                f"**Chamada para Ação (CTA) Principal:** {lp_details.get('cta', '')}",
                f"**Preferências Visuais/Referências (se houver):** {lp_details.get('visual_prefs', 'Nenhuma')}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a landing page está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_lp_content_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a landing page: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para CRIAR LANDING PAGE: {ve}")
                print(f"Prompt completo que causou o ValueError (CRIAR LANDING PAGE): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a landing page: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_lp_content_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR LANDING PAGE: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (CRIAR LANDING PAGE): {final_prompt}")
                return

    def _marketing_handle_criar_site(uploaded_files_info, site_details, llm):
        if not site_details.get("business_type") or not site_details["business_type"].strip():
            st.warning("Por favor, informe o tipo do seu negócio/empresa para o site.")
            st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
            return
        if not site_details.get("main_purpose") or not site_details["main_purpose"].strip():
            st.warning("Por favor, descreva o principal objetivo do seu site.")
            st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🛠️ Max IA está arquitetando a estrutura do seu site..."):
            prompt_parts = [
                "**Instrução para IA:** Você é um arquiteto de informação e web designer experiente, focado em criar sites eficazes para PMEs no Brasil. Desenvolva uma proposta de estrutura de site (mapa do site com principais páginas e seções dentro de cada página) e sugestões de conteúdo chave para cada seção. Considere as informações de suporte, se fornecidas.",
                f"**Tipo de Negócio/Empresa:** {site_details.get('business_type', '')}",
                f"**Principal Objetivo do Site:** {site_details.get('main_purpose', '')}",
                f"**Público-Alvo Principal:** {site_details.get('target_audience', 'Não especificado')}",
                f"**Páginas Essenciais Desejadas:** {site_details.get('essential_pages', 'Não especificadas')}",
                f"**Principais Produtos/Serviços/Diferenciais a serem destacados:** {site_details.get('key_features', 'Não especificados')}",
                f"**Personalidade da Marca:** {site_details.get('brand_personality', 'Não especificada')}",
                f"**Preferências Visuais/Referências (se houver):** {site_details.get('visual_references', 'Nenhuma')}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a estrutura do site está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_site_content_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para a estrutura do site: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para CRIAR SITE: {ve}")
                print(f"Prompt completo que causou o ValueError (CRIAR SITE): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para a estrutura do site: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_site_content_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para CRIAR SITE: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (CRIAR SITE): {final_prompt}")
                return

    def _marketing_handle_encontre_cliente(uploaded_files_info, client_details, llm):
        if not client_details.get("product_campaign") or not client_details["product_campaign"].strip():
            st.warning("Por favor, descreva o produto/serviço ou campanha para o qual deseja encontrar o cliente ideal.")
            st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🕵️ Max IA está investigando seu público-alvo..."):
            prompt_parts = [
                "**Instrução para IA:** Você é um 'Agente Detetive de Clientes', especialista em marketing e pesquisa de mercado para PMEs no Brasil. Sua tarefa é realizar uma análise completa do público-alvo com base nas informações fornecidas e gerar um relatório detalhado com os seguintes itens: 1. Persona Detalhada (Nome fictício, Idade, Profissão, Dores, Necessidades, Sonhos, Onde busca informação). 2. Sugestões de Canais de Marketing mais eficazes para alcançar essa persona. 3. Sugestões de Mensagens Chave e Ângulos de Comunicação que ressoem com essa persona. 4. Se 'Deep Research' estiver ativado, inclua insights adicionais sobre comportamento online, tendências e micro-segmentos. Considere as informações de suporte, se fornecidas.",
                f"**Produto/Serviço ou Campanha para Análise:** {client_details.get('product_campaign', '')}",
                f"**Localização Geográfica (Cidade(s), Região):** {client_details.get('location', 'Não especificada')}",
                f"**Verba Aproximada para Ação/Campanha (se aplicável):** {client_details.get('budget', 'Não informada')}",
                f"**Faixa Etária e Gênero Predominante (se souber):** {client_details.get('age_gender', 'Não especificados')}",
                f"**Principais Interesses, Hobbies, Dores, Necessidades do Público Desejado:** {client_details.get('interests', 'Não especificados')}",
                f"**Canais de Marketing que já utiliza ou considera:** {client_details.get('current_channels', 'Não especificados')}",
                f"**Nível de Pesquisa:** {'Deep Research Ativado (análise mais aprofundada)' if client_details.get('deep_research', False) else 'Pesquisa Padrão'}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a análise de cliente está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_client_analysis_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de cliente: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {ve}")
                print(f"Prompt completo que causou o ValueError (ENCONTRAR CLIENTE): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de cliente: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_client_analysis_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para ENCONTRAR CLIENTE: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (ENCONTRAR CLIENTE): {final_prompt}")
                return

    def _marketing_handle_conheca_concorrencia(uploaded_files_info, competitor_details, llm):
        if not competitor_details.get("your_business") or not competitor_details["your_business"].strip():
            st.warning("Por favor, descreva seu próprio negócio/produto para comparação com a concorrência.")
            st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
            return
        if not competitor_details.get("competitors_list") or not competitor_details["competitors_list"].strip():
            st.warning("Por favor, liste seus principais concorrentes para análise.")
            st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
            return
        if not competitor_details.get("aspects_to_analyze"):
            st.warning("Por favor, selecione pelo menos um aspecto da concorrência para analisar.")
            st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
            return

        with st.spinner("🔬 Max IA está analisando a concorrência..."):
            aspects_str = ", ".join(competitor_details.get('aspects_to_analyze', []))
            prompt_parts = [
                "**Instrução para IA:** Você é um 'Agente de Inteligência Competitiva', especialista em análise de mercado para PMEs no Brasil. Com base nas informações do negócio do usuário e da lista de concorrentes, elabore um relatório breve e útil. Para cada concorrente listado (ou os principais, se a lista for longa), analise os 'Aspectos para Análise' selecionados. Destaque os pontos fortes e fracos de cada um em relação a esses aspectos e, ao final, sugira 2-3 oportunidades ou diferenciais que o negócio do usuário pode explorar. Considere as informações de suporte, se fornecidas.",
                f"**Negócio do Usuário (para comparação):** {competitor_details.get('your_business', '')}",
                f"**Concorrentes (nomes, sites, redes sociais, se possível):** {competitor_details.get('competitors_list', '')}",
                f"**Aspectos para Análise:** {aspects_str if aspects_str else 'Não especificados'}"
            ]
            if uploaded_files_info:
                prompt_parts.append(f"**Informações de Arquivos de Suporte (considere o conteúdo relevante se aplicável):** {', '.join([f['name'] for f in uploaded_files_info])}.")

            final_prompt = "\n\n".join(prompt_parts)

            if not final_prompt or not final_prompt.strip():
                st.error("🚧 Max IA detectou que o prompt final para a análise de concorrência está vazio. Por favor, preencha os campos necessários.")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                return

            try:
                ai_response = llm.invoke(final_prompt)

                if hasattr(ai_response, 'content'):
                    st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = ai_response.content
                else:
                    st.warning("Resposta da IA não continha o atributo 'content' esperado. Usando a resposta como string.")
                    st.session_state[f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'] = str(ai_response)

            except ValueError as ve:
                st.error(f"🚧 Max IA encontrou um erro de valor ao processar sua solicitação para análise de concorrência: {ve}")
                st.error("Isso pode ser devido a um formato inesperado nos dados enviados ou uma configuração interna.")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                print(f"ValueError DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {ve}")
                print(f"Prompt completo que causou o ValueError (ANÁLISE DE CONCORRÊNCIA): {final_prompt}")
                return
            except Exception as e_invoke:
                st.error(f"🚧 Max IA teve um problema ao se comunicar com o modelo de IA para análise de concorrência: {e_invoke}")
                st.error(f"Detalhes do prompt que podem ter causado o erro (primeiros 500 caracteres): {final_prompt[:500]}...")
                st.session_state.pop(f'generated_competitor_analysis_new{APP_KEY_SUFFIX}', None)
                print(f"Erro GERAL DETALHADO em llm.invoke para ANÁLISE DE CONCORRÊNCIA: {e_invoke}")
                print(f"Prompt completo que causou o Erro Geral (ANÁLISE DE CONCORRÊNCIA): {final_prompt}")
                return

    class MaxAgente:
        def __init__(self, llm_passed_model):
            if llm_passed_model is None:
                st.error("❌ Erro crítico: MaxAgente tentou ser inicializado sem um modelo LLM.")
                st.stop()
            self.llm = llm_passed_model
            if f'memoria_max_bussola_plano{APP_KEY_SUFFIX}' not in st.session_state:
                st.session_state[f'memoria_max_bussola_plano{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_plano{APP_KEY_SUFFIX}", return_messages=True)
            if f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}' not in st.session_state:
                st.session_state[f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_bussola_ideias{APP_KEY_SUFFIX}", return_messages=True)
            if f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}' not in st.session_state:
                st.session_state[f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}'] = ConversationBufferMemory(memory_key=f"historico_chat_financeiro_precos{APP_KEY_SUFFIX}", return_messages=True)

            self.memoria_max_bussola_plano = st.session_state[f'memoria_max_bussola_plano{APP_KEY_SUFFIX}']
            self.memoria_max_bussola_ideias = st.session_state[f'memoria_max_bussola_ideias{APP_KEY_SUFFIX}']
            self.memoria_max_financeiro_precos = st.session_state[f'memoria_max_financeiro_precos{APP_KEY_SUFFIX}']
            self.memoria_plano_negocios = self.memoria_max_bussola_plano
            self.memoria_calculo_precos = self.memoria_max_financeiro_precos
            self.memoria_gerador_ideias = self.memoria_max_bussola_ideias

        def _criar_cadeia_conversacional(self, system_message_content, memoria_especifica, memory_key_placeholder_base="historico_chat"):
            actual_memory_key = memoria_especifica.memory_key
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(system_message_content),
                MessagesPlaceholder(variable_name=actual_memory_key),
                HumanMessagePromptTemplate.from_template("{input_usuario}")
            ])
            return LLMChain(llm=self.llm, prompt=prompt_template, memory=memoria_especifica, verbose=False)

        def exibir_max_marketing_total(self):
            st.header("🚀 MaxMarketing Total")
            st.caption("Seu copiloto Max IA para criar estratégias, posts, campanhas e mais!")
            st.markdown("---")
            marketing_files_info_for_prompt_local = []
            with st.sidebar:
                st.subheader("📎 Suporte para MaxMarketing")
                uploaded_marketing_files = st.file_uploader(
                    "Upload de arquivos de CONTEXTO para Marketing (opcional):",
                    accept_multiple_files=True,
                    type=['png', 'jpg', 'jpeg', 'txt', 'md', 'pdf', 'csv', 'xlsx', 'docx', 'pptx'],
                    key=f"marketing_files_uploader_max{APP_KEY_SUFFIX}"
                )
                if uploaded_marketing_files:
                    temp_marketing_files_info = []
                    for up_file in uploaded_marketing_files:
                        temp_marketing_files_info.append({"name": up_file.name, "type": up_file.type, "size": up_file.size})
                    if temp_marketing_files_info:
                        marketing_files_info_for_prompt_local = temp_marketing_files_info
                        st.success(f"{len(uploaded_marketing_files)} arquivo(s) de contexto carregado(s) para MaxMarketing!")
                    with st.expander("Ver arquivos de contexto de Marketing"):
                        for finfo in marketing_files_info_for_prompt_local:
                            st.write(f"- {finfo['name']} ({finfo['type']})")

            main_action_key = f"main_marketing_action_choice_max{APP_KEY_SUFFIX}"
            opcoes_menu_marketing_dict = {
                "Selecione uma opção...": 0,
                "1 - Criar post para redes sociais ou e-mail": 1,
                "2 - Criar campanha de marketing completa": 2,
                "3 - Criar estrutura e conteúdo para landing page": 3,
                "4 - Criar estrutura e conteúdo para site com IA": 4,
                "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)": 5,
                "6 - Conhecer a concorrência (Análise Competitiva)": 6
            }
            opcoes_radio_marketing = list(opcoes_menu_marketing_dict.keys())
            radio_index_key = f"{main_action_key}_index"
            if radio_index_key not in st.session_state:
                st.session_state[radio_index_key] = 0
            def update_marketing_radio_index_on_change():
                st.session_state[radio_index_key] = opcoes_radio_marketing.index(st.session_state[main_action_key])
            main_action = st.radio(
                "Olá! Sou o Max, seu agente de Marketing. O que vamos criar hoje?",
                opcoes_radio_marketing,
                index=st.session_state[radio_index_key],
                key=main_action_key,
                on_change=update_marketing_radio_index_on_change
            )
            st.markdown("---")
            platforms_config_options = {
                "Instagram": "insta", "Facebook": "fb", "X (Twitter)": "x", "WhatsApp": "wpp",
                "TikTok": "tt", "Kwai": "kwai", "YouTube (descrição/roteiro)": "yt",
                "E-mail Marketing (lista própria)": "email_own",
                "E-mail Marketing (Campanha Google Ads)": "email_google"
            }

            # Lógica para "Criar post"
            if main_action == "1 - Criar post para redes sociais ou e-mail":
                st.subheader("✨ Criador de Posts com Max IA")
                # Usaremos uma chave para controlar a exibição do resultado e evitar o erro do download_button
                SESSION_KEY_POST_CONTENT = f'generated_post_content_new{APP_KEY_SUFFIX}'
                FORM_KEY_POST = f"post_creator_form_max{APP_KEY_SUFFIX}"

                # Se o conteúdo já foi gerado, exibe direto
                if SESSION_KEY_POST_CONTENT in st.session_state:
                    _marketing_display_output_options(st.session_state[SESSION_KEY_POST_CONTENT], f"post_output_max{APP_KEY_SUFFIX}", "post_max_ia")
                    if st.button("Criar Novo Post", key=f"clear_post_content_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_POST_CONTENT, None)
                        st.rerun()
                else: # Caso contrário, exibe o formulário
                    with st.form(key=FORM_KEY_POST):
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_post = f"post_select_all_max{APP_KEY_SUFFIX}"
                        select_all_post_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_post)
                        cols_post = st.columns(2); selected_platforms_post_ui = []
                        for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                            col_index = i % 2
                            platform_key = f"post_platform_max_{platform_suffix}{APP_KEY_SUFFIX}"
                            with cols_post[col_index]:
                                if st.checkbox(platform_name, key=platform_key, value=select_all_post_checked):
                                    selected_platforms_post_ui.append(platform_name)
                                if "E-mail Marketing" in platform_name and st.session_state.get(platform_key):
                                    st.caption("💡 Para e-mail marketing, considere segmentar sua lista e personalizar a saudação.")
                        post_details = _marketing_get_objective_details(f"post_max{APP_KEY_SUFFIX}", "post")
                        submit_button_pressed_post = st.form_submit_button("💡 Gerar Post com Max IA!")

                        if submit_button_pressed_post:
                            _marketing_handle_criar_post(marketing_files_info_for_prompt_local, post_details, selected_platforms_post_ui, self.llm)
                            # _marketing_handle_criar_post agora define o session_state. Vamos dar rerun para exibir.
                            st.rerun()
            
            # Lógica similar para "Criar campanha"
            elif main_action == "2 - Criar campanha de marketing completa":
                st.subheader("🌍 Planejador de Campanhas de Marketing com Max IA")
                SESSION_KEY_CAMPAIGN_CONTENT = f'generated_campaign_content_new{APP_KEY_SUFFIX}'
                FORM_KEY_CAMPAIGN = f"campaign_creator_form_max{APP_KEY_SUFFIX}"

                if SESSION_KEY_CAMPAIGN_CONTENT in st.session_state:
                    _marketing_display_output_options(st.session_state[SESSION_KEY_CAMPAIGN_CONTENT], f"campaign_output_max{APP_KEY_SUFFIX}", "campanha_max_ia")
                    if st.button("Criar Nova Campanha", key=f"clear_campaign_content_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_CAMPAIGN_CONTENT, None)
                        st.rerun()
                else:
                    with st.form(key=FORM_KEY_CAMPAIGN):
                        campaign_name = st.text_input("Nome da Campanha:", key=f"campaign_name_max{APP_KEY_SUFFIX}")
                        st.subheader(" Plataformas Desejadas:")
                        key_select_all_camp = f"campaign_select_all_max{APP_KEY_SUFFIX}"
                        select_all_camp_checked = st.checkbox("Selecionar Todas as Plataformas Acima", key=key_select_all_camp)
                        cols_camp = st.columns(2); selected_platforms_camp_ui = []
                        for i, (platform_name, platform_suffix) in enumerate(platforms_config_options.items()):
                            col_index = i % 2
                            platform_key = f"campaign_platform_max_{platform_suffix}{APP_KEY_SUFFIX}"
                            with cols_camp[col_index]:
                                if st.checkbox(platform_name, key=platform_key, value=select_all_camp_checked):
                                    selected_platforms_camp_ui.append(platform_name)
                        campaign_details_obj = _marketing_get_objective_details(f"campaign_max{APP_KEY_SUFFIX}", "campanha")
                        campaign_duration = st.text_input("Duração Estimada:", key=f"campaign_duration_max{APP_KEY_SUFFIX}")
                        campaign_budget_approx = st.text_input("Orçamento Aproximado (opcional):", key=f"campaign_budget_max{APP_KEY_SUFFIX}")
                        specific_kpis = st.text_area("KPIs mais importantes:", key=f"campaign_kpis_max{APP_KEY_SUFFIX}")
                        submit_button_pressed_camp = st.form_submit_button("🚀 Gerar Plano de Campanha com Max IA!")

                        if submit_button_pressed_camp:
                            campaign_specifics_dict = {"name": campaign_name, "duration": campaign_duration, "budget": campaign_budget_approx, "kpis": specific_kpis}
                            _marketing_handle_criar_campanha(marketing_files_info_for_prompt_local, campaign_details_obj, campaign_specifics_dict, selected_platforms_camp_ui, self.llm)
                            st.rerun()

            # Lógica similar para "Criar landing page"
            elif main_action == "3 - Criar estrutura e conteúdo para landing page":
                st.subheader("📄 Gerador de Estrutura para Landing Pages com Max IA")
                SESSION_KEY_LP_CONTENT = f'generated_lp_content_new{APP_KEY_SUFFIX}'
                FORM_KEY_LP = f"landing_page_form_max{APP_KEY_SUFFIX}"

                if SESSION_KEY_LP_CONTENT in st.session_state:
                    st.subheader("💡 Estrutura e Conteúdo Sugeridos para Landing Page:")
                    st.markdown(st.session_state[SESSION_KEY_LP_CONTENT])
                    st.download_button(label="📥 Baixar Sugestões da LP",data=st.session_state[SESSION_KEY_LP_CONTENT].encode('utf-8'), file_name=f"landing_page_sugestoes_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain", key=f"download_lp_max_ தனி{APP_KEY_SUFFIX}") # Chave única
                    if st.button("Criar Nova Estrutura de LP", key=f"clear_lp_content_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_LP_CONTENT, None)
                        st.rerun()
                else:
                    with st.form(key=FORM_KEY_LP):
                        lp_purpose = st.text_input("Principal objetivo da landing page:", key=f"lp_purpose_max{APP_KEY_SUFFIX}")
                        lp_target_audience = st.text_input("Para quem é esta landing page? (Persona)", key=f"lp_audience_max{APP_KEY_SUFFIX}")
                        lp_main_offer = st.text_area("Oferta principal e irresistível:", key=f"lp_offer_max{APP_KEY_SUFFIX}")
                        lp_key_benefits = st.text_area("3-5 principais benefícios/transformações:", key=f"lp_benefits_max{APP_KEY_SUFFIX}")
                        lp_cta = st.text_input("Chamada para ação (CTA) principal:", key=f"lp_cta_max{APP_KEY_SUFFIX}")
                        lp_visual_prefs = st.text_input("Preferência de cores, estilo visual ou sites de referência? (Opcional)", key=f"lp_visual_max{APP_KEY_SUFFIX}")
                        submitted_lp = st.form_submit_button("🛠️ Gerar Estrutura da LP com Max IA!")
                        if submitted_lp:
                            lp_details_dict = {"purpose": lp_purpose, "target_audience": lp_target_audience, "main_offer": lp_main_offer, "key_benefits": lp_key_benefits, "cta": lp_cta, "visual_prefs": lp_visual_prefs}
                            _marketing_handle_criar_landing_page(marketing_files_info_for_prompt_local, lp_details_dict, self.llm)
                            st.rerun()
            
            # Lógica similar para "Criar site"
            elif main_action == "4 - Criar estrutura e conteúdo para site com IA":
                st.subheader("🏗️ Arquiteto de Sites com Max IA")
                SESSION_KEY_SITE_CONTENT = f'generated_site_content_new{APP_KEY_SUFFIX}'
                FORM_KEY_SITE = f"site_creator_form_max{APP_KEY_SUFFIX}"
                if SESSION_KEY_SITE_CONTENT in st.session_state:
                    st.subheader("🏛️ Estrutura e Conteúdo Sugeridos para o Site:")
                    st.markdown(st.session_state[SESSION_KEY_SITE_CONTENT])
                    st.download_button(label="📥 Baixar Sugestões do Site",data=st.session_state[SESSION_KEY_SITE_CONTENT].encode('utf-8'), file_name=f"site_sugestoes_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_site_max_ தனி{APP_KEY_SUFFIX}") # Chave única
                    if st.button("Criar Nova Estrutura de Site", key=f"clear_site_content_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_SITE_CONTENT, None)
                        st.rerun()
                else:
                    with st.form(key=FORM_KEY_SITE):
                        site_business_type = st.text_input("Tipo do seu negócio/empresa:", key=f"site_biz_type_max{APP_KEY_SUFFIX}")
                        site_main_purpose = st.text_area("Principal objetivo do seu site:", key=f"site_purpose_max{APP_KEY_SUFFIX}")
                        site_target_audience = st.text_input("Público principal do site:", key=f"site_audience_max{APP_KEY_SUFFIX}")
                        site_essential_pages = st.text_area("Páginas essenciais (Ex: Home, Sobre, Serviços):", key=f"site_pages_max{APP_KEY_SUFFIX}")
                        site_key_features = st.text_area("Principais produtos/serviços/diferenciais:", key=f"site_features_max{APP_KEY_SUFFIX}")
                        site_brand_personality = st.text_input("Personalidade da sua marca:", key=f"site_brand_max{APP_KEY_SUFFIX}")
                        site_visual_references = st.text_input("Preferências de cores, estilo ou sites de referência? (Opcional)", key=f"site_visual_ref_max{APP_KEY_SUFFIX}")
                        submitted_site = st.form_submit_button("🏛️ Gerar Estrutura do Site com Max IA!")
                        if submitted_site:
                            site_details_dict = {"business_type": site_business_type, "main_purpose": site_main_purpose, "target_audience": site_target_audience, "essential_pages": site_essential_pages, "key_features": site_key_features, "brand_personality": site_brand_personality, "visual_references": site_visual_references}
                            _marketing_handle_criar_site(marketing_files_info_for_prompt_local, site_details_dict, self.llm)
                            st.rerun()

            # Lógica similar para "Encontrar cliente"
            elif main_action == "5 - Encontrar meu cliente ideal (Análise de Público-Alvo)":
                st.subheader("🎯 Decodificador de Clientes com Max IA")
                SESSION_KEY_CLIENT_ANALYSIS = f'generated_client_analysis_new{APP_KEY_SUFFIX}'
                FORM_KEY_CLIENT = f"find_client_form_max{APP_KEY_SUFFIX}"
                if SESSION_KEY_CLIENT_ANALYSIS in st.session_state:
                    st.subheader("🕵️‍♂️ Análise de Público-Alvo e Recomendações:")
                    st.markdown(st.session_state[SESSION_KEY_CLIENT_ANALYSIS])
                    st.download_button(label="📥 Baixar Análise de Público",data=st.session_state[SESSION_KEY_CLIENT_ANALYSIS].encode('utf-8'), file_name=f"analise_publico_alvo_max_ia{APP_KEY_SUFFIX}.txt", mime="text/plain",key=f"download_client_analysis_max_ தனி{APP_KEY_SUFFIX}") # Chave única
                    if st.button("Nova Análise de Cliente", key=f"clear_client_analysis_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_CLIENT_ANALYSIS, None)
                        st.rerun()
                else:
                    with st.form(key=FORM_KEY_CLIENT):
                        fc_product_campaign = st.text_area("Produto/serviço ou campanha para análise:", key=f"fc_campaign_max{APP_KEY_SUFFIX}")
                        fc_location = st.text_input("Cidade(s) ou região de alcance:", key=f"fc_location_max{APP_KEY_SUFFIX}")
                        fc_budget = st.text_input("Verba aproximada para ação/campanha? (Opcional)", key=f"fc_budget_max{APP_KEY_SUFFIX}")
                        fc_age_gender = st.text_input("Faixa etária e gênero predominante:", key=f"fc_age_gender_max{APP_KEY_SUFFIX}")
                        fc_interests = st.text_area("Principais interesses, hobbies, dores, necessidades:", key=f"fc_interests_max{APP_KEY_SUFFIX}")
                        fc_current_channels = st.text_area("Canais de marketing que já utiliza ou considera:", key=f"fc_channels_max{APP_KEY_SUFFIX}")
                        fc_deep_research = st.checkbox("Habilitar 'Deep Research' (análise mais aprofundada pela IA)", key=f"fc_deep_max{APP_KEY_SUFFIX}")
                        submitted_fc = st.form_submit_button("🔍 Encontrar Meu Cliente com Max IA!")
                        if submitted_fc:
                            client_details_dict = {"product_campaign": fc_product_campaign, "location": fc_location, "budget": fc_budget, "age_gender": fc_age_gender, "interests": fc_interests, "current_channels": fc_current_channels, "deep_research": fc_deep_research}
                            _marketing_handle_encontre_cliente(marketing_files_info_for_prompt_local, client_details_dict, self.llm)
                            st.rerun()

            # Lógica similar para "Analisar concorrência"
            elif main_action == "6 - Conhecer a concorrência (Análise Competitiva)":
                st.subheader("🧐 Radar da Concorrência com Max IA")
                SESSION_KEY_COMPETITOR_ANALYSIS = f'generated_competitor_analysis_new{APP_KEY_SUFFIX}'
                FORM_KEY_COMPETITOR = f"competitor_analysis_form_max{APP_KEY_SUFFIX}"
                if SESSION_KEY_COMPETITOR_ANALYSIS in st.session_state:
                    st.subheader("📊 Análise da Concorrência e Insights:")
                    st.markdown(st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS])
                    st.download_button(label="📥 Baixar Análise da Concorrência", data=st.session_state[SESSION_KEY_COMPETITOR_ANALYSIS].encode('utf-8'), file_name=f"analise_concorrencia_max_ia{APP_KEY_SUFFIX}.txt",mime="text/plain",key=f"download_competitor_analysis_max_ தனி{APP_KEY_SUFFIX}") # Chave única
                    if st.button("Nova Análise de Concorrência", key=f"clear_competitor_analysis_button{APP_KEY_SUFFIX}"):
                        st.session_state.pop(SESSION_KEY_COMPETITOR_ANALYSIS, None)
                        st.rerun()
                else:
                    with st.form(key=FORM_KEY_COMPETITOR):
                        ca_your_business = st.text_area("Descreva seu próprio negócio/produto para comparação:", key=f"ca_your_biz_max{APP_KEY_SUFFIX}")
                        ca_competitors_list = st.text_area("Liste seus principais concorrentes (nomes, sites, redes sociais):", key=f"ca_competitors_max{APP_KEY_SUFFIX}")
                        ca_aspects_to_analyze = st.multiselect( "Quais aspectos da concorrência analisar?", ["Presença Online", "Tipos de Conteúdo", "Comunicação", "Pontos Fortes", "Pontos Fracos", "Preços (se observável)", "Engajamento"], default=["Presença Online", "Pontos Fortes", "Pontos Fracos"], key=f"ca_aspects_max{APP_KEY_SUFFIX}")
                        submitted_ca = st.form_submit_button("📡 Analisar Concorrentes com Max IA!")
                        if submitted_ca:
                            competitor_details_dict = {"your_business": ca_your_business, "competitors_list": ca_competitors_list, "aspects_to_analyze": ca_aspects_to_analyze}
                            _marketing_handle_conheca_concorrencia(marketing_files_info_for_prompt_local, competitor_details_dict, self.llm)
                            st.rerun()
            
            elif main_action == "Selecione uma opção...":
                st.info("👋 Bem-vindo ao MaxMarketing Total! Escolha uma das opções acima para começar.")
                LOGO_PATH_MARKETING_WELCOME = "images/max-ia-logo.png"
                try:
                    st.image(LOGO_PATH_MARKETING_WELCOME, width=200)
                except Exception:
                    st.image("https://i.imgur.com/7IIYxq1.png", caption="Max IA (Fallback)", width=200)

        def exibir_max_financeiro(self):
            # ... (código existente, sem st.form aqui, então _handle_chat_with_image não deve ter problemas)
            st.header("💰 MaxFinanceiro")
            st.caption("Seu agente Max IA para inteligência financeira, cálculo de preços e mais.")
            st.subheader("💲 Cálculo de Preços Inteligente com Max IA")
            st.caption("Descreva seu produto/serviço, custos, mercado e objetivos. Envie uma imagem se ajudar.")
            current_section_key_finance = "max_financeiro_precos"
            memoria_financeiro = self.memoria_max_financeiro_precos
            uploaded_image_calc = st.file_uploader("Envie uma imagem do produto (opcional):", type=["png", "jpg", "jpeg"], key=f"preco_img_max_financeiro{APP_KEY_SUFFIX}")
            system_message_financeiro = "Você é Max IA, um especialista em finanças e precificação para PMEs. Ajude o usuário a calcular o preço de seus produtos ou serviços, considerando custos, margens, mercado e valor percebido. Seja claro e didático."
            chain_financeiro = self._criar_cadeia_conversacional(system_message_financeiro, memoria_financeiro)
            def conversar_max_financeiro_precos(input_usuario, descricao_imagem_contexto=None):
                prompt_final_usuario = input_usuario
                if descricao_imagem_contexto:
                    prompt_final_usuario = f"{descricao_imagem_contexto}\n\n{input_usuario}"
                resposta_ai = chain_financeiro.invoke({"input_usuario": prompt_final_usuario})
                return resposta_ai['text']
            _handle_chat_with_image(current_section_key_finance, "Descreva o produto/serviço, custos, etc.", conversar_max_financeiro_precos, uploaded_image_calc)
            _sidebar_clear_button_max("Preços (MaxFinanceiro)", memoria_financeiro, current_section_key_finance)

        def exibir_max_administrativo(self):
            st.header("⚙️ MaxAdministrativo")
            st.image("images/max-ia-logo.png", width=150)
            st.subheader("Olá! Sou o Max, seu agente para otimizar a gestão administrativa do seu negócio.")
            st.info("Esta área está em desenvolvimento e em breve trará ferramentas para simplificar suas rotinas administrativas, organizar tarefas, gerenciar equipes e muito mais. Volte em breve!")
            st.balloons()

        def exibir_max_pesquisa_mercado(self):
            st.header("📈 MaxPesquisa de Mercado")
            st.image("images/max-ia-logo.png", width=150)
            st.subheader("Olá! Sou o Max, seu agente para desvendar o mercado e seus clientes.")
            st.info("Esta área está em desenvolvimento. Em breve, você poderá realizar análises de público-alvo aprofundadas, entender a concorrência e descobrir novas tendências de mercado, tudo com a ajuda da IA.")
            st.caption("Por enquanto, algumas funcionalidades de análise de público e concorrência estão disponíveis no MaxMarketing Total.")

        def exibir_max_bussola(self):
            # ... (código existente, sem st.form aqui para os chats, então deve estar ok)
            st.header("🧭 MaxBússola Estratégica")
            st.caption("Seu guia Max IA para planejamento estratégico, novas ideias e direção de negócios.")
            tab1_plano, tab2_ideias = st.tabs(["🗺️ Plano de Negócios com Max IA", "💡 Gerador de Ideias com Max IA"])
            with tab1_plano:
                st.subheader("📝 Elaborando seu Plano de Negócios com Max IA")
                st.caption("Converse com o Max para desenvolver seções do seu plano de negócios, obter insights e refinar suas estratégias.")
                current_section_key_plano = "max_bussola_plano"
                memoria_plano = self.memoria_max_bussola_plano
                system_message_plano = "Você é Max IA, um consultor de negócios experiente. Ajude o usuário a criar um rascunho de plano de negócios, seção por seção. Faça perguntas, ofereça sugestões e ajude a estruturar as ideias."
                chain_plano = self._criar_cadeia_conversacional(system_message_plano, memoria_plano)
                def conversar_max_bussola_plano(input_usuario):
                    resposta_ai = chain_plano.invoke({"input_usuario": input_usuario})
                    return resposta_ai['text']
                exibir_chat_e_obter_input(current_section_key_plano, "Sua resposta ou próxima seção do plano...", conversar_max_bussola_plano)
                _sidebar_clear_button_max("Plano (MaxBússola)", memoria_plano, current_section_key_plano)
            with tab2_ideias:
                st.subheader("💡 Gerador de Ideias para seu Negócio com Max IA")
                st.caption("Descreva um desafio, uma área que quer inovar, ou peça sugestões. Envie arquivos de texto ou imagem para dar mais contexto.")
                current_section_key_ideias = "max_bussola_ideias"
                memoria_ideias = self.memoria_max_bussola_ideias
                system_message_ideias = "Você é Max IA, um especialista em inovação e brainstorming. Ajude o usuário a gerar novas ideias para seus negócios, resolver problemas ou explorar novas oportunidades. Use o contexto de arquivos, se fornecido."
                chain_ideias = self._criar_cadeia_conversacional(system_message_ideias, memoria_ideias)
                def conversar_max_bussola_ideias(input_usuario, contexto_arquivos=None):
                    prompt_final_usuario = input_usuario
                    if contexto_arquivos:
                        prompt_final_usuario = f"Contexto dos arquivos:\n{contexto_arquivos}\n\nCom base nisso e na minha solicitação: {input_usuario}"
                    resposta_ai = chain_ideias.invoke({"input_usuario": prompt_final_usuario})
                    return resposta_ai['text']
                uploaded_files_ideias_ui = st.file_uploader("Envie arquivos de contexto (opcional - .txt, .png, .jpg):", type=["txt", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"ideias_file_uploader_max_bussola{APP_KEY_SUFFIX}")
                _handle_chat_with_files(current_section_key_ideias, "Descreva seu desafio ou peça ideias:", conversar_max_bussola_ideias, uploaded_files_ideias_ui)
                _sidebar_clear_button_max("Ideias (MaxBússola)", memoria_ideias, current_section_key_ideias)

        def exibir_max_trainer(self):
            st.header("🎓 MaxTrainer IA")
            st.image("images/max-ia-logo.png", width=150)
            st.subheader("Olá! Sou o Max, seu treinador pessoal de IA para negócios.")
            st.info("Esta área está em desenvolvimento. Em breve, o MaxTrainer trará tutoriais interativos, dicas personalizadas sobre como usar o Max IA ao máximo, e insights para você se tornar um mestre em aplicar IA no seu dia a dia empresarial.")
            st.write("Imagine aprender sobre:")
            st.markdown("""
            - Como criar os melhores prompts para cada agente Max IA.
            - Interpretando os resultados da IA e aplicando-os na prática.
            - Novas funcionalidades e como elas podem te ajudar.
            - Estudos de caso e exemplos de sucesso.
            """)
            st.balloons()

    # --- Funções Utilitárias Globais ---
    # (inicializar_ou_resetar_chat, exibir_chat_e_obter_input, _sidebar_clear_button_max, 
    #  _handle_chat_with_image, _handle_chat_with_files permanecem como antes)
    # ... (elas já estão no seu código colado, mantive-as para referência de onde entram) ...
    def inicializar_ou_resetar_chat(area_chave, mensagem_inicial_ia, memoria_agente_instancia):
        chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
        st.session_state[chat_display_key] = [{"role": "assistant", "content": mensagem_inicial_ia}]
        if memoria_agente_instancia:
            memoria_agente_instancia.clear()
            if hasattr(memoria_agente_instancia.chat_memory, 'add_ai_message'):
                memoria_agente_instancia.chat_memory.add_ai_message(mensagem_inicial_ia)
            elif hasattr(memoria_agente_instancia.chat_memory, 'messages') and isinstance(memoria_agente_instancia.chat_memory.messages, list):
                memoria_agente_instancia.chat_memory.messages.clear()
                memoria_agente_instancia.chat_memory.messages.append(AIMessage(content=mensagem_inicial_ia))
        if area_chave == "max_financeiro_precos":
            st.session_state.pop(f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}', None)
            st.session_state.pop(f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}', None)
            st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)
        elif area_chave == "max_bussola_ideias":
            st.session_state.pop(f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}', None)
            st.session_state.pop(f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}', None)
            st.session_state.pop(f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}', None)

    def exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_funcao_agente):
        chat_display_key = f"chat_display_{area_chave}{APP_KEY_SUFFIX}"
        if chat_display_key not in st.session_state:
            st.session_state[chat_display_key] = []
        for msg_info in st.session_state[chat_display_key]:
            with st.chat_message(msg_info["role"]):
                st.markdown(msg_info["content"])
        prompt_usuario = st.chat_input(prompt_placeholder, key=f"chat_input_{area_chave}{APP_KEY_SUFFIX}")
        if prompt_usuario:
            st.session_state[chat_display_key].append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"): st.markdown(prompt_usuario)
            if area_chave in ["max_financeiro_precos", "max_bussola_ideias"]:
                st.session_state[f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'] = True
            with st.spinner("Max IA está processando... 🤔"):
                resposta_ai = funcao_conversa_agente(prompt_usuario, **kwargs_funcao_agente)
                st.session_state[chat_display_key].append({"role": "assistant", "content": resposta_ai})
            st.rerun()

    def _sidebar_clear_button_max(label, memoria, section_key_prefix):
        if st.sidebar.button(f"🗑️ Limpar Histórico de {label}", key=f"btn_reset_{section_key_prefix}{APP_KEY_SUFFIX}_clear_max"):
            msg_inicial = f"Ok, vamos recomeçar {label.lower()}! Qual o seu ponto de partida?"
            if section_key_prefix == "max_financeiro_precos":
                msg_inicial = "Ok, vamos recomeçar o cálculo de preços com MaxFinanceiro! Descreva seu produto ou serviço."
            elif section_key_prefix == "max_bussola_ideias":
                msg_inicial = "Ok, vamos recomeçar a geração de ideias com MaxBússola! Qual o seu ponto de partida?"
            elif section_key_prefix == "max_bussola_plano":
                msg_inicial = "Olá! Sou Max IA com a MaxBússola. Vamos elaborar um rascunho do seu plano de negócios? Comece me contando sobre sua ideia."
            inicializar_ou_resetar_chat(section_key_prefix, msg_inicial, memoria)
            st.rerun()

    def _handle_chat_with_image(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_image_obj):
        descricao_imagem_para_ia = None
        processed_image_id_key = f'processed_image_id_{area_chave}{APP_KEY_SUFFIX}'
        last_uploaded_info_key = f'last_uploaded_image_info_{area_chave}{APP_KEY_SUFFIX}'
        user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'
        if uploaded_image_obj is not None:
            if st.session_state.get(processed_image_id_key) != uploaded_image_obj.file_id:
                try:
                    img_pil = Image.open(uploaded_image_obj); st.image(img_pil, caption=f"Imagem: {uploaded_image_obj.name}", width=150)
                    descricao_imagem_para_ia = f"Usuário carregou imagem '{uploaded_image_obj.name}'."
                    st.session_state[last_uploaded_info_key] = descricao_imagem_para_ia
                    st.session_state[processed_image_id_key] = uploaded_image_obj.file_id
                    st.info(f"Imagem '{uploaded_image_obj.name}' pronta para o diálogo com Max IA.")
                except Exception as e_img_proc:
                    st.error(f"Erro ao processar imagem: {e_img_proc}")
                    st.session_state[last_uploaded_info_key] = None; st.session_state[processed_image_id_key] = None
            else:
                descricao_imagem_para_ia = st.session_state.get(last_uploaded_info_key)
        kwargs_chat = {}
        ctx_img_prox_dialogo = st.session_state.get(last_uploaded_info_key)
        if ctx_img_prox_dialogo and not st.session_state.get(user_input_processed_key, False):
            kwargs_chat['descricao_imagem_contexto'] = ctx_img_prox_dialogo
        exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
        if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
            if st.session_state.get(last_uploaded_info_key):
                st.session_state[last_uploaded_info_key] = None
            st.session_state[user_input_processed_key] = False

    def _handle_chat_with_files(area_chave, prompt_placeholder, funcao_conversa_agente, uploaded_files_objs):
        contexto_para_ia_local = None
        processed_file_id_key = f'processed_file_id_{area_chave}{APP_KEY_SUFFIX}'
        uploaded_info_key = f'uploaded_file_info_{area_chave}_for_prompt{APP_KEY_SUFFIX}'
        user_input_processed_key = f'user_input_processed_{area_chave}{APP_KEY_SUFFIX}'
        if uploaded_files_objs:
            current_file_signature = "-".join(sorted([f"{f.name}-{f.size}-{f.file_id}" for f in uploaded_files_objs]))
            if st.session_state.get(processed_file_id_key) != current_file_signature or not st.session_state.get(uploaded_info_key):
                text_contents, image_info = [], []
                for f_item in uploaded_files_objs:
                    try:
                        if f_item.type == "text/plain":
                            text_contents.append(f"Arquivo '{f_item.name}':\n{f_item.read().decode('utf-8')[:3000]}...")
                        elif f_item.type in ["image/png","image/jpeg"]:
                            st.image(Image.open(f_item),caption=f"Contexto: {f_item.name}",width=100)
                            image_info.append(f"Imagem '{f_item.name}'.")
                    except Exception as e_file_proc:
                        st.error(f"Erro ao processar '{f_item.name}': {e_file_proc}")
                full_ctx_str = ("\n\n--- TEXTO DOS ARQUIVOS ---\n" + "\n\n".join(text_contents) if text_contents else "") + \
                               ("\n\n--- IMAGENS FORNECIDAS ---\n" + "\n".join(image_info) if image_info else "")
                if full_ctx_str.strip():
                    st.session_state[uploaded_info_key] = full_ctx_str.strip()
                    contexto_para_ia_local = st.session_state[uploaded_info_key]
                    st.info("Arquivo(s) de contexto pronto(s) para Max IA.")
                else:
                    st.session_state[uploaded_info_key] = None
                st.session_state[processed_file_id_key] = current_file_signature
            else:
                contexto_para_ia_local = st.session_state.get(uploaded_info_key)
        kwargs_chat = {}
        if contexto_para_ia_local and not st.session_state.get(user_input_processed_key, False):
            kwargs_chat['contexto_arquivos'] = contexto_para_ia_local
        exibir_chat_e_obter_input(area_chave, prompt_placeholder, funcao_conversa_agente, **kwargs_chat)
        if user_input_processed_key in st.session_state and st.session_state[user_input_processed_key]:
            if st.session_state.get(uploaded_info_key):
                st.session_state[uploaded_info_key] = None
            st.session_state[user_input_processed_key] = False

    # --- Instanciação do Agente ---
    if 'max_agente_instancia' not in st.session_state or \
       not isinstance(st.session_state.max_agente_instancia, MaxAgente) or \
       (hasattr(st.session_state.max_agente_instancia, 'llm') and st.session_state.max_agente_instancia.llm != llm_model_instance):
        
        if llm_model_instance:
            st.session_state.max_agente_instancia = MaxAgente(llm_passed_model=llm_model_instance)
        else:
            st.session_state.max_agente_instancia = None 
    
    agente = None # Inicializa agente como None
    if st.session_state.get('max_agente_instancia') and llm_model_instance:
        agente = st.session_state.max_agente_instancia

    # --- Interface da Sidebar e Lógica de Navegação (Somente se agente foi instanciado) ---
    if agente:
        st.sidebar.write(f"Logado como: {display_email}")
        if st.sidebar.button("Logout", key=f"main_app_logout_max{APP_KEY_SUFFIX}"):
            st.session_state.user_session_pyrebase = None
            keys_to_clear_on_logout = [k for k in st.session_state if APP_KEY_SUFFIX in k or k.startswith('memoria_') or k.startswith('chat_display_') or k.startswith('generated_') or k.startswith('post_') or k.startswith('campaign_')]
            keys_to_clear_on_logout.extend(['max_agente_instancia', 'area_selecionada_max_ia',
                                            'firebase_init_success_message_shown', 'firebase_app_instance',
                                            'llm_init_success_sidebar_shown_main_app'])
            for key_to_clear in keys_to_clear_on_logout:
                st.session_state.pop(key_to_clear, None)
            st.rerun()

        LOGO_PATH_SIDEBAR_APP = "images/max-ia-logo.png"
        try:
            st.sidebar.image(LOGO_PATH_SIDEBAR_APP, width=150)
        except Exception:
            st.sidebar.image("https://i.imgur.com/7IIYxq1.png", width=150, caption="Max IA (Fallback)")

        st.sidebar.title("Max IA")
        st.sidebar.markdown("Seu Agente IA para Maximizar Resultados!")
        st.sidebar.markdown("---")

        opcoes_menu_max_ia = {
            "👋 Bem-vindo ao Max IA": "painel_max_ia",
            "🚀 MaxMarketing Total": "max_marketing_total",
            "💰 MaxFinanceiro": "max_financeiro",
            "⚙️ MaxAdministrativo": "max_administrativo",
            "📈 MaxPesquisa de Mercado": "max_pesquisa_mercado",
            "🧭 MaxBússola Estratégica": "max_bussola",
            "🎓 MaxTrainer IA": "max_trainer_ia"
        }
        radio_key_sidebar_main_max = f'sidebar_selection_max_ia{APP_KEY_SUFFIX}'

        if 'area_selecionada_max_ia' not in st.session_state or st.session_state.area_selecionada_max_ia not in opcoes_menu_max_ia.keys():
            st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.keys())[0]

        radio_index_key_nav_max = f'{radio_key_sidebar_main_max}_index'
        if radio_index_key_nav_max not in st.session_state:
            try:
                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(st.session_state.area_selecionada_max_ia)
            except ValueError:
                st.session_state[radio_index_key_nav_max] = 0
                st.session_state.area_selecionada_max_ia = list(opcoes_menu_max_ia.keys())[0]

        def update_main_radio_index_on_change_max_ia():
            st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(st.session_state[radio_key_sidebar_main_max])

        area_selecionada_label_max_ia = st.sidebar.radio(
            "Max Agentes IA:",
            options=list(opcoes_menu_max_ia.keys()),
            key=radio_key_sidebar_main_max,
            index=st.session_state[radio_index_key_nav_max],
            on_change=update_main_radio_index_on_change_max_ia
        )

        if area_selecionada_label_max_ia != st.session_state.area_selecionada_max_ia:
            st.session_state.area_selecionada_max_ia = area_selecionada_label_max_ia
            if area_selecionada_label_max_ia != "🚀 MaxMarketing Total":
                keys_to_clear_marketing_nav = [k for k in st.session_state if k.startswith(f"generated_") and APP_KEY_SUFFIX in k or k.startswith(f"post_max{APP_KEY_SUFFIX}") or k.startswith(f"campaign_max{APP_KEY_SUFFIX}")]
                for key_clear_nav_mkt in keys_to_clear_marketing_nav:
                    st.session_state.pop(key_clear_nav_mkt, None)
            st.rerun()

        current_section_key_max_ia = opcoes_menu_max_ia.get(st.session_state.area_selecionada_max_ia)

        # --- SELEÇÃO E EXIBIÇÃO DA SEÇÃO ATUAL ---
        if current_section_key_max_ia == "painel_max_ia":
            st.markdown("<div style='text-align: center;'><h1>👋 Bem-vindo ao Max IA!</h1></div>", unsafe_allow_html=True)
            logo_base64 = convert_image_to_base64('images/max-ia-logo.png')
            if logo_base64:
                st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{logo_base64}' width='200'></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align: center;'><p>(Logo não pôde ser carregado)</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.2em;'>Olá! Eu sou o <strong>Max</strong>, seu conjunto de agentes de IA dedicados a impulsionar o sucesso da sua Pequena ou Média Empresa.</p></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align: center;'><p style='font-size: 1.1em;'>Use o menu à esquerda para selecionar um agente especializado e começar a transformar seu negócio hoje mesmo.</p></div>", unsafe_allow_html=True)
            st.markdown("---")
            st.subheader("Conheça seus Agentes Max IA:")
            cols_cards = st.columns(3)
            card_data = [
                ("🚀 MaxMarketing Total", "Crie posts, campanhas, sites e muito mais!"),
                ("💰 MaxFinanceiro", "Inteligência para preços, custos e finanças."),
                ("⚙️ MaxAdministrativo", "Otimize sua gestão e rotinas (Em breve!)."),
                ("📈 MaxPesquisa de Mercado", "Desvende seu público e a concorrência (Em breve!)."),
                ("🧭 MaxBússola Estratégica", "Planejamento, ideias e direção para o futuro."),
                ("🎓 MaxTrainer IA", "Aprenda a usar todo o poder da IA (Em breve!).")
            ]
            for i, (title, caption) in enumerate(card_data):
                with cols_cards[i % 3]:
                    matching_key = None
                    for menu_title, section_key_val in opcoes_menu_max_ia.items():
                        if title.startswith(menu_title.split(" ")[0]):
                            if menu_title.startswith(title):
                                matching_key = section_key_val
                                break
                            try:
                                agent_name_in_title = title.split(" ")[1]
                                if agent_name_in_title.lower() in section_key_val.lower():
                                    matching_key = section_key_val
                                    break
                            except IndexError:
                                pass
                    if matching_key:
                        if st.button(title, key=f"btn_goto_card_{matching_key}{APP_KEY_SUFFIX}", use_container_width=True, help=f"Ir para {title}"):
                            st.session_state.area_selecionada_max_ia = [k for k, v in opcoes_menu_max_ia.items() if v == matching_key][0]
                            try:
                                st.session_state[radio_index_key_nav_max] = list(opcoes_menu_max_ia.keys()).index(st.session_state.area_selecionada_max_ia)
                            except ValueError: pass
                            st.rerun()
                    else:
                         st.markdown(f"**{title}**")
                    st.caption(caption)
                    st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
            st.balloons()
        elif current_section_key_max_ia == "max_marketing_total":
            agente.exibir_max_marketing_total()
        elif current_section_key_max_ia == "max_financeiro":
            agente.exibir_max_financeiro()
        elif current_section_key_max_ia == "max_administrativo":
            agente.exibir_max_administrativo()
        elif current_section_key_max_ia == "max_pesquisa_mercado":
            agente.exibir_max_pesquisa_mercado()
        elif current_section_key_max_ia == "max_bussola":
            agente.exibir_max_bussola()
        elif current_section_key_max_ia == "max_trainer_ia":
            agente.exibir_max_trainer()
    else: # Se agente é None (devido a llm_model_instance ser None)
        st.error("🚨 O Max IA não pôde ser totalmente iniciado.")
        st.info("Isso pode ter ocorrido devido a um problema com a chave da API do Google ou ao contatar os serviços do Google Generative AI.")
        if llm_init_exception:
            st.exception(llm_init_exception)

# --- Seção de Login/Registro (executada se user_is_authenticated for False) ---
else:
    st.session_state.pop('auth_error_shown', None)
    st.title("🔑 Bem-vindo ao Max IA")
    st.sidebar.subheader("Login / Registro")
    auth_action_choice_key = "app_auth_choice_pyrebase_max"
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key=auth_action_choice_key)
    if auth_action_choice == "Login":
        with st.sidebar.form("app_login_form_pyrebase_max"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")
            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('firebase_init_success_message_shown', None)
                        st.rerun()
                    except Exception as e_login:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try:
                            error_details_str = e_login.args[0] if len(e_login.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "USER_DISABLED" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos, ou usuário desabilitado."
                            elif api_error_message: error_message_login = f"Erro no login: {api_error_message}"
                        except: pass
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha.")
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("app_register_form_pyrebase_max"):
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")
            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                        try:
                            pb_auth_client.send_email_verification(user['idToken'])
                            st.sidebar.info("Email de verificação enviado (cheque sua caixa de entrada e spam).")
                        except Exception as verify_email_error_local:
                            st.sidebar.caption(f"Nota: Não foi possível enviar email de verificação: {verify_email_error_local}")
                    except Exception as e_register:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e_register.args[0] if len(e_register.args) > 0 else "{}"
                            error_data = json.loads(error_details_str.replace("'", "\""))
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message:
                                error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except:
                            error_message_register = f"Erro no registro: {str(e_register)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client: st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else: st.sidebar.warning("Por favor, preencha email e senha para registro.")
    if not error_message_firebase_init:
        st.info("Faça login ou registre-se na barra lateral para usar o Max IA.")
    LOGO_PATH_LOGIN_UNAUTH = "images/max-ia-logo.png"
    try:
        st.image(LOGO_PATH_LOGIN_UNAUTH, width=200)
    except Exception:
        st.image("https://i.imgur.com/7IIYxq1.png", width=200, caption="Max IA (Fallback)")

st.sidebar.markdown("---")
st.sidebar.info("Max IA | Desenvolvido por Yaakov Israel com Gemini Pro")
