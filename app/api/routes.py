"""Banking risk-report HTTP endpoints."""

from time import perf_counter
from uuid import uuid4

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

    workflow_start = perf_counter()
    profile_start = perf_counter()
    profile = request.app.state.customer_repository.get_customer_profile(payload.customer_id)
    profile_extraction_ms = (perf_counter() - profile_start) * 1000

    storage = request.app.state.banking_storage
    profile_persistence_ms = 0.0
    if storage is not None:
        persistence_start = perf_counter()
        storage.save_customer_profile(profile)
        profile_persistence_ms = (perf_counter() - persistence_start) * 1000

    result = request.app.state.banking_risk_orchestrator.create_risk_report(profile)
    observability = {
        "trace_id": str(uuid4()),
        "profile_extraction_ms": profile_extraction_ms,
        "profile_persistence_ms": profile_persistence_ms,
        "generation_ms": result.generation_duration_ms,
        "validation_ms": result.validation_duration_ms,
        "refinement_ms": result.refinement_duration_ms,
        "report_persistence_ms": 0.0,
        "total_duration_ms": (perf_counter() - workflow_start) * 1000,
        "persisted": storage is not None,
    }
    if storage is not None:
        persistence_start = perf_counter()
        report_id = storage.save_risk_report(
            profile, result, observability, request.app.state.openai_model
        )
        observability["report_persistence_ms"] = (perf_counter() - persistence_start) * 1000
        observability["total_duration_ms"] = (perf_counter() - workflow_start) * 1000
        storage.update_report_observability(report_id, observability)
    return result.model_copy(update={"observability": observability})


@router.get("/customer-profiles/{customer_id}", response_model=CustomerProfileModel)
def get_customer_profile(customer_id: str, request: Request) -> CustomerProfileModel:
    """Return the complete normalized Excel profile used by the agents."""

    return request.app.state.customer_repository.get_customer_profile(customer_id)
