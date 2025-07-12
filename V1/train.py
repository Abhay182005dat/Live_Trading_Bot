import datetime
import time
import pandas as pd
import pyotp
import ta
import joblib
from tqdm import tqdm
from SmartApi import SmartConnect
from sklearn.ensemble import RandomForestClassifier
import os
# ----- CREDENTIALS -----
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP")

# ----- CONFIG -----
SYMBOL = "ADANIPOWER-EQ"
SYMBOL_TOKEN = "17388"
EXCHANGE = "NSE"
INTERVAL = "FIVE_MINUTE"
NUM_DAYS = 45  # ⬅️ Training data range

# ----- ML CONFIG -----
FUTURE_WINDOW = 3
THRESHOLD = 0.001  # 0.1% move
MODEL_FILENAME = "rf_intraday_model.pkl"

# ----- SmartAPI Login -----
def create_session():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    obj = SmartConnect(api_key=API_KEY)
    session = obj.generateSession(USER_ID, PASSWORD, totp)
    return obj

# ----- Fetch intraday data for 1 day -----
def fetch_day_candles(obj, date):
    start_time = datetime.datetime.combine(date, datetime.time(9, 15))
    end_time = datetime.datetime.combine(date, datetime.time(15, 30))

    params = {
        "exchange": EXCHANGE,
        "symboltoken": SYMBOL_TOKEN,
        "interval": INTERVAL,
        "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
        "todate": end_time.strftime("%Y-%m-%d %H:%M")
    }

    try:
        candles = obj.getCandleData(params)['data']
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except:
        return pd.DataFrame()

# ----- Generate all past trading days (excluding weekends) -----
def get_past_trading_days(n):
    today = datetime.datetime.today()
    days = []
    while len(days) < n:
        today -= datetime.timedelta(days=1)
        if today.weekday() < 5:  # Mon–Fri only
            days.append(today.date())
    return days[::-1]

# ----- Feature Engineering -----
def add_features(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['macd'] = ta.trend.MACD(df['close']).macd()
    df['sma'] = ta.trend.SMAIndicator(df['close'], window=10).sma_indicator()
    df['returns'] = df['close'].pct_change()
    df.dropna(inplace=True)
    return df

# ----- Labeling -----
def label_data_intraday(df, future_window=3, threshold=0.001):
    df['future_price'] = df['close'].shift(-future_window)
    df['future_return'] = (df['future_price'] - df['close']) / df['close']
    df['label'] = 0
    df.loc[df['future_return'] > threshold, 'label'] = 1
    df.loc[df['future_return'] < -threshold, 'label'] = -1
    df.dropna(inplace=True)
    return df

# ----- Train Model -----
def train_model(df):
    X = df[['rsi', 'macd', 'sma', 'returns']]
    y = df['label']
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    return model

# ----- MAIN -----
def main():
    print("🔐 Logging into SmartAPI...")
    obj = create_session()

    print(f"📦 Collecting 5-min RELIANCE data for {NUM_DAYS} trading days...")
    trading_days = get_past_trading_days(NUM_DAYS)
    all_data = []

    for date in tqdm(trading_days):
        df = fetch_day_candles(obj, date)
        if not df.empty:
            all_data.append(df)
        time.sleep(1.1)  # avoid rate limits

    full_df = pd.concat(all_data)
    print("✅ Data shape:", full_df.shape)

    print("🧠 Adding features...")
    full_df = add_features(full_df)

    print("🏷️ Labeling...")
    full_df = label_data_intraday(full_df, FUTURE_WINDOW, THRESHOLD)

    print("🎯 Training Random Forest model...")
    model = train_model(full_df)

    joblib.dump(model, MODEL_FILENAME)
    print(f"✅ Model saved as {MODEL_FILENAME}")
    print("🚀 Ready for live trading!")

if __name__ == "__main__":
    main()
