"""Read and aggregate customer data stored in the project Excel workbook."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile
import xml.etree.ElementTree as ElementTree

from fastapi import HTTPException, status

from app.banking_models import CustomerProfileModel


_SPREADSHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RELATIONSHIP_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_EXCEL_EPOCH = datetime(1899, 12, 30)


class ExcelCustomerRepository:
    """Build validated banking profiles by joining the workbook's customer sheets."""

    def __init__(self, workbook_path: Path | str) -> None:
        self._workbook_path = Path(workbook_path)

    def get_customer_profile(self, customer_id: int | str) -> CustomerProfileModel:
        """Return all available workbook information for one customer."""

        sheets = self._read_sheets()
        customer_key = str(customer_id)
        master_rows = self._rows_for_customer(sheets["MasterData"], customer_key)
        if not master_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id!r} was not found in the Excel workbook.",
            )

        liquidity_rows = self._rows_for_customer(sheets["Liquidity"], customer_key)
        if not liquidity_rows:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Customer {customer_id!r} has no liquidity history in the Excel workbook.",
            )
        latest_liquidity = max(liquidity_rows, key=lambda row: self._excel_date(row["reference date"]))

        return CustomerProfileModel.model_validate(
            {
                "customer_id": self._customer_id(customer_id),
                "current_balance": float(latest_liquidity["balance €"]),
                "total_transaction_amount": sum(
                    float(row["amount"])
                    for row in self._rows_for_customer(sheets["Transactions"], customer_key)
                ),
                "transactions": [
                    {
                        "operation_date": self._excel_date(row["operation date"]),
                        "transaction_type": row["type"],
                        "category": self._none_if_empty(row.get("category")),
                        "channel": self._none_if_empty(row.get("channel ")),
                        "amount": float(row["amount"]),
                    }
                    for row in self._rows_for_customer(sheets["Transactions"], customer_key)
                ],
                "default_history": [
                    {
                        "reference_date": self._excel_date(row["reference date"]),
                        "status": int(row["status code"]),
                        "status_description": self._none_if_empty(row.get("status desc")),
                    }
                    for row in self._rows_for_customer(sheets["Default"], customer_key)
                ],
                "products": [
                    {
                        "product": row["PRODUCTS OWNED"],
                        "opening_date": self._year_date(row.get("DATE OPENING")),
                        "closure_date": self._year_date(row.get("DATE CLOSURE")),
                    }
                    for row in self._rows_for_customer(sheets["Products"], customer_key)
                ],
                "customer_data": self._customer_data(master_rows[0]),
                "liquidity_history": [
                    {
                        "reference_date": self._excel_date(row["reference date"]),
                        "balance": float(row["balance €"]),
                    }
                    for row in liquidity_rows
                ],
                "investments": [
                    {
                        "operation_date": self._excel_date(row["operation date"]),
                        "product": row["product"],
                        "channel": self._none_if_empty(row.get("channel ")),
                        "amount": float(row["amount"]),
                    }
                    for row in self._rows_for_customer(sheets["Investments"], customer_key)
                ],
                "regional_context": self._regional_context(sheets["SocioDemographic"], master_rows[0]),
            }
        )

    def _read_sheets(self) -> dict[str, list[dict[str, str]]]:
        if not self._workbook_path.is_file():
            raise RuntimeError(f"Excel workbook was not found: {self._workbook_path}")
        with ZipFile(self._workbook_path) as archive:
            strings = self._shared_strings(archive)
            targets = self._sheet_targets(archive)
            return {
                name: self._sheet_rows(archive, target, strings)
                for name, target in targets.items()
            }

    @staticmethod
    def _shared_strings(archive: ZipFile) -> list[str]:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        return [
            "".join(node.text or "" for node in item.iter(f"{_SPREADSHEET_NS}t"))
            for item in root.findall(f"{_SPREADSHEET_NS}si")
        ]

    @staticmethod
    def _sheet_targets(archive: ZipFile) -> dict[str, str]:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        return {
            sheet.attrib["name"]: targets[sheet.attrib[f"{_RELATIONSHIP_NS}id"]]
            for sheet in workbook.findall(f"{_SPREADSHEET_NS}sheets/{_SPREADSHEET_NS}sheet")
        }

    @staticmethod
    def _sheet_rows(archive: ZipFile, target: str, strings: list[str]) -> list[dict[str, str]]:
        root = ElementTree.fromstring(archive.read(f"xl/{target}"))
        values: list[list[str]] = []
        for row in root.findall(f".//{_SPREADSHEET_NS}row"):
            cells: list[str] = []
            for cell in row.findall(f"{_SPREADSHEET_NS}c"):
                value = cell.findtext(f"{_SPREADSHEET_NS}v", default="")
                if cell.attrib.get("t") == "s" and value:
                    value = strings[int(value)]
                cells.append(value)
            values.append(cells)
        header_index = next(
            (index for index, row in enumerate(values) if "customer ID" in row), 0
        )
        headers = values[header_index]
        return [
            dict(zip(headers, row, strict=False))
            for row in values[header_index + 1 :]
            if any(row)
        ]

    @staticmethod
    def _rows_for_customer(rows: list[dict[str, str]], customer_id: str) -> list[dict[str, str]]:
        return [row for row in rows if row.get("customer ID") == customer_id]

    @staticmethod
    def _customer_id(customer_id: int | str) -> int | str:
        return int(customer_id) if str(customer_id).isdigit() else customer_id

    @staticmethod
    def _excel_date(value: str) -> date:
        return (_EXCEL_EPOCH + timedelta(days=float(value))).date()

    @staticmethod
    def _year_date(value: str | None) -> date | None:
        return date(int(value), 1, 1) if value else None

    @staticmethod
    def _none_if_empty(value: str | None) -> str | None:
        return value or None

    @staticmethod
    def _customer_data(row: dict[str, str]) -> dict[str, Any]:
        return {
            "date_of_birth": ExcelCustomerRepository._excel_date(row["DATE OF BIRTH"]),
            "region": row["REGION"],
            "address": row["ADDRESS"],
            "sex": row["SEX"],
            "customer_type_level_1": row["TYPE OF CUSTOMER LEV 1 "],
            "customer_type_level_2": ExcelCustomerRepository._none_if_empty(row.get("TYPE OF CUSTOMER LEV 2")),
        }

    @staticmethod
    def _regional_context(rows: list[dict[str, str]], customer: dict[str, str]) -> dict[str, Any] | None:
        region = customer["REGION"]
        match = next((row for row in rows if row.get("REGION") == region), None)
        if match is None:
            return None
        return {
            "region": region,
            "squared_kilometers": float(match["Squared kilometers"]),
            "delinquency_rate": float(match["Deliquency rates"]),
        }
