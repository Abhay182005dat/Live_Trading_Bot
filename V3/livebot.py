import time
import datetime
import pandas as pd
import pyotp
import ta
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from SmartApi import SmartConnect
import pytz
import logging 
import os
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("live_trading_log.log"),
        logging.StreamHandler()
    ]
)

PAPER_TRADE = False

# ---- CREDENTIALS ----
load_dotenv()
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")

# ---- TRADE CONFIG ----
# SYMBOLS = [('HINDUNILVR-EQ','1394')]  # Using same as backtest
EXCHANGE = "NSE"
INTERVAL = "FIVE_MINUTE"
# QUANTITY = 30  # Same as backtest QTY
BROKERAGE_PER_TRADE = 20
# LOT_SIZE = 60  # Same as backtest

# ---- TRADE CONFIG FROM ENVIRONMENT ----
TRADING_SYMBOL = os.getenv("TRADING_SYMBOL")
TRADING_TOKEN = os.getenv("TRADING_TOKEN")
QUANTITY = int(os.getenv("TRADING_QUANTITY", "30"))
PAPER_TRADE = os.getenv("PAPER_TRADE", "True").lower() == "true"

if not TRADING_SYMBOL or not TRADING_TOKEN:
    logging.error("TRADING_SYMBOL and TRADING_TOKEN must be set via Streamlit interface")
    exit(1)

required_vars = [API_KEY, USER_ID, PASSWORD, TOTP_SECRET]
if not all(required_vars):
    logging.error("Missing required API credentials in environment variables")
    exit(1)


# ---- STRATEGY CONFIG ----
TARGET_PROFIT_PCT = 1.8
STOP_LOSS_PCT = 0.5
MAX_DAILY_TRADES = 2

# ---- STATE ----
in_position = False
buy_price = None
entry_time = None
daily_trade_count = 0
prev_ema5 = None
prev_ema20 = None
prev_close = None
last_reset_date = None

def safety_stop_triggered():
    try:
        with open("stop.txt", "r") as f:
            return "STOP" in f.read()
    except FileNotFoundError:
        return False

def create_session():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    obj = SmartConnect(api_key=API_KEY)
    session = obj.generateSession(USER_ID, PASSWORD, totp)
    refresh_token = session['data']['refreshToken']
    return obj, refresh_token

def fetch_accumulated_data(obj, current_date, symbol, token, days_back=25):
    """Fetch accumulated data for proper EMA calculation - same as backtest"""
    all_data = []
    successful_days = 0
    
    for i in range(days_back, -1, -1):
        date = current_date - datetime.timedelta(days=i)
        if date.weekday() >= 5:  # Skip weekends
            continue
            
        logging.info(f"Fetching data for {date.strftime('%Y-%m-%d')} {symbol}...")
        df_day = fetch_intraday_data(obj, date, symbol, token)
        if not df_day.empty:
            all_data.append(df_day)
            successful_days += 1
            logging.info(f"{len(df_day)} candles")
        else:
            logging.info("No data")
        
        time.sleep(0.5)
    
    if not all_data:
        return pd.DataFrame()
    
    combined_df = pd.concat(all_data, axis=0)
    combined_df = combined_df.sort_index()
    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    
    logging.info(f"Total accumulated: {len(combined_df)} candles from {successful_days} days")
    return combined_df
def wait_for_next_5min_candle():
    """Wait until the next 5-minute candle formation time"""
    now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
    current_minute = now.minute
    current_second = now.second
    
    # Calculate minutes past the latest 5-minute interval
    minutes_past_5 = current_minute % 5
    
    # Calculate seconds to wait until the next 5-minute mark
    if minutes_past_5 == 0 and current_second == 0:
        # Already at perfect 5-minute mark
        return
    
    seconds_to_wait = (5 - minutes_past_5) * 60 - current_second
    
    next_candle_time = now + datetime.timedelta(seconds=seconds_to_wait)
    
    logging.info(f"Current time: {now.strftime('%H:%M:%S')}")
    logging.info(f" Next 5-min candle at: {next_candle_time.strftime('%H:%M:%S')}")
    logging.info(f"Waiting {seconds_to_wait} seconds...")
    
    time.sleep(seconds_to_wait)
    logging.info("Synchronized with 5-minute candles!")

