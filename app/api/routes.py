"""Banking risk-report HTTP endpoints."""

from fastapi import APIRouter, Request, status

from app.banking_orchestrator import RiskReportResult
from app.excel_customer_repository import ExcelCustomerRepository
from app.banking_models import CustomerProfileModel
from app.schemas import CustomerRiskReportRequest

router = APIRouter(tags=["banking-risk"])


@router.post(
    "/generate-risk-report",
    response_model=RiskReportResult,
    status_code=status.HTTP_200_OK,
)
def generate_risk_report(payload: CustomerRiskReportRequest, request: Request) -> RiskReportResult:
    """Generate, validate, and if necessary refine a banking risk report."""

    profile = request.app.state.customer_repository.get_customer_profile(payload.customer_id)
    return request.app.state.banking_risk_orchestrator.create_risk_report(profile)


@router.get("/customer-profiles/{customer_id}", response_model=CustomerProfileModel)
def get_customer_profile(customer_id: str, request: Request) -> CustomerProfileModel:
    """Return the complete normalized Excel profile used by the agents."""

    return request.app.state.customer_repository.get_customer_profile(customer_id)
