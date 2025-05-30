import streamlit as st
import sys
import importlib

st.write("--- Início do Teste Detalhado de Importação v2 ---")
st.write(f"Versão do Python: {sys.version}")

sfa_module = None
try:
    import streamlit_firebase_auth as sfa
    sfa_module = sfa # Atribui se a importação for bem-sucedida
    st.success("SUCESSO! Módulo 'streamlit_firebase_auth' importado como 'sfa'.")
    st.write(f"Localização: {sfa.__file__ if hasattr(sfa, '__file__') else 'N/A'}")
    st.write("Conteúdo de dir(sfa):")
    st.json(dir(sfa))

    # Tentativa de acesso via sfa.components.Komponenten
    if hasattr(sfa, 'components') and hasattr(sfa.components, 'Komponenten'):
        st.write("--- Tentando acessar via sfa.components.Komponenten ---")
        try:
            # A classe Komponenten é instanciada dentro do __init__.py da lib,
            # e seus métodos login_button/logout_button são expostos.
            # Se a exposição direta falhou, mas 'components' e 'Komponenten' existem,
            # algo está quebrado na re-exportação da biblioteca.
            # No entanto, as funções login_button/logout_button no __init__.py da lib
            # são atribuídas a partir de uma instância de Komponenten.
            # Vamos verificar se podemos chamar as funções que deveriam estar no módulo 'sfa' diretamente,
            # pois é assim que a biblioteca foi projetada para ser usada.

            if hasattr(sfa, 'login_button'):
                st.success("SUCESSO! 'sfa.login_button' encontrado diretamente!")
                # Para realmente testar, precisamos de segredos configurados, o que não é o foco deste script mínimo.
                # Apenas a existência do atributo é suficiente por agora.
            else:
                st.error("ERRO: 'sfa.login_button' NÃO encontrado diretamente. Isso é inesperado.")

            if hasattr(sfa, 'logout_button'):
                st.success("SUCESSO! 'sfa.logout_button' encontrado diretamente!")
            else:
                st.error("ERRO: 'sfa.logout_button' NÃO encontrado diretamente. Isso é inesperado.")

            # Se o acesso direto acima falhou, isso indica um problema na biblioteca
            # ou no ambiente que impede o __init__.py da biblioteca de funcionar 100%.
            # Acessar sfa.components.Komponenten().login_button() seria um paliativo
            # para uma biblioteca que não está se comportando como documentado.

        except Exception as e_komp_access:
            st.error(f"ERRO ao tentar acessar atributos via sfa.components: {type(e_komp_access).__name__} - {e_komp_access}")
            st.exception(e_komp_access)
    else:
        st.warning("Submódulo 'sfa.components' ou classe 'sfa.components.Komponenten' não encontrados.")

except ImportError as e_imp:
    st.error(f"🚨 FALHA NA IMPORTAÇÃO de 'streamlit_firebase_auth as sfa': {e_imp}")
    st.info("Verifique os logs de build no Streamlit Cloud para 'streamlit-firebase-auth==1.0.5' e 'firebase-admin'.")
except Exception as e_gen:
    st.error(f"🚨 ERRO INESPERADO: {type(e_gen).__name__} - {e_gen}")
    st.exception(e_gen)

st.write("--- Fim do Teste Detalhado de Importação v2 ---")
