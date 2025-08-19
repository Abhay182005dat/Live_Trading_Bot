import streamlit as st
import subprocess
import threading
import time
import os
import sys
from dotenv import load_dotenv, set_key
from SmartApi import SmartConnect
import pyotp

load_dotenv()

API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")

if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = None
if 'smart_connect' not in st.session_state:
    st.session_state.smart_connect = None
if 'last_search_term' not in st.session_state:
    st.session_state.last_search_term = ""
if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False
if 'search_message' not in st.session_state:
    st.session_state.search_message = ""


def initialize_smart_connect():
    """Initialize SmartConnect API connection"""
    try:
        if st.session_state.smart_connect is None:
            totp = pyotp.TOTP(TOTP_SECRET).now()
            obj = SmartConnect(api_key=API_KEY)
            data = obj.generateSession(USER_ID, PASSWORD, totp)
            
            if data['status']:
                st.session_state.smart_connect = obj
                return True, "✅ Connected to SmartAPI successfully!"
            else:
                return False, f"❌ Login failed: {data.get('message', 'Unknown error')}"
    except Exception as e:
        return False, f"❌ Connection error: {str(e)}"
    
    return True, "✅ Already connected!"

def search_symbol(search_term, exchange="MCX"):
    """Search for symbols using SmartAPI"""
    try:
        if st.session_state.smart_connect is None:
            success, message = initialize_smart_connect()
            if not success:
                return [], message
        
        if len(search_term) < 2:
            return [], "Enter at least 2 characters to search"
        
        results = st.session_state.smart_connect.searchScrip(exchange, search_term.upper())
        
        actual_data = []
        if results is None:
            return [],"No response from API"
        
        results = results.get('data',[])
        
        if results and len(results) > 0:
            filtered_results = []
            for result in results:
                if isinstance(result, dict):
                    symbol = result.get('tradingsymbol', '')
                    token = result.get('symboltoken', '')
                    name = symbol.split('-')[0]
                    
                    if symbol and token:
                        filtered_results.append({
                            'symbol': symbol,
                            'token': str(token),
                            'name': name,
                            'exchange': result.get('exchange', exchange)
                        })
            
            return filtered_results[:10], f"✅ Found {len(filtered_results)} results"
        else:
            return [], "No results found"
            
    except Exception as e:
        return [], f"❌ Search error: {str(e)}"



# Configure page
st.set_page_config(
    page_title="Live Trading Bot",
    page_icon="📈",
    layout="centered",  # Changed to centered for more compact layout
    initial_sidebar_state="collapsed"
)

