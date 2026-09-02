"""Tests for the /stats period windows (24h / Week / Overall).

Every period used to be rendered from a card that shared one all-time Top Groups
table, and the bot-wide windowed totals were counted from a different array than
the Overall total. The result was three cards that reported the same data: only a
single number moved between them, and it could contradict the table underneath it.

These tests pin the two properties that were broken:
  * each period is counted from `chat_playback.play_dates` against its own cutoff;
  * each period renders its own leaderboard, so the cards genuinely differ.

The last section covers the write side, since a period can only be as accurate as
the play history behind it.
"""
import asyncio
import datetime

import database
import plugins._common as common


# ── fakes ─────────────────────────────────────────────────────────────────────

class _FakeCursor:
    """Stands in for both a Motor find() chain and an aggregate() cursor."""

    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, *a, **k):
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def __aiter__(self):
        for doc in self.docs:
            yield doc


class FakePlayback:
    """Minimal chat_playback: records pipelines, replays canned results."""

    def __init__(self, find_docs=(), agg_docs=()):
        self.find_docs = list(find_docs)
        self.agg_docs = list(agg_docs)
        self.pipelines = []

    def find(self, *a, **k):
        return _FakeCursor(self.find_docs)

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return _FakeCursor(self.agg_docs)


class FakeChat:
    def __init__(self, title):
        self.title = title


class FakeClient:
    def __init__(self, titles=None):
        self.titles = titles or {}
        self.get_chat_calls = []

        class _Me:
            id = 777
            username = "nubmusic"

        self.me = _Me()

    async def get_chat(self, chat_id):
        self.get_chat_calls.append(chat_id)
        if chat_id not in self.titles:
            raise RuntimeError("unknown chat")
        return FakeChat(self.titles[chat_id])


# ── cutoffs ───────────────────────────────────────────────────────────────────

def test_period_cutoffs_are_epochs_matching_their_window():
    reference = datetime.datetime(2026, 9, 3, 12, 0, 0)
    ref_epoch = reference.timestamp()

    day, day_label = common._stats_period_meta("24h", reference)
    week, week_label = common._stats_period_meta("week", reference)
    overall, overall_label = common._stats_period_meta("overall", reference)

    assert (day_label, week_label, overall_label) == ("24h", "Week", "Overall")
    assert ref_epoch - day == 24 * 3600
    assert ref_epoch - week == 7 * 24 * 3600
    assert overall is None, "Overall must be unwindowed"


def test_cutoffs_share_one_reference_so_periods_are_comparable():
    reference = datetime.datetime(2026, 9, 3, 12, 0, 0)
    cutoffs = common._stats_cutoffs(reference)

    assert set(cutoffs) == set(common._STATS_PERIODS)
    assert cutoffs["24h"] > cutoffs["week"], "a 24h window must start later than a week"
    assert cutoffs["overall"] is None


# ── per-chat windowed counts ──────────────────────────────────────────────────

def test_windowed_counts_differ_per_period():
    reference = datetime.datetime(2026, 9, 3, 12, 0, 0)
    cutoffs = common._stats_cutoffs(reference)
    ref_epoch = int(reference.timestamp())
    play_dates = [
        ref_epoch - 30 * 24 * 3600,  # a month ago
        ref_epoch - 5 * 24 * 3600,   # inside the week only
        ref_epoch - 3 * 3600,        # inside both windows
        ref_epoch - 60,              # inside both windows
    ]

    counts = common._windowed_play_counts(11, play_dates, cutoffs)

    assert counts["24h"] == 2
    assert counts["week"] == 3
    assert counts["overall"] == 11, "Overall reports play_count, not the capped array"


def test_windowed_counts_survive_a_chat_with_no_recorded_dates():
    """Legacy chats have play_count but no play_dates; windows are 0, not the total."""
    cutoffs = common._stats_cutoffs(datetime.datetime(2026, 9, 3, 12, 0, 0))

    counts = common._windowed_play_counts(42, [], cutoffs)

    assert counts["24h"] == 0
    assert counts["week"] == 0
    assert counts["overall"] == 42


# ── database windowing ────────────────────────────────────────────────────────

