import threading
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
from matplotlib.widgets import Button
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

plt.style.use('dark_background')

symbol = 'SPY'

class LiveSurface(EClient, EWrapper):

    def __init__(self):
        EClient.__init__(self, self)
        self.iv_dict = {}
        self.id_map = {}
        self.expirations = []
        self.strikes = []
        self.option_chains = []
        self.option_contracts = {}
        self.option_events = {}
        self.spot_price = 0
        self.underlying_conId = 0
        self.trading_class = ''
        self.multiplier = '100'
        self.data_mode = 'UNKNOWN'
        self.ready = threading.Event()
        self.resolved = threading.Event()
        self.chain_resolved = threading.Event()

    def connectAck(self):
        print("Connected to IBKR API")

    def nextValidId(self, orderId):
        print(f"API ready | nextValidId {orderId}")
        self.ready.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in [2104, 2106, 2107, 2108, 2158]:
            return
        if errorCode == 2176:
            print("Warning 2176: IB API version is old. Update it when convenient.")
            return
        if errorCode == 200 and reqId in self.option_events:
            self.option_events[reqId].set()
            print(f"{reqId}: Option contract not available")
            return
        print(f"{reqId}: Error {errorCode}: {errorString}")

    def marketDataType(self, reqId, marketDataType):
        modes = {1: 'LIVE', 2: 'FROZEN', 3: 'DELAYED', 4: 'DELAYED-FROZEN'}
        self.data_mode = modes.get(marketDataType, 'UNKNOWN')

    def contractDetails(self, reqId, contractDetails):
        if reqId == 1:
            self.underlying_conId = contractDetails.contract.conId
            print(f"Resolved underlying: {contractDetails.contract.symbol} | conId {self.underlying_conId}")
            self.resolved.set()
        elif reqId in self.option_events and reqId not in self.option_contracts:
            self.option_contracts[reqId] = contractDetails.contract

    def contractDetailsEnd(self, reqId):
        if reqId in self.option_events:
            self.option_events[reqId].set()

    def tickPrice(self, reqId, tickType, price, attrib):
        if reqId == 999 and tickType in [4, 9, 68, 75] and price > 0:
            self.spot_price = price

    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes):
        if exchange == 'SMART':
            self.option_chains.append({
                'tradingClass': tradingClass,
                'multiplier': multiplier,
                'expirations': list(expirations),
                'strikes': list(strikes)
            })

    def securityDefinitionOptionParameterEnd(self, reqId):
        if len(self.option_chains) == 0:
            self.chain_resolved.set()
            return

        preferred = [x for x in self.option_chains if x['tradingClass'] == symbol and x['multiplier'] == '100']
        best_chain = max(preferred if preferred else self.option_chains, key=lambda x: len(x['expirations']) * len(x['strikes']))

        self.expirations = sorted(best_chain['expirations'])
        self.strikes = sorted(best_chain['strikes'])
        self.trading_class = best_chain['tradingClass']
        self.multiplier = best_chain['multiplier']

        print(f"Option chain: {self.trading_class}")
        print(f"Multiplier: {self.multiplier}")
        print(f"Available expirations: {len(self.expirations)}")
        print(f"Available strikes: {len(self.strikes)}")

        self.chain_resolved.set()

    def tickOptionComputation(self, reqId, tickType, tickAttrib, impliedVol, delta, optPrice, pvDividend, gamma, vega, theta, undPrice):
        if tickType in [13, 83] and impliedVol is not None and 0 < impliedVol < 5:
            self.iv_dict[reqId] = impliedVol


def run_loop(app):
    app.run()


def start_app(symbol='SPY'):

    app = LiveSurface()
    app.connect("127.0.0.1", 7497, clientId=0)

    api_thread = threading.Thread(target=run_loop, args=(app,), daemon=True)
    api_thread.start()

    if not app.ready.wait(timeout=15):
        raise RuntimeError("IBKR API did not become ready.")

    app.reqMarketDataType(1)

    underlying = Contract()
    underlying.symbol = symbol
    underlying.secType = 'STK'
    underlying.exchange = 'SMART'
    underlying.primaryExchange = 'ARCA'
    underlying.currency = 'USD'

    print(f"Resolving {symbol} underlying contract...")

    app.reqContractDetails(1, underlying)

    if not app.resolved.wait(timeout=15):
        raise RuntimeError(f"Could not resolve underlying contract for {symbol}")

    print(f"{symbol} conId: {app.underlying_conId}")

    app.reqMktData(999, underlying, "", False, False, [])

    timeout = time.time() + 20

    while app.spot_price == 0 and time.time() < timeout:
        time.sleep(0.1)

    if app.spot_price == 0:
        raise RuntimeError("No live SPY price received. Check the SPY/Network B market data subscription.")

    spot = app.spot_price

    print(f"{symbol} price: {spot:.2f} ({app.data_mode})")

    app.reqSecDefOptParams(2, symbol, '', 'STK', app.underlying_conId)

    if not app.chain_resolved.wait(timeout=15):
        raise RuntimeError("Option chain request timed out.")

    today = time.strftime("%Y%m%d")

    target_exps = [e for e in app.expirations if e > today][:4]

    valid_strikes = [s for s in app.strikes if spot * 0.94 <= s <= spot * 1.06]

    if len(valid_strikes) > 9:
        indexes = np.linspace(0, len(valid_strikes) - 1, 9).astype(int)
        target_strikes = [valid_strikes[i] for i in indexes]
    else:
        target_strikes = valid_strikes

    print()
    print("Selected surface")
    print("----------------")
    print(f"Spot: {spot:.2f}")
    print(f"Expirations: {target_exps}")
    print(f"Strikes: {target_strikes}")
    print()

    contract_req_id = 5000
    contracts_to_check = {}

    for exp in target_exps:
        for strike in target_strikes:

            opt = Contract()
            opt.symbol = symbol
            opt.secType = 'OPT'
            opt.exchange = 'SMART'
            opt.currency = 'USD'
            opt.lastTradeDateOrContractMonth = exp
            opt.strike = float(strike)
            opt.right = 'P' if strike < spot else 'C'
            opt.multiplier = app.multiplier
            opt.tradingClass = app.trading_class

            app.option_events[contract_req_id] = threading.Event()
            contracts_to_check[contract_req_id] = (exp, strike, opt.right)

            app.reqContractDetails(contract_req_id, opt)

            contract_req_id += 1
            time.sleep(0.05)

    print("Checking valid option contracts...")

    req_id = 1000
    valid_contracts = 0

    for contract_req_id, option_info in contracts_to_check.items():

        app.option_events[contract_req_id].wait(timeout=3)

        if contract_req_id not in app.option_contracts:
            continue

        exp, strike, right = option_info
        opt = app.option_contracts[contract_req_id]

        app.id_map[req_id] = (exp, strike, right)

        app.reqMktData(req_id, opt, "", False, False, [])

        valid_contracts += 1
        req_id += 1

        time.sleep(0.1)

    print(f"Valid option contracts: {valid_contracts}")
    print("Waiting for live IV data...")

    return app


