"""Generate the synthetic Pocket Planner review set used by demo mode.

Pocket Planner is a fictional app, and every review below is written for this
project. The set is deterministic (fixed seed) and encodes one story on
purpose: release 2.3.0 changed the auth flow and started crashing at sign-in,
and 2.3.1 fixed it. Regression detection should find that without being told.

    uv run python scripts/generate_dataset.py
"""

import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src/review_radar/data/pocket_planner_reviews.json"
SEED = 2303

RELEASES: list[tuple[str, datetime, int]] = [
    # version, release date, number of reviews while it was current
    ("2.1.0", datetime(2026, 1, 12, tzinfo=UTC), 80),
    ("2.2.0", datetime(2026, 3, 9, tzinfo=UTC), 90),
    ("2.3.0", datetime(2026, 5, 4, tzinfo=UTC), 70),
    ("2.3.1", datetime(2026, 5, 20, tzinfo=UTC), 70),
    ("2.4.0", datetime(2026, 7, 13, tzinfo=UTC), 90),
]
END = datetime(2026, 9, 27, 18, tzinfo=UTC)

LANGUAGES = [("en", 0.62), ("es", 0.11), ("de", 0.10), ("fr", 0.09), ("pt", 0.08)]
TERRITORIES = {
    "en": ["US", "GB", "CA", "AU", "IN"],
    "es": ["ES", "MX", "AR"],
    "de": ["DE", "AT", "CH"],
    "fr": ["FR", "BE", "CA"],
    "pt": ["BR", "PT"],
}


@dataclass(frozen=True)
class Topic:
    key: str
    ratings: tuple[int, int]
    weights: dict[str, float]
    texts: dict[str, list[str]]
    titles: dict[str, list[str]]


def w(base: float, **overrides: float) -> dict[str, float]:
    weights = {version: base for version, _, _ in RELEASES}
    weights.update({k.removeprefix("v").replace("_", "."): v for k, v in overrides.items()})
    return weights