async def test_get_top_chats_ranks_by_the_window_not_all_time(monkeypatch):
    fake = FakePlayback(agg_docs=[{"chat_id": -100222, "plays": 9}, {"chat_id": -100111, "plays": 4}])
    monkeypatch.setattr(database, "chat_playback", fake)

    ranking = await database.get_top_chats(10, since=1_700_000_000)

    assert ranking == [(-100222, 9), (-100111, 4)]
    pipeline = fake.pipelines[0]
    assert pipeline[0]["$project"]["plays"] == database._windowed_plays_expr(1_700_000_000)
    assert pipeline[1] == {"$match": {"plays": {"$gt": 0}}}, "chats idle in the window must drop out"
    assert pipeline[2] == {"$sort": {"plays": -1}}
    assert pipeline[3] == {"$limit": 10}


async def test_get_top_chats_without_a_window_uses_all_time_play_count(monkeypatch):
    fake = FakePlayback(find_docs=[{"chat_id": -100111, "play_count": 50}])
    monkeypatch.setattr(database, "chat_playback", fake)

    ranking = await database.get_top_chats(10)

    assert ranking == [(-100111, 50)]
    assert fake.pipelines == [], "the all-time ranking needs no aggregation"


async def test_total_play_count_sums_the_window_from_play_dates(monkeypatch):
    fake = FakePlayback(agg_docs=[{"_id": None, "total": 7}])
    monkeypatch.setattr(database, "chat_playback", fake)

    total = await database.get_total_play_count(since=1_700_000_000)

    assert total == 7
    summed = fake.pipelines[0][0]["$group"]["total"]["$sum"]
    assert summed == database._windowed_plays_expr(1_700_000_000), (
        "the windowed total must count the same play_dates the ranking does"
    )


async def test_total_play_count_all_time_sums_play_count(monkeypatch):
    fake = FakePlayback(agg_docs=[{"_id": None, "total": 123}])
    monkeypatch.setattr(database, "chat_playback", fake)

    total = await database.get_total_play_count()

    assert total == 123
    assert fake.pipelines[0][0]["$group"]["total"] == {"$sum": "$play_count"}


async def test_windowed_total_never_raises_on_a_dead_database(monkeypatch):
    class _Boom:
        def aggregate(self, pipeline):
            raise RuntimeError("mongo unreachable")

    monkeypatch.setattr(database, "chat_playback", _Boom())

    assert await database.get_total_play_count(since=1_700_000_000) == 0


# ── leaderboards ──────────────────────────────────────────────────────────────

async def test_each_period_gets_its_own_leaderboard(monkeypatch):
    """Regression: one all-time table was pasted onto all three cards."""
    rankings = {
        "24h": [(-100111, 3)],
        "week": [(-100222, 12), (-100111, 5)],
        "overall": [(-100222, 40), (-100111, 31)],
    }
    seen = []

    async def _fake_top_chats(limit=10, since=None):
        seen.append(since)
        if since is None:
            return rankings["overall"]
        return rankings["24h"] if since == cutoffs["24h"] else rankings["week"]

    monkeypatch.setattr(common, "get_top_chats", _fake_top_chats)
    cutoffs = common._stats_cutoffs(datetime.datetime(2026, 9, 3, 12, 0, 0))
    client = FakeClient({-100111: "Alpha", -100222: "Beta"})

    tables = await common._build_top_groups_tables(client, cutoffs)

    assert len({tables["24h"], tables["week"], tables["overall"]}) == 3
    assert "24h" in tables["24h"] and "Week" in tables["week"] and "Overall" in tables["overall"]
    assert "Beta" not in tables["24h"], "a group idle in the window must not be ranked in it"
    assert "Beta" in tables["week"]
    assert seen == [cutoffs["24h"], cutoffs["week"], None]
    assert sorted(client.get_chat_calls) == [-100222, -100111], "titles resolved once per chat"


async def test_leaderboard_is_omitted_when_the_window_is_empty(monkeypatch):
    async def _none(limit=10, since=None):
        return []

    monkeypatch.setattr(common, "get_top_chats", _none)
    cutoffs = common._stats_cutoffs(datetime.datetime(2026, 9, 3, 12, 0, 0))

    tables = await common._build_top_groups_tables(FakeClient(), cutoffs)

    assert tables == {"24h": "", "week": "", "overall": ""}