class PlotState:

    def __init__(self):
        self.is_locked = False

    def toggle_lock(self, event):
        self.is_locked = not self.is_locked
        btn_label.set_text("Unlock" if self.is_locked else "Lock Updates")
        plt.draw()


def live_desktop_plot(app):

    plt.ion()

    fig = plt.figure(figsize=(16, 9))
    fig.canvas.manager.set_window_title('Live Implied Volatility Surface')
    fig.patch.set_facecolor('#0b0d0f')

    ax_3d = plt.subplot2grid((1, 3), (0, 0), colspan=2, projection='3d')
    ax_skew = plt.subplot2grid((1, 3), (0, 2))

    state = PlotState()

    ax_button = plt.axes([0.42, 0.03, 0.12, 0.04])

    global btn_label

    btn = Button(ax_button, 'Lock Updates', color='#1f2329', hovercolor='#2d333b')
    btn_label = btn.label
    btn_label.set_color('white')
    btn_label.set_fontsize(9)
    btn.on_clicked(state.toggle_lock)

    ax_3d.set_title(f'Waiting for {symbol} IV data...', color='white')
    ax_skew.set_title('Front Month Skew', color='white')

    print('Starting live plotting...')

    last_count = -1

    try:

        while True:

            if not state.is_locked:

                current_data = []

                for rid, iv in list(app.iv_dict.items()):

                    if rid not in app.id_map:
                        continue

                    exp, strike, right = app.id_map[rid]

                    current_data.append({
                        'Expiration': exp,
                        'Strike': strike,
                        'Right': right,
                        'IV': iv
                    })

                if len(current_data) != last_count:
                    print(f"IV points received: {len(current_data)}")
                    last_count = len(current_data)

                if len(current_data) > 5:

                    df = pd.DataFrame(current_data)

                    pivot = df.pivot_table(index='Expiration', columns='Strike', values='IV')
                    pivot = pivot.sort_index().sort_index(axis=1)

                    pivot = pivot.interpolate(method='linear', axis=1, limit_direction='both')
                    pivot = pivot.bfill(axis=1).ffill(axis=1)
                    pivot = pivot.interpolate(method='linear', axis=0, limit_direction='both')
                    pivot = pivot.bfill(axis=0).ffill(axis=0)

                    if pivot.shape[0] < 2 or pivot.shape[1] < 3:
                        plt.pause(0.5)
                        continue

                    X, Y_idx = np.meshgrid(pivot.columns.astype(float), np.arange(len(pivot.index)))
                    Z = pivot.values * 100

                    current_elev, current_azim = ax_3d.elev, ax_3d.azim

                    ax_3d.clear()
                    ax_3d.set_facecolor('#0b0d0f')

                    ax_3d.plot_surface(X, Y_idx, Z, cmap='magma', edgecolor='white', lw=0.1, alpha=0.9)

                    ax_3d.set_xlabel('Strike')
                    ax_3d.set_ylabel('Expiration')
                    ax_3d.set_zlabel('Implied Volatility (%)')

                    ax_3d.set_yticks(np.arange(len(pivot.index)))
                    ax_3d.set_yticklabels(pivot.index)

                    ax_3d.set_title(f'Live Implied Volatility Surface for {symbol} at {time.strftime("%H:%M:%S")}', color='white')
                    ax_3d.view_init(elev=current_elev, azim=current_azim)

                    ax_skew.clear()
                    ax_skew.set_facecolor('#161b22')

                    nearest_exp = pivot.index[0]
                    skew_data = pivot.iloc[0] * 100

                    ax_skew.plot(skew_data.index.astype(float), skew_data.values, marker='o', color='#00f2ff')
                    ax_skew.axvline(x=app.spot_price, color='#ff3e3e', linestyle='--', label=f'Spot {app.spot_price:.2f}')

                    ax_skew.set_title(f'Front Month Skew ({nearest_exp})', color='white')
                    ax_skew.set_xlabel('Strike')
                    ax_skew.set_ylabel('Implied Volatility (%)')

                    ax_skew.grid(alpha=0.15)
                    ax_skew.legend()

            plt.pause(0.5)

    except KeyboardInterrupt:
        app.disconnect()
        plt.close()


if __name__ == "__main__":

    app_instance = start_app(symbol)

    print('App Started')

    time.sleep(5)

    live_desktop_plot(app_instance)