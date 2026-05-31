import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from indicators import IndicatorLibrary
from scoring import ScoreParser

SECTOR_INDICES = {
    'NIFTY BANK': '^NSEBANK',
    'NIFTY IT': '^CNXIT',
    'NIFTY PHARMA': '^CNXPHARMA',
    'NIFTY AUTO': '^CNXAUTO',
    'NIFTY FMCG': '^CNXFMCG',
    'NIFTY METAL': '^CNXMETAL',
    'NIFTY REALTY': '^CNXREALTY',
    'NIFTY ENERGY': '^CNXENERGY',
    'NIFTY CONSUMPTION': '^CNXCONSUM',
    'NIFTY MEDIA': '^CNXMEDIA',
}

class SectorRotationEngine:
    def __init__(self, start_date, end_date, initial_capital=10000000):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data: Dict[str, pd.DataFrame] = {}
        self.portfolio_df = pd.DataFrame()
        self.trades = []
        self.monthly_returns = {}
        self.parser = ScoreParser()
    
    def download_sector_data(self):
        """Download historical data for all sector indices."""
        extended_start = pd.Timestamp(self.start_date) - timedelta(days=400)
        
        for sector_name, ticker in SECTOR_INDICES.items():
            try:
                df = yf.download(ticker, start=extended_start, end=self.end_date, progress=False)
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [col[0] for col in df.columns]
                    self.data[sector_name] = df
                    print(f"Downloaded {sector_name} ({ticker}): {len(df)} rows")
                else:
                    print(f"No data for {sector_name}")
            except Exception as e:
                print(f"Error downloading {sector_name}: {e}")
        
        print(f"Downloaded data for {len(self.data)} sector indices")
    
    def calculate_indicators(self, periods=None):
        """Calculate momentum/volatility metrics for all sectors."""
        for sector, df in self.data.items():
            try:
                if '6 Month Performance' not in df.columns:
                    df = IndicatorLibrary.add_momentum_volatility_metrics(df, periods)
                self.data[sector] = df
            except Exception as e:
                print(f"Error calculating indicators for {sector}: {e}")
    
    def run_backtest(self, scoring_formula, num_sectors=3, rebal_freq='Monthly', position_sizing='equal_weight'):
        """Run sector rotation backtest."""
        if not self.data:
            print("No sector data available")
            return
        
        self.calculate_indicators()
        
        all_dates = sorted(set(
            date for df in self.data.values()
            for date in df.index
            if self.start_date <= date <= self.end_date
        ))
        
        if not all_dates:
            print("No trading dates")
            return
        
        all_dates = pd.DatetimeIndex(all_dates)
        
        rebal_dates = self._get_rebalance_dates(all_dates, rebal_freq)
        
        cash = self.initial_capital
        holdings = {}
        portfolio_values = []
        
        for i, date in enumerate(all_dates):
            for sector in list(holdings.keys()):
                if sector in self.data and date in self.data[sector].index:
                    price = float(self.data[sector].loc[date, 'Close'].iloc[0] if isinstance(self.data[sector].loc[date, 'Close'], pd.Series) else self.data[sector].loc[date, 'Close'])
                    holdings[sector] = (holdings[sector][0], price)
            
            if date in rebal_dates:
                if holdings:
                    for sector, (shares, price) in holdings.items():
                        value = shares * price
                        cash += value
                    holdings = {}
                
                scores = {}
                for sector, df in self.data.items():
                    if date in df.index:
                        row = df.loc[date]
                        try:
                            score = self.parser.parse_and_calculate(scoring_formula, row)
                            if score > -999999:
                                scores[sector] = score
                        except:
                            continue
                
                ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                selected = ranked[:num_sectors]
                
                if selected and cash > 0:
                    if position_sizing == 'equal_weight':
                        sector_value = cash / len(selected)
                    elif position_sizing == 'score_weighted':
                        total_score = sum(abs(s) for _, s in selected)
                        if total_score <= 0:
                            sector_value = cash / len(selected)
                        else:
                            for sector, score in selected:
                                weight = abs(score) / total_score
                                sector_value = cash * weight
                    
                    for sector, score in selected:
                        price = float(self.data[sector].loc[date, 'Close'].iloc[0] if isinstance(self.data[sector].loc[date, 'Close'], pd.Series) else self.data[sector].loc[date, 'Close'])
                        alloc = sector_value if position_sizing == 'equal_weight' else cash * (abs(score) / total_score)
                        shares = int(alloc / price)
                        if shares > 0:
                            cost = shares * price
                            cash -= cost
                            holdings[sector] = (shares, price)
                            self.trades.append({
                                'Date': date,
                                'Sector': sector,
                                'Action': 'BUY',
                                'Shares': shares,
                                'Price': price,
                                'Value': cost,
                                'Score': score,
                                'Rank': [s for s, _ in selected].index(sector) + 1
                            })
            
            total_value = cash
            for sector, (shares, price) in holdings.items():
                total_value += shares * price
            portfolio_values.append({'Date': date, 'Portfolio Value': total_value})
        
        self.portfolio_df = pd.DataFrame(portfolio_values)
        if len(self.portfolio_df) > 0:
            self.portfolio_df.set_index('Date', inplace=True)
    
    def _get_rebalance_dates(self, all_dates, freq='Monthly'):
        """Generate rebalance dates."""
        if freq == 'Monthly':
            months = set()
            rebal_dates = []
            for d in all_dates:
                key = (d.year, d.month)
                if key not in months:
                    months.add(key)
                    rebal_dates.append(d)
            return pd.DatetimeIndex(rebal_dates)
        elif freq == 'Weekly':
            return all_dates[all_dates.weekday == 4]
        elif freq == 'Quarterly':
            quarters = set()
            rebal_dates = []
            for d in all_dates:
                key = (d.year, (d.month - 1) // 3)
                if key not in quarters:
                    quarters.add(key)
                    rebal_dates.append(d)
            return pd.DatetimeIndex(rebal_dates)
        return pd.DatetimeIndex([all_dates[0], all_dates[-1]])
    
    def get_metrics(self):
        """Calculate performance metrics."""
        if self.portfolio_df.empty:
            return {}
        
        final_value = self.portfolio_df['Portfolio Value'].iloc[-1]
        total_return = final_value - self.initial_capital
        return_pct = (total_return / self.initial_capital) * 100
        
        days = (self.portfolio_df.index[-1] - self.portfolio_df.index[0]).days
        years = days / 365.25
        cagr = ((final_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        running_max = self.portfolio_df['Portfolio Value'].cummax()
        drawdown = (self.portfolio_df['Portfolio Value'] - running_max) / running_max * 100
        max_dd = abs(drawdown.min())
        
        returns = self.portfolio_df['Portfolio Value'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100
        
        rf_rate = 0.05
        sharpe = (cagr / 100 - rf_rate) / (volatility / 100) if volatility > 0 else 0
        
        wins = sum(1 for t in self.trades if t.get('Action') == 'SELL' and t.get('Value', 0) > 0)
        losses = sum(1 for t in self.trades if t.get('Action') == 'SELL' and t.get('Value', 0) <= 0)
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        return {
            'Final Value': final_value,
            'Total Return': total_return,
            'Return %': return_pct,
            'CAGR %': cagr,
            'Max Drawdown %': max_dd,
            'Volatility %': volatility * 100,
            'Sharpe Ratio': sharpe,
            'Win Rate %': win_rate,
            'Total Trades': len(self.trades),
        }
    
    def get_sector_exposure(self):
        """Get sector exposure over time."""
        exposure = {}
        for trade in self.trades:
            if trade['Action'] == 'BUY':
                date = trade['Date']
                sector = trade['Sector']
                if date not in exposure:
                    exposure[date] = {}
                exposure[date][sector] = exposure[date].get(sector, 0) + trade['Value']
        return exposure
    
    def get_monthly_returns(self):
        """Calculate monthly returns."""
        if self.portfolio_df.empty:
            return pd.DataFrame()
        df = self.portfolio_df.copy()
        df['Year'] = df.index.year
        df['Month'] = df.index.month
        monthly_values = df.groupby(['Year', 'Month'])['Portfolio Value'].last()
        monthly_returns = monthly_values.pct_change() * 100
        monthly_df = monthly_returns.reset_index()
        monthly_df.columns = ['Year', 'Month', 'Return']
        pivot = monthly_df.pivot(index='Year', columns='Month', values='Return')
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        pivot.columns = [month_names[int(m)-1] for m in pivot.columns]
        yearly_totals = []
        for year in pivot.index:
            year_data = df[df['Year'] == year]['Portfolio Value']
            if len(year_data) > 0:
                yr_ret = ((year_data.iloc[-1] / year_data.iloc[0]) - 1) * 100
                yearly_totals.append(yr_ret)
            else:
                yearly_totals.append(None)
        pivot['Total'] = yearly_totals
        return pivot.round(3)
