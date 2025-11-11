"""
技术指标计算库
包含均线、MACD、RSI、ATR、斜率等常用技术指标的计算
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress


def calculate_ma(df: pd.DataFrame, periods: list[int], price_col: str = 'close') -> pd.DataFrame:
    """
    计算移动平均线
    
    Args:
        df: K线数据
        periods: 周期列表，如 [5, 10, 20, 40, 60]
        price_col: 价格列名
        
    Returns:
        添加了MA列的DataFrame
    """
    df = df.copy()
    for period in periods:
        df[f'MA{period}'] = df[price_col].rolling(window=period).mean()
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, 
                   price_col: str = 'close') -> pd.DataFrame:
    """
    计算MACD指标
    
    Args:
        df: K线数据
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期
        price_col: 价格列名
        
    Returns:
        添加了MACD、MACD_signal、MACD_hist列的DataFrame
    """
    df = df.copy()
    
    # 计算EMA
    ema_fast = df[price_col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[price_col].ewm(span=slow, adjust=False).mean()
    
    # MACD线 = 快线 - 慢线
    df['MACD'] = ema_fast - ema_slow
    
    # 信号线 = MACD的EMA
    df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    
    # 柱状图 = MACD - 信号线
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14, price_col: str = 'close') -> pd.DataFrame:
    """
    计算RSI相对强弱指标
    
    Args:
        df: K线数据
        period: 计算周期
        price_col: 价格列名
        
    Returns:
        添加了RSI列的DataFrame
    """
    df = df.copy()
    
    # 计算价格变化
    delta = df[price_col].diff()
    
    # 分离上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 计算平均涨跌
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # 计算RS和RSI
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算ATR平均真实波幅
    
    Args:
        df: K线数据（需要high, low, close列）
        period: 计算周期
        
    Returns:
        添加了ATR列的DataFrame
    """
    df = df.copy()
    
    # 确保数据类型正确
    high = pd.to_numeric(df['high'], errors='coerce')
    low = pd.to_numeric(df['low'], errors='coerce')
    close = pd.to_numeric(df['close'], errors='coerce')
    
    # 计算真实波幅
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 计算ATR
    df['ATR'] = tr.rolling(window=period).mean()
    
    return df