def fetch_intraday_data(obj, date, symbol, token):
    """Fetch intraday data for a specific date - same as backtest"""
    start_time = datetime.datetime.combine(date, datetime.time(9, 15))
    end_time = datetime.datetime.combine(date, datetime.time(15, 30))
    params = {
        "exchange": EXCHANGE,
        "symboltoken": token,
        "interval": INTERVAL,
        "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
        "todate": end_time.strftime("%Y-%m-%d %H:%M")
    }
    try:
        candles = obj.getCandleData(params)['data']
        df = pd.DataFrame(candles, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logging.info(f"Error fetching data for {date} {symbol}: {e}")
        return pd.DataFrame()

def compute_features(df):
    """Compute features exactly like backtest"""
    if len(df) < 200:
        return pd.DataFrame()

    # Calculate ADX and directional indicators
    adx_indicator = ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx14'] = adx_indicator.adx()
    df['di_plus'] = adx_indicator.adx_pos()
    df['di_minus'] = adx_indicator.adx_neg()
    
    # Calculate EMAs
    df['ema5'] = EMAIndicator(df['close'], window=5).ema_indicator()
    df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    df['ema50'] = EMAIndicator(df['close'], window=50).ema_indicator()
    df['ema100'] = EMAIndicator(df['close'], window=100).ema_indicator()
    df['ema200'] = EMAIndicator(df['close'], window=200).ema_indicator()
    df['ema9'] = EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema21'] = EMAIndicator(df['close'], window=21).ema_indicator()
    
    # Calculate RSI(14)
    df['rsi14'] = RSIIndicator(close=df['close'], window=14).rsi()
    
    # Calculate % difference from close price for convergence checks
    df['ema5_diff_pct'] = abs(df['ema5'] - df['close']) / df['close'] * 100
    df['ema20_diff_pct'] = abs(df['ema20'] - df['close']) / df['close'] * 100
    df['ema50_diff_pct'] = abs(df['ema50'] - df['close']) / df['close'] * 100
    df['ema100_diff_pct'] = abs(df['ema100'] - df['close']) / df['close'] * 100
    df['ema200_diff_pct'] = abs(df['ema200'] - df['close']) / df['close'] * 100
    
    # EMA convergence flag
    df['ema_convergence'] = (
        (df['ema5_diff_pct'] <= 3.0) &
        (df['ema20_diff_pct'] <= 3.0) &
        (df['ema50_diff_pct'] <= 3.0) &
        (df['ema100_diff_pct'] <= 3.0) &
        (df['ema200_diff_pct'] <= 3.0)
    )
    
    df.dropna(inplace=True)
    return df

def place_market_order(obj, transaction_type, symbol, token):
    """Place market order with logging"""
    if PAPER_TRADE:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[PAPER TRADE] {now} | {transaction_type} | Symbol: {symbol} | Qty: {QUANTITY}"
        print(log_msg)
        logging.info(log_msg)
        return {"status": "simulated", "action": transaction_type}
    else:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": EXCHANGE,
            "ordertype": "MARKET",
            "producttype": "MIS",
            "duration": "DAY",
            "quantity": QUANTITY
        }
        
        order = obj.placeOrder(order_params)
        print(f"✅ {transaction_type} order placed | Order ID: {order}")
        logging.info(f"REAL ORDER placed: {transaction_type} | ID: {order}")
        return order

def check_entry_signal(current_row, prev_row):
    """Check entry condition exactly like backtest"""
    if prev_row is None:
        return False
    
    current_close = current_row['close']
    current_rsi = current_row['rsi14']
    current_ema5 = current_row['ema5']
    current_ema20 = current_row['ema20']
    current_ema50 = current_row['ema50']
    
    prev_close = prev_row['close']
    prev_ema20 = prev_row['ema20']
    
    # Entry condition from backtest
    entry_condition = (
        ((current_rsi > 20 and current_rsi <= 30) or 
         (current_close > current_ema20 and prev_close <= prev_ema20)) and
        ((current_ema5 > current_ema20) and 
        (current_close > current_ema50))
    )# 
    
    return entry_condition

def check_exit_signal(current_row, prev_row, entry_price, current_time):
    """Check exit conditions exactly like backtest"""
    global prev_ema5, prev_ema20
    
    current_close = current_row['close']
    current_rsi = current_row['rsi14']
    current_ema5 = current_row['ema5']
    current_ema20 = current_row['ema20']
    
    # Calculate profit percentage
    profit_pct = ((current_close - entry_price) / entry_price) * 100
    
    # EMA cross down condition
    ema_cross_down = False
    if prev_ema5 is not None and prev_ema20 is not None:
        ema_cross_down = (prev_ema5 >= prev_ema20 and current_ema5 < current_ema20)
    
    # Exit conditions from backtest
    exit_reasons = []
    
    if profit_pct >= TARGET_PROFIT_PCT:
        exit_reasons.append("1.8% Profit Target")
    elif profit_pct <= -STOP_LOSS_PCT:
        exit_reasons.append("Stop Loss")
    elif ema_cross_down and profit_pct > 0:
        exit_reasons.append("EMA Cross Down")
    elif current_rsi >= 70:
        exit_reasons.append("RSI 70+")
    elif current_time >= datetime.time(15, 0):
        exit_reasons.append("EOD Exit")
    
    return exit_reasons, profit_pct

def reset_daily_counters():
    """Reset daily trade count"""
    global daily_trade_count, last_reset_date
    today = datetime.date.today()
    if last_reset_date != today:
        daily_trade_count = 0
        last_reset_date = today
        logging.info(f"Daily counters reset for {today}")