TOPICS: list[Topic] = [
    Topic(
        "login_crash",
        (1, 1),
        w(0.4, v2_3_0=17.0, v2_3_1=0.6),
        {
            "en": [
                "Since the update the app crashes as soon as I tap Sign in with Google.",
                "Crashes every time I try to log in. Reinstalled twice, same thing.",
                "App closes itself on the login screen after updating. Can't get to my tasks at all.",
                "Log in with Apple just crashes the app now. Was fine last week.",
            ],
            "es": [
                "Desde la actualización la app se cierra al iniciar sesión con Google.",
                "Se cierra cada vez que intento iniciar sesión. No puedo ver mis tareas.",
            ],
            "de": [
                "Seit dem Update stürzt die App beim Anmelden sofort ab.",
                "Absturz bei jeder Anmeldung mit Google. Komme nicht mehr an meine Aufgaben.",
            ],
            "fr": [
                "Depuis la mise à jour, l'application plante dès que je me connecte.",
                "Plantage à chaque connexion avec Google, impossible d'accéder à mes tâches.",
            ],
            "pt": [
                "Depois da atualização o app fecha sozinho quando faço login.",
                "O app trava e fecha toda vez que tento entrar com o Google.",
            ],
        },
        {
            "en": ["Crashes on login", "Unusable after update", "Can't sign in"],
            "es": ["Se cierra al entrar"],
            "de": ["Absturz beim Login"],
            "fr": ["Plante à la connexion"],
            "pt": ["Fecha no login"],
        },
    ),
    Topic(
        "session_logout",
        (1, 2),
        w(1.6, v2_3_0=7.0),
        {
            "en": [
                "It keeps logging me out and says my session expired. Every single day.",
                "Can't sign in, it just says 'session expired' and goes back to the start.",
                "Password reset email never arrives so I'm locked out of my account.",
            ],
            "es": ["Me cierra la sesión todo el tiempo y dice que la sesión expiró."],
            "de": ["Ich werde ständig abgemeldet, angeblich ist die Sitzung abgelaufen."],
            "fr": ["Je suis déconnecté sans arrêt, il dit que la session a expiré."],
            "pt": ["Fico sendo deslogado toda hora, diz que a sessão expirou."],
        },
        {
            "en": ["Logged out constantly", "Locked out"],
            "es": ["Sesión expirada"],
            "de": ["Ständig abgemeldet"],
            "fr": ["Déconnexions"],
            "pt": ["Sessão expira"],
        },
    ),
    Topic(
        "widget_crash",
        (1, 2),
        w(1.0, v2_4_0=1.6),
        {
            "en": [
                "The app crashes when I open a task from the home screen widget.",
                "Adding a task from the widget crashes the whole app.",
            ],
            "es": ["La app se cierra al abrir una tarea desde el widget."],
            "de": ["Die App stürzt ab, wenn ich eine Aufgabe über das Widget öffne."],
            "fr": ["L'application plante quand j'ouvre une tâche depuis le widget."],
            "pt": ["O app fecha quando abro uma tarefa pelo widget."],
        },
        {
            "en": ["Widget crash"],
            "es": ["Widget"],
            "de": ["Widget-Absturz"],
            "fr": ["Widget"],
            "pt": ["Widget"],
        },
    ),
    Topic(
        "slow_startup",
        (2, 3),
        w(3.0),
        {
            "en": [
                "Takes forever to open, like ten seconds on a new phone. Very slow.",
                "It's gotten really slow and laggy when scrolling through the week view.",
                "Slow to load my lists in the morning, the spinner just sits there.",
            ],
            "es": ["Tarda muchísimo en abrir y va muy lenta."],
            "de": ["Die App ist sehr langsam und braucht ewig zum Starten."],
            "fr": ["L'application est très lente à s'ouvrir."],
            "pt": ["Muito lento para abrir, demora demais."],
        },
        {
            "en": ["So slow", "Laggy"],
            "es": ["Lenta"],
            "de": ["Langsam"],
            "fr": ["Lente"],
            "pt": ["Lento"],
        },
    ),
    Topic(
        "battery",
        (2, 3),
        w(1.4),
        {
            "en": [
                "Drains my battery in the background even when I'm not using it.",
                "Battery usage is way too high since I turned on reminders.",
            ],
            "es": ["Consume mucha batería en segundo plano."],
            "de": ["Verbraucht im Hintergrund viel zu viel Akku."],
            "fr": ["Vide la batterie en arrière-plan."],
            "pt": ["Gasta muita bateria em segundo plano."],
        },
        {
            "en": ["Battery drain"],
            "es": ["Batería"],
            "de": ["Akku"],
            "fr": ["Batterie"],
            "pt": ["Bateria"],
        },
    ),
    Topic(
        "double_charge",
        (1, 2),
        w(1.6),
        {
            "en": [
                "I was charged twice for Pro this month and support hasn't answered.",
                "Paid for the yearly subscription but the app still shows the free plan.",
                "Restore purchase doesn't work, I paid for Pro and lost it on my new phone.",
            ],
            "es": ["Me cobraron dos veces la suscripción Pro."],
            "de": ["Das Abo wurde zweimal abgebucht und Pro ist trotzdem nicht aktiv."],
            "fr": ["J'ai été facturé deux fois pour l'abonnement Pro."],
            "pt": ["Fui cobrado duas vezes pela assinatura Pro."],
        },
        {
            "en": ["Charged twice", "Where is my Pro?"],
            "es": ["Cobro doble"],
            "de": ["Doppelt abgebucht"],
            "fr": ["Double facturation"],
            "pt": ["Cobrança dupla"],
        },
    ),
    Topic(
        "price",
        (2, 3),
        w(1.8),
        {
            "en": [
                "The subscription is too expensive for a to-do app. A one-time price would be fair.",
                "Nice app but the price for Pro went up and that's too much for me.",
            ],
            "es": ["La suscripción es demasiado cara para una app de tareas."],
            "de": ["Das Abo ist für eine To-do-App zu teuer."],
            "fr": ["L'abonnement est trop cher pour une simple liste de tâches."],
            "pt": ["A assinatura é cara demais para um app de tarefas."],
        },
        {
            "en": ["Too expensive"],
            "es": ["Muy cara"],
            "de": ["Zu teuer"],
            "fr": ["Trop cher"],
            "pt": ["Caro"],
        },
    ),
    Topic(
        "dark_mode",
        (2, 4),
        w(1.8),
        {
            "en": [
                "In dark mode the grey text on dark grey is really hard to read.",
                "Please fix the contrast in dark mode, the completed tasks are almost invisible.",
            ],
            "es": ["En modo oscuro el texto gris casi no se lee."],
            "de": ["Im Dunkelmodus ist der graue Text kaum lesbar."],
            "fr": ["En mode sombre, le texte gris est illisible."],
            "pt": ["No modo escuro o texto cinza quase não dá para ler."],
        },
        {
            "en": ["Dark mode contrast"],
            "es": ["Modo oscuro"],
            "de": ["Dunkelmodus"],
            "fr": ["Mode sombre"],
            "pt": ["Modo escuro"],
        },
    ),
    Topic(
        "confusing_nav",
        (2, 4),
        w(1.8),
        {
            "en": [
                "It took me ages to find where to set a recurring task. The menus are confusing.",
                "The new layout is confusing, I can't find the settings button anymore.",
            ],
            "es": ["El menú es confuso, no encuentro dónde crear tareas repetidas."],
            "de": ["Die Menüs sind verwirrend, ich finde die wiederkehrenden Aufgaben nicht."],
            "fr": ["Les menus sont déroutants, je ne trouve pas les tâches récurrentes."],
            "pt": ["O menu é confuso, não acho onde criar tarefas recorrentes."],
        },
        {
            "en": ["Confusing menus"],
            "es": ["Confuso"],
            "de": ["Verwirrend"],
            "fr": ["Déroutant"],
            "pt": ["Confuso"],
        },
    ),
    Topic(
        "small_widget",
        (2, 3),
        w(0.4, v2_4_0=6.0),
        {
            "en": [
                "The redesigned widget is too small, I can only see two tasks now.",
                "Bring back the old widget layout, the new one hides most of my list.",
            ],
            "es": ["El nuevo widget es muy pequeño, solo muestra dos tareas."],
            "de": ["Das neue Widget ist zu klein und zeigt nur zwei Aufgaben."],
            "fr": ["Le nouveau widget est trop petit, on ne voit que deux tâches."],
            "pt": ["O widget novo é pequeno demais, só mostra duas tarefas."],
        },
        {
            "en": ["New widget is worse"],
            "es": ["Widget pequeño"],
            "de": ["Widget zu klein"],
            "fr": ["Widget trop petit"],
            "pt": ["Widget pequeno"],
        },
    ),
    Topic(
        "reminders_late",
        (2, 3),
        w(1.6),
        {
            "en": [
                "Reminders show up 20 minutes late or not at all.",
                "Notifications for my tasks don't arrive on time anymore.",
            ],
            "es": ["Los recordatorios llegan tarde o no llegan."],
            "de": ["Erinnerungen kommen zu spät oder gar nicht."],
            "fr": ["Les rappels arrivent en retard ou pas du tout."],
            "pt": ["Os lembretes chegam atrasados ou nem chegam."],
        },
        {
            "en": ["Late reminders"],
            "es": ["Recordatorios"],
            "de": ["Erinnerungen"],
            "fr": ["Rappels"],
            "pt": ["Lembretes"],
        },
    ),
    Topic(
        "calendar_sync",
        (2, 3),
        w(1.6),
        {
            "en": [
                "Google Calendar events stopped syncing, my agenda is empty.",
                "Sync between my phone and iPad is broken, tasks don't show up on the other device.",
            ],
            "es": ["La sincronización con Google Calendar no funciona."],
            "de": ["Die Synchronisierung mit dem Google Kalender funktioniert nicht mehr."],
            "fr": ["La synchronisation avec Google Agenda ne marche plus."],
            "pt": ["A sincronização com o Google Agenda parou de funcionar."],
        },
        {
            "en": ["Sync broken"],
            "es": ["Sincronización"],
            "de": ["Sync kaputt"],
            "fr": ["Synchro"],
            "pt": ["Sincronização"],
        },
    ),
    Topic(
        "want_watch",
        (3, 5),
        w(1.8),
        {
            "en": [
                "Would love an Apple Watch app so I can tick off tasks from my wrist.",
                "Please add a watch app. It's the only thing missing for me.",
            ],
            "es": ["Me encantaría una app para el Apple Watch."],
            "de": ["Bitte eine Apple-Watch-App hinzufügen, das fehlt mir noch."],
            "fr": ["Ce serait génial d'avoir une app pour l'Apple Watch."],
            "pt": ["Seria ótimo ter um app para o Apple Watch."],
        },
        {
            "en": ["Watch app please"],
            "es": ["Apple Watch"],
            "de": ["Apple Watch"],
            "fr": ["Apple Watch"],
            "pt": ["Apple Watch"],
        },
    ),
    Topic(
        "want_shared",
        (3, 5),
        w(1.8),
        {
            "en": [
                "Please add shared lists so my partner and I can plan groceries together.",
                "It would be great to share a project with my team and assign tasks.",
            ],
            "es": ["Por favor añadan listas compartidas para usar en familia."],
            "de": ["Bitte geteilte Listen einbauen, damit ich mit meiner Familie planen kann."],
            "fr": ["Merci d'ajouter des listes partagées pour la famille."],
            "pt": ["Por favor adicionem listas compartilhadas para usar com a família."],
        },
        {
            "en": ["Shared lists?"],
            "es": ["Listas compartidas"],
            "de": ["Geteilte Listen"],
            "fr": ["Listes partagées"],
            "pt": ["Listas compartilhadas"],
        },
    ),
    Topic(
        "want_export",
        (3, 4),
        w(1.0),
        {
            "en": ["I'd like a way to export my tasks to CSV or PDF for work reports."],
            "es": ["Me gustaría poder exportar mis tareas a PDF."],
            "de": ["Ich wünsche mir einen Export der Aufgaben als PDF."],
            "fr": ["J'aimerais pouvoir exporter mes tâches en PDF."],
            "pt": ["Gostaria de poder exportar minhas tarefas em PDF."],
        },
        {
            "en": ["Export option"],
            "es": ["Exportar"],
            "de": ["Export"],
            "fr": ["Export"],
            "pt": ["Exportar"],
        },
    ),
    Topic(
        "praise_general",
        (5, 5),
        w(9.0, v2_3_0=4.0),
        {
            "en": [
                "Best planner I've used. Simple, clean and it just works.",
                "Love this app, it keeps my whole week organized.",
                "Great app! I use it every day for work and home.",
                "Clean design and very easy to use. Worth it.",
            ],
            "es": ["¡Me encanta! Muy fácil de usar y me organiza la semana."],
            "de": ["Tolle App, einfach und übersichtlich. Nutze sie jeden Tag."],
            "fr": ["Super application, simple et efficace. Je l'utilise tous les jours."],
            "pt": ["Adoro esse app, simples e muito fácil de usar."],
        },
        {
            "en": ["Love it", "Perfect planner", "Five stars"],
            "es": ["Excelente"],
            "de": ["Super"],
            "fr": ["Génial"],
            "pt": ["Ótimo"],
        },
    ),
    Topic(
        "praise_habits",
        (4, 5),
        w(3.0),
        {
            "en": [
                "The habit tracker is fantastic, I finally kept a streak for two months.",
                "Love the habit streaks, they really keep me motivated.",
            ],
            "es": ["El seguimiento de hábitos es fantástico."],
            "de": ["Der Gewohnheits-Tracker ist klasse und motiviert mich."],
            "fr": ["Le suivi des habitudes est génial, très motivant."],
            "pt": ["O controle de hábitos é fantástico, me motiva muito."],
        },
        {
            "en": ["Habit streaks rock"],
            "es": ["Hábitos"],
            "de": ["Gewohnheiten"],
            "fr": ["Habitudes"],
            "pt": ["Hábitos"],
        },
    ),
    Topic(
        "praise_focus",
        (4, 5),
        w(0.0, v2_4_0=5.0),
        {
            "en": [
                "The new focus timer in 2.4 is exactly what I needed. Love it.",
                "Great update, the focus timer is really helpful for studying.",
            ],
            "es": ["El nuevo temporizador de concentración es genial."],
            "de": ["Der neue Fokus-Timer ist super hilfreich."],
            "fr": ["Le nouveau minuteur de concentration est génial."],
            "pt": ["O novo timer de foco é ótimo."],
        },
        {
            "en": ["Focus timer!"],
            "es": ["Temporizador"],
            "de": ["Fokus-Timer"],
            "fr": ["Minuteur"],
            "pt": ["Timer de foco"],
        },
    ),
    Topic(
        "praise_fixed",
        (4, 5),
        w(0.0, v2_3_1=9.0),
        {
            "en": [
                "Login works again after the last update, thank you for the quick fix!",
                "The sign-in crash is fixed. Back to five stars.",
            ],
            "es": ["Ya funciona el inicio de sesión, gracias por arreglarlo tan rápido."],
            "de": ["Die Anmeldung funktioniert wieder, danke für die schnelle Lösung!"],
            "fr": ["La connexion fonctionne à nouveau, merci pour la correction rapide !"],
            "pt": ["O login voltou a funcionar, obrigado pela correção rápida!"],
        },
        {
            "en": ["Fixed, thanks"],
            "es": ["Arreglado"],
            "de": ["Behoben"],
            "fr": ["Corrigé"],
            "pt": ["Corrigido"],
        },
    ),
]

