"""
ML智能排序器
对规则筛选后的股票进行智能排序和评分
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from simple_feature_engineering import SimpleFeatureEngineer
from prophet_predictor import ProphetPredictor

warnings.filterwarnings('ignore')

# 检查LightGBM是否可用
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("警告: LightGBM未安装，将使用规则评分")
    print("安装方法: pip install lightgbm")


class MLRanker:
    """
    ML智能排序器
    
    功能：
    1. 提取30个核心特征
    2. Prophet预测未来趋势
    3. LightGBM打分排序（如果已训练）
    4. 规则评分（LightGBM不可用时的后备方案）
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: 配置字典
        """
        self.config = config
        self.feature_engineer = SimpleFeatureEngineer()
        
        # Prophet预测器
        prophet_config = config.get('ml_ranking', {}).get('prophet', {})
        self.prophet_predictor = ProphetPredictor(
            forecast_periods=prophet_config.get('forecast_periods', 3),
            changepoint_prior_scale=prophet_config.get('changepoint_prior_scale', 0.05)
        )
        
        # LightGBM模型（可选）
        self.model = None
        self.feature_names = []
        self.use_prophet = config.get('ml_ranking', {}).get('use_prophet', True)
    
    def rank_stocks(self, watchlist_df: pd.DataFrame, data_dir) -> pd.DataFrame:
        """
        对观察池股票进行排序
        
        Args:
            watchlist_df: 规则筛选后的观察池
            data_dir: K线数据目录
            
        Returns:
            排序后的DataFrame，增加了ML评分和预测
        """
        # 确保data_dir是Path对象
        if not isinstance(data_dir, Path):
            data_dir = Path(str(data_dir))
        
        results = []
        
        print(f"\n【ML排序】处理{len(watchlist_df)}只候选股票...")
        
        for idx, row in tqdm(watchlist_df.iterrows(), total=len(watchlist_df), desc="ML评分"):
            stock_code = str(row['code'])  # 确保是字符串
            
            try:
                # 加载月线数据
                monthly_df = self._load_kline_data(stock_code, data_dir, 'monthly')
                if monthly_df is None or len(monthly_df) < 24:
                    continue
                
                # Step 1: 提取特征
                features = self.extract_features(monthly_df)
                if features is None:
                    continue
                
                # Step 2: Prophet预测（可选）
                prophet_pred = None
                if self.use_prophet and self.prophet_predictor.enabled:
                    prophet_pred = self.prophet_predictor.predict_trend(monthly_df)
                    if prophet_pred:
                        # 将Prophet特征加入
                        prophet_features = self.prophet_predictor.extract_features_for_ml(monthly_df)
                        features.update(prophet_features)
                
                # Step 3: 计算综合评分
                ml_score = self.calculate_score(features, prophet_pred)
                
                # 构建结果
                result = row.to_dict()
                result.update({
                    'ml_score': round(ml_score, 2),
                    'prophet_forecast_return': round(prophet_pred['forecast_return'] * 100, 2) if prophet_pred else 0,
                    'prophet_trend': prophet_pred['trend_direction'] if prophet_pred else 'unknown',
                    'prophet_confidence': round(prophet_pred['confidence'], 2) if prophet_pred else 0,
                })
                
                # 保存关键特征（用于分析）
                result['key_features'] = self._extract_key_features(features)
                
                results.append(result)
                
            except Exception as e:
                import traceback
                print(f"\n处理 {stock_code} 失败: {e}")
                if stock_code == '600010':  # 只打印第一个的详细错误
                    traceback.print_exc()
                continue
        
        if not results:
            print("警告: 没有股票通过ML排序")
            return pd.DataFrame()
        
        # 转为DataFrame
        results_df = pd.DataFrame(results)
        
        # 按ML评分排序
        results_df = results_df.sort_values('ml_score', ascending=False)
        
        # 限制输出数量
        top_n = self.config.get('ml_ranking', {}).get('output', {}).get('top_n', 50)
        min_score = self.config.get('ml_ranking', {}).get('output', {}).get('min_score', 60)
        
        # 筛选：分数>=阈值，数量<=top_n
        results_df = results_df[results_df['ml_score'] >= min_score].head(top_n)
        
        return results_df
    
    def extract_features(self, monthly_df: pd.DataFrame) -> dict | None:
        """
        提取所有特征
        
        Returns:
            特征字典
        """
        try:
            # 使用特征工程类提取30个核心特征
            features_df = self.feature_engineer.create_investment_features(monthly_df)
            
            if features_df.empty or len(features_df) == 0:
                return None
            
            # 取最新一行（当前状态）
            latest = features_df.iloc[-1]
            
            # 转为字典
            feature_dict = {}
            for feature_name in self.feature_engineer.get_core_feature_names():
                if feature_name in latest.index:
                    value = latest[feature_name]
                    # 处理NaN和Inf
                    if pd.isna(value) or np.isinf(value):
                        value = 0
                    feature_dict[feature_name] = float(value)
                else:
                    feature_dict[feature_name] = 0
            
            return feature_dict
            
        except Exception as e:
            print(f"特征提取失败: {e}")
            return None
    
    def calculate_score(self, features: dict, prophet_pred: dict = None) -> float:
        """
        计算综合评分（0-100分）
        
        使用规则评分系统（简单、可解释、稳定）
        """
        score = 50  # 基础分
        
        # ===== 趋势类特征（30分）=====
        # MA10斜率（10分）
        ma10_slope = features.get('MA10_slope', 0)
        if ma10_slope > 0.02:
            score += 10
        elif ma10_slope > 0:
            score += 5
        
        # 6个月收益率（10分）
        return_6m = features.get('return_6m', 0)
        if return_6m > 0.10:
            score += 10
        elif return_6m > 0:
            score += 5
        
        # 均线多头排列（10分）
        ma_alignment = features.get('ma_alignment', 0)
        if ma_alignment >= 2:
            score += 10
        elif ma_alignment >= 1:
            score += 5
        
        # ===== 波动收敛特征（20分）=====
        # 波动收敛度（10分）
        vol_contraction = features.get('volatility_contraction', 1)
        if vol_contraction < 0.7:  # 波动明显收敛
            score += 10
        elif vol_contraction < 0.9:
            score += 5
        
        # 横盘评分（10分）
        consolidation = features.get('consolidation_score', 0)
        if consolidation >= 6:
            score += 10
        elif consolidation >= 4:
            score += 5
        
        # ===== 量价配合特征（20分）=====
        # 上涨下跌量能比（10分）
        volume_ud_ratio = features.get('volume_up_down_ratio', 0)
        if volume_ud_ratio > 1.5:
            score += 10
        elif volume_ud_ratio > 1.2:
            score += 5
        
        # 量价配合度（10分）
        volume_coop = features.get('volume_cooperation', 0)
        if volume_coop == 1:
            score += 10
        
        # ===== 动能特征（10分）=====
        # MACD（5分）
        macd = features.get('MACD', 0)
        if macd > 0:
            score += 3
        
        # MACD金叉（2分）
        macd_cross = features.get('macd_cross', 0)
        if macd_cross == 1:
            score += 2
        
        # 动量（5分）
        momentum = features.get('momentum_6m', 0)
        if momentum > 0:
            score += 5
        
        # ===== Prophet预测加分（20分）=====
        if prophet_pred:
            forecast_return = prophet_pred['forecast_return']
            confidence = prophet_pred['confidence']
            
            # 预测收益加分（15分）
            if forecast_return > 0.15:  # 预测涨>15%
                score += 15
            elif forecast_return > 0.10:  # 预测涨>10%
                score += 12
            elif forecast_return > 0.05:  # 预测涨>5%
                score += 8
            elif forecast_return > 0.02:  # 预测涨>2%
                score += 4
            elif forecast_return < -0.05:  # 预测跌>5%
                score -= 10
            
            # 置信度加分（5分）
            if confidence > 0.8:
                score += 5
            elif confidence > 0.6:
                score += 3
        
        # 限制在0-100
        return min(max(score, 0), 100)
    
    def _extract_key_features(self, features: dict) -> str:
        """
        提取关键特征（用于展示）
        """
        key_features = []
        
        if features.get('MA10_slope', 0) > 0.01:
            key_features.append('趋势强劲')
        
        if features.get('volatility_contraction', 1) < 0.8:
            key_features.append('波动收敛')
        
        if features.get('volume_up_down_ratio', 0) > 1.2:
            key_features.append('量能配合')
        
        if features.get('macd_cross', 0) == 1:
            key_features.append('MACD金叉')
        
        if features.get('breakout_signal', 0) == 1:
            key_features.append('突破信号')
        
        return ', '.join(key_features) if key_features else '符合基本条件'
    
    def _load_kline_data(self, stock_code: str, data_dir, freq: str) -> pd.DataFrame | None:
        """
        加载K线数据
        """
        # 确保data_dir是Path对象
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        
        # 确保stock_code是字符串
        stock_code = str(stock_code)
        
        freq_map = {
            'daily': '_daily_1y.csv',
            'weekly': '_weekly_5y.csv',
            'monthly': '_monthly_10y.csv'
        }
        
        file_path = data_dir / stock_code / f"{stock_code}{freq_map[freq]}"
        
        if not file_path.exists():
            return None
        
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                return None
            df = df.sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            return None
    
    def train_lightgbm_model(self, training_data: pd.DataFrame):
        """
        训练LightGBM模型（可选）
        
        Args:
            training_data: 训练数据，包含特征和标签
                          columns: [...features..., 'future_return']
        """
        if not LIGHTGBM_AVAILABLE:
            print("LightGBM不可用，无法训练模型")
            return
        
        # 分离特征和标签
        feature_cols = self.feature_engineer.get_core_feature_names()
        if self.use_prophet:
            feature_cols += self.prophet_predictor.get_feature_names()
        
        X = training_data[feature_cols]
        y = training_data['future_return']
        
        # LightGBM参数
        params = self.config.get('ml_ranking', {}).get('lightgbm', {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'n_estimators': 100,
        })
        
        # 训练
        self.model = lgb.LGBMRegressor(**params)
        self.model.fit(X, y)
        self.feature_names = feature_cols
        
        # 特征重要性
        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n特征重要性 Top 10:")
        print(importance_df.head(10))
        
        return self.model
    
    def save_model(self, path: str):
        """保存模型"""
        if self.model is not None and LIGHTGBM_AVAILABLE:
            self.model.booster_.save_model(path)
            print(f"模型已保存到: {path}")
    
    def load_model(self, path: str):
        """加载模型"""
        if LIGHTGBM_AVAILABLE:
            import lightgbm as lgb
            self.model = lgb.Booster(model_file=path)
            print(f"模型已加载: {path}")