def live_trading():
    """Main live trading loop with backtest strategy"""
    global in_position, buy_price, entry_time, daily_trade_count
    global prev_ema5, prev_ema20, prev_close
    
    obj, refresh_token = create_session()
    symbol = TRADING_SYMBOL
    token = TRADING_TOKEN
    
    print(f"🚀 Live Trading Started for {symbol}")
    logging.info(f"Live Trading Started for {symbol} (QTY : {QUANTITY},paper trade : {PAPER_TRADE})")

    prev_row = None
    
    while True:
        if safety_stop_triggered():
            print("Exiting...")
            logging.warning("Trading stopped by user (STOP file detected).")
            break
        
        # Check session validity
        try:
            obj.getProfile(refresh_token)
        except Exception as e:
            logging.warning("🔁 Session expired. Renewing...")
            try:
                new_session = obj.renewAccessToken(refresh_token)
                logging.info("Session renewed.")
            except Exception as e:
                logging.error(f"Could not renew session: {e}")
                obj, refresh_token = create_session()
        
        # Reset daily counters if new day
        reset_daily_counters()
        
        # Check trading hours (9:15 AM to 2:30 PM IST)
        ist_now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = ist_now.time()
        
        if current_time < datetime.time(9, 15) or current_time >= datetime.time(15, 30):
            logging.info("Market closed. Sleeping for 60s...")
            time.sleep(60)
            continue
        
        # Skip trading after 2:30 PM for new entries
        if current_time >= datetime.time(14, 30) and not in_position:
            logging.info("No new entries after 2:30 PM. Sleeping for 60s...")
            
            time.sleep(60)
            continue
        
        try:
            # Get accumulated data for proper EMA calculation
            current_date = ist_now.date()
            df = fetch_accumulated_data(obj, current_date, symbol, token, days_back=5)
            
            if df.empty or len(df) < 200:
                print("⚠️ Not enough accumulated data for EMAs")
                logging.warning("Not enough accumulated data for EMAs")
                time.sleep(60)
                continue
            
            df = compute_features(df)
            
            if df.empty:
                print("⚠️ No computed features")
                logging.warning("No computed features")
                time.sleep(60)
                continue
            
            # Get current and previous data points
            current_row = df.iloc[-2]
            if len(df) >= 3:
                prev_row = df.iloc[-3]
            
            current_price = current_row['close']
            current_rsi = current_row['rsi14']
            
            logging.info(f"\n[{ist_now.strftime('%H:%M:%S')}] Price: INR {current_price:.2f} | "
                  f"RSI: {current_rsi:.1f} | "
                  f"EMA5: {current_row['ema5']:.2f} | "
                  f"EMA20: {current_row['ema20']:.2f} | "
                  f"Position: {'YES' if in_position else 'NO'} | "
                  f"Daily Trades: {daily_trade_count}")
            
            # Entry Logic
            if not in_position and daily_trade_count < MAX_DAILY_TRADES:
                if check_entry_signal(current_row, prev_row):
                    print(f"📈 BUY Signal Detected at {current_price:.2f}")
                    logging.info(f"BUY Signal: RSI={current_rsi:.1f}, EMA5={current_row['ema5']:.2f}, EMA20={current_row['ema20']:.2f}")
                    
                    place_market_order(obj, "BUY", symbol, token)
                    buy_price = current_price
                    entry_time = ist_now
                    in_position = True
                    daily_trade_count += 1
            
            # Exit Logic
            elif in_position:
                exit_reasons, profit_pct = check_exit_signal(current_row, prev_row, buy_price, current_time)
                
                print(f"📊 Position P&L: {profit_pct:.2f}%")
                
                if exit_reasons:
                    exit_reason = exit_reasons[0]  # Take first reason
                    profit_amount = (current_price - buy_price) * QUANTITY - BROKERAGE_PER_TRADE
                    
                    print(f"🔴 SELL Signal: {exit_reason} at {current_price:.2f} | P&L: ₹{profit_amount:.2f}")
                    logging.info(f"SELL Signal: {exit_reason} | Entry: INR {buy_price:.2f} | Exit: INR {current_price:.2f} | P&L: INR {profit_amount:.2f}")
                    
                    place_market_order(obj, "SELL", symbol, token)
                    in_position = False
                    buy_price = None
                    entry_time = None
            
            # Update previous values for next iteration
            prev_ema5 = current_row['ema5']
            prev_ema20 = current_row['ema20']
            prev_close = current_price
            #prev_row = current_row
            
        except Exception as e:
            print(f"❌ Error: {e}")
            logging.error(f"Error in main loop: {e}")
        
        # Forced exit at market close
        if ist_now.hour == 15 and ist_now.minute >= 29:
            if in_position:
                final_price = current_row['close']
                profit_amount = (final_price - buy_price) * QUANTITY - BROKERAGE_PER_TRADE
                print(f"⏹️ Forced Exit at Market Close | Final Price: ₹{final_price:.2f} | P&L: ₹{profit_amount:.2f}")
                logging.warning(f"Forced Exit at Market Close | P&L: ₹{profit_amount:.2f}")
                place_market_order(obj, "SELL", symbol, token)
                in_position = False
                buy_price = None
                entry_time = None
            break
        
        # Wait 5 minutes before next iteration
        print("Waiting for next 5-minute candle ...")
        logging.info("Waiting for next 5-minute candle ...")

        wait_for_next_5min_candle()

if __name__ == "__main__":
    live_trading()
