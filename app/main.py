"""FastAPI application factory."""

from fastapi import FastAPI

from app.api.routes import router as banking_router
from app.core.config import settings
from app.banking_orchestrator import BankingRiskOrchestrator
from app.excel_customer_repository import ExcelCustomerRepository
from app.persistence import BankingStorage


def create_app() -> FastAPI:
    """Create the HTTP application without side effects at import time."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-assisted banking risk-report generation.",
    )
    application.state.banking_risk_orchestrator = BankingRiskOrchestrator()
    application.state.customer_repository = ExcelCustomerRepository(settings.excel_workbook_path)
    application.state.banking_storage = (
        BankingStorage(settings.database_url) if settings.database_url else None
    )
    application.state.openai_model = settings.openai_model
    application.include_router(banking_router)
    return application


app = create_app()
