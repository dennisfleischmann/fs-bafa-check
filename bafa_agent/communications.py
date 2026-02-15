from __future__ import annotations

from typing import Dict, List


def render_secretary_memo(evaluation: Dict[str, object]) -> str:
    lines: List[str] = []
    case_id = evaluation.get("case_id", "unknown")
    lines.append(f"Interne BAFA-Vorpruefung - Fall {case_id}")
    lines.append("")
    for result in evaluation.get("results", []):
        status = result.get("status", "CLARIFY")
        measure = result.get("measure_id", "unknown")
        reason = result.get("reason", "")
        lines.append(f"- {measure}: {status} ({reason})")
        questions = result.get("questions", [])
        if questions:
            lines.append("  Nachforderung:")
            for question in questions:
                lines.append(f"  - {question}")
    return "\n".join(lines)


def render_customer_email(result: Dict[str, object]) -> str:
    status = result.get("status", "CLARIFY")
    measure = result.get("measure_id", "Massnahme")
    reason = result.get("reason", "")
    questions = result.get("questions", [])

    lines: List[str] = [f"Betreff: Vorpruefung {measure}", "", "Guten Tag,"]

    if status == "PASS":
        lines.append(f"die Massnahme {measure} ist auf Basis der vorliegenden Angaben foerderfaehig.")
    elif status == "FAIL":
        lines.append(f"die Massnahme {measure} ist auf Basis der vorliegenden Angaben nicht foerderfaehig.")
    else:
        lines.append(f"die Massnahme {measure} ist aktuell nicht abschliessend pruefbar.")

    if questions:
        lines.append("")
        lines.append("Bitte reichen Sie folgende Angaben nach:")
        for question in questions:
            lines.append(f"- {question}")

    lines.extend(
        [
            "",
            "Hinweis: Vorpruefung auf Basis der im Angebot genannten Angaben.",
            "Finale Pruefung erfolgt im Rahmen der Antragstellung und technischer Nachweise.",
            "",
            f"Grundlage: {reason}",
            "",
            "Viele Gruesse",
        ]
    )

    return "\n".join(lines)
