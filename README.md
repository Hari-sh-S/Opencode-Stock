---
title: Investing Scanner — Put Hedge
emoji: 📊
colorFrom: red
colorTo: blue
sdk: streamlit
sdk_version: "1.41.1"
app_file: app.py
pinned: true
---

# 📊 Investing Scanner — Nifty Put Hedge Edition

An advanced backtesting platform for the Indian Stock Market with **Nifty Put Hedge** support — protect your portfolio using NIFTY ATM Weekly Puts when a regime filter triggers.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Dhan](https://img.shields.io/badge/Dhan_API-Integrated-green?style=for-the-badge)

---

## 🚀 Features

### Core Backtesting
- **Multiple Universe Support** — Nifty50, Nifty500, sectoral indices, custom lists
- **Regime Filters** — EMA, MACD, SuperTrend, Equity, Breadth-based
- **Flexible Rebalancing** — Weekly / Monthly with holiday handling
- **Uncorrelated Assets** — Allocate to Gold, Bonds on regime trigger

### 🛡️ Nifty Put Hedge (New)
- Automatically buys **NIFTY ATM Weekly Puts** when regime filter triggers
- **Delta-neutral lot sizing**: `portfolio_value / nifty_spot / (0.5 × lot_size)`
- Tradebook shows full option details: `NIFTY25000PE03JUL2025`
- Data via **Dhan Rolling Options API** (5 years of expired options data)
- VIX/Black-Scholes fallback when API unavailable
- Hedge Efficiency metrics in Performance tab

---

## ⚙️ Setup

### 1. Clone & Install

```bash
git clone https://github.com/Hari-sh-S/investing-scanner-put-hedge.git
cd investing-scanner-put-hedge
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
cp .env.example .env
```

Open `.env` and fill in:
```
DHAN_CLIENT_ID=your_client_id
DHAN_PIN=your_5_digit_pin
```

> **Note:** `DHAN_ACCESS_TOKEN` is auto-filled by the app — you don't need to set it manually.

### 3. Run Locally

```bash
streamlit run app.py
```

---

## 🔐 Dhan Authentication — Step-by-Step

The app uses **TOTP-based authentication** to get a fresh access token from Dhan.  
Your Client ID and PIN are saved once; you only enter a TOTP each session.

### First-Time Setup

1. **Open the app** → click the **🔐 Dhan Auth** tab (rightmost tab)

2. **Expand "⚙️ Saved Credentials"** section:
   - Enter your **Dhan Client ID** (10-digit number from Dhan app → Profile)
   - Enter your **Dhan PIN** (the 5-digit PIN you use to log in to Dhan)
   - Click **💾 Save Client ID & PIN**
   - ✅ You'll see a confirmation — these are saved to `.env` permanently

3. **Authenticate with TOTP**:
   - Open **Google Authenticator** (or any TOTP app) on your phone
   - Find your **Dhan** entry and note the 6-digit code
   - Type it into the **TOTP (6 digits)** box in the app
   - Click **🔑 Authenticate**
   - ✅ If successful, the access token is auto-saved to `.env`

4. **Test the connection**:
   - Click **🔍 Test Connection**
   - You should see:
     - ✅ Dhan client created
     - ✅ API Test Passed (equity data)
     - ✅ Rolling Options API works (for Put Hedge)

### Daily Use (Token Refresh)

Dhan access tokens expire daily. Each morning:

1. Go to **🔐 Dhan Auth** tab
2. Enter today's TOTP (6-digit code from your authenticator)
3. Click **🔑 Authenticate**
4. Done — backtest with Put Hedge will now work for the day

> **Tip:** If you see `DHAN_ACCESS_TOKEN not configured` error in backtests, just re-authenticate here.

### Setting Up TOTP on Dhan

If you haven't set up TOTP yet:
1. Log in to [Dhan Web](https://web.dhan.co) or the Dhan app
2. Go to **Profile → Security → 2FA Settings**
3. Enable **TOTP** and scan the QR code with Google Authenticator
4. Save the backup codes securely

---

## 🛡️ Using Nifty Put Hedge

### How It Works

When a regime filter triggers (e.g., NIFTY 50 drops below its 200 EMA):

1. The engine fetches the current NIFTY ATM Weekly Put premium from Dhan API
2. Calculates **delta-neutral lots**: buys enough puts to fully offset portfolio delta
3. Records the trade as `NIFTY25000PE03JUL2025` (with actual strike + expiry)
4. When regime recovers, closes the puts and records proceeds

### Configuration

In the **Backtest → Regime Filter** section:

| Setting | Description |
|---------|-------------|
| **Regime Action** | Select "Nifty Put Hedge" |
| **Hedge Ratio** | `1.0` = full delta neutral, `0.5` = half hedge, `1.5` = over-hedge |
| **Keep Stocks + Add Puts** | ✅ Keep stocks AND buy puts (insurance mode) |

### Understanding the Tradebook

Put hedge trades appear as:

| Date | Ticker | Action | Shares | Price | Strike | Expiry |
|------|--------|--------|--------|-------|--------|--------|
| 2024-08-05 | NIFTY24700PE08AUG2024 | BUY_HEDGE | 225 | 480.5 | 24700 | 2024-08-08 |
| 2024-08-20 | NIFTY24700PE08AUG2024 | SELL_HEDGE | 225 | 120.0 | 24700 | 2024-08-08 |

### Performance Metrics

After backtest, the **Nifty Put Hedge Analysis** section shows:
- **Hedge Events** — number of times hedge was activated
- **Hedge Cost** — total premium paid
- **Hedge Proceeds** — total received on closing
- **Hedge Net P&L** — net profit/loss from hedges
- **Hedge Efficiency** — (Proceeds − Cost) / Cost × 100%

---

## 📁 Project Structure

```
investing-scanner-put-hedge/
├── app.py                    # Main Streamlit app (5 tabs)
├── portfolio_engine.py       # Backtesting engine + put hedge logic
├── nifty_put_hedge.py        # 🛡️ Dhan Rolling Options API + delta-neutral calc
├── config.py                 # Dhan TOTP auth + credential persistence
├── scoring.py                # Strategy scoring
├── indicators.py             # Technical indicators
├── nse_fetcher.py            # NSE data utilities
├── nifty_universe.py         # Stock universe definitions
├── requirements.txt          # Dependencies
├── .env.example              # Credentials template (copy to .env)
└── README.md
```

---

## 📦 Requirements

- Python 3.8+
- **Dhan Data API subscription** (for Rolling Options historical data)
- Dhan account with TOTP/2FA enabled

Key dependencies:
```
streamlit
pandas
yfinance
plotly
dhanhq         # Dhan broker SDK
python-dotenv
requests
scipy
```

---

## 📝 License

Educational purposes only. Comply with Dhan and NSE data terms of service.

---

⭐ **Star this repo** if useful! | Based on [investing-scanner](https://github.com/Hari-sh-S/investing-scanner)
