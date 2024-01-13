from dataclasses import dataclass
import json
import os

INPUT_FILE = "blacklist.txt"
BLACKLIST_DATA = "blacklist/blacklist.json"

CATEGORY_SORTING = {
    "Scam": 100,
    "RMT": 200,
    "GW2Exchange": 300,
    "Other": 400,
    "Unknown": 500,
}

@dataclass
class BlacklistEntry:
    username: str
    category: str

    def to_json(self) -> dict:
        # Format for BLACKLIST_DATA
        return {
            "username": self.username,
            "category": self.category,
        }

    def sortkey(self) -> int:
        if self.category in CATEGORY_SORTING:
            return CATEGORY_SORTING[self.category]
        return 500

    def to_new_str(self) -> str:
        return f"{self.username}\t{self.category}"


@dataclass
class RenameEntry(BlacklistEntry):
    old_username: str

    def to_new_str(self) -> str:
        return f"[ {self.username}\t{self.category} - Renamed from {self.old_username} ]"

    def sortkey(self) -> int:
        # Sort renames after non-renames in same category
        return super().sortkey() + 10


class Blacklist:
    current_update: list[BlacklistEntry]
    previous_update: list[BlacklistEntry]
    full_blacklist: list[BlacklistEntry]

    def __init__(self):
        self.current_update = []
        self.previous_update = []

        with open(BLACKLIST_DATA) as f:
            data = json.load(f)
            self.full_blacklist = [
                BlacklistEntry(**x) for x in data
            ]

        with open(INPUT_FILE) as f:
            target = "current"
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line[0] == "#":
                    if "previous" in line.lower():
                        target = "previous"
                    continue
                if " -> " in line:
                    old, new = line.split(" -> ")
                    entry = self.update_username(old, new)
                    new_entry = RenameEntry(
                        username=entry.username,
                        category=entry.category,
                        old_username=old,
                    )
                    self.add_to_updates(
                        entry=new_entry,
                        target=target,
                    )
                    continue
                username, category = line.rsplit(" ", 1)
                if username and category:
                    new_entry = self.get_or_append(
                        username=username,
                        category=category,
                    )
                    self.add_to_updates(
                        entry=new_entry,
                        target=target,
                    )
                    continue

                print(f"Unable to process non-blank line in input:\n{line}")
                raise RuntimeError("Unable to process input line.")

        self.save_blacklist()

    def save_blacklist(self):
        with open(BLACKLIST_DATA, "w") as f:
            data = [x.to_json() for x in self.full_blacklist]
            json.dump(data, f)

    def get_or_append(self, username: str, category: str) -> BlacklistEntry:
        entry = self.get_entry(username)
        if entry:
            entry.category = category
            return entry
        entry = BlacklistEntry(
            username=username,
            category=category
        )
        self.full_blacklist.append(entry)
        return entry


    def get_entry(self, username: str) -> BlacklistEntry | None:
        for entry in self.full_blacklist:
            if entry.username.lower() == username.lower():
                return entry
        return None

    def get_entry_from_current(self, username: str) -> BlacklistEntry | None:
        for entry in self.current_update:
            if entry.username.lower() == username.lower():
                return entry
        return None

    def get_entry_from_previous(self, username: str) -> BlacklistEntry | None:
        for entry in self.previous_update:
            if entry.username.lower() == username.lower():
                return entry
        return None

    def update_username(self, old: str, new: str) -> BlacklistEntry:
        # First, if new is already in the blacklist, we're done
        if entry := self.get_entry(new):
            return entry

        # Otherwise, get the old entry and update it, if we can
        if entry := self.get_entry(old):
            entry.username = new
            return entry

        # Finally, this wasn't an update, throw an error
        print(f"You asked us to update usernames from {old} to {new}, but {old} isn't "
              f"in the blacklist. Please submit this as a new entry instead.")
        raise RuntimeError("Unable to process username change.")

    def add_to_updates(self, entry: BlacklistEntry, target: str):
        if "previous" in target:
            self.previous_update.append(entry)
        else:
            self.current_update.append(entry)

    def format_username(self, username: str) -> str:
        # This function just surrounds the username with formatting characters
        # based on whether it is in the current or previous update.
        if self.get_entry_from_current(username):
            return f"\n**{username}**\n"
        if self.get_entry_from_previous(username):
            return f"\n*{username}*\n"
        return username


@dataclass
class Embed:
    blacklist: Blacklist
    directory = "blacklist/embeds"

    def save_embed(self) -> None:
        with open(os.path.join(self.directory, self.filename), "w") as f:
            json.dump(self.build_embed(), f)


