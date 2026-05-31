import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Dict, List

try:
    from config import get_kite_client, get_dhan_client, validate_credentials as validate_dhan_creds
except ImportError:
    get_kite_client = None
    get_dhan_client = None
    validate_dhan_creds = None


class LivePortfolioTracker:
    """Unified live portfolio tracker supporting Zerodha and Dhan."""
    
    def __init__(self, broker: str = "Zerodha"):
        self.broker = broker
        self.client = None
        self.positions = []
        self.holdings = []
        self.funds = {}
        self._init_client()
    
    def _init_client(self):
        """Initialize the broker client."""
        if self.broker == "Zerodha":
            if get_kite_client:
                try:
                    self.client = get_kite_client()
                except Exception as e:
                    st.warning(f"Zerodha client init failed: {e}")
                    self.client = None
        elif self.broker == "Dhan":
            if get_dhan_client:
                try:
                    self.client = get_dhan_client()
                except Exception as e:
                    st.warning(f"Dhan client init failed: {e}")
                    self.client = None
    
    def fetch_positions(self) -> List[Dict]:
        """Fetch current open positions."""
        self.positions = []
        if not self.client:
            return self.positions
        
        try:
            if self.broker == "Zerodha":
                positions = self.client.positions()
                for pos in positions.get('net', []):
                    self.positions.append({
                        'ticker': pos.get('tradingsymbol', ''),
                        'exchange': pos.get('exchange', ''),
                        'quantity': abs(pos.get('quantity', 0)),
                        'buy_price': abs(pos.get('average_price', 0)),
                        'current_price': pos.get('last_price', 0),
                        'pnl': pos.get('pnl', 0),
                        'product': pos.get('product', ''),
                    })
            elif self.broker == "Dhan":
                try:
                    resp = self.client.get_positions()
                    if isinstance(resp, dict) and resp.get('status') == 'success':
                        data = resp.get('data', [])
                        for pos in data:
                            self.positions.append({
                                'ticker': pos.get('tradingSymbol', ''),
                                'exchange': pos.get('exchangeSegment', ''),
                                'quantity': abs(pos.get('buyQty', 0)),
                                'buy_price': abs(pos.get('buyAvg', 0)),
                                'current_price': pos.get('lastPrice', 0),
                                'pnl': pos.get('unrealizedMtom', 0),
                                'product': pos.get('productType', ''),
                            })
                except Exception as e:
                    print(f"Dhan positions fetch error: {e}")
        except Exception as e:
            print(f"Error fetching positions from {self.broker}: {e}")
        
        return self.positions
    
    def fetch_holdings(self) -> List[Dict]:
        """Fetch current holdings."""
        self.holdings = []
        if not self.client:
            return self.holdings
        
        try:
            if self.broker == "Zerodha":
                holdings = self.client.holdings()
                for h in holdings:
                    self.holdings.append({
                        'ticker': h.get('tradingsymbol', ''),
                        'exchange': h.get('exchange', ''),
                        'quantity': h.get('quantity', 0),
                        'buy_price': h.get('average_price', 0),
                        'current_price': h.get('last_price', 0),
                        'pnl': h.get('pnl', 0),
                    })
            elif self.broker == "Dhan":
                try:
                    resp = self.client.get_holdings()
                    if isinstance(resp, dict) and resp.get('status') == 'success':
                        data = resp.get('data', [])
                        for h in data:
                            self.holdings.append({
                                'ticker': h.get('tradingSymbol', ''),
                                'exchange': h.get('exchangeSegment', ''),
                                'quantity': h.get('totalBuyQuantity', 0) - h.get('totalSellQuantity', 0),
                                'buy_price': h.get('buyAvgPrice', 0),
                                'current_price': h.get('lastPrice', 0),
                                'pnl': h.get('unrealizedProfitDhan', 0),
                            })
                except Exception as e:
                    print(f"Dhan holdings fetch error: {e}")
        except Exception as e:
            print(f"Error fetching holdings from {self.broker}: {e}")
        
        return self.holdings
    
    def fetch_funds(self) -> Dict:
        """Fetch available funds and margin."""
        self.funds = {}
        if not self.client:
            return self.funds
        
        try:
            if self.broker == "Zerodha":
                margins = self.client.margins()
                equity = margins.get('equity', {})
                self.funds = {
                    'available_cash': equity.get('available', {}).get('live_balance', 0),
                    'used_margin': equity.get('used', {}).get('debt', 0),
                    'total_equity': equity.get('net', 0),
                }
            elif self.broker == "Dhan":
                try:
                    resp = self.client.get_fund_limit()
                    if isinstance(resp, dict):
                        self.funds = {
                            'available_cash': float(resp.get('availableBalance', 0)),
                            'used_margin': float(resp.get('usedMargin', 0)),
                            'total_equity': float(resp.get('totalBalance', 0)),
                        }
                except Exception as e:
                    print(f"Dhan funds fetch error: {e}")
        except Exception as e:
            print(f"Error fetching funds from {self.broker}: {e}")
        
        return self.funds
    
    def get_portfolio_summary(self) -> Dict:
        """Get a consolidated portfolio summary."""
        positions = self.fetch_positions()
        holdings = self.fetch_holdings()
        funds = self.fetch_funds()
        
        total_invested = sum(h.get('buy_price', 0) * h.get('quantity', 0) for h in holdings)
        total_current = sum(h.get('current_price', 0) * h.get('quantity', 0) for h in holdings)
        total_pnl = sum(h.get('pnl', 0) for h in holdings)
        
        position_value = sum(p.get('current_price', 0) * p.get('quantity', 0) for p in positions)
        position_pnl = sum(p.get('pnl', 0) for p in positions)
        
        return {
            'total_invested': total_invested,
            'total_current': total_current,
            'total_pnl': total_pnl + position_pnl,
            'total_pnl_pct': (total_pnl / total_invested * 100) if total_invested > 0 else 0,
            'position_value': position_value,
            'available_cash': funds.get('available_cash', 0),
            'num_positions': len(positions),
            'num_holdings': len(holdings),
            'funds': funds,
        }


