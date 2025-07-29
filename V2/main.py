import streamlit as st
import subprocess
import os
import json
import time

def update_env_var(key, value):
    # Safely read and update/create .env keys
    if os.path.exists(".env"):
        with open(".env", "r") as file:
            lines = file.readlines()
    else:
        lines = []

    found = False
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}\n")

    with open(".env", "w") as file:
        file.writelines(lines)


CREDENTIALS_FILE = "users.json"
LOG_FILE = "live_trading_log.log"
st.set_page_config(page_title="Smart Trading App", layout="centered")

STOP_FILE = "stop.txt"

if "initialized" not in st.session_state:
    # Only do this once per app session
    st.session_state.initialized = True
    with open(STOP_FILE, "w") as f:
        f.write("")  # Clear the stop file

# Styling
st.markdown("""
    <style>
    .main-title {
        font-size: 3em;
        text-align: center;
        color: #4CAF50;
        margin-bottom: 10px;
    }
    .subtitle {
        font-size: 1.2em;
        text-align: center;
        color: #777;
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)


# Load credentials
def load_users():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    return {}


# Save new user
def save_user(username, password):
    users = load_users()
    users[username] = password
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(users, f)


# Initialize auth and training states
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "training_done" not in st.session_state:
    st.session_state.training_done = False


# Define tabs: Tab 1 = Existing app UI, Tab 2 = Logs
tabs = st.tabs(["Main", "Live Trading Logs"])

# ----------------- Tab 1: Existing UI ------------------
with tabs[0]:

    # =========== LOGIN / SIGNUP PAGE ===========
    if not st.session_state.authenticated:
        st.markdown("<div class='main-title'>📊 Smart Trading App</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle'>Login or Sign Up to Start Trading</div>", unsafe_allow_html=True)


        auth_mode = st.radio("Choose Action", ["Login", "Sign Up"], horizontal=True)
        st.markdown("---")
        username = st.text_input("👤 Username")
        password = st.text_input("🔐 Password", type="password")

        if auth_mode == "Login":
            if st.button("🔓 Login"):
                users = load_users()
                if username in users and users[username] == password:
                    st.session_state.authenticated = True
                    st.success("✅ Logged in successfully!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
        else:
            if st.button("📝 Sign Up"):
                users = load_users()
                if username in users:
                    st.warning("⚠️ User already exists.")
                else:
                    save_user(username, password)
                    st.success("🎉 User created! Please login.")
        st.stop()

    # =========== TRADING FORM and TRAINING ===========
    st.title("📈 Auto Trading Bot (SmartAPI + ML)")
    st.markdown("Fill in the details below to start trading:")

    qty_mode = st.radio("Quantity Mode", ["Auto", "Manual"], horizontal=True)
    with st.form("trading_form"):
        api_key = st.text_input("API Key", type="password")
        user_id = st.text_input("Client ID")
        password_input = st.text_input("Password", type="password", key="trading_password")
        totp = st.text_input("TOTP Secret", type="password")
        symbol = st.text_input("Stock Symbol (e.g., NIFTY01AUGFUT)")
        token = st.text_input("Symbol Token (e.g., 99926009)")

        stoploss = st.number_input("Stoploss %", min_value=0.0, max_value=100.0, value=0.5, format="%.2f")
        target = st.number_input("Target %", min_value=0.0, max_value=100.0, value=0.5, format="%.2f")

        qty = None
        if qty_mode == "Manual":
            qty = st.number_input("Enter Quantity", min_value=1, value=50)

        paper_trade = st.checkbox("Run in Paper Trade Mode (No Real Orders)", value=True)

        submitted = st.form_submit_button("Train Bot")

    if submitted:
        # Save environment variables
        update_env_var("API_KEY", api_key)
        update_env_var("USER_ID", user_id)
        update_env_var("PASSWORD", password_input)
        update_env_var("TOTP_SECRET", totp)
        update_env_var("SYMBOL", symbol)
        update_env_var("SYMBOL_TOKEN", token)
        update_env_var("STOPLOSS_PCT", stoploss)
        update_env_var("TARGET_PCT", target)
        update_env_var("PAPER_TRADE", int(paper_trade))
        update_env_var("AUTO_QTY", int(qty_mode == "Auto"))
        update_env_var("QUANTITY", qty if qty_mode == "Manual" else 0)

        st.session_state.env_vars = {
            "SYMBOL": symbol,
            "SYMBOL_TOKEN": token,
            "STOPLOSS_PCT": str(stoploss),
            "TARGET_PCT": str(target),
            "PAPER_TRADE": str(int(paper_trade)),
            "AUTO_QTY": str(int(qty_mode == "Auto")),
            "QUANTITY": str(qty if qty_mode == "Manual" else 0)
        }
        st.success("✅ Model training started...")

        with st.spinner("Training Model:"):
            try:
                subprocess.run(["python", "train.py"], check=True)
                st.success("Model trained successfully!")
                st.session_state.training_done = True  # Mark training done here
            except subprocess.CalledProcessError as e:
                st.error("Training failed, check the logs.")
                st.stop()

        st.success("🎯 Model trained successfully!")
        st.success("✅ Trading environment updated successfully!")

        st.write("🔧 Launch Config:")
        st.json(st.session_state.env_vars)

    # Button to launch live trading bot after training
    if st.session_state.training_done:
        if st.button("Launch Live Trading Bot"):
            st.success("✅ Starting live trading bot...")
            subprocess.Popen(["python", "livebot.py"], env={**os.environ, **st.session_state.env_vars})

# ----------------- Tab 2: Live Trading Logs ------------------
with tabs[1]:
    st.header("Live Trading Logs")

    if not st.session_state.get("training_done", False):
        st.warning("Please complete training before viewing live trading logs.")
    else:
        refresh_rate = st.slider("Refresh logs every (seconds):", min_value=2, max_value=30, value=5)

        # Read and show log file content
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                logs = f.read()
        else:
            logs = "No trading logs available yet."

        st.text_area("Trading Logs", value=logs, height=500, key="log_area")

        # Autorefresh logic using time
        time.sleep(refresh_rate)
        st.rerun()