OPENERS = {
    "en": ["", "", "", "Honestly, ", "Update: ", "Hmm. "],
    "es": ["", "", "Sinceramente, "],
    "de": ["", "", "Ehrlich gesagt: "],
    "fr": ["", "", "Franchement, "],
    "pt": ["", "", "Sinceramente, "],
}
CLOSERS = {
    "en": ["", "", "", " Please fix.", " Otherwise a good app.", " I use it daily."],
    "es": ["", "", " Por favor arréglenlo."],
    "de": ["", "", " Bitte beheben."],
    "fr": ["", "", " Merci de corriger."],
    "pt": ["", "", " Por favor corrijam."],
}
NAMES = ["Otter", "Maple", "Comet", "Pixel", "Harbor", "Fennel", "Juniper", "Robin", "Sprout"]
ADJECTIVES = ["Quiet", "Busy", "Sunny", "Lucky", "Brave", "Tidy", "Sleepy", "Rapid", "Calm"]


def pick_language(rng: random.Random) -> str:
    return rng.choices([code for code, _ in LANGUAGES], weights=[p for _, p in LANGUAGES])[0]


def closer_for(topic: Topic, language: str, rng: random.Random) -> str:
    # Praise with "Please fix." reads as noise, not realism.
    if topic.key.startswith("praise") or topic.key.startswith("want"):
        return ""
    return rng.choice(CLOSERS[language])


