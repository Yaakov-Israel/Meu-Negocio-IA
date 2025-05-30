import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(page_title="Teste Autenticação v6 - Ajuste Final", layout="wide")
st.title("Teste Super Mínimo v6 com `streamlit-authenticator`")

# Carrega as credenciais e configurações do cookie diretamente dos segredos
try:
    # Verifica se as seções e chaves existem para evitar KeyErrors antes de to_dict()
    if 'credentials' not in st.secrets or 'usernames' not in st.secrets['credentials']:
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seção '[credentials]' ou subchave 'usernames' ausente nos segredos.")
        st.stop()
    if 'cookie' not in st.secrets or not all(k in st.secrets['cookie'] for k in ['name', 'key', 'expiry_days']):
        st.error("🚨 ERRO DE CONFIGURAÇÃO: Seção '[cookie]' ou chaves ('name', 'key', 'expiry_days') ausentes/incompletas.")
        st.stop()

    # CONVERSÃO PARA DICIONÁRIO PURO ANTES DE PASSAR PARA O AUTHENTICATOR
    credentials_for_auth = st.secrets["credentials"].to_dict() 
    cookie_for_auth_dict = st.secrets["cookie"].to_dict() 
    
    authenticator = stauth.Authenticate(
        credentials_for_auth,        # Agora é um dict Python puro
        cookie_for_auth_dict['name'],
        cookie_for_auth_dict['key'],
        cookie_for_auth_dict['expiry_days']
    )

    name_of_user, authentication_status, username = authenticator.login()

    st.subheader("Resultado da Tentativa de Login:")
    st.write(f"Nome Retornado: `{name_of_user}`")
    st.write(f"Status da Autenticação: `{authentication_status}`")
    st.write(f"Username Retornado: `{username}`")

    if authentication_status:
        st.success(f"🎉 Login BEM-SUCEDIDO como {name_of_user} ({username})!")
        authenticator.logout('Logout', 'sidebar', key='logout_v6_super_min')
        st.write("Pode prosseguir para o app completo!")
    elif authentication_status == False:
        st.error("Usuário ou senha inválido. Verifique as credenciais e o hash da senha nos segredos.")
    elif authentication_status == None:
        st.info("Formulário de login acima. Por favor, insira suas credenciais.")

except KeyError as e_key_final: # Captura KeyErrors específicos dos segredos ANTES do to_dict
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS (KeyError): Chave não encontrada: {e_key_final}")
    st.info("Verifique se as seções '[credentials]' (com sub-dicionário 'usernames') e '[cookie]' (com 'name', 'key', 'expiry_days') existem e estão corretas nos seus Segredos do Streamlit Cloud.")
    st.exception(e_key_final)
except AttributeError as e_attr_final: # Captura AttributeError se .to_dict() não existir (improvável para st.secrets)
    st.error(f"🚨 ERRO AO ACESSAR SEGREDOS (AttributeError): {e_attr_final}")
    st.info("Pode ser um problema com a estrutura do objeto de segredos.")
    st.exception(e_attr_final)
except Exception as e_main_final: # Captura todos os outros erros
    st.error(f"🚨 ERRO INESPERADO NO APP DE TESTE v6: {type(e_main_final).__name__} - {e_main_final}")
    st.exception(e_main_final)

st.caption("Fim do teste v6.")
