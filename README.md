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

## PostgreSQL și observabilitate

Pornește baza locală de date:

```powershell
docker compose up -d
```

Adaugă în `.env`:

```text
DATABASE_URL=postgresql+psycopg://banking:banking@localhost:5432/banking
```

La prima cerere `POST /generate-risk-report`, aplicația creează tabelele
`customer_profiles` și `risk_reports`. Primul conține profilul ETL
normalizat, iar al doilea păstrează fiecare raport, validarea și timpii
etapelor de procesare.

Conectare din terminal:

```powershell
docker compose exec postgres psql -U banking -d banking
```

Exemple de interogări:

```sql
SELECT customer_id, loaded_at FROM customer_profiles;
SELECT id, customer_id, risk_level, is_valid, refinement_count, total_duration_ms
FROM risk_reports
ORDER BY created_at DESC;
```

Pentru DBeaver/pgAdmin: host `localhost`, port `5432`, database `banking`,
user `banking`, parolă `banking`. Aceste credențiale sunt numai pentru
dezvoltare locală.

Adminer este disponibil în browser după `docker compose up -d` la
`http://localhost:18080`. Selectează `PostgreSQL` și folosește serverul
`postgres`, userul `banking`, parola `banking` și baza `banking`.
