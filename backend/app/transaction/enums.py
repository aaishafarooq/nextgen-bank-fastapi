from enum import Enum


class TransactionTypeEnum(str, Enum):
    Deposit = "deposit"
    Withdrawal = "withdrawal"
    Transfer = "transfer"
    Reversal = "reversal"
    Fee_Charged = "fee_charged"
    Loan_Disbursement = "loan_disbursement"
    Loan_Repayment = "loan_repayment"
    Interest_Credited = "interest_credited"


class TransactionStatusEnum(str, Enum):
    Pending = "pending"
    Completed = "completed"
    Failed = "failed"
    Reversed = "reversed"
    Cancelled = "cancelled"


class TransactionCategoryEnum(str, Enum):
    Credit = "credit"
    Debit = "debit"