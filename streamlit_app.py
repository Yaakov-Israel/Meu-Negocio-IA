import streamlit as st
import os

# Usamos um set_page_config simples para não termos erros.
st.set_page_config(page_title="Diagnóstico Max IA", layout="wide")

st.title("🔬 Sonda Forense do Ambiente")
st.write("Esta análise nos dirá exatamente como o Streamlit Cloud está vendo nossos arquivos.")

try:
    # 1. Onde o script acredita que está? (Current Working Directory)
    cwd = os.getcwd()
    st.subheader("1. Diretório de Trabalho Atual (onde o script está rodando):")
    st.code(cwd, language="bash")

    # 2. O que ele vê neste diretório?
    st.subheader(f"2. Conteúdo encontrado em '{cwd}':")
    items_in_cwd = os.listdir(cwd)
    st.code("\n".join(items_in_cwd), language="bash")

    # 3. Vamos verificar se a nossa pasta de projeto está aqui.
    if "meu-negocio-ia" in items_in_cwd:
        st.success("✅ SUCESSO: A pasta do projeto 'meu-negocio-ia' foi encontrada aqui!")
        
        project_path = os.path.join(cwd, "meu-negocio-ia")
        st.subheader(f"3. Conteúdo DENTRO de '{project_path}':")
        items_in_project = os.listdir(project_path)
        st.code("\n".join(items_in_project), language="bash")

        # 4. O TESTE FINAL: O caminho para o prompts.json existe a partir daqui?
        final_path_to_check = os.path.join(project_path, "prompts", "prompts.json")
        st.subheader(f"4. Teste final: o caminho '{final_path_to_check}' existe?")
        if os.path.exists(final_path_to_check):
            st.success(f"✅ SIM! O arquivo foi encontrado em '{final_path_to_check}'.")
            st.balloons()
            st.markdown("---")
            st.header("Diagnóstico Concluído: O Problema é o Caminho Relativo.")
            st.write("A solução será ajustar nossos arquivos para usar caminhos absolutos baseados no local do script.")
        else:
            st.error(f"❌ NÃO! Mesmo encontrando a pasta do projeto, o arquivo de prompts não foi localizado em '{final_path_to_check}'. Verifique se a pasta 'prompts' e o arquivo 'prompts.json' estão corretamente nomeados e dentro da pasta 'meu-negocio-ia'.")

    else:
        st.error("❌ FALHA CRÍTICA: A pasta do projeto 'meu-negocio-ia' NÃO foi encontrada no diretório de trabalho. Isso confirma que o script está rodando um nível acima do esperado.")
        st.markdown("---")
        st.header("Diagnóstico Concluído: O Problema é o Diretório de Execução.")
        st.write("A solução será ajustar nossos arquivos para usar caminhos absolutos baseados no local do script.")


except Exception as e:
    st.error(f"Um erro ocorreu durante o diagnóstico: {e}")
