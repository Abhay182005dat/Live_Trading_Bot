# Smart_Trading_Bot

This is a basic-intermediate level project where I am exploring ways to trade stocks using predictions based on Machine Learning and Deep Learning, combined with algorithmic trading strategies.

# Live Trading Bot

A basic-intermediate level project exploring automated stock trading using predictions from Machine Learning and Deep Learning models, combined with traditional technical analysis.

---

## Project Overview

This repository contains an automated stock trading bot leveraging the power of machine learning and deep learning to generate trading signals. The bot integrates technical indicators and predictive models to make informed decisions for live or paper trading.

---

## Key Features

- Implementation of ML and DL models for price prediction
- Use of technical indicators like EMA, RSI, MACD for enhanced signals
- Supports live trading and paper trading modes
- Backtested on 5 years of data for version 3 (still in development, experimenting with new strategies)
- Modular strategy design for easy experimentation and customization
- Risk management tools including stop loss and take profit parameters

---

## Installation & Setup

1. **Clone the repository**:

```bash
git clone <your-repo-url>
cd Smart_Trading_Bot
```
2. Install dependencies:

```
pip install -r requirements.txt
```
3. Set up environment variables:
```
API_KEY=your_api_key
USER_ID=your_user_id
PASSWORD=your_password
TOTP_SECRET=your_totp_secret
TRADING_SYMBOL=your_trading_symbol
TRADING_TOKEN=your_trading_token
TRADING_QUANTITY=30
PAPER_TRADE=True

```
4. Run the app using Streamlit:
```
streamlit run main.py

```
