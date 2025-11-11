"""
简化版特征工程 - 30个核心投资特征
专为股票筛选投资设计，不做高频量化交易
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from indicators import calculate_all_indicators, calculate_ma_slope


class SimpleFeatureEngineer:
    """
    简化版特征工程：只保留投资筛选需要的30个核心特征
    
    特征分类：
    - 趋势类（10个）：判断大势
    - 波动类（5个）：识别筑底/突破
    - 量价类（5个）：判断量能健康度
    - 动能类（5个）：判断买入时机
    - 支撑阻力类（3个）：判断位置
    - 时间类（2个）：考虑季节性
    """
    
    def create_investment_features(self, monthly_df: pd.DataFrame) -> pd.DataFrame:
        """
        创建30个核心投资特征
        
        Args:
            monthly_df: 月线K线数据
            
        Returns:
            添加了特征的DataFrame
        """
        df = monthly_df.copy()
        
        # 确保数据类型正确（严格转换）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 删除包含NaN的关键列
        if df['close'].isna().all():
            return pd.DataFrame()  # 返回空DataFrame
        
        # ===== 1. 趋势类（10个）=====
        # 先计算基础技术指标
        df = calculate_all_indicators(df, freq='monthly')
        
        # 1.1 均线斜率
        if 'MA10' in df.columns:
            df['MA10_slope'] = calculate_ma_slope(df, 'MA10', lookback=6)
        else:
            df['MA10_slope'] = 0
        
        # 1.2 价格相对MA10位置
        if 'MA10' in df.columns:
            df['price_to_ma10'] = df['close'] / df['MA10']
        else:
            df['price_to_ma10'] = 1
        
        # 1.3 收益率系列
        df['return_6m'] = df['close'].pct_change(6)
        df['return_12m'] = df['close'].pct_change(12)
        
        # 1.4 均线多头排列得分（0-2分）
        ma_alignment = 0
        if 'MA5' in df.columns and 'MA10' in df.columns:
            ma_alignment += (df['MA5'] > df['MA10']).astype(int)
        if 'MA10' in df.columns and 'MA20' in df.columns:
            ma_alignment += (df['MA10'] > df['MA20']).astype(int)
        df['ma_alignment'] = ma_alignment
        
        # 1.5 价格相对12月高点位置（月线数据用12个月）
        df['price_to_52w_high'] = df['close'] / df['close'].rolling(12).max()
        
        # 1.6 趋势强度（简化版ADX）
        if 'high' in df.columns and 'low' in df.columns:
            df['trend_strength'] = self._calculate_simple_trend_strength(df)
        else:
            df['trend_strength'] = 0
        
        # 1.7-1.10 预留给Prophet特征（在MLRanker中添加）
        
        # ===== 2. 波动类（5个）=====
        # 2.1 6个月波动率（变异系数）
        df['volatility_6m'] = df['close'].rolling(6).std() / df['close'].rolling(6).mean()
        
        # 2.2 波动收敛度（VCP核心特征）
        vol_3m = df['close'].rolling(3).std()
        vol_6m = df['close'].rolling(6).std()
        df['volatility_contraction'] = vol_3m / vol_6m
        
        # 2.3 最大回撤（24个月）
        rolling_max = df['close'].rolling(24).max()
        df['max_drawdown_24m'] = (rolling_max - df['close']) / rolling_max
        
        # 2.4 横盘月数检测
        df['consolidation_score'] = self._detect_consolidation(df)
        
        # 2.5 突破信号
        df['breakout_signal'] = self._detect_breakout(df)
        
        # ===== 3. 量价类（5个）=====
        # 3.1 量能比
        df['volume_ma20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']
        
        # 3.2 上涨月vs下跌月量能比
        df['volume_up_down_ratio'] = self._calculate_volume_up_down_ratio(df)
        
        # 3.3 OBV趋势
        df['price_change'] = df['close'].diff()
        df['volume_direction'] = np.where(df['price_change'] > 0, df['volume'], -df['volume'])
        df['obv'] = df['volume_direction'].cumsum()
        df['obv_trend'] = df['obv'].diff(3)  # OBV 3个月变化
        
        # 3.4 放量标记
        df['volume_surge'] = (df['volume_ratio'] > 1.5).astype(int)
        
        # 3.5 量价配合度
        df['volume_cooperation'] = self._check_volume_cooperation(df)
        
        # ===== 4. 动能类（5个）=====
        # MACD、RSI已在calculate_all_indicators中计算
        
        # 4.1 MACD金叉信号
        if 'MACD' in df.columns and 'MACD_signal' in df.columns:
            df['macd_cross'] = (
                (df['MACD'].shift(1) < df['MACD_signal'].shift(1)) & 
                (df['MACD'] > df['MACD_signal'])
            ).astype(int)
        else:
            df['macd_cross'] = 0
        
        # 4.2 6个月动量
        df['momentum_6m'] = df['close'] - df['close'].shift(6)
        
        # 4.3 动量加速度
        momentum_3m = df['close'] - df['close'].shift(3)
        df['momentum_acceleration'] = momentum_3m.diff(3)
        
        # 4.4 RSI位置（如果有）
        if 'RSI' in df.columns:
            df['rsi_position'] = np.where(df['RSI'] < 30, -1,  # 超卖
                                 np.where(df['RSI'] > 70, 1,   # 超买
                                          0))                   # 正常
        else:
            df['rsi_position'] = 0
        
        # 4.5 价格动量百分比
        df['momentum_pct_6m'] = df['return_6m']  # 复用
        
        # ===== 5. 支撑阻力类（3个）=====
        # 5.1 支撑位（20周期低点）
        df['support_level'] = df['low'].rolling(20).min()
        
        # 5.2 阻力位（20周期高点）
        df['resistance_level'] = df['high'].rolling(20).max()
        
        # 5.3 距离阻力位
        df['distance_to_resistance'] = (df['resistance_level'] - df['close']) / df['close']
        
        # ===== 6. 时间类（2个）=====
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df['quarter'] = df['date'].dt.quarter
            df['month'] = df['date'].dt.month
            df['is_earnings_season'] = df['month'].isin([4, 8, 10]).astype(int)
        else:
            df['quarter'] = 0
            df['is_earnings_season'] = 0
        
        return df
    
    def _calculate_simple_trend_strength(self, df: pd.DataFrame, period: int = 6) -> pd.Series:
        """
        计算简化版趋势强度
        基于价格斜率的标准化
        """
        # 计算价格线性回归斜率
        slopes = []
        closes = df['close'].values
        
        for i in range(len(df)):
            if i < period - 1:
                slopes.append(0)
            else:
                y = closes[i - period + 1:i + 1]
                if np.any(np.isnan(y)):
                    slopes.append(0)
                else:
                    x = np.arange(period)
                    slope = np.polyfit(x, y, 1)[0]
                    # 归一化
                    normalized_slope = slope / closes[i] if closes[i] != 0 else 0
                    slopes.append(abs(normalized_slope))  # 绝对值表示趋势强度
        
        return pd.Series(slopes, index=df.index)
    
    def _detect_consolidation(self, df: pd.DataFrame) -> pd.Series:
        """
        检测横盘（0-10分）
        波动率越小、横盘时间越长，分数越高
        """
        scores = []
        
        for i in range(len(df)):
            if i < 8:  # 至少需要8个月数据
                scores.append(0)
                continue
            
            score = 0
            
            # 检测最近4-8个月的波动率
            for lookback in range(4, 9):
                if i >= lookback:
                    period = df['close'].iloc[i - lookback + 1:i + 1]
                    if len(period) > 0:
                        volatility = period.std() / period.mean()
                        if volatility < 0.15:  # 波动率<15%
                            score = max(score, lookback)  # 横盘时间越长分数越高
            
            scores.append(score)
        
        return pd.Series(scores, index=df.index)
    
    def _detect_breakout(self, df: pd.DataFrame) -> pd.Series:
        """
        检测突破信号（0或1）
        突破近期高点且放量
        """
        breakout = pd.Series(0, index=df.index)
        
        if len(df) < 20:
            return breakout
        
        # 20周期最高价
        high_20 = df['high'].rolling(20).max()
        
        # 当前收盘价突破20周期最高
        price_breakout = df['close'] > high_20.shift(1)
        
        # 成交量放大
        volume_surge = df['volume_ratio'] > 1.3
        
        # 两者同时满足
        breakout = (price_breakout & volume_surge).astype(int)
        
        return breakout
    
    def _calculate_volume_up_down_ratio(self, df: pd.DataFrame, lookback: int = 6) -> pd.Series:
        """
        计算上涨月vs下跌月的量能比
        """
        ratios = []
        
        for i in range(len(df)):
            if i < lookback:
                ratios.append(1.0)
                continue
            
            recent = df.iloc[i - lookback + 1:i + 1]
            
            # 分离上涨和下跌月
            up_months = recent[recent['close'].diff() > 0]
            down_months = recent[recent['close'].diff() < 0]
            
            up_volume = up_months['volume'].mean() if len(up_months) > 0 else 1
            down_volume = down_months['volume'].mean() if len(down_months) > 0 else 1
            
            ratio = up_volume / down_volume if down_volume > 0 else 1.0
            ratios.append(ratio)
        
        return pd.Series(ratios, index=df.index)
    
    def _check_volume_cooperation(self, df: pd.DataFrame, lookback: int = 6) -> pd.Series:
        """
        检查量价配合（1表示配合好，0表示不好）
        上涨时放量、下跌时缩量
        """
        cooperation = []
        
        for i in range(len(df)):
            if i < lookback:
                cooperation.append(0)
                continue
            
            recent = df.iloc[i - lookback + 1:i + 1]
            
            # 计算上涨日和下跌日的平均量能比
            price_changes = recent['close'].diff()
            
            up_volume_ratio = recent[price_changes > 0]['volume_ratio'].mean()
            down_volume_ratio = recent[price_changes < 0]['volume_ratio'].mean()
            
            # 上涨时量能比 > 下跌时量能比，则配合好
            if pd.notna(up_volume_ratio) and pd.notna(down_volume_ratio):
                is_good = 1 if up_volume_ratio > down_volume_ratio else 0
            else:
                is_good = 0
            
            cooperation.append(is_good)
        
        return pd.Series(cooperation, index=df.index)
    
    def get_core_feature_names(self) -> list:
        """
        返回30个核心特征名
        """
        return [
            # 趋势类（10个）
            'MA10', 'MA10_slope', 'price_to_ma10', 'return_6m', 'return_12m',
            'ma_alignment', 'price_to_52w_high', 'trend_strength',
            
            # 波动类（5个）
            'volatility_6m', 'volatility_contraction', 'max_drawdown_24m',
            'consolidation_score', 'breakout_signal',
            
            # 量价类（5个）
            'volume_ratio', 'volume_up_down_ratio', 'obv_trend',
            'volume_surge', 'volume_cooperation',
            
            # 动能类（5个）
            'MACD', 'MACD_hist', 'macd_cross', 'momentum_6m', 'momentum_acceleration',
            
            # 支撑阻力类（3个）
            'support_level', 'resistance_level', 'distance_to_resistance',
            
            # 时间类（2个）
            'quarter', 'is_earnings_season',
        ]
    
    def get_feature_importances(self) -> dict:
        """
        返回特征的预期重要性（用于后续分析）
        """
        return {
            # 趋势类（高重要性）
            'MA10_slope': 0.95,
            'return_6m': 0.90,
            'return_12m': 0.85,
            'price_to_ma10': 0.80,
            'ma_alignment': 0.85,
            
            # 波动类（中高重要性）
            'volatility_contraction': 0.80,
            'max_drawdown_24m': 0.70,
            'consolidation_score': 0.75,
            
            # 量价类（高重要性）
            'volume_up_down_ratio': 0.85,
            'volume_cooperation': 0.80,
            
            # 动能类（中高重要性）
            'MACD': 0.75,
            'momentum_6m': 0.80,
            
            # 其他（中低重要性）
            'distance_to_resistance': 0.60,
            'quarter': 0.50,
        }

