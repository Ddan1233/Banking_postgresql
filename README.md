# Banking Risk Multi-Agent API

FastAPI application for creating customer risk reports from data aggregated by
customer ID from the supplied Excel workbook.

## Etapa 3: motorul multi-agent

`BankingRiskOrchestrator` rulează fluxul:

`GeneratorAgent → ValidatorAgent → RefinerAgent → ValidatorAgent`

- Generatorul produce un `RiskReport` structurat cu OpenAI Responses API și
  Structured Outputs.
- Validatorul aplică reguli de business explicite. Un client cu default în
  istoric nu poate primi recomandări de credit.
- Refinerul corectează draftul respins, apoi raportul este validat din nou.

În lipsa unei chei OpenAI, generatorul și refinerul folosesc un fallback local,
determinist, potrivit pentru dezvoltare și teste.

## API

Swagger expune un singur endpoint de business:

`POST /generate-risk-report`

Exemplu de cerere:

```json
{
  "customer_id": 2
}
```

`GET /customer-profiles/{customer_id}` returnează profilul normalizat complet
construit din foile Excel înainte ca acesta să fie folosit de agenți.

Răspunsul include raportul final, `validation.is_valid`, eventualele erori și
numărul de rafinări.

## Rulare locală

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Deschide `http://127.0.0.1:8000/docs`.

## Teste

```powershell
pytest tests/test_banking_models.py tests/test_banking_multi_agent.py -q
```
