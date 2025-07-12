import time
import datetime
import pandas as pd
import pyotp
import ta
import joblib
from SmartApi import SmartConnect
from sklearn.ensemble import RandomForestClassifier
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

PAPER_TRADE = True

# ---- CREDENTIALS ----
load_dotenv()
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP")

# ---- TRADE CONFIG ----
SYMBOL = "ADANIPOWER-EQ"
SYMBOL_TOKEN = "17388"
EXCHANGE = "NSE"
TRADE_TYPE = "INTRADAY"  # or DELIVERY
ORDER_TYPE = "MARKET"
PRODUCT_TYPE = "MIS"     # use "CNC" for DELIVERY
QUANTITY = 50             # adjust as per capital
INTERVAL = "FIVE_MINUTE"

TARGET_PCT = 0.003       # 0.3%
STOPLOSS_PCT = 0.002     # 0.2%

# ---- STATE ----
in_position = False
buy_price = None

# ---- SETUP ----
model = joblib.load("rf_intraday_model.pkl")

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
    return obj,refresh_token

def fetch_latest_candle(obj):

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    minutes = (now.minute // 5)* 5
    end_t = now.replace(minute=minutes , second=0 , microsecond = 0)
    from_time = end_t - datetime.timedelta(hours=3)

    print("From:", from_time)
    print("To  :", now)

    params = {
        "exchange": EXCHANGE,
        "symboltoken": SYMBOL_TOKEN,
        "interval": INTERVAL,
        "fromdate": from_time.strftime("%Y-%m-%d %H:%M"),
        "todate": now.strftime("%Y-%m-%d %H:%M")
    }
    candles = obj.getCandleData(params)['data']
    time.sleep(1.1)
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

def compute_features(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['macd'] = ta.trend.MACD(df['close']).macd()
    df['sma'] = ta.trend.SMAIndicator(df['close'], window=10).sma_indicator()
    df['returns'] = df['close'].pct_change()
    df = df.dropna(subset=['rsi', 'macd', 'sma', 'returns'])
    return df

def place_market_order(obj, transaction_type):
    if PAPER_TRADE:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[PAPER TRADE] {now} | {transaction_type} | Symbol: {SYMBOL} | Qty: {QUANTITY}"
        print(log_msg)
        logging.info(log_msg)
        return {"status": "simulated", "action": transaction_type}
    else:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": SYMBOL,
            "symboltoken": SYMBOL_TOKEN,
            "transactiontype": transaction_type,
            "exchange": EXCHANGE,
            "ordertype": ORDER_TYPE,
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": QUANTITY
        }
        print("Sending request with:", order_params)
 
        order = obj.placeOrder(order_params)
        print(f"✅ {transaction_type} order placed | Order ID: {order}")
        logging.info(f" REAL ORDER placed: {transaction_type} | ID: {order}")
        return order


# ---- MAIN LOOP ----
def live_trading():
    global in_position, buy_price
    obj,refresh_token = create_session()
    print("🚀 Live Trading Started for", SYMBOL)
    logging.info(f"Live Trading Started for {SYMBOL}")

    try:
        obj.getProfile(refresh_token)
    except Exception as e:
        logging.warning("🔁 Session expired. Renewing...") 
        try:
            new_session = obj.renewAccessToken(refresh_token)
            logging.info("✅ Session renewed.")
        except Exception as e:
            logging.error(f"❌ Could not renew session: {e}")
            logging.info("🔄 Attempting full login again...")
            obj, refresh_token = create_session()

    while True:

        if safety_stop_triggered():
            print("Exitted......")
            logging.warning(" Trading stopped by user (STOP file detected).")
            break

        try:
            df = fetch_latest_candle(obj)

            if df.empty:
                print("⚠️ No candle data received!")
                logging.warning("No candle data received!")
                time.sleep(60)
                continue  # Skip this loop iteration

            df = compute_features(df)

            if df.empty:
                print("⚠️ Not enough data after feature engineering!")
                logging.warning("Not enough data after feature engineering!")
                time.sleep(60)
                continue
            latest = df.iloc[-1]

            if df.empty:
                print("No data received. Retrying...")
                time.sleep(1)
                continue

            if len(df) < 6:
                print("⏳ Waiting for more data...")
                time.sleep(60)
                continue


            X = latest[['rsi', 'macd', 'sma', 'returns']].values.reshape(1, -1)
            prediction = model.predict(X)[0]
            current_price = latest['close']
            print(f"\n🕒 {latest.name} | Price: ₹{current_price:.2f} | Signal: {prediction}")

            if not in_position and prediction == 1:
                print("📈 BUY Signal Detected")
                logging.info(" BUY Signal Detected")
                place_market_order(obj, "BUY")
                buy_price = current_price
                in_position = True

            elif in_position:
                change = (current_price - buy_price) / buy_price
                if change >= TARGET_PCT:
                    print("🎯 Target hit, SELLING...")
                    logging.info(" Target hit, SELLING...")
                    place_market_order(obj, "SELL")
                    in_position = False
                elif change <= -STOPLOSS_PCT or prediction == -1:
                    print("🛑 Stop-loss hit or SELL signal, SELLING...")
                    logging.warning("Stop loss hit !")
                    place_market_order(obj, "SELL")
                    in_position = False

        except Exception as e:
            print("❌ Error:", e)
            logging.error(e)

        # Wait 5 minutes before next candle
        time.sleep(300)

if __name__ == "__main__":
    live_trading()
