import streamlit as st
import sys
import importlib # Para tentar importar de forma mais programática

st.write("--- Início do Teste Detalhado de Importação ---")
st.write(f"Versão do Python: {sys.version}")
st.write("Caminhos do Sistema (sys.path):")
st.json(sys.path) # Mostra onde o Python procura por módulos

st.write("--- Tentativa de Importação Direta ---")
try:
    from streamlit_firebase_auth import login_button
    st.success("SUCESSO ao importar 'login_button' de 'streamlit_firebase_auth'!")
    st.write(f"Localização do módulo 'streamlit_firebase_auth' (se encontrado): {login_button.__module__ if hasattr(login_button, '__module__') else 'Não aplicável'}")
except ImportError as e_imp_direct:
    st.error(f"🚨 FALHA na importação direta: {e_imp_direct}")
except Exception as e_direct:
    st.error(f"🚨 ERRO INESPERADO na importação direta: {type(e_direct).__name__} - {e_direct}")

st.write("--- Tentativa de Importação do Módulo Inteiro ---")
sfa_module = None
try:
    import streamlit_firebase_auth as sfa_test_module
    sfa_module = sfa_test_module # Atribui se a importação for bem-sucedida
    st.success("SUCESSO! Módulo 'streamlit_firebase_auth' importado como 'sfa_test_module'.")
    st.write(f"Tipo de sfa_test_module: {type(sfa_test_module)}")
    st.write(f"Localização do arquivo do módulo: {sfa_test_module.__file__ if hasattr(sfa_test_module, '__file__') else 'Não disponível'}")
    st.write("Atributos disponíveis em 'sfa_test_module':")
    st.json(dir(sfa_test_module)) # Usar st.json para melhor formatação de listas grandes

    # Verifica atributos específicos novamente
    if hasattr(sfa_test_module, 'login_button'):
        st.write("-> Atributo 'login_button' ENCONTRADO em sfa_test_module.")
    else:
        st.warning("-> Atributo 'login_button' NÃO encontrado em sfa_test_module.")
    
    if hasattr(sfa_test_module, 'FirebaseAuth'):
        st.write("-> Atributo 'FirebaseAuth' ENCONTRADO em sfa_test_module.")
    else:
        st.warning("-> Atributo 'FirebaseAuth' NÃO encontrado em sfa_test_module.")

except ImportError as e_imp_module:
    st.error(f"🚨 FALHA ao importar 'streamlit_firebase_auth as sfa_test_module': {e_imp_module}")
except Exception as e_module:
    st.error(f"🚨 ERRO INESPERADO ao importar módulo inteiro: {type(e_module).__name__} - {e_module}")

st.write("--- Tentativa de Importação com importlib ---")
try:
    spec = importlib.util.find_spec("streamlit_firebase_auth")
    if spec is None:
        st.error("🚨 importlib.util.find_spec NÃO encontrou 'streamlit_firebase_auth'.")
    else:
        st.success("importlib.util.find_spec ENCONTROU 'streamlit_firebase_auth'.")
        st.write(f"Localização do spec: {spec.origin}")
        # Tenta carregar o módulo usando o spec
        # module_via_importlib = importlib.util.module_from_spec(spec)
        # spec.loader.exec_module(module_via_importlib)
        # st.success("Módulo carregado via importlib!")
        # st.write(dir(module_via_importlib))
except Exception as e_importlib:
    st.error(f"🚨 ERRO com importlib: {type(e_importlib).__name__} - {e_importlib}")


st.write("--- Testando importação de um pacote padrão diferente (dateutil) ---")
try:
    import dateutil.parser
    st.success("SUCESSO ao importar 'dateutil.parser'!")
    st.write(f"Exemplo de uso: {dateutil.parser.parse('2025-05-30')}")
except ImportError:
    st.error("🚨 FALHA ao importar 'dateutil.parser'. Isso pode indicar um problema geral com a instalação de QUALQUER novo pacote.")
    st.info("Adicione 'python-dateutil' ao seu requirements.txt se este erro ocorrer.")


st.write("--- Fim do Teste Detalhado de Importação ---")
