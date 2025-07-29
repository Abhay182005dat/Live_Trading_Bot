import datetime
import time
import pandas as pd
import pyotp
import ta
import joblib
from tqdm import tqdm
from SmartApi import SmartConnect
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
from dotenv import load_dotenv
import os

# ----- CREDENTIALS -----
load_dotenv()
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")
TOTP_SECRET = os.getenv("TOTP_SECRET")


# ----- CONFIG -----
SYMBOL = os.getenv("SYMBOL")
SYMBOL_TOKEN = os.getenv("SYMBOL_TOKEN")
EXCHANGE = "NSE"
INTERVAL = "FIVE_MINUTE"
START_DATE = datetime.date.today() - datetime.timedelta(days=30)
# ----- ML CONFIG -----
FUTURE_WINDOW = 3
THRESHOLD = 0.001  # 0.1% move
MODEL_FILENAME = "xgb_intraday_model.pkl"

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
def get_trading_days(start, end):
    days = []
    curr = start
    while curr <= end:
        if curr.weekday() < 5:  # Mon–Fri
            days.append(curr)
        curr += datetime.timedelta(days=1)
    return days

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
    df['label'] = 1
    df.loc[df['future_return'] > threshold, 'label'] = 2
    df.loc[df['future_return'] < -threshold, 'label'] = 0
    df.dropna(inplace=True)
    return df


# ----- MAIN -----
def main():
    print("🔐 Logging into SmartAPI...")
    obj = create_session()

    print(f"📦 Collecting 5-min {SYMBOL} data for 365 trading days...")
    trading_days = get_trading_days(START_DATE, datetime.date.today())

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
    full_df.to_csv("csv2.csv")
    
    print("🎯 Training XGBoost model...")

    full_df = full_df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Split data
    from sklearn.model_selection import train_test_split
    X = full_df[['rsi', 'macd', 'sma', 'returns']]
    y = full_df['label']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # Train model
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        objective='multi:softmax',
        num_class=3,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    model.fit(X_train, y_train)

    # Evaluate
    print("📊 Accuracy on holdout set:", model.score(X_test, y_test))

    # Save model
    joblib.dump(model, MODEL_FILENAME)
    print(f"✅ Model saved as {MODEL_FILENAME}")
    print("🚀 Ready for live trading!")


    joblib.dump(model, MODEL_FILENAME)
    print(f"✅ Model saved as {MODEL_FILENAME}")
    print("🚀 Ready for live trading!")

if __name__ == "__main__":
    main()
