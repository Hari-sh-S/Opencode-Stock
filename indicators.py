import pandas as pd
import ta
import numpy as np

class IndicatorLibrary:
    @staticmethod
    def add_sma(df, window, column='Close'):
        col_data = df[column] if not isinstance(df[column], pd.DataFrame) else df[column].squeeze()
        df[f'SMA_{window}'] = ta.trend.sma_indicator(col_data, window=window)
        return df

    @staticmethod
    def add_ema(df, window, column='Close'):
        col_data = df[column] if not isinstance(df[column], pd.DataFrame) else df[column].squeeze()
        df[f'EMA_{window}'] = ta.trend.ema_indicator(col_data, window=window)
        return df

    @staticmethod
    def add_rsi(df, window=14, column='Close'):
        col_data = df[column] if not isinstance(df[column], pd.DataFrame) else df[column].squeeze()
        df[f'RSI_{window}'] = ta.momentum.rsi(col_data, window=window)
        return df

    @staticmethod
    def add_macd(df, window_slow=26, window_fast=12, window_sign=9, column='Close'):
        col_data = df[column] if not isinstance(df[column], pd.DataFrame) else df[column].squeeze()
        macd = ta.trend.MACD(col_data, window_slow=window_slow, window_fast=window_fast, window_sign=window_sign)
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Diff'] = macd.macd_diff()
        return df

    @staticmethod
    def add_bollinger_bands(df, window=20, window_dev=2, column='Close'):
        col_data = df[column] if not isinstance(df[column], pd.DataFrame) else df[column].squeeze()
        indicator_bb = ta.volatility.BollingerBands(close=col_data, window=window, window_dev=window_dev)
        df['BB_High'] = indicator_bb.bollinger_hband()
        df['BB_Low'] = indicator_bb.bollinger_lband()
        df['BB_Mid'] = indicator_bb.bollinger_mavg()
        return df

    @staticmethod
    def add_supertrend(df, period=7, multiplier=3):
        """Optimized SuperTrend using vectorized NumPy operations."""
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        
        # ATR calculation (vectorized)
        tr = np.maximum.reduce([
            (high - low).values,
            np.abs((high - close.shift(1)).values),
            np.abs((low - close.shift(1)).values)
        ])
        atr = pd.Series(tr, index=df.index).ewm(span=period).mean()
        
        hl2 = (high + low) / 2
        upper = hl2 + (multiplier * atr)
        lower = hl2 - (multiplier * atr)
        
        # Vectorized SuperTrend using NumPy
        supertrend = _compute_supertrend_fast(close.values, upper.values, lower.values)
        
        df['Supertrend'] = supertrend
        df['Supertrend_Signal'] = np.where(close.values > supertrend, 1, -1)
        return df

    @staticmethod
    def add_momentum_volatility_metrics(df, required_periods=None):
        """
        FAST vectorized Performance and Risk metrics for multiple timeframes.
        Uses pure NumPy operations for maximum speed.
        
        Args:
            df: DataFrame with OHLCV data
            required_periods: Optional set of (months, metric_type) tuples.
                             If None, calculates default periods (1, 3, 6, 9, 12 months)
        """
        if isinstance(df, pd.Series):
            raise ValueError("Input must be a DataFrame, not a Series")
        
        if 'Close' not in df.columns:
            raise ValueError("DataFrame must have a 'Close' column")
        
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        
        # Default periods (val, unit)
        active_periods = {(1, 'Month'), (3, 'Month'), (6, 'Month'), (9, 'Month'), (12, 'Month')}
        
        # Add any additional required periods
        if required_periods:
            for item in required_periods:
                # Handle legacy format (months, type) or new format (val, unit, type)
                if len(item) == 3:
                    val, unit, _ = item
                    active_periods.add((val, unit))
                elif len(item) == 2:
                    val, _ = item
                    active_periods.add((val, 'Month'))
        
        # Convert periods to trading days
        # Month ~ 21 days, Week ~ 5 days
        periods = {}
        for val, unit in active_periods:
            if unit == 'Month':
                name = '1 Year' if val == 12 else f'{val} Month'
                window = val * 21
            elif unit == 'Week':
                name = f'{val} Week'
                window = val * 5
            else:
                continue
                
            periods[name] = window
        
        # Pre-calculate returns once 
        daily_returns = close.pct_change()
        if 'Daily_Returns' not in df.columns:
            df['Daily_Returns'] = daily_returns
        
        for name, window in periods.items():
            # 1. Performance - vectorized
            col_name = f'{name} Performance'
            if col_name not in df.columns:
                df[col_name] = close.pct_change(periods=window)
            
            # 2. Volatility - vectorized
            col_name = f'{name} Volatility'
            if col_name not in df.columns:
                df[col_name] = daily_returns.rolling(window).std() * np.sqrt(252)
            
            # 2b. Downside Volatility - only negative returns
            col_name = f'{name} Downside Volatility'
            if col_name not in df.columns:
                downside = daily_returns.clip(upper=0)
                df[col_name] = downside.rolling(window).std() * np.sqrt(252)
            
            # 3. Max Drawdown - vectorized
            col_name = f'{name} Max Drawdown'
            if col_name not in df.columns:
                rolling_max = close.rolling(window).max()
                drawdown = (close - rolling_max) / rolling_max
                df[col_name] = drawdown.rolling(window).min()
            
            # 4. Sharpe - vectorized
            col_name = f'{name} Sharpe'
            if col_name not in df.columns:
                mean_ret = daily_returns.rolling(window).mean()
                std_ret = daily_returns.rolling(window).std()
                sharpe = (mean_ret / std_ret) * np.sqrt(252)
                df[col_name] = sharpe.replace([np.inf, -np.inf], 0)
            
            # 5. Sortino - vectorized
            col_name = f'{name} Sortino'
            if col_name not in df.columns:
                downside = daily_returns.clip(upper=0)
                mean_ret = daily_returns.rolling(window).mean()
                downside_std = downside.rolling(window).std()
                sortino = (mean_ret / downside_std) * np.sqrt(252)
                df[col_name] = sortino.replace([np.inf, -np.inf], 0)
            
            # 6. Calmar - vectorized
            col_name = f'{name} Calmar'
            if col_name not in df.columns:
                perf_col = f'{name} Performance'
                dd_col = f'{name} Max Drawdown'
                calmar = df[perf_col] / df[dd_col].abs()
                df[col_name] = calmar.replace([np.inf, -np.inf], 0)
            
            # 7. % Positive Days - percentage of days with positive returns
            col_name = f'{name} Positive Days'
            if col_name not in df.columns:
                positive_mask = (daily_returns > 0).astype(float)
                df[col_name] = positive_mask.rolling(window).mean()
            
            # 8. % Negative Days - percentage of days with negative returns
            col_name = f'{name} Negative Days'
            if col_name not in df.columns:
                negative_mask = (daily_returns < 0).astype(float)
                df[col_name] = negative_mask.rolling(window).mean()
            
            # 9. % Distance From High - (rolling_high - close) / close
            # Shows how far below the N-period high the stock is (0 = at high, positive = below high)
            col_name = f'{name} Distance From High'
            if col_name not in df.columns:
                rolling_high = close.rolling(window).max()
                df[col_name] = (rolling_high - close) / close
            
            # 10. % Distance From Low - (close - rolling_low) / rolling_low
            # Shows how far above the N-period low the stock is (0 = at low, positive = above low)
            col_name = f'{name} Distance From Low'
            if col_name not in df.columns:
                rolling_low = close.rolling(window).min()
                distance_from_low = (close - rolling_low) / rolling_low
                df[col_name] = distance_from_low.replace([np.inf, -np.inf], 0)
        
        df.fillna(0, inplace=True)
        return df
    
    @staticmethod
    def add_regime_filters(df, supertrend_period=7, supertrend_multiplier=3, sma_period=50, ema_period=68):
        """Optimized regime indicators - only calculate what's needed.
        
        Args:
            df: DataFrame with OHLCV data
            supertrend_period: ATR period for SuperTrend (default 7)
            supertrend_multiplier: Band multiplier for SuperTrend (default 3)
            sma_period: Period for SMA regime filter (default 50)
            ema_period: Period for EMA regime filter (default 68)
        """
        if isinstance(df, pd.Series):
            raise ValueError("Input must be a DataFrame, not a Series")
        
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        
        # Prepare df_temp for resampling (needs DatetimeIndex)
        if df.index.name != 'Date':
            df_temp = df.copy()
            if 'Date' in df.columns:
                df_temp = df_temp.set_index('Date')
        else:
            df_temp = df
        
        # 1a. SMA - Daily (1D)
        df[f'SMA_{sma_period}'] = close.rolling(sma_period).mean()
        df['SMA_1D'] = df[f'SMA_{sma_period}']
        df['SMA_1D_Direction'] = np.where(close > df['SMA_1D'], 'BUY', 'SELL')
        
        # 1b. SMA - Weekly (1W)
        try:
            weekly_close = df_temp['Close'].resample('W').last().dropna()
            if len(weekly_close) >= sma_period:
                weekly_sma = weekly_close.rolling(sma_period).mean()
                df['SMA_1W'] = weekly_sma.reindex(df_temp.index, method='ffill')
                df['SMA_1W_Direction'] = np.where(close > df['SMA_1W'], 'BUY', 'SELL')
            else:
                df['SMA_1W'] = df['SMA_1D']
                df['SMA_1W_Direction'] = df['SMA_1D_Direction']
        except Exception:
            df['SMA_1W'] = df['SMA_1D']
            df['SMA_1W_Direction'] = df['SMA_1D_Direction']
        
        # 1c. SMA - Monthly (1M)
        try:
            monthly_close = df_temp['Close'].resample('ME').last().dropna()
            if len(monthly_close) >= min(sma_period, 12):  # Use smaller period for monthly
                monthly_sma = monthly_close.rolling(min(sma_period, 12)).mean()
                df['SMA_1M'] = monthly_sma.reindex(df_temp.index, method='ffill')
                df['SMA_1M_Direction'] = np.where(close > df['SMA_1M'], 'BUY', 'SELL')
            else:
                df['SMA_1M'] = df['SMA_1D']
                df['SMA_1M_Direction'] = df['SMA_1D_Direction']
        except Exception:
            df['SMA_1M'] = df['SMA_1D']
            df['SMA_1M_Direction'] = df['SMA_1D_Direction']
        
        # 2a. EMA - Daily (1D)
        for period in [34, 68, 100, 150, 200]:
            df[f'EMA_{period}'] = close.ewm(span=period, adjust=False).mean()
        df['EMA_1D'] = close.ewm(span=ema_period, adjust=False).mean()
        df['EMA_1D_Direction'] = np.where(close > df['EMA_1D'], 'BUY', 'SELL')
        
        # 2b. EMA - Weekly (1W)
        try:
            weekly_close = df_temp['Close'].resample('W').last().dropna()
            if len(weekly_close) >= ema_period:
                weekly_ema = weekly_close.ewm(span=ema_period, adjust=False).mean()
                df['EMA_1W'] = weekly_ema.reindex(df_temp.index, method='ffill')
                df['EMA_1W_Direction'] = np.where(close > df['EMA_1W'], 'BUY', 'SELL')
            else:
                df['EMA_1W'] = df['EMA_1D']
                df['EMA_1W_Direction'] = df['EMA_1D_Direction']
        except Exception:
            df['EMA_1W'] = df['EMA_1D']
            df['EMA_1W_Direction'] = df['EMA_1D_Direction']
        
        # 2c. EMA - Monthly (1M)
        try:
            monthly_close = df_temp['Close'].resample('ME').last().dropna()
            if len(monthly_close) >= min(ema_period, 12):  # Use smaller period for monthly
                monthly_ema = monthly_close.ewm(span=min(ema_period, 12), adjust=False).mean()
                df['EMA_1M'] = monthly_ema.reindex(df_temp.index, method='ffill')
                df['EMA_1M_Direction'] = np.where(close > df['EMA_1M'], 'BUY', 'SELL')
            else:
                df['EMA_1M'] = df['EMA_1D']
                df['EMA_1M_Direction'] = df['EMA_1D_Direction']
        except Exception:
            df['EMA_1M'] = df['EMA_1D']
            df['EMA_1M_Direction'] = df['EMA_1D_Direction']
        
        # 3. MACD (single calculation)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Diff'] = df['MACD'] - df['MACD_Signal']
        
        # 3. SuperTrend - Daily (1D), Weekly (1W), Monthly (1M) versions
        # Using user-configurable period and multiplier
        st_period = supertrend_period
        st_mult = supertrend_multiplier
        
        # 3a. SuperTrend 1D (Daily)
        tr = np.maximum.reduce([
            (high - low).values,
            np.abs((high - close.shift(1)).fillna(0).values),
            np.abs((low - close.shift(1)).fillna(0).values)
        ])
        atr = pd.Series(tr, index=df.index).ewm(span=st_period).mean()
        hl2 = (high + low) / 2
        upper = hl2 + (st_mult * atr)
        lower = hl2 - (st_mult * atr)
        supertrend = _compute_supertrend_fast(close.values, upper.values, lower.values)
        df['Supertrend'] = supertrend
        df['Supertrend_Direction'] = np.where(close.values > supertrend, 'BUY', 'SELL')
        # Alias for 1D
        df['Supertrend_1D'] = supertrend
        df['Supertrend_1D_Direction'] = df['Supertrend_Direction']
        
        # 3b. SuperTrend 1W (Weekly)
        # Resample to weekly OHLC
        if df.index.name != 'Date':
            df_temp = df.copy()
            if 'Date' in df.columns:
                df_temp = df_temp.set_index('Date')
        else:
            df_temp = df
        
        try:
            weekly_ohlc = df_temp[['Open', 'High', 'Low', 'Close']].resample('W').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last'
            }).dropna()
            
            if len(weekly_ohlc) >= 10:
                w_high = weekly_ohlc['High']
                w_low = weekly_ohlc['Low']
                w_close = weekly_ohlc['Close']
                
                w_tr = np.maximum.reduce([
                    (w_high - w_low).values,
                    np.abs((w_high - w_close.shift(1)).fillna(0).values),
                    np.abs((w_low - w_close.shift(1)).fillna(0).values)
                ])
                w_atr = pd.Series(w_tr, index=weekly_ohlc.index).ewm(span=st_period).mean()
                w_hl2 = (w_high + w_low) / 2
                w_upper = w_hl2 + (st_mult * w_atr)
                w_lower = w_hl2 - (st_mult * w_atr)
                w_supertrend = _compute_supertrend_fast(w_close.values, w_upper.values, w_lower.values)
                weekly_ohlc['Supertrend_1W'] = w_supertrend
                weekly_ohlc['Supertrend_1W_Direction'] = np.where(w_close.values > w_supertrend, 'BUY', 'SELL')
                
                # Forward-fill to daily
                df['Supertrend_1W'] = weekly_ohlc['Supertrend_1W'].reindex(df_temp.index, method='ffill')
                df['Supertrend_1W_Direction'] = weekly_ohlc['Supertrend_1W_Direction'].reindex(df_temp.index, method='ffill')
            else:
                df['Supertrend_1W'] = df['Supertrend']
                df['Supertrend_1W_Direction'] = df['Supertrend_Direction']
        except Exception:
            df['Supertrend_1W'] = df['Supertrend']
            df['Supertrend_1W_Direction'] = df['Supertrend_Direction']
        
        # 3c. SuperTrend 1M (Monthly)
        try:
            monthly_ohlc = df_temp[['Open', 'High', 'Low', 'Close']].resample('ME').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last'
            }).dropna()
            
            if len(monthly_ohlc) >= 10:
                m_high = monthly_ohlc['High']
                m_low = monthly_ohlc['Low']
                m_close = monthly_ohlc['Close']
                
                m_tr = np.maximum.reduce([
                    (m_high - m_low).values,
                    np.abs((m_high - m_close.shift(1)).fillna(0).values),
                    np.abs((m_low - m_close.shift(1)).fillna(0).values)
                ])
                m_atr = pd.Series(m_tr, index=monthly_ohlc.index).ewm(span=st_period).mean()
                m_hl2 = (m_high + m_low) / 2
                m_upper = m_hl2 + (st_mult * m_atr)
                m_lower = m_hl2 - (st_mult * m_atr)
                m_supertrend = _compute_supertrend_fast(m_close.values, m_upper.values, m_lower.values)
                monthly_ohlc['Supertrend_1M'] = m_supertrend
                monthly_ohlc['Supertrend_1M_Direction'] = np.where(m_close.values > m_supertrend, 'BUY', 'SELL')
                
                # Forward-fill to daily
                df['Supertrend_1M'] = monthly_ohlc['Supertrend_1M'].reindex(df_temp.index, method='ffill')
                df['Supertrend_1M_Direction'] = monthly_ohlc['Supertrend_1M_Direction'].reindex(df_temp.index, method='ffill')
            else:
                df['Supertrend_1M'] = df['Supertrend']
                df['Supertrend_1M_Direction'] = df['Supertrend_Direction']
        except Exception:
            df['Supertrend_1M'] = df['Supertrend']
            df['Supertrend_1M_Direction'] = df['Supertrend_Direction']
        
        # 4. SMA and trend indicators
        df['SMA_200'] = close.rolling(200).mean()
        df['Above_SMA_200'] = (close > df['SMA_200']).astype(int)
        df['52W_High'] = close.rolling(252).max()
        df['52W_Low'] = close.rolling(252).min()
        df['Near_52W_High'] = ((close / df['52W_High']) > 0.95).astype(int)
        df['Near_52W_Low'] = ((close / df['52W_Low']) < 1.05).astype(int)
        df['SMA_63'] = close.rolling(63).mean()
        df['SMA_126'] = close.rolling(126).mean()
        df['Bullish_Trend'] = (df['SMA_63'] > df['SMA_126']).astype(int)
        
        return df

    @staticmethod
    @staticmethod
    def add_adx(df, period=14):
        """Add Average Directional Index (ADX) for trend strength measurement."""
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        adx_indicator = ta.trend.ADXIndicator(high, low, close, window=period)
        df[f'ADX_{period}'] = adx_indicator.adx()
        df[f'ADX_PlusDI_{period}'] = adx_indicator.adx_pos()
        df[f'ADX_MinusDI_{period}'] = adx_indicator.adx_neg()
        return df

    @staticmethod
    def add_volume_indicators(df, volume_sma_period=20):
        """Add volume-based indicators for stock filtering."""
        if 'Volume' not in df.columns:
            return df
        volume = df['Volume'].squeeze() if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        df[f'Volume_SMA_{volume_sma_period}'] = volume.rolling(volume_sma_period).mean()
        df['Volume_Above_SMA'] = volume > df[f'Volume_SMA_{volume_sma_period}']
        return df

    @staticmethod
    def add_donchian_channels(df, exit_period=55, recovery_period=20):
        """Calculate Donchian channels for regime filter.
        
        Turtle Trading rules:
        - Exit (trigger): Close breaks below N-period low (default 55)
        - Recovery: Close breaks above M-period high (default 20)
        
        Asymmetric periods reduce whipsaw during choppy markets.
        """
        if isinstance(df, pd.Series):
            raise ValueError("Input must be a DataFrame, not a Series")
        
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        
        # Donchian Low (for exit trigger) - uses low prices
        df[f'Donchian_Low_{exit_period}'] = low.rolling(exit_period).min()
        
        # Donchian High (for recovery) - uses high prices
        df[f'Donchian_High_{recovery_period}'] = high.rolling(recovery_period).max()
        
        # Store current close for comparison
        df['Donchian_Close'] = close
        
        return df
    
    @staticmethod
    def add_swing_atr(df, swing_period=20, atr_period=14):
        """Calculate Swing pivot levels with ATR buffer.
        
        Exit signal: Close < Swing_Low - (buffer × ATR)
        Recovery signal: Close > Swing_High + (buffer × ATR)
        
        The ATR buffer helps filter out noise and false breakouts.
        """
        if isinstance(df, pd.Series):
            raise ValueError("Input must be a DataFrame, not a Series")
        
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        
        # Swing Low (lowest low over N periods)
        df[f'Swing_Low_{swing_period}'] = low.rolling(swing_period).min()
        
        # Swing High (highest high over N periods)
        df[f'Swing_High_{swing_period}'] = high.rolling(swing_period).max()
        
        # ATR calculation (using EMA for smoothness)
        if f'ATR_{atr_period}' not in df.columns:
            tr = np.maximum.reduce([
                (high - low).values,
                np.abs((high - close.shift(1)).fillna(0).values),
                np.abs((low - close.shift(1)).fillna(0).values)
            ])
            df[f'ATR_{atr_period}'] = pd.Series(tr, index=df.index).ewm(span=atr_period, adjust=False).mean()
        
        # Store current close for comparison
        df['Swing_Close'] = close
        
        return df
    
    @staticmethod
    def _add_supertrend_basic(df, period, multiplier, suffix=""):
        """Simplified supertrend for regime filter."""
        high = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
        low = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
        close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']
        
        tr = np.maximum.reduce([
            (high - low).values,
            np.abs((high - close.shift(1)).fillna(0).values),
            np.abs((low - close.shift(1)).fillna(0).values)
        ])
        atr = pd.Series(tr, index=df.index).ewm(span=period, adjust=False).mean()
        hl2 = (high + low) / 2
        upper = hl2 + (multiplier * atr)
        lower = hl2 - (multiplier * atr)
        
        supertrend = _compute_supertrend_fast(close.values, upper.values, lower.values)
        df[f'Supertrend{suffix}'] = supertrend
        return df


def _compute_supertrend_fast(close, upper, lower):
    """Optimized SuperTrend using NumPy (no Python loops where possible)."""
    n = len(close)
    supertrend = np.empty(n)
    supertrend[0] = upper[0]
    
    # Use Numba-style loop (still fast with NumPy arrays)
    for i in range(1, n):
        if close[i] > upper[i-1]:
            supertrend[i] = lower[i]
        elif close[i] < lower[i-1]:
            supertrend[i] = upper[i]
        else:
            supertrend[i] = supertrend[i-1]
    
    return supertrend

