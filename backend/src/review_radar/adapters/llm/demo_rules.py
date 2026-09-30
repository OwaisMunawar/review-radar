"""Keyword rules that stand in for a model in demo mode.

This is deliberately a plain, readable rule list rather than anything clever:
its job is to make the pipeline runnable offline and deterministic, and the
eval harness reports honestly how far it is from a real model. Patterns cover
the five languages in the demo dataset.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from review_radar.domain.models import Category, Sentiment, Severity, Triage

CRASH = (
    r"crash|closes itself|force clos|freez|se cierra|se cuelga|stürzt|absturz|\bplant(e|age)|"
    r"fecha sozinho|fecha quando|trava|travou|o app fecha"
)
LOGIN = (
    r"log ?in|sign ?in|sign-in|iniciar sesión|inicio de sesión|anmeld|login|connexion|"
    r"connecte|entrar"
)
FIXED = (
    r"\bfixed\b|works again|thanks? for the (quick )?fix|arreglarlo|funciona otra vez|"
    r"ya funciona|\bwieder\b|behoben|à nouveau|corrigé|voltou a funcionar|correção"
)
WANT = (
    r"would love|please add|would be great|i'?d like|i wish|wish (it|there)|me encantaría|"
    r"añadan|agreguen|wünsche|bitte .*(hinzufügen|einbauen)|ce serait|merci d'ajouter|"
    r"j'aimerais|seria ótimo|adicionem|gostaria"
)
PRAISE = (
    r"\blove\b|great|best|excellent|amazing|awesome|perfect|encanta|excelente|genial|toll|"
    r"super|klasse|génial|adoro|ótimo|incrível|fácil|easy to use|übersichtlich|efficace"
)


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    category: Category
    severity: Severity
    summary: str
    matches: Callable[[str, int], bool]


def _has(pattern: str) -> Callable[[str, int], bool]:
    compiled = re.compile(pattern)
    return lambda text, _rating: compiled.search(text) is not None


def _all(*patterns: str) -> Callable[[str, int], bool]:
    compiled = [re.compile(p) for p in patterns]
    return lambda text, _rating: all(c.search(text) for c in compiled)


def _positive(pattern: str) -> Callable[[str, int], bool]:
    compiled = re.compile(pattern)
    return lambda text, rating: rating >= 4 and compiled.search(text) is not None


RULES: tuple[Rule, ...] = (
    Rule(
        "fixed",
        Category.PRAISE,
        Severity.LOW,
        "Sign-in works again after the fix",
        _positive(FIXED),
    ),
    Rule(
        "login_crash",
        Category.CRASH,
        Severity.CRITICAL,
        "App crashes when signing in",
        _all(CRASH, LOGIN),
    ),
    Rule(
        "widget_crash",
        Category.CRASH,
        Severity.HIGH,
        "App crashes when opening a task from the widget",
        _all(CRASH, r"widget"),
    ),
    Rule("crash", Category.CRASH, Severity.HIGH, "App crashes during normal use", _has(CRASH)),
    Rule(
        "session",
        Category.LOGIN,
        Severity.HIGH,
        "Users get logged out or cannot sign in",
        _has(
            r"log(ging|s|ged)? (me )?out|session|locked out|password|can'?t (sign|log) ?in|"
            r"cierra la sesión|sesión|abgemeldet|sitzung|déconnect|deslogad|sessão"
        ),
    ),
    Rule(
        "charged",
        Category.PAYMENTS,
        Severity.CRITICAL,
        "Charged for Pro but it is not active",
        _has(
            r"charged|refund|restore purchase|free plan|cobraron|cobro|abgebucht|facturé|"
            r"cobrad|reembolso|rückerstatt|remboursement"
        ),
    ),
    Rule(
        "price",
        Category.PAYMENTS,
        Severity.LOW,
        "Subscription price feels too high",
        _has(
            r"expensive|price|pricing|too much|\bcara\b|precio|teuer|preis|\bcher\b|prix|"
            r"\bcaro\b|preço"
        ),
    ),
    Rule(
        "slow",
        Category.PERFORMANCE,
        Severity.MEDIUM,
        "App is slow to open and scroll",
        _has(r"slow|\blag|forever|seconds to|\blent[ao]\b|tarda|langsam|ewig|\blente\b|demora"),
    ),
    Rule(
        "battery",
        Category.PERFORMANCE,
        Severity.MEDIUM,
        "App drains the battery in the background",
        _has(r"battery|batería|akku|batterie|bateria"),
    ),
    Rule(
        "small_widget",
        Category.UX,
        Severity.MEDIUM,
        "Redesigned widget shows too few tasks",
        _all(r"widget", r"small|pequeño|pequeno|klein|petit|old|hides|two tasks|dos tareas"),
    ),
    Rule(
        "dark_mode",
        Category.UX,
        Severity.LOW,
        "Text is hard to read in dark mode",
        _has(r"dark mode|contrast|modo oscuro|dunkelmodus|mode sombre|modo escuro"),
    ),
    Rule(
        "confusing",
        Category.UX,
        Severity.MEDIUM,
        "Menus make settings hard to find",
        _has(
            r"confus|can'?t find|hard to find|verwirrend|finde .* nicht|déroutant|"
            r"je ne trouve pas|não acho|no encuentro"
        ),
    ),
    Rule(
        "reminders",
        Category.OTHER,
        Severity.MEDIUM,
        "Reminders arrive late or not at all",
        _has(r"reminder|notification|recordatorio|erinnerung|rappel|lembrete|notificaç"),
    ),
    Rule(
        "sync",
        Category.OTHER,
        Severity.HIGH,
        "Calendar and device sync is broken",
        _has(r"sync|calendar|sincroniz|synchron|kalender|agenda"),
    ),
    Rule(
        "watch", Category.FEATURE_REQUEST, Severity.LOW, "Wants an Apple Watch app", _has(r"watch")
    ),
    Rule(
        "shared",
        Category.FEATURE_REQUEST,
        Severity.LOW,
        "Wants shared lists for families and teams",
        _has(r"shared|share a|compartid|geteilte|partagé|compartilhad"),
    ),
    Rule(
        "export",
        Category.FEATURE_REQUEST,
        Severity.LOW,
        "Wants to export tasks to CSV or PDF",
        _has(r"export"),
    ),
    Rule(
        "habits",
        Category.PRAISE,
        Severity.LOW,
        "Loves the habit tracker",
        _positive(r"habit|hábito|gewohnheit|habitude"),
    ),
    Rule(
        "focus",
        Category.PRAISE,
        Severity.LOW,
        "Loves the new focus timer",
        _positive(r"focus|temporizador|fokus|minuteur|timer"),
    ),
    Rule("feature", Category.FEATURE_REQUEST, Severity.LOW, "Asks for a new feature", _has(WANT)),
    Rule(
        "praise", Category.PRAISE, Severity.LOW, "Happy with the planner overall", _positive(PRAISE)
    ),
)


def detect_language(text: str) -> str:
    """Crude stopword vote; good enough to pick a reply template."""
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    votes = {
        "es": {"el", "la", "que", "de", "muy", "desde", "por", "mis", "se", "una", "los"},
        "de": {"die", "der", "und", "ist", "nicht", "ich", "mit", "seit", "zu", "das", "beim"},
        "fr": {"le", "la", "les", "est", "je", "pas", "très", "depuis", "une", "des", "mes"},
        "pt": {"o", "a", "não", "muito", "para", "com", "os", "que", "uma", "minhas", "é"},
        "en": {"the", "and", "is", "it", "to", "i", "my", "app", "this", "of", "when"},
    }
    scores = {lang: sum(w in vocab for w in words) for lang, vocab in votes.items()}
    best = max(scores, key=lambda lang: (scores[lang], lang == "en"))
    return best if scores[best] > 0 else "en"


def sentiment_for(category: Category, rating: int) -> Sentiment:
    if category is Category.PRAISE or rating >= 4:
        return Sentiment.POSITIVE
    if rating == 3 or category is Category.FEATURE_REQUEST:
        return Sentiment.NEUTRAL
    return Sentiment.NEGATIVE


def rule_triage(text: str, rating: int, *, version: str | None = None) -> Triage:
    lowered = text.lower()
    for rule in RULES:
        if rule.matches(lowered, rating):
            category, severity, summary = rule.category, rule.severity, rule.summary
            break
    else:
        if rating >= 4:
            category, severity, summary = Category.PRAISE, Severity.LOW, "Positive feedback"
        else:
            category, severity, summary = Category.OTHER, Severity.MEDIUM, "General complaint"
    return Triage(
        sentiment=sentiment_for(category, rating),
        category=category,
        severity=severity,
        app_version=version,
        summary=summary,
        language=detect_language(text),
    )
