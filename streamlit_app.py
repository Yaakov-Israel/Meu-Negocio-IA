import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(page_title="Teste Autenticação v5 - Super Mínimo", layout="wide")
st.title("Teste Super Mínimo com `streamlit-authenticator`")

# Carrega as credenciais e configurações do cookie diretamente dos segredos
# Espera-se que st.secrets.credentials e st.secrets.cookie existam e estejam formatados corretamente.
try:
    credentials_for_auth = st.secrets["credentials"]
    cookie_for_auth = st.secrets["cookie"]
    
    # A biblioteca streamlit-authenticator espera que 'credentials' seja um dict 
    # e que dentro dele 'usernames' seja um dict.
    # E que 'cookie' seja um dict com 'name', 'key', 'expiry_days'.
    
    authenticator = stauth.Authenticate(
        credentials_for_auth, # Passa o objeto SecretsSection diretamente
        cookie_for_auth['name'],
        cookie_for_auth['key'],
        cookie_for_auth['expiry_days']
    )

    name_of_user, authentication_status, username = authenticator.login()

    st.subheader("Resultado da Tentativa de Login:")
    st.write(f"Nome Retornado: `{name_of_user}`")
    st.write(f"Status da Autenticação: `{authentication_status}`")
    st.write(f"Username Retornado: `{username}`")

    if authentication_status:
        st.success(f"🎉 Login BEM-SUCEDIDO como {name_of_user} ({username})!")
        authenticator.logout('Logout', 'sidebar', key='logout_v5_super_min')
        st.write("Pode prosseguir para o app completo!")
    elif authentication_status == False:
        st.error("Usuário ou senha inválido. Verifique as credenciais e o hash da senha nos segredos.")
    elif authentication_status == None:
        st.info("Formulário de login acima. Por favor, insira suas credenciais.")

except KeyError as e_key:
    st.error(f"🚨 ERRO DE CONFIGURAÇÃO DE SEGREDOS: Chave não encontrada: {e_key}")
    st.info("Verifique se as seções '[credentials]' (com sub-dicionário 'usernames') e '[cookie]' (com 'name', 'key', 'expiry_days') existem e estão corretas nos seus Segredos do Streamlit Cloud.")
    st.exception(e_key)
except Exception as e_main:
    st.error(f"🚨 ERRO INESPERADO NO APP DE TESTE: {type(e_main).__name__} - {e_main}")
    st.exception(e_main)

st.caption("Fim do teste v5.")
