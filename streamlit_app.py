import streamlit as st

st.write("Tentando importar streamlit_firebase_auth...")
try:
    import streamlit_firebase_auth as sfa
    st.success("SUCESSO! Módulo 'streamlit_firebase_auth' importado como 'sfa'.")
    st.write("Atributos disponíveis em 'sfa':")
    st.write(dir(sfa))

    # Tenta acessar funções que deveriam existir
    if hasattr(sfa, 'login_button'):
        st.write("Função 'login_button' encontrada em 'sfa'!")
    else:
        st.error("ERRO: Função 'login_button' NÃO encontrada em 'sfa'.")

    if hasattr(sfa, 'logout_button'):
        st.write("Função 'logout_button' encontrada em 'sfa'!")
    else:
        st.error("ERRO: Função 'logout_button' NÃO encontrada em 'sfa'.")

    if hasattr(sfa, 'FirebaseAuth'):
        st.write("Classe 'FirebaseAuth' encontrada em 'sfa'!")
    else:
        st.error("ERRO: Classe 'FirebaseAuth' NÃO encontrada em 'sfa'.")

except ImportError as e_imp:
    st.error(f"🚨 FALHA NA IMPORTAÇÃO: {e_imp}")
    st.info("Verifique os logs de build no Streamlit Cloud para 'streamlit-firebase-auth==1.0.5'.")
except Exception as e_gen:
    st.error(f"🚨 ERRO INESPERADO: {type(e_gen).__name__} - {e_gen}")
    st.exception(e_gen)

st.write("--- Fim do Teste de Importação ---")
