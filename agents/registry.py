from agents.base import HealthcareAgent

AGENTS = [
    HealthcareAgent(
        name="symptom_analyst",
        purpose="Clarify symptoms, duration, severity, and relevant context.",
        keywords=("pain", "fever", "cough", "symptom", "feel", "sick", "headache"),
    ),
    HealthcareAgent(
        name="report_reader",
        purpose="Explain medical reports and lab values in plain language.",
        keywords=("report", "lab", "blood test", "pdf", "scan", "result"),
    ),
    HealthcareAgent(
        name="medication_manager",
        purpose="Track medicines and flag possible adherence or safety concerns.",
        keywords=("medicine", "medication", "tablet", "dose", "prescription", "pill"),
    ),
    HealthcareAgent(
        name="care_coordinator",
        purpose="Prepare next steps, specialist questions, and a concise doctor brief.",
        keywords=("doctor", "specialist", "appointment", "brief", "next step", "care"),
    ),
    HealthcareAgent(
        name="emergency_detector",
        purpose="Identify red flags and give immediate emergency escalation guidance.",
        keywords=("emergency", "severe", "unconscious", "bleeding", "chest pain", "suicide"),
        emergency_keywords=(
            "chest pain",
            "can't breathe",
            "cannot breathe",
            "unconscious",
            "severe bleeding",
            "suicide",
            "overdose",
        ),
    ),
]