# Custom CSS - Compact square design
st.markdown("""
<style>
    /* Main container styling for square layout */
    .main .block-container {
        max-width: 600px;
        padding: 1rem 1rem;
        margin: 0 auto;
    }
    
    .main-title {
        font-size: 2.2em;
        text-align: center;
        color: #4CAF50;
        margin-bottom: 5px;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
    }
    
    .subtitle {
        font-size: 1em;
        text-align: center;
        color: #777;
        margin-bottom: 20px;
        font-weight: 400;
    }
    
    .status-running {
        background-color: #d4edda;
        color: #155724;
        padding: 6px 12px;
        border-radius: 6px;
        border-left: 3px solid #28a745;
        text-align: center;
        font-weight: 500;
        margin-bottom: 10px;
        font-size: 0.9em;
    }
    
    .status-stopped {
        background-color: #f8d7da;
        color: #721c24;
        padding: 6px 12px;
        border-radius: 6px;
        border-left: 3px solid #dc3545;
        text-align: center;
        font-weight: 500;
        margin-bottom: 10px;
        font-size: 0.9em;
    }
    
    .form-container {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .form-section {
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid #eee;
    }
    
    .form-section:last-child {
        border-bottom: none;
        margin-bottom: 0;
    }
    
    .form-label {
        font-weight: 600;
        color: #495057;
        margin-bottom: 5px;
        display: block;
        font-size: 0.85rem;
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin: 10px 0;
    }
    
    .metric-item {
        background-color: #f8f9fa;
        padding: 8px 10px;
        border-radius: 6px;
        border: 1px solid #e9ecef;
        text-align: center;
    }
    
    .metric-label {
        font-size: 0.7rem;
        color: #6c757d;
        margin-bottom: 2px;
    }
    
    .metric-value {
        font-weight: 600;
        color: #495057;
        font-size: 0.8rem;
    }
    
    .button-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-top: 15px;
    }
    
    /* Compact tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        padding: 2px;
        justify-content: center;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 30px;
        padding: 0 12px;
        font-size: 0.8rem;
        font-weight: 500;
        border-radius: 6px;
    }
    
    /* Form inputs - smaller */
    .stSelectbox > div > div{
        border-radius: 6px;
        font-size : 0.8 rem;
        height : 35px
    }
    
    .stCheckbox {
        margin-top: 3px;
    }
    
    .stCheckbox > label {
        font-size: 0.85rem;
    }
    
    /* Compact buttons */
    .stButton > button {
        padding: 6px 15px;
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.8rem;
        height: 35px;
        width: 100%;
    }
    
    /* Log area - compact */
    .log-container {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 10px;
        margin-top: 10px;
    }
    
    .stTextArea textarea {
        font-family: 'Consolas', monospace;
        font-size: 15px;
        border-radius: 6px;
    }
    
    /* Compact metrics */
    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 5px;
        border-radius: 6px;
        margin: 2px;
    }
    
    [data-testid="metric-container"] > div {
        font-size: 0.7rem;
    }
    
    [data-testid="metric-container"] > div > div {
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'bot_process' not in st.session_state:
    st.session_state.bot_process = None
if 'log_content' not in st.session_state:
    st.session_state.log_content = ""

# Available stock symbols
STOCK_SYMBOLS = {
    'HINDUNILVR-EQ': '1394',
    'RELIANCE-EQ': '2885',
    'TCS-EQ': '11536',
    'INFY-EQ': '1594',
    'HDFCBANK-EQ': '1333',
    'ICICIBANK-EQ': '4963',
    'SBIN-EQ': '3045',
    'BHARTIARTL-EQ': '10604',
    'ITC-EQ': '424',
    'KOTAKBANK-EQ': '1922'

}

def update_env_file(symbol, token, quantity, paper_trade):
    """Update .env file with trading parameters"""
    env_file = '.env'
    
    # Load existing environment variables
    load_dotenv()
    
    # Set new trading parameters
    os.environ['TRADING_SYMBOL'] = symbol
    os.environ['TRADING_TOKEN'] = token
    os.environ['TRADING_QUANTITY'] = str(quantity)
    os.environ['PAPER_TRADE'] = str(paper_trade)
    
    # Update .env file
    set_key(env_file, 'TRADING_SYMBOL', symbol)
    set_key(env_file, 'TRADING_TOKEN', token)
    set_key(env_file, 'TRADING_QUANTITY', str(quantity))
    set_key(env_file, 'PAPER_TRADE', str(paper_trade))
    
    st.success(f"✅ Configuration updated!", icon="💾")

def read_log_file():
    """Read the latest content from log file"""
    try:
        with open("live_trading_log.log", "r") as f:
            content = f.read()
            return content
    except FileNotFoundError:
        return "Log file not found. Start the bot to generate logs."

def start_trading_bot():
    """Start the trading bot as a subprocess"""
    try:
        # Start the livebot.py as a subprocess
        process = subprocess.Popen(
            [sys.executable, "livebot.py"],
        )
        st.session_state.bot_process = process
        st.session_state.bot_running = True
        return True
    except Exception as e:
        st.error(f"Failed to start bot: {e}")
        return False

def stop_trading_bot():
    """Stop the trading bot"""
    try:
        # Create stop.txt file to signal the bot to stop
        with open("stop.txt", "w") as f:
            f.write("STOP")
        
        # If process exists, terminate it
        if st.session_state.bot_process:
            process_id = st.session_state.bot_process.pid
            st.info(f"🛑 Stopping bot (PID: {process_id})...")
            time.sleep(1)
            
            st.session_state.bot_process.terminate()
            try:
                st.session_state.bot_process.wait(timeout=2)
                st.success("✅ Bot stopped!")
                
            except subprocess.TimeoutExpired:
                st.warning("⚠️ Force killing...")
                st.session_state.bot_process.kill()
                st.session_state.bot_process.wait()
                st.success("✅ Bot terminated!")

            time.sleep(1)
            st.session_state.bot_process = None
        
        st.session_state.bot_running = False
        
        # Remove stop.txt file after a moment
        threading.Timer(2.0, lambda: os.remove("stop.txt") if os.path.exists("stop.txt") else None).start()
        
        st.rerun()
        return True
    
    except Exception as e:
        st.error(f"Failed to stop bot: {e}")
        return False

def main():
    # Header - compact
    st.markdown('<h1 class="main-title">📈 Trading Bot</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Automated Trading Dashboard</p>', unsafe_allow_html=True)
    
    # Bot status
    if st.session_state.bot_running:
        st.markdown('<div class="status-running">🟢 Running</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-stopped">🔴 Stopped</div>', unsafe_allow_html=True)
    
    # Create compact tabs
    tab1, tab2 = st.tabs(["⚙️ Config", "📊 Logs"])
    
    # Tab 1: Trading Configuration - Compact Form
    with tab1:

        
        # Stock Selection Section
        selected_stock_name = None
        selected_token  = None
        
        st.markdown('<div class="form-label">📈 Stock Selection</div>', unsafe_allow_html=True)
        search_term = st.text_input("Search Symbol ", placeholder="Type symbol name eg: RELIANCE ")

        if search_term:
            if search_term != st.session_state.last_search_term:
                st.session_state.last_search_term = search_term
                st.session_state.search_performed = False

            if not st.session_state.search_performed:
                results, message  = search_symbol(search_term)
                st.session_state.search_results = results 
                st.session_state.search_message = message 
                st.session_state.search_performed = True
            else :
                results = st.session_state.search_results
                message = st.session_state.search_message



            if results:
                st.markdown(f"<small>{message}</small>",unsafe_allow_html=True)

                for i, result in enumerate(results):
                    if st.button(f"{result['symbol']} - {result['name']}", key=f"search_result_{i}",use_container_width=True):
                        st.session_state.selected_symbol = result
                        st.session_state.last_search_term = ""
                        st.session_state.search_performed = False
                        st.rerun()
            else:
                if message:
                    st.markdown(f"<small style='color: orange;'>{message}</small>",unsafe_allow_html=True)
        else:
            # Clear search state when input is empty
            st.session_state.last_search_term = ""
            st.session_state.search_performed = False


        if st.session_state.selected_symbol:
            selected_stock_name = st.session_state.selected_symbol['symbol']
            selected_token = st.session_state.selected_symbol['token']
            
            st.success(f"Selected: {selected_stock_name} (Token: {selected_token})")
            
            if st.button("❌ Clear Selection", use_container_width=True):
                st.session_state.selected_symbol = None
                st.rerun()
        else:
            # Fallback to dropdown with default symbols
            st.markdown("**Or choose from default symbols:**")
            selected_stock_name = st.selectbox(
                "Default Stocks",
                options=list(STOCK_SYMBOLS.keys()),
                index=0,
                label_visibility="collapsed"
            )
            selected_token = STOCK_SYMBOLS[selected_stock_name]
        
        col1, col2 = st.columns([1, 1])
        with col1:
            quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=1000,
                value=30,
                step=1
            )
        
        with col2:
            st.write(" ") # spacer
            st.write(" ")
            paper_trade = st.checkbox("Paper Mode", value=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        

        # Update Configuration Button
        if st.button("💾 Update Config", use_container_width=True):
            update_env_file(selected_stock_name, selected_token, quantity, paper_trade)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Control Buttons - Grid
        st.markdown('<div class="button-grid">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Start", disabled=st.session_state.bot_running, use_container_width=True):
                if not st.session_state.bot_running:
                    # First update environment variables
                    update_env_file(selected_stock_name, selected_token, quantity, paper_trade)
                    
                    # Then start the bot
                    if start_trading_bot():
                        st.success(f"Started {selected_stock_name.split('-')[0]}")
                        st.rerun()
        
        with col2:
            if st.button("🛑 Stop", disabled=not st.session_state.bot_running, use_container_width=True):
                if st.session_state.bot_running:
                    stop_trading_bot()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Tab 2: Logs - Compact
    with tab2:
        
        # Log statistics - compact metrics
        log_content = read_log_file()
        
        if log_content and not log_content.startswith("Log file not found"):
            lines = log_content.split('\n')
            total_lines = len([line for line in lines if line.strip()])
            
            # Quick stats in 2x2 grid
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Lines", total_lines)
                if os.path.exists("live_trading_log.log"):
                    file_size = os.path.getsize("live_trading_log.log")
                    st.metric("Size", f"{file_size}B")
            with col2:
                if os.path.exists("live_trading_log.log"):
                    mod_time = os.path.getmtime("live_trading_log.log")
                    last_update = time.strftime("%H:%M:%S", time.localtime(mod_time))
                    st.metric("Updated", last_update)
                status = "Running" if st.session_state.bot_running else "Stopped"
                st.metric("Status", status)
        
        # Log display - compact height
        st.text_area(
            "Trading Logs (Auto-refresh)",
            value=log_content,
            height=300,  # Reduced height for square layout
            disabled=True
        )
        
        # Log controls - compact grid
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🧹 Clear", use_container_width=True):
                try:
                    with open("live_trading_log.log", "w") as f:
                        f.write("")
                    st.success("Cleared!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
        with col3:
            if st.button("📥 Download", use_container_width=True):
                if os.path.exists("live_trading_log.log"):
                    with open("live_trading_log.log", "r") as f:
                        st.download_button(
                            "Download Log",
                            f.read(),
                            "trading_log.txt",
                            "text/plain",
                            use_container_width=True
                        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Auto-refresh when bot is running
    if st.session_state.bot_running and not search_term:
        time.sleep(3)
        st.rerun()

if __name__ == "__main__":
    main()