class NewEmbed(Embed):
    filename = "new.txt"
    order = 1

    def get_current_mode(self) -> str:
        if any(isinstance(x, RenameEntry) for x in self.blacklist.current_update):
            return "ini"
        return "fix"

    def get_previous_mode(self) -> str:
        if any(isinstance(x, RenameEntry) for x in self.blacklist.previous_update):
            return "ini"
        return "fix"

    def get_current_names(self) -> str:
        return self.get_names(use_list=self.blacklist.current_update)

    def get_previous_names(self) -> str:
        return self.get_names(use_list=self.blacklist.previous_update)

    def get_names(self, use_list: list[BlacklistEntry]) -> str:
        res = ""
        for entry in sorted(use_list, key=lambda x:x.sortkey()):
            res += entry.to_new_str() + "\n"
        return res

    def build_embed(self) -> dict:
        res = {}
        res['plainText'] = (
            "The following is the current list of individuals that we " +
            "recommend you do not trade with. Individuals on this list have either broken " +
            "ToS or have been reported for trade misconduct. The most recent addition is " +
            "**bolded**. Older entry is *with cursive*.\n\n" +
            "Check out <#1065084098613346398> for easier updating of your in-game blocklist!"
        )
        res['description'] = (
            "**__New Entry__**\n```" +
            self.get_current_mode() + "\n" +
            self.get_current_names() +
            f"```\n\n**__Older Entry__**\n```" +
            self.get_previous_mode() + "\n" +
            self.get_previous_names() +
            "```"
        )
        res['color'] = 16541188
        return res


class NormalEmbed(Embed):
    category = None
    letter_range = None
    footer = None

    def build_embed(self) -> dict:
        res = {
            "title": self.get_title(),
            "description": self.get_description(),
            "color": self.get_color(),
        }
        if self.footer:
            res["footer"] = self.footer
        return res

    def get_title(self) -> str:
        return self.title

    def get_description(self) -> str:
        entries = self.get_entries()
        res = "\n".join([
            self.blacklist.format_username(x.username)
            for x in entries
        ])
        return res

    def get_entries(self) -> list[BlacklistEntry]:
        entries = sorted(self.blacklist.full_blacklist, key=lambda x:x.username.lower())
        if self.category:
            entries = [x for x in entries if x.category == self.category]
        if self.letter_range:
            entries = [x for x in entries if x.username.upper()[0] in self.letter_range]
        return entries

    def get_color(self) -> int:
        return self.color


def range_char(start, stop):
    return list(chr(n) for n in range(ord(start), ord(stop) + 1))


class ScamEmbed(NormalEmbed):
    category = "Scam"
    title = "__Scam__"
    color = 14748684
    filename = "scam.txt"


class RMTALEmbed(NormalEmbed):
    category = "RMT"
    title = "__RMT__  *(Real Money Trading)*  (A-L)"
    color = 7451177
    filename = "rmta.txt"
    letter_range = range_char("A", "L")
    footer = "page 1/2"


class RMTMZEmbed(NormalEmbed):
    category = "RMT"
    title = "__RMT__  *(Real Money Trading)*  (M-Z)"
    color = 7451177
    filename = "rmtb.txt"
    letter_range = range_char("M", "Z")
    footer = "page 2/2"


class ExchangeEmbed(NormalEmbed):
    category = "GW2Exchange"
    title = "__GW2 Exchange__"
    color = 12297507
    filename = "exchange.txt"


class OtherEmbed(NormalEmbed):
    category = "Other"
    title = "__Other__"
    color = 8604544
    filename = "other.txt"

    def get_description(self) -> str:
        res = super().get_description()
        return (
            f"*Reasons other than the ones above. \nActivities such as: "
            f"Gross misconduct, horrendous trade etiquette, other ToS "
            f"violations, etc.. \nMost of them will still have something "
            f"to do with trade.*\n\n{res}"
        )

class UnknownEmbed(NormalEmbed):
    category = "Unknown"
    title = "__Unknown__"
    color = 8604544
    filename = "unknown.txt"

    def get_description(self) -> str:
        res = super().get_description()
        return (
            f"*The reason behind blacklisting these names has been lost "
            f"with time.\nDespite this, we recommend not to trade with "
            f"them.*\n\n{res}"
        )


if __name__ == "__main__":
    blacklist = Blacklist()

    NewEmbed(blacklist=blacklist).save_embed()
    ScamEmbed(blacklist=blacklist).save_embed()
    RMTALEmbed(blacklist=blacklist).save_embed()
    RMTMZEmbed(blacklist=blacklist).save_embed()
    ExchangeEmbed(blacklist=blacklist).save_embed()
    OtherEmbed(blacklist=blacklist).save_embed()
    UnknownEmbed(blacklist=blacklist).save_embed()
