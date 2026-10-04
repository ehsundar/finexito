"""Due dates typed in English: `tomorrow 9am`, `every other friday`, `every! 3 days`.

``Due.parse`` reads a whole phrase, as the date field sends it; ``Due.find``
finds one inside a task's text, as quick add sends it. Calendar dates go to
dateparser and recurrence to dateutil's rrule; this module only knows which
words mean what.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import dateparser
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrulestr

WEEKDAYS = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}  # fmt: skip
RRULE_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
UNITS = {"day": "DAILY", "week": "WEEKLY", "month": "MONTHLY", "year": "YEARLY"}
ADVERBS = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY", "yearly": "YEARLY"}

WEEKDAY = "(?:" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + ")"
MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
ORDINAL = r"(\d{1,2})(?:st|nd|rd|th)?"
DAY_MONTH = rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}|{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?)"
CALENDAR = rf"(?:{DAY_MONTH}(?:\s+\d{{4}})?|\d{{1,2}}/\d{{1,2}}(?:/\d{{2}}(?:\d{{2}})?)?)"
TIME = r"(?:at\s+)?(?:(\d{1,2})(?::(\d{2}))?\s*(am|pm)|(\d{1,2}):(\d{2}))"
ONE_OFF = re.compile(
    rf"(?P<date>today|tod|tomorrow|tom|this\s+weekend|next\s+week|(?:next\s+)?{WEEKDAY}"
    rf"|in\s+\d+\s+(?:day|week|month)s?|{CALENDAR})?"
    rf"(?:\s*(?P<time>{TIME}))?",
    re.I,
)
RECURRING = re.compile(
    rf"(?:(?P<adverb>daily|weekly|monthly|yearly)|every(?P<bang>!)?\s+(?P<body>.+?))"
    rf"(?:\s+(?P<time>{TIME}))?"
    rf"(?:\s+start(?:ing)?\s+(?P<start>.+?))?"
    rf"(?:\s+until\s+(?P<until>.+?))?"
    rf"(?:\s+for\s+(?P<count>\d+)\s+times?)?",
    re.I,
)
# A phrase inside a task is at most this many words.
MAX_WORDS = 12


@dataclass
class Due:
    """A parsed due date. No date at all means "no date"."""

    date: date | None = None
    time: time | None = None
    # RFC 5545 text, DTSTART and RRULE, in the member's wall-clock time.
    rule: str = ""
    from_completion: bool = False
    string: str = ""

    @classmethod
    def parse(cls, phrase: str, today: date) -> "Due":
        """The due date ``phrase`` means; ValueError if it means nothing."""
        phrase = " ".join(phrase.split())
        if phrase.lower() == "no date":
            return cls()
        if match := ONE_OFF.fullmatch(phrase):
            if not (match["date"] or match["time"]):
                raise ValueError(phrase)
            day = one_off_date(match["date"], today) if match["date"] else today
            return cls(date=day, time=parse_time(match["time"]), string=phrase)
        if match := RECURRING.fullmatch(phrase):
            return recurring(match, phrase, today)
        raise ValueError(phrase)

    @classmethod
    def find(cls, text: str, today: date) -> tuple["Due", tuple[int, int], str] | None:
        """The first phrase in ``text`` that is a due date, its span, and the text without it.

        The longest phrase wins at each word. A backslash before a phrase keeps
        it as text, and is dropped.
        """
        words = list(re.finditer(r"\S+", text))
        escapes = []
        for i, first in enumerate(words):
            for j in range(min(len(words), i + MAX_WORDS), i, -1):
                start, end = first.start(), words[j - 1].end()
                escaped = text[start] == "\\"
                try:
                    due = cls.parse(text[start + escaped : end], today)
                except ValueError:
                    continue
                if escaped:
                    escapes.append(start)
                    break
                rest = text[:start] + text[end:]
                for index in reversed(escapes):
                    rest = rest[:index] + rest[index + 1 :]
                return due, (start, end), " ".join(rest.split())
        return None


def one_off_date(phrase: str, today: date) -> date:
    phrase = " ".join(phrase.lower().split())
    if phrase in ("today", "tod"):
        return today
    if phrase in ("tomorrow", "tom"):
        return today + timedelta(days=1)
    if phrase == "this weekend":
        return today + timedelta(days=(5 - today.weekday()) % 7)
    if phrase == "next week":
        return today + timedelta(days=7 - today.weekday())
    if (day := phrase.removeprefix("next ")) in WEEKDAYS:
        return today + timedelta(days=(WEEKDAYS[day] - today.weekday() - 1) % 7 + 1)
    if match := re.fullmatch(r"in (\d+) (day|week|month)s?", phrase):
        n, unit = int(match[1]), match[2]
        return today + relativedelta(**{unit + "s": n})
    return calendar_date(phrase, today)


def calendar_date(phrase: str, today: date) -> date:
    """`12 oct`, `oct 12th`, `12/10/2027`: day first, the next one if there's no year."""
    found = dateparser.parse(
        re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", phrase),
        languages=["en"],
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.combine(today, time()),
            "REQUIRE_PARTS": ["day", "month"],
        },
    )
    if found is None:
        raise ValueError(phrase)
    return found.date()


