"""Offline BTCUSDT research only. No authenticated or order-placement endpoints."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_DOWN
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Config:
    equity: float = 1000.
    fee: float = .001
    slippage: float = .0002  # Combined spread/slippage on each side
    risk: float = .0025
    exposure: float = .35
    reward: float = 1.5
    early_time_exit: bool = True
    step: float = .00001  # Research assumption, not current exchange metadata
    min_notional: float = 5.
    warmup_hours: int = 1000
    daily_loss: float = .01
    drawdown: float = .05

def download_month(month: str, folder: Path) -> Path:
    pd.Period(month, freq='M')  # Validate before using in URL
    name = f'BTCUSDT-1m-{month}.zip'
    path = folder / name
    url = 'https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/' + name
    folder.mkdir(parents=True, exist_ok=True)
    checksum = urllib.request.urlopen(url + '.CHECKSUM', timeout=60).read().decode().split()[0]
    raw = path.read_bytes() if path.exists() else urllib.request.urlopen(url, timeout=60).read()
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise ValueError(f'Checksum mismatch: {name}')
    path.write_bytes(raw)
    path.with_suffix('.zip.CHECKSUM').write_text(checksum + '  ' + name + '\n')
    return path

def read_data(folder: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(folder.glob('BTCUSDT-1m-*.zip')):
        checksum = path.with_suffix('.zip.CHECKSUM').read_text().split()[0]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError(f'Checksum mismatch: {path}')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.endswith('.csv')]
            if len(names) != 1:
                raise ValueError('Expected one CSV per archive')
            a = pd.read_csv(z.open(names[0]), header=None, usecols=range(6))
        a.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        # Binance spot archives changed from milliseconds to microseconds in 2025.
        ts = a.pop('time').astype('int64')
        a.index = pd.to_datetime(np.where(ts > 10**14, ts // 1000, ts), unit='ms', utc=True)
        frames.append(a.astype(float))
    if not frames:
        raise ValueError('No verified Binance ZIP files found')
    df = pd.concat(frames).sort_index()
    validate(df)
    return df

def validate(df):
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError('Duplicate or unordered timestamps')
    if not (df.index.to_series().diff().dropna() == pd.Timedelta(minutes=1)).all():
        raise ValueError('Missing minute bars: repair data before running')
    if not np.isfinite(df.to_numpy()).all() or (df[['open','high','low','close']] <= 0).any().any():
        raise ValueError('Invalid numeric data')
    if (df.volume < 0).any() or (df.high < df[['open','close','low']].max(axis=1)).any() or (df.low > df[['open','close','high']].min(axis=1)).any():
        raise ValueError('Invalid OHLCV')

def bars(df, minutes):
    rule = f'{minutes}min'
    b = df.resample(rule, label='right', closed='left').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    counts = df.close.resample(rule, label='right', closed='left').count()
    return b[counts == minutes].copy()

def wilder(s, n=14):
    result = np.full(len(s), np.nan)
    x = s.to_numpy(float)
    valid = np.flatnonzero(np.isfinite(x))
    if len(valid) < n:
        return pd.Series(result, index=s.index)
    start = valid[0]
    seed = start + n - 1
    result[seed] = x[start:seed+1].mean()
    for i in range(seed+1, len(x)):
        result[i] = (result[i-1] * (n-1) + x[i]) / n
    return pd.Series(result, index=s.index)

def indicators(df):
    f, m, h = bars(df, 5), bars(df, 15), bars(df, 60)
    ema = lambda s, n: s.ewm(span=n, adjust=False).mean()
    he = ema(h.close, 200)
    regime = (h.close > he) & (he > he.shift(5))
    setup = (ema(m.close,20) > ema(m.close,50)) & (m.close > ema(m.close,50))
    fe = ema(f.close,20)
    delta = f.close.diff()
    up, down = wilder(delta.clip(lower=0)), wilder(-delta.clip(upper=0))
    rsi = 100 - 100 / (1 + up / down)
    rsi[(up == 0) & (down == 0)] = 50
    tr = pd.concat([f.high-f.low, (f.high-f.close.shift()).abs(), (f.low-f.close.shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr)
    touched = (f.low <= fe).shift(1).rolling(3).max() == 1
    f['signal'] = (regime.reindex(f.index, method='ffill').astype("boolean").fillna(False) & setup.reindex(f.index,method='ffill').astype("boolean").fillna(False) & touched & (f.close > fe) & (f.close > f.high.shift()) & rsi.between(45,65) & (rsi > rsi.shift()) & (f.volume >= 1.2*f.volume.shift().rolling(20).mean()))
    f['stop'] = np.minimum(f.low.rolling(3).min() - .1*atr, f.close - 1.5*atr)
    f['reference'] = f.close
    f['regime_exit'] = (h.close < he).reindex(f.index, method='ffill').astype("boolean").fillna(False)
    return f[['signal','stop','reference','regime_exit']]

def size_trade(reference, stop, equity, cash, c):
    """Quote-fee equivalent accounting; slippage applied to execution prices."""
    d = (reference-stop)/reference
    if not .004 <= d <= .012:
        return None
    entry = reference*(1+c.slippage)
    unit_cost = entry*(1+c.fee)
    stop_proceeds = stop*(1-c.slippage)*(1-c.fee)
    unit_loss = unit_cost-stop_proceeds
    quantity = min(equity*c.risk/unit_loss, equity*c.exposure/entry, cash/unit_cost)
    step = Decimal(str(c.step))
    q = float((Decimal(str(quantity))/step).to_integral_value(rounding=ROUND_DOWN)*step)
    if q <= 0 or q*entry < c.min_notional or q*stop < c.min_notional:
        return None
    cost, loss = q*unit_cost, q*unit_loss
    target = (cost+c.reward*loss)/(q*(1-c.fee)*(1-c.slippage))
    return dict(q=q, entry=entry, cost=cost, risk=loss, stop=stop, target=target, entry_fee=q*entry*c.fee)

def run(df, c=Config(), start=None, end=None, signals=None, events=None):
    validate(df)
    sig = indicators(df) if signals is None else signals
    first = df.index[0] + pd.Timedelta(hours=c.warmup_hours)
    start = max(first, pd.Timestamp(start)) if start else first
    end = pd.Timestamp(end) if end else df.index[-1]+pd.Timedelta(minutes=1)
    data = df.loc[(df.index >= start) & (df.index < end)]
    if data.empty:
        raise ValueError('No scoring data after warm-up')
    aligned = sig.reindex(data.index)
    regime = sig.regime_exit.reindex(data.index, method='ffill').astype("boolean").fillna(False).to_numpy(bool)
    signal = aligned.signal.astype("boolean").fillna(False).to_numpy(bool)
    stops = aligned.stop.to_numpy(float)
    refs = aligned.reference.to_numpy(float)
    blocked = np.zeros(len(data), dtype=bool)
    if events is not None:
        for event in events:
            blocked |= (data.index >= event-pd.Timedelta(minutes=30)) & (data.index <= event+pd.Timedelta(minutes=30))
    cash, peak, day_start = c.equity, c.equity, c.equity
    pos, day, losses, paused, halted, cooldown = None, None, 0, False, False, data.index[0]
    trades, curve = [], []
    def sell(price, timestamp, reason):
        nonlocal cash,pos,losses,paused,cooldown
        fill = price*(1-c.slippage)
        fee = pos['q']*fill*c.fee
        proceeds = pos['q']*fill-fee
        pnl = proceeds-pos['cost']
        cash += proceeds
        trades.append({**pos,'exit_time':timestamp,'exit':fill,'exit_fee':fee,'pnl':pnl,'r':pnl/pos['risk'],'reason':reason})
        losses = losses+1 if pnl < 0 else 0
        paused |= losses >= 3
        pos = None
        cooldown = timestamp.ceil('5min')+pd.Timedelta(minutes=15)
    def mark(price):
        return cash + (pos['q']*price*(1-c.slippage)*(1-c.fee) if pos else 0)
    for i, row in enumerate(data.itertuples()):
        t, o, high, low, close, _ = row
        if t.date() != day:
            day, day_start, losses, paused = t.date(), mark(o), 0, False
        eq = mark(o)
        peak = max(peak,eq)
        if eq <= peak*(1-c.drawdown):
            halted = True
        if eq <= day_start*(1-c.daily_loss):
            paused = True
        if pos:
            age = (t-pos['entry_time']).total_seconds()/60
            if halted or paused:
                sell(o,t,'drawdown' if halted else 'daily_loss')
            elif o <= pos['stop']:
                sell(o,t,'stop_gap')
            elif o >= pos['target']:
                sell(pos['target'],t,'target')
            elif age >= 180 or (c.early_time_exit and age >= 60 and not pos['time_checked'] and mark(o)-cash-pos['cost'] < .3*pos['risk']) or regime[i]:
                sell(o,t,'regime' if regime[i] else 'time')
            elif age >= 60:
                pos['time_checked'] = True
        if pos is None and not (paused or halted or blocked[i]) and t >= cooldown and signal[i]:
            # Skip stale/chased entries: validate signal-close and executable-open distances.
            if .004 <= (refs[i]-stops[i])/refs[i] <= .012:
                p = size_trade(o,stops[i],cash,cash,c)
                if p:
                    pos = {**p,'entry_time':t,'time_checked':False}
                    cash -= pos['cost']
        if pos:
            # Conservative minute-bar ordering: adverse low before high.
            budget_stop = max(pos['stop'], (day_start*(1-c.daily_loss)-cash)/(pos['q']*(1-c.slippage)*(1-c.fee)), (peak*(1-c.drawdown)-cash)/(pos['q']*(1-c.slippage)*(1-c.fee)))
            if low <= budget_stop:
                is_dd = budget_stop > pos['stop'] and abs(mark(budget_stop)-peak*(1-c.drawdown)) < 1e-7
                is_day = budget_stop > pos['stop'] and not is_dd
                sell(min(o,budget_stop),t+pd.Timedelta(minutes=1),'drawdown' if is_dd else 'daily_loss' if is_day else 'stop')
                halted |= is_dd
                paused |= is_day
            elif high >= pos['target']:
                sell(pos['target'],t+pd.Timedelta(minutes=1),'target')
        eq = mark(close)
        peak = max(peak,eq)
        curve.append((t+pd.Timedelta(minutes=1),eq, bool(pos)))
    if pos:
        sell(data.close.iloc[-1],data.index[-1]+pd.Timedelta(minutes=1),'end_of_data')
        curve[-1] = (curve[-1][0],cash,False)
    ledger = pd.DataFrame(trades)
    equity = pd.DataFrame(curve, columns=['time','equity','invested']).set_index('time')
    pnl = ledger.pnl if len(ledger) else pd.Series(dtype=float)
    gross_loss = -pnl[pnl<0].sum()
    dd = equity.equity / equity.equity.cummax().clip(lower=c.equity)-1
    # Equal-cost full-allocation BTC benchmark, including terminal liquidation.
    bh = c.equity/(data.open.iloc[0]*(1+c.slippage)*(1+c.fee))*data.close.iloc[-1]*(1-c.slippage)*(1-c.fee)
    summary = dict(config=asdict(c),start=str(data.index[0]),end=str(end),trades=len(ledger),final_equity=cash,net_return=cash/c.equity-1,net_profit=float(pnl.sum()),win_rate=float((pnl>0).mean()) if len(pnl) else None,profit_factor=float(pnl[pnl>0].sum()/gross_loss) if gross_loss else None,expectancy_r=float(ledger.r.mean()) if len(ledger) else None,max_drawdown=float(-dd.min()),fees=float((ledger.entry_fee+ledger.exit_fee).sum()) if len(ledger) else 0.,exposure_fraction=float(equity.invested.mean()),halted=bool(halted),buy_hold_final_equity=float(bh),cash_final_equity=c.equity,news_filter=events is not None)
    streak = longest = 0
    for value in pnl:
        streak = streak+1 if value < 0 else 0
        longest = max(longest,streak)
    summary['longest_losing_streak'] = longest
    summary['average_holding_minutes'] = float(((ledger.exit_time-ledger.entry_time).dt.total_seconds()/60).mean()) if len(ledger) else None
    summary['exit_reasons'] = ledger.reason.value_counts().to_dict() if len(ledger) else {}
    summary['first_halt_time'] = next((str(x['exit_time']) for x in trades if x['reason']=='drawdown'),None)
    return ledger,equity,summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('download'); d.add_argument('--from-month',required=True); d.add_argument('--to-month',required=True); d.add_argument('--data',default='data')
    b = sub.add_parser('run'); b.add_argument('--data',default='data'); b.add_argument('--start',required=True); b.add_argument('--end',required=True); b.add_argument('--out',default='reports/run'); b.add_argument('--slippage',type=float,default=.0002); b.add_argument('--fee',type=float,default=.001); b.add_argument('--events',help='CSV with UTC time column; scheduled event times only')
    a = parser.parse_args()
    if a.command == 'download':
        months = [str(x) for x in pd.period_range(a.from_month,a.to_month,freq='M')]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for path in pool.map(lambda m:download_month(m,Path(a.data)),months):
                print(path,flush=True)
    else:
        if not 0 <= a.fee < .01 or not 0 <= a.slippage < .01:
            parser.error('Fees/slippage must be decimal fractions between 0 and 0.01')
        events = pd.to_datetime(pd.read_csv(a.events)['time'],utc=True) if a.events else None
        df = read_data(Path(a.data))
        start,end = pd.Timestamp(a.start,tz='UTC'),pd.Timestamp(a.end,tz='UTC')
        if start < df.index[0]+pd.Timedelta(hours=1000) or end > df.index[-1]+pd.Timedelta(minutes=1):
            parser.error('Data must cover requested range plus 1000 hours warm-up')
        trades,eq,summary = run(df,Config(fee=a.fee,slippage=a.slippage),start,end,events=events)
        out = Path(a.out); out.mkdir(parents=True,exist_ok=True)
        trades.to_csv(out/'trades.csv',index=False)
        eq.resample('1D').last().to_csv(out/'daily_equity.csv')
        summary['data_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(a.data).glob('*.zip'))}
        (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
        print(json.dumps(summary,indent=2,allow_nan=False))

if __name__ == '__main__':
    main()
