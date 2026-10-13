"""Whitelisted decimal calculations with exact source operands; no expression evaluation."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from .quality import _numbers


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Calculation operands must be finite decimal values")
    if len(str(value)) > 64:
        raise ValueError("Calculation operand exceeds supported decimal range")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Invalid calculation operand") from error
    if (
        not number.is_finite()
        or len(number.as_tuple().digits) > 30
        or number.copy_abs() > Decimal("1e18")
        or (number and number.copy_abs() < Decimal("1e-12"))
    ):
        raise ValueError("Calculation operand exceeds supported decimal range")
    return number


def audit_calculation(source, derivation, expected):
    if not isinstance(derivation, dict) or set(derivation) != {"operation", "precision", "inputs"}:
        raise ValueError("Derivation requires only operation, precision and inputs")
    operation, precision, inputs = (
        derivation["operation"],
        derivation["precision"],
        derivation["inputs"],
    )
    if operation not in {"sum", "difference", "ratio", "percentage", "percentage_change"}:
        raise ValueError("Unsupported calculation operation")
    if isinstance(precision, bool) or not isinstance(precision, int) or not 0 <= precision <= 6:
        raise ValueError("Calculation precision must be 0–6 decimal places")
    if not isinstance(inputs, list) or not (
        2 <= len(inputs) <= 8 if operation == "sum" else len(inputs) == 2
    ):
        raise ValueError("sum requires 2–8 inputs; other operations require exactly two")
    target, metric, category, unit, period = expected
    issues, references, numbers, seen = [], [], [], set()
    for operand in inputs:
        if not isinstance(operand, dict) or set(operand) != {
            "value",
            "start",
            "quote",
            "category",
            "unit",
            "period",
        }:
            raise ValueError("Each operand requires value, start, quote, category, unit and period")
        value = _number(operand["value"])
        start, quote = operand["start"], operand["quote"]
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
            or not isinstance(quote, str)
            or not quote.strip()
            or len(quote) > 2000
        ):
            raise ValueError("Operand needs a source offset and bounded quote")
        for key in ("category", "unit", "period"):
            if (
                not isinstance(operand[key], str)
                or not operand[key].strip()
                or len(operand[key]) > 60
            ):
                raise ValueError("Operand context must contain bounded text")
        fingerprint = (
            start,
            quote,
            str(value),
            operand["category"],
            operand["unit"],
            operand["period"],
        )
        if fingerprint in seen:
            issues.append("duplicate_calculation_operand")
        seen.add(fingerprint)
        if source[start : start + len(quote)] != quote:
            issues.append("operand_quote_mismatch")
        if value not in _numbers(quote):
            issues.append("operand_value_missing")
        normalized = re.sub(r"\s+", " ", quote).casefold()
        for key, text in (
            ("metric", metric),
            ("category", operand["category"]),
            ("unit", operand["unit"]),
            ("period", operand["period"]),
        ):
            if re.sub(r"\s+", " ", text).casefold() not in normalized:
                issues.append(f"operand_{key}_missing")
        if operand["period"].casefold() not in period.casefold():
            issues.append("calculation_period_mismatch")
        references.append(
            {
                "source_start": start,
                "source_end": start + len(quote),
                "category": operand["category"],
                "unit": operand["unit"],
                "period": operand["period"],
                "value": str(value),
            }
        )
        numbers.append(value)
    if len({operand["unit"] for operand in inputs}) != 1:
        issues.append("calculation_input_unit_mismatch")
    expected_unit = (
        "%"
        if operation in {"percentage", "percentage_change"}
        else "ratio"
        if operation == "ratio"
        else inputs[0]["unit"]
    )
    if unit != expected_unit:
        issues.append("calculation_output_unit_mismatch")
    computed = None
    with localcontext() as context:
        context.prec = 128
        if operation == "sum":
            computed = sum(numbers)
        elif operation == "difference":
            computed = numbers[0] - numbers[1]
        else:
            denominator = numbers[0] if operation == "percentage_change" else numbers[1]
            if denominator == 0:
                issues.append("calculation_zero_denominator")
            else:
                computed = (
                    (numbers[1] - numbers[0]) / denominator * 100
                    if operation == "percentage_change"
                    else numbers[0] / denominator * (100 if operation == "percentage" else 1)
                )
        if computed is not None:
            computed = computed.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
            if computed != Decimal(str(target)):
                issues.append("calculation_result_mismatch")
    return sorted(set(issues)), {
        "operation": operation,
        "precision": precision,
        "rounding": "ROUND_HALF_UP",
        "inputs": references,
        "computed_value": str(computed) if computed is not None else None,
        "target": {
            "value": str(target),
            "metric": metric,
            "category": category,
            "unit": unit,
            "period": period,
        },
    }
