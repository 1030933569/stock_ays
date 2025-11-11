"""
Prophet趋势预测器
用于预测未来N个月的价格趋势
"""

from __future__ import annotations

import warnings
import pandas as pd
import numpy as np

# 抑制Prophet的警告信息
warnings.filterwarnings('ignore')

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("警告: Prophet未安装，预测功能将被禁用")
    print("安装方法: pip install prophet")


class ProphetPredictor:
    """
    Prophet趋势预测器
    
    功能：
    1. 分解时间序列（趋势 + 季节性）
    2. 预测未来N个月价格
    3. 给出置信区间
    4. 提取可用于ML的特征
    """
    
    def __init__(self, forecast_periods: int = 3, changepoint_prior_scale: float = 0.05):
        """
        Args:
            forecast_periods: 预测未来N个月
            changepoint_prior_scale: 趋势灵活性（0.001-0.5，越大越灵活）
        """
        self.forecast_periods = forecast_periods
        self.changepoint_prior_scale = changepoint_prior_scale
        self.enabled = PROPHET_AVAILABLE
    
    def predict_trend(self, monthly_df: pd.DataFrame) -> dict | None:
        """
        预测未来趋势
        
        Args:
            monthly_df: 月线K线数据（需要date和close列）
            
        Returns:
            {
                'forecast_return': float,      # 预测N个月收益率
                'trend_direction': str,        # 趋势方向
                'confidence': float,           # 置信度 (0-1)
                'trend_strength': float,       # 趋势强度
                'prophet_features': dict,      # Prophet特征（用于ML）
                'current_price': float,
                'predicted_price': float
            }
        """
        if not self.enabled:
            return None
        
        if len(monthly_df) < 12:
            return None
        
        # 准备Prophet数据
        df_prophet = self._prepare_data(monthly_df)
        if df_prophet is None:
            return None
        
        try:
            # 训练Prophet模型
            model = self._train_prophet(df_prophet)
            
            # 生成预测
            forecast = self._generate_forecast(model, df_prophet)
            
            # 提取结果
            result = self._extract_results(df_prophet, forecast)
            
            return result
            
        except Exception as e:
            print(f"Prophet预测失败: {e}")
            return None
    
    def _prepare_data(self, monthly_df: pd.DataFrame) -> pd.DataFrame | None:
        """
        准备Prophet格式数据
        """
        if 'date' not in monthly_df.columns or 'close' not in monthly_df.columns:
            return None
        
        df_prophet = monthly_df[['date', 'close']].copy()
        df_prophet.columns = ['ds', 'y']
        
        # 确保日期格式正确
        df_prophet['ds'] = pd.to_datetime(df_prophet['ds'])
        
        # 确保价格是数值
        df_prophet['y'] = pd.to_numeric(df_prophet['y'], errors='coerce')
        
        # 删除NaN
        df_prophet = df_prophet.dropna()
        
        if len(df_prophet) < 12:
            return None
        
        return df_prophet
    
    def _train_prophet(self, df_prophet: pd.DataFrame) -> Prophet:
        """
        训练Prophet模型
        """
        model = Prophet(
            yearly_seasonality=True,       # 年度季节性（如财报季）
            weekly_seasonality=False,      # 月线数据不需要周季节性
            daily_seasonality=False,       # 月线数据不需要日季节性
            changepoint_prior_scale=self.changepoint_prior_scale,
            interval_width=0.95,           # 95%置信区间
            seasonality_mode='additive'    # 加法模式（更适合股票）
        )
        
        # 静默训练
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(df_prophet)
        
        return model
    
    def _generate_forecast(self, model: Prophet, df_prophet: pd.DataFrame) -> pd.DataFrame:
        """
        生成预测
        """
        # 创建未来日期
        future = model.make_future_dataframe(periods=self.forecast_periods, freq='M')
        
        # 预测
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            forecast = model.predict(future)
        
        return forecast
    
    def _extract_results(self, df_prophet: pd.DataFrame, forecast: pd.DataFrame) -> dict:
        """
        提取预测结果
        """
        # 当前价格和预测价格
        current_price = df_prophet['y'].iloc[-1]
        predicted_price = forecast['yhat'].iloc[-1]
        
        # 预测收益率
        forecast_return = (predicted_price - current_price) / current_price
        
        # 判断趋势方向
        trend_direction = self._classify_trend(forecast_return)
        
        # 计算置信度
        future_lower = forecast['yhat_lower'].iloc[-1]
        future_upper = forecast['yhat_upper'].iloc[-1]
        uncertainty = (future_upper - future_lower) / current_price
        confidence = max(0, min(1, 1 - uncertainty))  # 不确定性越小，置信度越高
        
        # 提取Prophet特征
        prophet_features = self._extract_prophet_features(forecast, df_prophet)
        
        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(forecast, current_price)
        
        return {
            'forecast_return': forecast_return,
            'trend_direction': trend_direction,
            'confidence': confidence,
            'trend_strength': trend_strength,
            'prophet_features': prophet_features,
            'current_price': current_price,
            'predicted_price': predicted_price,
            'lower_bound': future_lower,
            'upper_bound': future_upper
        }
    
    def _classify_trend(self, forecast_return: float) -> str:
        """
        分类趋势方向
        """
        if forecast_return > 0.10:
            return 'strong_up'      # 强烈上涨（>10%）
        elif forecast_return > 0.05:
            return 'up'             # 上涨（5-10%）
        elif forecast_return > 0.02:
            return 'weak_up'        # 弱上涨（2-5%）
        elif forecast_return > -0.02:
            return 'flat'           # 横盘（±2%）
        elif forecast_return > -0.05:
            return 'weak_down'      # 弱下跌（-2--5%）
        elif forecast_return > -0.10:
            return 'down'           # 下跌（-5--10%）
        else:
            return 'strong_down'    # 强烈下跌（<-10%）
    
    def _extract_prophet_features(self, forecast: pd.DataFrame, df_prophet: pd.DataFrame) -> dict:
        """
        提取Prophet分解的特征
        """
        # 最后一个历史数据点的特征
        last_historical_idx = len(df_prophet) - 1
        
        features = {
            'trend': forecast['trend'].iloc[last_historical_idx],
            'trend_change': forecast['trend'].iloc[last_historical_idx] - 
                          forecast['trend'].iloc[max(0, last_historical_idx - 6)],
            'yearly_seasonality': forecast.get('yearly', pd.Series([0] * len(forecast))).iloc[last_historical_idx],
        }
        
        # 添加趋势变化率
        if len(forecast) >= 6:
            recent_trend = forecast['trend'].iloc[-6:].values
            if len(recent_trend) >= 2:
                try:
                    from scipy.stats import linregress
                    x = np.arange(len(recent_trend))
                    slope = linregress(x, recent_trend).slope
                    features['trend_slope'] = slope
                except:
                    features['trend_slope'] = 0
            else:
                features['trend_slope'] = 0
        else:
            features['trend_slope'] = 0
        
        return features
    
    def _calculate_trend_strength(self, forecast: pd.DataFrame, current_price: float) -> float:
        """
        计算趋势强度（0-1）
        基于趋势分量的斜率
        """
        if len(forecast) < 6:
            return 0
        
        # 取最近6个月的趋势
        recent_trend = forecast['trend'].iloc[-6:].values
        
        if len(recent_trend) < 2:
            return 0
        
        try:
            # 计算趋势斜率
            x = np.arange(len(recent_trend))
            from scipy.stats import linregress
            slope = linregress(x, recent_trend).slope
            
            # 归一化到0-1
            normalized_slope = abs(slope) / current_price
            strength = min(normalized_slope * 10, 1.0)  # 放大10倍并限制到1
            
            return strength
        except:
            return 0
    
    def extract_features_for_ml(self, monthly_df: pd.DataFrame) -> dict:
        """
        提取Prophet特征用于机器学习
        
        Returns:
            包含Prophet特征的字典，可直接加入特征矩阵
        """
        prediction = self.predict_trend(monthly_df)
        
        if prediction is None:
            # 如果预测失败，返回零值特征
            return {
                'prophet_forecast_return': 0,
                'prophet_confidence': 0,
                'prophet_trend_strength': 0,
                'prophet_trend': 0,
                'prophet_trend_change': 0,
                'prophet_trend_slope': 0
            }
        
        # 提取关键特征
        features = {
            'prophet_forecast_return': prediction['forecast_return'],
            'prophet_confidence': prediction['confidence'],
            'prophet_trend_strength': prediction['trend_strength'],
            'prophet_trend': prediction['prophet_features']['trend'],
            'prophet_trend_change': prediction['prophet_features']['trend_change'],
            'prophet_trend_slope': prediction['prophet_features']['trend_slope']
        }
        
        return features
    
    def get_feature_names(self) -> list:
        """
        返回Prophet特征名列表
        """
        return [
            'prophet_forecast_return',
            'prophet_confidence',
            'prophet_trend_strength',
            'prophet_trend',
            'prophet_trend_change',
            'prophet_trend_slope'
        ]


