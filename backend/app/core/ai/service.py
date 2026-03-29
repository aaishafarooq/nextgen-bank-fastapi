from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.ai.config import ai_settings
from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.ai.models import TransactionRiskScore
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.ml.deployment import ModelInference, update_transaction_risk
from backend.app.transaction.enums import TransactionFailureReason
from backend.app.transaction.models import Transaction
from backend.app.transaction.utils import mark_transaction_failed

logger = get_logger()


class TransactionAIService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model_inference = ModelInference(session)

    async def analyze_transaction(
        self, transaction: Transaction, user_id: UUID
    ) -> dict:
        try:
            fraud_probability, prediction_details = (
                await self.model_inference.predict_fraud(transaction)
            )

            risk_score = TransactionRiskScore(
                transaction_id=transaction.id,
                risk_score=fraud_probability,
                risk_factors=prediction_details.get("risk_factors", {}),
                ai_model_version=prediction_details.get("model_version", "unknown"),
            )

            self.session.add(risk_score)

            await update_transaction_risk(
                transaction=transaction,
                fraud_probability=fraud_probability,
                risk_threshold=ai_settings.RISK_SCORE_THRESHOLD,
                prediction_details=prediction_details,
                session=self.session,
            )

            needs_review = fraud_probability >= ai_settings.RISK_SCORE_THRESHOLD

            response = {
                "risk_score": fraud_probability,
                "risk_factors": prediction_details.get("risk_factors", {}),
                "needs_review": needs_review,
                "recommendation": "block" if needs_review else "allow",
                "model_version": prediction_details.get("model_version", "unknown"),
                "score_id": risk_score.id,
                "model_details": {
                    "model_name": prediction_details.get("model_name", "unknown"),
                    "prediction_time": prediction_details.get("prediction_time", None),
                    "is_fallback": prediction_details.get("is_fallback", False),
                },
            }

            if needs_review:
                logger.warning(
                    f"High risk transaction detected: {transaction.id}, "
                    f"Score: {fraud_probability}, Factors: {prediction_details.get('risk_factors', {})}"
                )
            return response
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")

            return {
                "risk_score": 0.8,
                "risk_factors": {"error": str(e)},
                "needs_review": True,
                "recommendation": "block",
                "model_version": "fallback",
                "error": str(e),
            }

    async def handle_flagged_transaction(
        self, transaction: Transaction, risk_analysis: dict[str, Any]
    ) -> None:
        try:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SUSPICIOUS_ACTIVITY,
                details={
                    "risk_score": risk_analysis["risk_score"],
                    "risk_factors": risk_analysis["risk_factors"],
                    "model_version": risk_analysis.get("model_version", "unknown"),
                    "model_details": risk_analysis.get("model_details", {}),
                },
                session=self.session,
                error_message="This transaction has been flagged as potentially fraudulent. An account executive "
                "will review the transaction, before its "
                "either approved or rejected",
            )

            transaction.ai_review_status = AIReviewStatusEnum.FLAGGED
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error handling flagged transaction: {str(e)}")
            raise

    async def get_user_transaction_risk_history(
        self,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_risk_score: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        try:
            stmt = (
                select(Transaction, TransactionRiskScore)
                .join(TransactionRiskScore)
                .where(
                    Transaction.id == TransactionRiskScore.transaction_id,
                    Transaction.sender_id == user_id,
                )
            )
            if start_date:
                stmt = stmt.where(TransactionRiskScore.created_at >= start_date)

            if end_date:
                stmt = stmt.where(TransactionRiskScore.created_at <= end_date)

            if min_risk_score is not None:
                stmt = stmt.where(TransactionRiskScore.risk_score >= min_risk_score)

            stmt = stmt.order_by(desc(TransactionRiskScore.created_at)).limit(limit)

            result = await self.session.exec(stmt)

            tx_risk_pairs = result.all()

            response = []

            for tx, risk in tx_risk_pairs:
                response.append(
                    {
                        "transaction_id": str(tx.id),
                        "reference": tx.reference,
                        "amount": str(tx.amount),
                        "date": tx.created_at.isoformat(),
                        "risk_score": risk.risk_score,
                        "risk_factors": risk.risk_factors,
                        "ai_review_status": tx.ai_review_status,
                        "model_version": risk.ai_model_version,
                    }
                )
            return response

        except Exception as e:
            logger.error(f"Error fetching risk history: {str(e)}")
            raise


async def review_flagged_transaction(
    self,
    transaction_id: UUID,
    reviewer_id: UUID,
    is_fraud: bool,
    notes: str | None = None,
    session: AsyncSession = Depends(get_session),
    approve_transaction: bool = False,
) -> dict[str, Any]:
    try:
        tx_stmt = (
            select(Transaction, TransactionRiskScore)
            .join(TransactionRiskScore)
            .where(
                Transaction.id == TransactionRiskScore.transaction_id,
                Transaction.id == transaction_id,
            )
        )

        result = await session.exec(tx_stmt)
        tx_risk = result.first()

        if not tx_risk:
            raise ValueError(
                f"Transaction {transaction_id} not found or has no risk score"
            )

        transaction, risk_score = tx_risk

        risk_score.is_confirmed_fraud = is_fraud
        risk_score.reviewed_by = reviewer_id

        transaction.ai_review_status = (
            AIReviewStatusEnum.CONFIRMED_FRAUD
            if is_fraud
            else AIReviewStatusEnum.CLEARED
        )

        if not transaction.transaction_metadata:
            transaction.transaction_metadata = {}

        transaction.transaction_metadata["fraud_review"] = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": str(reviewer_id),
            "is_fraud": is_fraud,
            "notes": notes or "",
        }

        if approve_transaction and not is_fraud:
            from backend.app.api.services.transaction import (
                _complete_approved_transfer,
                _complete_approved_withdrawal,
            )

            if transaction.transaction_type == "Transfer":
                await _complete_approved_transfer(transaction, session)
            elif transaction.transaction_type == "Withdrawal":
                await _complete_approved_withdrawal(transaction, session)

        session.add(transaction)
        session.add(risk_score)

        await session.commit()

        return {
            "status": "success",
            "transaction_id": str(transaction.id),
            "is_fraud": is_fraud,
            "approved": approve_transaction and not is_fraud,
            "new_status": transaction.ai_review_status,
        }
    except Exception as e:
        logger.error(f"Error reviewing flagged transaction: {str(e)}")

        await session.rollback()
        raise