def parse_time(phrase: str | None) -> time | None:
    if not phrase:
        return None
    match = re.fullmatch(TIME, phrase.strip(), re.I)
    if match[3]:
        hour, minute = int(match[1]), int(match[2] or 0)
        if not 1 <= hour <= 12:
            raise ValueError(phrase)
        hour = hour % 12 + (12 if match[3].lower() == "pm" else 0)
    else:
        hour, minute = int(match[4]), int(match[5])
    if hour > 23 or minute > 59:
        raise ValueError(phrase)
    return time(hour, minute)


def recurring(match: re.Match, phrase: str, today: date) -> Due:
    rule = (
        f"FREQ={ADVERBS[match['adverb'].lower()]}"
        if match["adverb"]
        else repeat(" ".join(match["body"].lower().split()), today)
    )
    if match["until"]:
        rule += f";UNTIL={calendar_or_relative(match['until'], today):%Y%m%d}T235959"
    if match["count"]:
        rule += f";COUNT={int(match['count'])}"
    at = parse_time(match["time"])
    start = calendar_or_relative(match["start"], today) if match["start"] else today
    # The series starts on its first day, so `every other friday` means this
    # Friday, not whichever Friday rrule's fortnight lands on.
    dtstart = datetime.combine(start, at or time())
    unspaced = re.sub(r";INTERVAL=\d+", "", rule)
    first = rrulestr(f"RRULE:{unspaced}", dtstart=dtstart).after(dtstart, inc=True)
    if first is None:
        raise ValueError(phrase)
    text = f"DTSTART:{first:%Y%m%dT%H%M%S}\nRRULE:{rule}"
    return Due(
        date=first.date(),
        time=at,
        rule=text,
        from_completion=bool(match["bang"]),
        string=phrase,
    )


def calendar_or_relative(phrase: str, today: date) -> date:
    match = ONE_OFF.fullmatch(" ".join(phrase.split()))
    if not match or not match["date"] or match["time"]:
        raise ValueError(phrase)
    return one_off_date(match["date"], today)


def repeat(body: str, today: date) -> str:
    """The RRULE (without DTSTART) for what follows `every`."""
    if body == "day":
        return "FREQ=DAILY"
    if body == "weekday":
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    if body == "last day":
        return "FREQ=MONTHLY;BYMONTHDAY=-1"
    if body in UNITS:
        return f"FREQ={UNITS[body]}"
    if match := re.fullmatch(r"(\d+|other) (day|week|month|year)s?", body):
        interval = 2 if match[1] == "other" else int(match[1])
        if interval < 1:
            raise ValueError(body)
        return f"FREQ={UNITS[match[2]]};INTERVAL={interval}"
    if match := re.fullmatch(rf"other ({WEEKDAY})", body):
        return f"FREQ=WEEKLY;INTERVAL=2;BYDAY={RRULE_DAYS[WEEKDAYS[match[1]]]}"
    if re.fullmatch(rf"{WEEKDAY}(?:\s*(?:,|and)\s*{WEEKDAY})*", body):
        days = sorted({WEEKDAYS[day] for day in re.findall(WEEKDAY, body)})
        return "FREQ=WEEKLY;BYDAY=" + ",".join(RRULE_DAYS[day] for day in days)
    if match := re.fullmatch(rf"(?:month on the )?{ORDINAL}", body):
        if not 1 <= int(match[1]) <= 31:
            raise ValueError(body)
        return f"FREQ=MONTHLY;BYMONTHDAY={int(match[1])}"
    if re.fullmatch(DAY_MONTH, body):
        day = calendar_date(body, today)
        return f"FREQ=YEARLY;BYMONTH={day.month};BYMONTHDAY={day.day}"
    raise ValueError(body)
