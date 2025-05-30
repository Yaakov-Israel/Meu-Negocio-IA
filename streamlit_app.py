import streamlit as st
import streamlit_authenticator as stauth # Requer streamlit-authenticator instalado

st.set_page_config(page_title="Gerador de Hash PME Pro", layout="centered")
st.title("🔑 Gerador de Hash para `streamlit-authenticator`")
st.caption("Use este utilitário para gerar o hash da senha desejada.")
st.info("Este app é temporário, apenas para gerar o hash. Depois, volte seu app principal.")

password_input = st.text_input("Digite a senha para a qual você quer gerar o hash:", 
                             type="password", 
                             value="mazaltovazimovcaradepauzovi", # Sugestão, você pode mudar para testar
                             key="pwd_to_hash_input_v9_cloud_gen")

if st.button("Gerar Hash Seguro!", key="btn_generate_hash_v9_cloud_gen"):
    if password_input:
        try:
            # A classe Hasher espera uma LISTA de senhas
            hashed_passwords_list = stauth.Hasher([password_input]).generate()

            if hashed_passwords_list and isinstance(hashed_passwords_list, list) and len(hashed_passwords_list) > 0:
                generated_hash_value = hashed_passwords_list[0]
                st.success("Hash gerado com sucesso!")
                st.write("Copie o hash abaixo e cole no campo 'password' do seu usuário na seção '[credentials.usernames.SEU_USUARIO]' dos seus Segredos no Streamlit Cloud:")
                st.code(generated_hash_value, language=None) # language=None para texto simples
                st.warning("Lembre-se de NUNCA armazenar a senha original em texto plano nos segredos em produção. Use este hash gerado.")
            else:
                st.error("A geração do hash não retornou um resultado esperado (lista vazia ou formato incorreto).")
                st.write(f"Retorno de generate(): {hashed_passwords_list}")

        except AttributeError as e_attr:
            st.error(f"🚨 ERRO: Parece que 'streamlit_authenticator.Hasher' não está disponível ou a biblioteca não foi carregada corretamente.")
            st.error(f"Detalhe: {type(e_attr).__name__} - {e_attr}")
            st.info("Verifique se 'streamlit-authenticator==0.3.2' está no requirements.txt e se foi instalado sem erros nos logs de build.")
            st.exception(e_attr)
        except Exception as e_hash_gen_cloud:
            st.error(f"🚨 ERRO AO GERAR HASH: {type(e_hash_gen_cloud).__name__} - {e_hash_gen_cloud}")
            st.exception(e_hash_gen_cloud)
    else:
        st.warning("Por favor, digite uma senha para gerar o hash.")

st.markdown("---")
st.info("Após copiar o hash, você precisará: 1. Colocar este hash nos seus segredos no Streamlit Cloud. 2. Restaurar seu arquivo `streamlit_app.py` principal no GitHub. 3. Dar 'Reboot' no app no Streamlit Cloud.")
