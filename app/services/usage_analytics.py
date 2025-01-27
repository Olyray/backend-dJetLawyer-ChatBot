from sqlalchemy import func
from typing import List
from app.models.token_usage import TokenUsage
from app.db.session import SessionLocal
from app.schemas.usage import MonthlyUsage, UserMonthlyUsage, TokenUsage as TokenUsageSchema
import uuid

def get_monthly_average_usage() -> List[MonthlyUsage]:
    with SessionLocal() as db:
        result = db.query(
            func.avg(TokenUsage.tokens_used).label('avg_tokens'),
            func.stddev_pop(TokenUsage.tokens_used).label('std_dev_tokens'),
            func.date_trunc('month', TokenUsage.timestamp).label('month')
        ).group_by(func.date_trunc('month', TokenUsage.timestamp)).all()
    
    return [
        MonthlyUsage(
            month=r.month, 
            avg_tokens=r.avg_tokens, 
            std_dev_tokens=r.std_dev_tokens if r.std_dev_tokens is not None else 0
            ) for r in result
        ]

def get_user_monthly_usage(user_id: uuid) -> List[UserMonthlyUsage]:
    with SessionLocal() as db:
        result = db.query(
            func.sum(TokenUsage.tokens_used).label('total_tokens'),
            func.date_trunc('month', TokenUsage.timestamp).label('month')
        ).filter(TokenUsage.user_id == user_id).group_by(
            func.date_trunc('month', TokenUsage.timestamp)
        ).all()
    
    return [UserMonthlyUsage(month=r.month, total_tokens=r.total_tokens) for r in result]

def get_recent_token_usage(user_id: uuid, limit: int = 10) -> List[TokenUsageSchema]:
    with SessionLocal() as db:
        usage = db.query(TokenUsage).filter(TokenUsage.user_id == user_id).order_by(TokenUsage.timestamp.desc()).limit(limit).all()
    return [TokenUsageSchema.from_orm(u) for u in usage]