def calculate_ma_slope(df: pd.DataFrame, ma_col: str, lookback: int = 6) -> pd.Series:
    """
    计算均线斜率（归一化）
    
    Args:
        df: K线数据
        ma_col: 均线列名
        lookback: 回看周期
        
    Returns:
        归一化的斜率序列（斜率/当前价格）
    """
    slopes = []
    ma_values = df[ma_col].values
    
    for i in range(len(df)):
        if i < lookback - 1 or pd.isna(ma_values[i]):
            slopes.append(np.nan)
        else:
            x = np.arange(lookback)
            y = ma_values[i - lookback + 1:i + 1]
            
            # 如果有NaN值，跳过
            if np.any(np.isnan(y)):
                slopes.append(np.nan)
                continue
            
            # 线性回归计算斜率
            slope = linregress(x, y).slope
            # 归一化：斜率 / 当前均线值
            normalized_slope = slope / ma_values[i] if ma_values[i] != 0 else 0
            slopes.append(normalized_slope)
    
    return pd.Series(slopes, index=df.index)


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    计算量能比率（当前成交量 / N日均量）
    
    Args:
        df: K线数据
        period: 计算周期
        
    Returns:
        添加了volume_ratio列的DataFrame
    """
    df = df.copy()
    
    # 确保volume是数值类型
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    
    # 计算均量
    avg_volume = df['volume'].rolling(window=period).mean()
    
    # 计算量比
    df['volume_ratio'] = df['volume'] / avg_volume
    
    return df


def calculate_price_position(df: pd.DataFrame, period: int = 52, price_col: str = 'close') -> pd.DataFrame:
    """
    计算价格相对位置（当前价 / N周期最高价）
    
    Args:
        df: K线数据
        period: 回看周期
        price_col: 价格列名
        
    Returns:
        添加了price_position列的DataFrame
    """
    df = df.copy()
    
    # 计算N周期最高价
    highest = df[price_col].rolling(window=period).max()
    
    # 计算相对位置
    df['price_position'] = df[price_col] / highest
    
    return df


def check_ma_alignment(df: pd.DataFrame, ma_cols: list[str], ascending: bool = True) -> pd.Series:
    """
    检查均线排列（多头/空头排列）
    
    Args:
        df: K线数据
        ma_cols: 均线列名列表，如 ['MA5', 'MA10', 'MA20']
        ascending: True为多头排列（MA5>MA10>MA20），False为空头排列
        
    Returns:
        布尔序列，True表示满足排列条件
    """
    if len(ma_cols) < 2:
        return pd.Series([True] * len(df), index=df.index)
    
    result = pd.Series([True] * len(df), index=df.index)
    
    for i in range(len(ma_cols) - 1):
        if ascending:
            result &= df[ma_cols[i]] > df[ma_cols[i + 1]]
        else:
            result &= df[ma_cols[i]] < df[ma_cols[i + 1]]
    
    return result


def analyze_volume_pattern(df: pd.DataFrame, lookback: int = 8) -> dict:
    """
    分析量价配合模式
    
    Args:
        df: K线数据（需要close和volume列）
        lookback: 回看周期
        
    Returns:
        包含量价分析结果的字典
    """
    if len(df) < lookback:
        return {
            'up_volume_ratio': 0,
            'down_volume_ratio': 0,
            'volume_cooperation': False
        }
    
    recent = df.tail(lookback).copy()
    
    # 计算涨跌
    recent['price_change'] = recent['close'].diff()
    recent['volume'] = pd.to_numeric(recent['volume'], errors='coerce')
    
    # 分离上涨和下跌周期
    up_periods = recent[recent['price_change'] > 0]
    down_periods = recent[recent['price_change'] < 0]
    
    # 计算平均成交量
    up_volume = up_periods['volume'].mean() if len(up_periods) > 0 else 0
    down_volume = down_periods['volume'].mean() if len(down_periods) > 0 else 1
    
    # 计算量能比
    volume_ratio = up_volume / down_volume if down_volume > 0 else 0
    
    return {
        'up_volume_ratio': up_volume,
        'down_volume_ratio': down_volume,
        'volume_cooperation': volume_ratio > 1.2,  # 上涨周量能大于下跌周
        'volume_ratio': volume_ratio
    }


def detect_golden_cross(df: pd.DataFrame, fast_ma: str = 'MA5', slow_ma: str = 'MA10', 
                        lookback: int = 3) -> bool:
    """
    检测均线金叉（近期发生）
    
    Args:
        df: K线数据
        fast_ma: 快线列名
        slow_ma: 慢线列名
        lookback: 回看周期（检测最近N个周期内是否金叉）
        
    Returns:
        True表示近期发生金叉
    """
    if len(df) < lookback + 1:
        return False
    
    recent = df.tail(lookback + 1)
    
    # 检查是否有金叉（快线从下方穿越慢线）
    for i in range(1, len(recent)):
        prev_diff = recent.iloc[i-1][fast_ma] - recent.iloc[i-1][slow_ma]
        curr_diff = recent.iloc[i][fast_ma] - recent.iloc[i][slow_ma]
        
        if prev_diff <= 0 and curr_diff > 0:
            return True
    
    return False


def detect_macd_golden_cross(df: pd.DataFrame, lookback: int = 3) -> bool:
    """
    检测MACD金叉（近期发生）
    
    Args:
        df: K线数据（需要先计算MACD）
        lookback: 回看周期
        
    Returns:
        True表示近期发生MACD金叉
    """
    if 'MACD' not in df.columns or 'MACD_signal' not in df.columns:
        return False
    
    if len(df) < lookback + 1:
        return False
    
    recent = df.tail(lookback + 1)
    
    # 检查MACD是否金叉
    for i in range(1, len(recent)):
        prev_diff = recent.iloc[i-1]['MACD'] - recent.iloc[i-1]['MACD_signal']
        curr_diff = recent.iloc[i]['MACD'] - recent.iloc[i]['MACD_signal']
        
        if prev_diff <= 0 and curr_diff > 0:
            return True
    
    return False


def calculate_all_indicators(df: pd.DataFrame, freq: str = 'daily') -> pd.DataFrame:
    """
    一次性计算所有技术指标
    
    Args:
        df: K线数据
        freq: 频率类型 'daily', 'weekly', 'monthly'
        
    Returns:
        添加了所有指标的DataFrame
    """
    df = df.copy()
    
    # 确保数据类型正确
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 根据频率选择合适的均线周期
    if freq == 'daily':
        ma_periods = [5, 10, 20, 40, 60]
    elif freq == 'weekly':
        ma_periods = [5, 10, 20, 40]
    else:  # monthly
        ma_periods = [5, 10, 20]
    
    # 计算各类指标
    df = calculate_ma(df, ma_periods)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_atr(df)
    df = calculate_volume_ratio(df, period=20)
    df = calculate_price_position(df, period=52)
    
    # 计算主要均线的斜率
    if 'MA10' in df.columns:
        df['MA10_slope'] = calculate_ma_slope(df, 'MA10', lookback=6)
    if 'MA40' in df.columns:
        df['MA40_slope'] = calculate_ma_slope(df, 'MA40', lookback=6)
    
    return df


def find_support_resistance(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    寻找支撑位和阻力位
    
    Args:
        df: K线数据
        lookback: 回看周期
        
    Returns:
        包含支撑位和阻力位的字典
    """
    if len(df) < lookback:
        return {'support': None, 'resistance': None}
    
    recent = df.tail(lookback)
    
    # 简单的支撑阻力：最近N期的低点和高点
    support = recent['low'].min()
    resistance = recent['high'].max()
    
    return {
        'support': support,
        'resistance': resistance,
        'current': df.iloc[-1]['close']
    }