# 简单的后备预测器（当Prophet不可用时）
class SimpleTrendPredictor:
    """
    简单的线性预测器（Prophet的后备方案）
    """
    
    def __init__(self, forecast_periods: int = 3):
        self.forecast_periods = forecast_periods
    
    def predict_trend(self, monthly_df: pd.DataFrame) -> dict | None:
        """
        使用简单线性回归预测
        """
        if len(monthly_df) < 12:
            return None
        
        try:
            # 取最近12个月
            recent = monthly_df.tail(12)
            prices = recent['close'].values
            
            # 线性回归
            x = np.arange(len(prices))
            from scipy.stats import linregress
            slope, intercept, r_value, _, _ = linregress(x, prices)
            
            # 预测未来
            future_x = len(prices) + self.forecast_periods - 1
            predicted_price = slope * future_x + intercept
            
            current_price = prices[-1]
            forecast_return = (predicted_price - current_price) / current_price
            
            # 简单的置信度估计（基于R²）
            confidence = abs(r_value)
            
            return {
                'forecast_return': forecast_return,
                'trend_direction': 'up' if forecast_return > 0 else 'down',
                'confidence': confidence,
                'trend_strength': abs(slope) / current_price,
                'prophet_features': {
                    'trend': current_price,
                    'trend_change': slope * 6,
                    'trend_slope': slope
                },
                'current_price': current_price,
                'predicted_price': predicted_price
            }
        except:
            return None