async def test_unresolvable_chat_falls_back_to_its_id(monkeypatch):
    async def _one(limit=10, since=None):
        return [(-100999, 2)]

    monkeypatch.setattr(common, "get_top_chats", _one)
    cutoffs = common._stats_cutoffs(datetime.datetime(2026, 9, 3, 12, 0, 0))

    tables = await common._build_top_groups_tables(FakeClient(), cutoffs)

    assert "-100999" in tables["24h"]


# ── bot-wide card ─────────────────────────────────────────────────────────────

class FakeBotCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, *a, **k):
        return self.doc


def _patch_bot_wide(monkeypatch, doc, totals, rankings):
    async def _total(since=None):
        return totals[since is None]

    async def _top(limit=10, since=None):
        return rankings[since is None]

    monkeypatch.setattr(common, "collection", FakeBotCollection(doc))
    monkeypatch.setattr(common, "get_total_play_count", _total)
    monkeypatch.setattr(common, "get_top_chats", _top)


async def test_bot_wide_cards_report_their_own_totals(monkeypatch):
    _patch_bot_wide(
        monkeypatch,
        doc={"bot_id": 777, "users": [-100111, 5], "chat_type_cache": {"-100111": "supergroup", "5": "private"}},
        totals={True: 500, False: 9},
        rankings={True: [(-100111, 500)], False: [(-100111, 9)]},
    )

    cards = await common._build_stats_cards(FakeClient({-100111: "Alpha"}), 777)

    assert set(cards) == set(common._STATS_PERIODS)
    assert "Songs Played (24h)" in cards["24h"]
    assert "Songs Played (Week)" in cards["week"]
    assert "Songs Played (Overall)" in cards["overall"]
    # The windowed cards also state the all-time figure, so a matching pair is
    # visibly a young history rather than a bug.
    assert "Songs Played (All Time)" in cards["24h"]
    assert "Songs Played (All Time)" not in cards["overall"]
    assert len(set(cards.values())) == 3


async def test_bot_wide_card_reports_plays_without_the_roster_doc(monkeypatch):
    """A missing bot doc is not 'no data' when chats have played."""
    _patch_bot_wide(
        monkeypatch,
        doc=None,
        totals={True: 12, False: 4},
        rankings={True: [(-100111, 12)], False: [(-100111, 4)]},
    )

    cards = await common._build_stats_cards(FakeClient({-100111: "Alpha"}), 777)

    assert cards, "plays exist, so the card must render instead of claiming no data"
    assert "Alpha" in cards["24h"]


async def test_bot_wide_card_is_empty_when_nothing_is_stored(monkeypatch):
    _patch_bot_wide(monkeypatch, doc=None, totals={True: 0, False: 0}, rankings={True: [], False: []})

    assert await common._build_stats_cards(FakeClient(), 777) == {}


# ── recording plays ───────────────────────────────────────────────────

async def test_db_task_holds_a_reference_until_the_write_finishes():
    """The loop only weakly references a task, so an unheld one can be collected
    mid-flight and the play would never be recorded."""
    written = []

    async def _write():
        await asyncio.sleep(0)
        written.append(True)

    task = database.db_task(_write())

    assert task in database._bg_db_tasks
    await task
    assert written == [True]
    assert task not in database._bg_db_tasks, "completed writes must not leak"


async def test_db_task_swallows_a_failing_write():
    async def _boom():
        raise RuntimeError("mongo unreachable")

    await database.db_task(_boom())  # must not raise into the playback path


async def test_set_last_played_records_one_play_with_its_epoch(monkeypatch):
    """play_count and play_dates are written together, so they cannot disagree."""
    calls = []

    class _Playback:
        async def update_one(self, filter, update, upsert=False):
            calls.append((filter, update, upsert))

    monkeypatch.setattr(database, "chat_playback", _Playback())

    await database.set_last_played(-100111, 1_788_000_000)

    filter, update, upsert = calls[0]
    assert filter == {"chat_id": -100111}
    assert upsert is True
    assert update["$inc"] == {"play_count": 1}
    assert update["$set"] == {"last_played": 1_788_000_000}
    push = update["$push"]["play_dates"]
    assert push["$each"] == [1_788_000_000]
    assert push["$slice"] <= -5000, "the window must outlive a week of heavy play"
