from build_blacklist import *


IMPORT = "blacklist_from_sheets.txt"

if __name__ == "__main__":
    blacklist = Blacklist()

    with open(IMPORT) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            username, category = line.rsplit("\t", 1)
            if username and category:
                new_entry = blacklist.get_or_append(
                    username=username,
                    category=category,
                )
                continue

            print(f"Unable to process non-blank line in input:\n{line}")
            raise RuntimeError("Unable to process input line.")

    blacklist.save_blacklist()



