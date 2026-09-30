"""A deterministic stand-in for an LLM, built on PydanticAI's FunctionModel.

The agents, prompts, output schemas and validators are exactly the ones used
with real models; only the model is swapped. That keeps demo mode an honest
exercise of the pipeline rather than a separate code path.
"""

from collections import Counter

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from review_radar.adapters.llm.demo_rules import rule_triage
from review_radar.adapters.llm.prompts import parse_items, parse_tags
from review_radar.domain.models import Category

DEMO_MODEL_NAME = "demo-rules"

REPLIES: dict[str, dict[Category, str]] = {
    "en": {
        Category.CRASH: "Sorry about the crash, that's not the experience we want. The team is "
        "on it. If it keeps happening, please reach us via Help > Contact us in the app.",
        Category.PERFORMANCE: "Thanks for flagging the slowdown. We're working on speed and "
        "battery use, and your report helps us reproduce it.",
        Category.LOGIN: "Sorry you're having trouble signing in. We're looking into it. For "
        "account-specific help, please use Help > Contact us in the app.",
        Category.PAYMENTS: "Sorry about the billing trouble. Please contact us through Help > "
        "Contact us in the app so we can look at your purchase.",
        Category.UX: "Thanks for the honest feedback on the design. We've shared it with the "
        "team working on the next update.",
        Category.FEATURE_REQUEST: "Thanks for the suggestion! We've added it to the list the "
        "team reviews when planning updates.",
        Category.PRAISE: "Thank you for the kind words! We're glad Pocket Planner helps you "
        "stay organized.",
        Category.OTHER: "Thanks for letting us know. We're looking into it, and Help > Contact "
        "us in the app is the fastest way to reach the team.",
    },
    "es": {
        Category.CRASH: "Sentimos el cierre inesperado. El equipo ya lo está revisando. Si "
        "sigue pasando, escríbenos desde Ayuda > Contacto en la app.",
        Category.PERFORMANCE: "Gracias por avisarnos de la lentitud. Estamos mejorando la "
        "velocidad y el consumo de batería.",
        Category.LOGIN: "Sentimos los problemas para iniciar sesión. Lo estamos revisando. "
        "Para ayuda con tu cuenta, usa Ayuda > Contacto en la app.",
        Category.PAYMENTS: "Sentimos el problema con el pago. Escríbenos desde Ayuda > "
        "Contacto en la app para revisar tu compra.",
        Category.UX: "Gracias por tu opinión sobre el diseño. La compartimos con el equipo.",
        Category.FEATURE_REQUEST: "¡Gracias por la sugerencia! La tendremos en cuenta al "
        "planificar próximas versiones.",
        Category.PRAISE: "¡Muchas gracias! Nos alegra que Pocket Planner te ayude a organizarte.",
        Category.OTHER: "Gracias por avisarnos. Lo estamos revisando.",
    },
    "de": {
        Category.CRASH: "Das tut uns leid. Das Team kümmert sich um den Absturz. Falls er "
        "wieder auftritt, schreib uns über Hilfe > Kontakt in der App.",
        Category.PERFORMANCE: "Danke für den Hinweis. Wir arbeiten an Tempo und Akkuverbrauch.",
        Category.LOGIN: "Schade, dass die Anmeldung Probleme macht. Wir sehen uns das an. Für "
        "Hilfe zu deinem Konto nutze bitte Hilfe > Kontakt in der App.",
        Category.PAYMENTS: "Das tut uns leid. Bitte schreib uns über Hilfe > Kontakt in der "
        "App, damit wir deinen Kauf prüfen können.",
        Category.UX: "Danke für das ehrliche Feedback zum Design. Wir geben es ans Team weiter.",
        Category.FEATURE_REQUEST: "Danke für den Vorschlag! Wir nehmen ihn in unsere Planung auf.",
        Category.PRAISE: "Vielen Dank! Schön, dass dir Pocket Planner beim Planen hilft.",
        Category.OTHER: "Danke für den Hinweis. Wir sehen uns das an.",
    },
    "fr": {
        Category.CRASH: "Désolés pour ce plantage. L'équipe s'en occupe. Si cela continue, "
        "écrivez-nous via Aide > Nous contacter dans l'application.",
        Category.PERFORMANCE: "Merci du signalement. Nous travaillons sur la rapidité et "
        "l'autonomie.",
        Category.LOGIN: "Désolés pour ces soucis de connexion. Nous regardons cela. Pour votre "
        "compte, passez par Aide > Nous contacter dans l'application.",
        Category.PAYMENTS: "Désolés pour ce problème de paiement. Contactez-nous via Aide > "
        "Nous contacter pour que nous vérifiions votre achat.",
        Category.UX: "Merci pour ce retour sur le design. Nous le transmettons à l'équipe.",
        Category.FEATURE_REQUEST: "Merci pour la suggestion ! Nous l'ajoutons à nos idées.",
        Category.PRAISE: "Merci beaucoup ! Ravis que Pocket Planner vous aide au quotidien.",
        Category.OTHER: "Merci de nous l'avoir signalé. Nous regardons cela.",
    },
    "pt": {
        Category.CRASH: "Sentimos muito pelo fechamento inesperado. A equipe já está vendo "
        "isso. Se continuar, fale com a gente em Ajuda > Contato no app.",
        Category.PERFORMANCE: "Obrigado pelo aviso. Estamos melhorando velocidade e bateria.",
        Category.LOGIN: "Sentimos pelos problemas de login. Estamos verificando. Para ajuda com "
        "a sua conta, use Ajuda > Contato no app.",
        Category.PAYMENTS: "Sentimos pelo problema na cobrança. Fale com a gente em Ajuda > "
        "Contato no app para verificarmos a sua compra.",
        Category.UX: "Obrigado pelo retorno sobre o design. Vamos repassar para a equipe.",
        Category.FEATURE_REQUEST: "Obrigado pela sugestão! Vamos considerar nas próximas versões.",
        Category.PRAISE: "Muito obrigado! Que bom que o Pocket Planner ajuda na sua rotina.",
        Category.OTHER: "Obrigado por avisar. Estamos verificando.",
    },
}


def _prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return ""


def _answer(info: AgentInfo, args: dict[str, object]) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(info.output_tools[0].name, args)], model_name=DEMO_MODEL_NAME
    )


def _triage(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    tags = parse_tags(_prompt(messages))
    version = tags.get("version")
    triage = rule_triage(
        f"{tags.get('title', '')}\n{tags.get('body', '')}",
        int(tags.get("rating", "3")),
        version=None if version in (None, "unknown") else version,
    )
    return _answer(info, triage.model_dump(mode="json"))


def _reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    tags = parse_tags(_prompt(messages))
    templates = REPLIES.get(tags.get("language", "en"), REPLIES["en"])
    body = templates[Category(tags.get("category", Category.OTHER.value))]
    return _answer(info, {"body": body})


def _theme(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    summaries = parse_items(_prompt(messages))
    # The most common summary is the most representative wording for the cluster.
    title = Counter(summaries).most_common(1)[0][0] if summaries else "Mixed feedback"
    return _answer(info, {"title": title.rstrip(".")[:60]})


def demo_triage_model() -> FunctionModel:
    return FunctionModel(_triage, model_name=DEMO_MODEL_NAME)


def demo_reply_model() -> FunctionModel:
    return FunctionModel(_reply, model_name=DEMO_MODEL_NAME)


def demo_theme_model() -> FunctionModel:
    return FunctionModel(_theme, model_name=DEMO_MODEL_NAME)
