# --- Lógica de Autenticação e Estado da Sessão ---
# (Esta parte inicial permanece a mesma que funcionou para o login)
if 'user_session_pyrebase' not in st.session_state:
    st.session_state.user_session_pyrebase = None

user_is_authenticated = False
if st.session_state.user_session_pyrebase and 'idToken' in st.session_state.user_session_pyrebase:
    try:
        refreshed_user_info = pb_auth_client.get_account_info(st.session_state.user_session_pyrebase['idToken'])
        st.session_state.user_session_pyrebase['email'] = refreshed_user_info['users'][0].get('email', "Email não disponível")
        user_is_authenticated = True
    except Exception as e: 
        try:
            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
            error_data = json.loads(error_details_str.replace("'", "\""))
            api_error_message = error_data.get('error', {}).get('message', "ERRO_DESCONHECIDO")
            if "TOKEN_EXPIRED" in api_error_message or "INVALID_ID_TOKEN" in api_error_message:
                st.session_state.user_session_pyrebase = None 
                user_is_authenticated = False
                if 'auth_error_shown' not in st.session_state: 
                    st.sidebar.warning("Sua sessão expirou. Por favor, faça login novamente.")
                    st.session_state.auth_error_shown = True
            else: 
                st.session_state.user_session_pyrebase = None 
                user_is_authenticated = False
                if 'auth_error_shown' not in st.session_state:
                    st.sidebar.error(f"Erro ao verificar sessão: {api_error_message}. Faça login.")
                    st.session_state.auth_error_shown = True
        except (json.JSONDecodeError, IndexError, TypeError):
            st.session_state.user_session_pyrebase = None 
            user_is_authenticated = False
            if 'auth_error_shown' not in st.session_state:
                st.sidebar.error(f"Erro ao verificar sessão (parsing). Faça login.")
                st.session_state.auth_error_shown = True
        # Se o token se tornou inválido, e a sessão ainda existe (mas será None agora), forçar rerun para UI atualizar
        if not user_is_authenticated and st.session_state.get('user_session_pyrebase') is None:
             if 'auth_error_shown' in st.session_state: # Evitar rerun infinito se o erro já foi mostrado
                 pass
             else:
                 st.experimental_rerun() # ou st.rerun() - para forçar a UI de login

# --- Interface do Usuário Condicional ---
if user_is_authenticated:
    st.session_state.pop('auth_error_shown', None) 
    display_email = st.session_state.user_session_pyrebase.get('email', "Usuário Logado")
    st.sidebar.write(f"Bem-vindo(a), {display_email}!")
    
    # ***** MODIFICAÇÃO IMPORTANTE AQUI *****
    if st.sidebar.button("Logout", key="app_logout_button_v21_fix"): # Nova chave para o botão
        st.session_state.user_session_pyrebase = None
        # Removidas as linhas st.session_state.pop() que poderiam causar instabilidade
        st.rerun() # Usando st.rerun() que é a forma mais atualizada
    
    st.header("🚀 Assistente PME Pro")
    st.subheader("Você está autenticado!")
    st.write("O restante da lógica do aplicativo (Marketing, Plano de Negócios, etc.) será adicionado aqui no próximo passo.")

else:
    # (O restante do código para mostrar formulários de login/registro permanece o mesmo)
    st.session_state.pop('auth_error_shown', None) 
    st.sidebar.subheader("Login / Registro")
    auth_action_choice = st.sidebar.radio("Ação:", ("Login", "Registrar Novo Usuário"), key="app_auth_action_choice_v20_fix") # Chave pode ser a mesma ou nova

    if auth_action_choice == "Login":
        with st.sidebar.form("app_login_form_v20_fix"): # Chave pode ser a mesma ou nova
            login_email = st.text_input("Email")
            login_password = st.text_input("Senha", type="password")
            login_button_clicked = st.form_submit_button("Login")

            if login_button_clicked:
                if login_email and login_password and pb_auth_client:
                    try:
                        user_session = pb_auth_client.sign_in_with_email_and_password(login_email, login_password)
                        st.session_state.user_session_pyrebase = dict(user_session)
                        st.session_state.pop('show_init_success', None) 
                        st.rerun() # Usando st.rerun()
                    except Exception as e:
                        error_message_login = "Erro no login. Verifique suas credenciais."
                        try: 
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_details_str_normalized = error_details_str.replace("'", "\"")
                            error_data = json.loads(error_details_str_normalized)
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "INVALID_LOGIN_CREDENTIALS" in api_error_message or "EMAIL_NOT_FOUND" in api_error_message or "INVALID_PASSWORD" in api_error_message or "INVALID_EMAIL" in api_error_message:
                                error_message_login = "Email ou senha inválidos."
                            elif api_error_message: 
                                error_message_login = f"Erro: {api_error_message}"
                        except: pass
                        st.sidebar.error(error_message_login)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha.")
    
    elif auth_action_choice == "Registrar Novo Usuário":
        with st.sidebar.form("app_register_form_v20_fix"): # Chave pode ser a mesma ou nova
            reg_email = st.text_input("Email para registro")
            reg_password = st.text_input("Senha para registro (mínimo 6 caracteres)", type="password")
            submit_register = st.form_submit_button("Registrar")

            if submit_register:
                if reg_email and reg_password and pb_auth_client:
                    try:
                        user = pb_auth_client.create_user_with_email_and_password(reg_email, reg_password)
                        st.sidebar.success(f"Usuário {reg_email} registrado! Por favor, faça o login.")
                    except Exception as e:
                        error_message_register = "Erro no registro."
                        try:
                            error_details_str = e.args[0] if len(e.args) > 0 else "{}"
                            error_details_str_normalized = error_details_str.replace("'", "\"")
                            error_data = json.loads(error_details_str_normalized)
                            api_error_message = error_data.get('error', {}).get('message', '')
                            if "EMAIL_EXISTS" in api_error_message:
                                error_message_register = "Este email já está registrado. Tente fazer login."
                            elif api_error_message:
                                error_message_register = f"Erro no registro: {api_error_message}"
                        except:
                             error_message_register = f"Erro no registro: {str(e)}"
                        st.sidebar.error(error_message_register)
                elif not pb_auth_client:
                     st.sidebar.error("Cliente Firebase Auth não inicializado.")
                else:
                    st.sidebar.warning("Por favor, preencha email e senha para registro.")
    
    if not error_message_firebase_init: # Só mostra esta info se o Firebase init foi OK
        st.info("Bem-vindo! Faça login ou registre-se para usar o Assistente PME Pro.")
        logo_url_login = "https://i.imgur.com/7IIYxq1.png" 
        st.image(logo_url_login, width=200)


st.sidebar.markdown("---")
st.sidebar.markdown("Assistente PME Pro - v0.2.1 Alpha (Pyrebase)") # Versão incrementada