def render_live_dashboard(broker: str = "Zerodha"):
    """Render the live portfolio dashboard in Streamlit."""
    st.markdown(f"### 📡 Live Portfolio — {broker}")
    
    if 'live_tracker' not in st.session_state or st.session_state.get('live_broker') != broker:
        st.session_state.live_tracker = LivePortfolioTracker(broker)
        st.session_state.live_broker = broker
    
    tracker = st.session_state.live_tracker
    
    col_refresh, col_broker = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh", key=f"refresh_{broker}"):
            tracker._init_client()
    
    if not tracker.client:
        st.error(f"❌ {broker} client not connected. Please check your credentials in the config.")
        return
    
    with st.spinner(f"Fetching {broker} portfolio..."):
        summary = tracker.get_portfolio_summary()
        positions_df = pd.DataFrame(tracker.positions) if tracker.positions else pd.DataFrame()
        holdings_df = pd.DataFrame(tracker.holdings) if tracker.holdings else pd.DataFrame()
    
    # Summary cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Total P&L", f"₹{summary['total_pnl']:,.0f}")
    sc2.metric("P&L %", f"{summary['total_pnl_pct']:.2f}%")
    sc3.metric("Available Cash", f"₹{summary['available_cash']:,.0f}")
    sc4.metric("Positions", summary['num_positions'])
    
    # Positions table
    if not positions_df.empty:
        st.markdown("#### Open Positions")
        display_cols = ['ticker', 'quantity', 'buy_price', 'current_price', 'pnl']
        display_df = positions_df[display_cols] if all(c in positions_df.columns for c in display_cols) else positions_df
        display_df.columns = [c.title().replace('_', ' ') for c in display_df.columns]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No open positions.")
    
    # Holdings table
    if not holdings_df.empty:
        st.markdown("#### Holdings")
        display_cols = ['ticker', 'quantity', 'buy_price', 'current_price', 'pnl']
        display_df = holdings_df[display_cols] if all(c in holdings_df.columns for c in display_cols) else holdings_df
        display_df.columns = [c.title().replace('_', ' ') for c in display_df.columns]
        st.dataframe(display_df, use_container_width=True)
    
    # Fund details
    if summary.get('funds'):
        with st.expander("💰 Fund Details"):
            fund_data = {
                'Metric': ['Available Cash', 'Used Margin', 'Total Equity'],
                'Value': [
                    f"₹{summary['funds'].get('available_cash', 0):,.0f}",
                    f"₹{summary['funds'].get('used_margin', 0):,.0f}",
                    f"₹{summary['funds'].get('total_equity', 0):,.0f}",
                ]
            }
            st.dataframe(pd.DataFrame(fund_data), use_container_width=True, hide_index=True)
