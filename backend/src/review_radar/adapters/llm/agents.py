"""PydanticAI agents behind the application's model ports.

Each adapter owns one Agent with a typed output. Agents are built per adapter
instance, with the model injected, so tests and demo mode swap the model
without touching module state.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError, ModelAPIError
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResult

from review_radar.adapters.llm.demo_model import (
    demo_reply_model,
    demo_theme_model,
    demo_triage_model,
)
from review_radar.adapters.llm.prompts import (
    REPLY_INSTRUCTIONS,
    STORE_NOTES,
    THEME_INSTRUCTIONS,
    TRIAGE_INSTRUCTIONS,
    reply_prompt,
    review_prompt,
    theme_prompt,
)
from review_radar.domain.errors import LlmError
from review_radar.domain.models import (
    LlmPurpose,
    LlmUsage,
    ReplyText,
    StoredReview,
    ThemeTitle,
    Triage,
)

ModelRef = Model | str


def _usage(
    result: AgentRunResult[object], purpose: LlmPurpose, model_name: str, started: float
) -> LlmUsage:
    usage = result.usage
    try:
        cost = Decimal(str(result.response.cost().total_price))
    except (LookupError, AssertionError):
        # Demo and self-hosted models have no public price.
        cost = Decimal(0)
    return LlmUsage(
        purpose=purpose,
        model_name=result.response.model_name or model_name,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=cost,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


def _model_name(model: ModelRef) -> str:
    return model if isinstance(model, str) else model.model_name


class PydanticAiTriager:
    def __init__(self, model: ModelRef) -> None:
        self._model_name = _model_name(model)
        self._agent = Agent(
            model,
            output_type=Triage,
            instructions=TRIAGE_INSTRUCTIONS,
            retries=2,
            name="triage",
        )

    async def triage(self, review: StoredReview) -> tuple[Triage, LlmUsage]:
        started = time.perf_counter()
        try:
            result = await self._agent.run(review_prompt(review))
        except (AgentRunError, ModelAPIError) as exc:
            raise LlmError(f"triage failed: {exc}", details={"review_id": str(review.id)}) from exc
        triage = result.output
        if triage.app_version is None and review.app_version:
            triage = triage.model_copy(update={"app_version": review.app_version})
        return triage, _usage(result, LlmPurpose.TRIAGE, self._model_name, started)


@dataclass(frozen=True, slots=True)
class ReplyDeps:
    store: str
    limit: int


class PydanticAiReplyWriter:
    def __init__(self, model: ModelRef) -> None:
        self._model_name = _model_name(model)
        agent = Agent(
            model,
            output_type=ReplyText,
            deps_type=ReplyDeps,
            retries=2,
            name="reply",
        )

        @agent.instructions
        def instructions(ctx: RunContext[ReplyDeps]) -> str:
            return REPLY_INSTRUCTIONS.format(
                limit=ctx.deps.limit, store_note=STORE_NOTES.get(ctx.deps.store, "")
            )

        @agent.output_validator
        def within_limit(ctx: RunContext[ReplyDeps], output: ReplyText) -> ReplyText:
            text = output.body.strip()
            if not text:
                raise ModelRetry("The reply is empty.")
            if len(text) > ctx.deps.limit:
                # Asking the model to shorten keeps its wording; truncating would not.
                raise ModelRetry(
                    f"The reply is {len(text)} characters; rewrite it under {ctx.deps.limit}."
                )
            return ReplyText(body=text)

        self._agent = agent

    async def write(self, review: StoredReview, triage: Triage, limit: int) -> tuple[str, LlmUsage]:
        started = time.perf_counter()
        deps = ReplyDeps(store=review.store.value, limit=limit)
        try:
            result = await self._agent.run(reply_prompt(review, triage, limit), deps=deps)
        except (AgentRunError, ModelAPIError) as exc:
            raise LlmError(f"reply failed: {exc}", details={"review_id": str(review.id)}) from exc
        return result.output.body, _usage(result, LlmPurpose.REPLY, self._model_name, started)


class PydanticAiThemeNamer:
    def __init__(self, model: ModelRef) -> None:
        self._model_name = _model_name(model)
        self._agent = Agent(
            model,
            output_type=ThemeTitle,
            instructions=THEME_INSTRUCTIONS,
            retries=2,
            name="theme_title",
        )

    async def name(self, summaries: Sequence[str]) -> tuple[str, LlmUsage]:
        started = time.perf_counter()
        try:
            result = await self._agent.run(theme_prompt(summaries))
        except (AgentRunError, ModelAPIError) as exc:
            raise LlmError(f"theme naming failed: {exc}") from exc
        return result.output.title, _usage(
            result, LlmPurpose.THEME_TITLE, self._model_name, started
        )


@dataclass(frozen=True, slots=True)
class ModelSuite:
    triager: PydanticAiTriager
    reply_writer: PydanticAiReplyWriter
    theme_namer: PydanticAiThemeNamer


def build_models(model: str) -> ModelSuite:
    if model == "demo":
        return ModelSuite(
            triager=PydanticAiTriager(demo_triage_model()),
            reply_writer=PydanticAiReplyWriter(demo_reply_model()),
            theme_namer=PydanticAiThemeNamer(demo_theme_model()),
        )
    return ModelSuite(
        triager=PydanticAiTriager(model),
        reply_writer=PydanticAiReplyWriter(model),
        theme_namer=PydanticAiThemeNamer(model),
    )