def generate() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    reviews: list[dict[str, object]] = []
    app_store_id = 9_100_000_000
    play_id = 0
    boundaries = [start for _, start, _ in RELEASES[1:]] + [END]

    for (version, start, count), end in zip(RELEASES, boundaries, strict=True):
        weights = [t.weights[version] for t in TOPICS]
        for _ in range(count):
            topic = rng.choices(TOPICS, weights=weights)[0]
            language = pick_language(rng)
            texts = topic.texts.get(language) or topic.texts["en"]
            body = (rng.choice(OPENERS[language]) + rng.choice(texts)).strip()
            body = (body + closer_for(topic, language, rng)).strip()
            created = start + timedelta(
                seconds=rng.randint(3600, int((end - start).total_seconds()))
            )
            store = "app_store" if rng.random() < 0.55 else "google_play"
            rating = rng.randint(*topic.ratings)
            if store == "app_store":
                app_store_id += rng.randint(1, 900)
                external_id = str(app_store_id)
                title: str | None = rng.choice(topic.titles.get(language) or topic.titles["en"])
            else:
                play_id += 1
                external_id = f"gp:{SEED:04d}-{play_id:05d}"
                title = None
            author = f"{rng.choice(ADJECTIVES)}{rng.choice(NAMES)}{rng.randint(1, 99)}"
            reviews.append(
                {
                    "store": store,
                    "external_id": external_id,
                    "rating": rating,
                    "title": title,
                    "body": body,
                    "language": language,
                    "app_version": version,
                    "territory": rng.choice(TERRITORIES[language]),
                    "author": author,
                    "created_at": created.isoformat(),
                    "topic": topic.key,
                }
            )
    reviews.sort(key=lambda r: str(r["created_at"]))
    return reviews


def main() -> None:
    reviews = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app": {"name": "Pocket Planner", "bundle_id": "app.pocketplanner.ios", "fictional": True},
        "generated_by": "scripts/generate_dataset.py",
        "seed": SEED,
        "reviews": reviews,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    by_version: dict[str, int] = {}
    for review in reviews:
        by_version[str(review["app_version"])] = by_version.get(str(review["app_version"]), 0) + 1
    print(f"wrote {len(reviews)} reviews to {OUT.name}: {by_version}")


if __name__ == "__main__":
    main()
