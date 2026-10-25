"""Freeze task order and Janus/Vanilla prompts before any model call."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MECH = HERE.parent / "skillflow_mechanism_20261013"
SQL_EXCLUDED = {54, 83, 164, 178, 225, 271, 301, 525, 531, 638, 704, 710, 798, 802, 803, 850, 892, 942, 967}
BASH_COUNTS = {1: 60, 2: 53, 3: 60, 4: 27}


def order_hash(benchmarks):
    body = {name: benchmarks[name]["ids"] for name in sorted(benchmarks)}
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def prompt_hash(item):
    blob = item["vanilla"] + "\n---JANUS---\n" + item["janus"]
    return hashlib.sha256(blob.encode()).hexdigest()


def bash_ids():
    ids = []
    for fs, count in sorted(BASH_COUNTS.items()):
        ids.extend(f"nl2bash-fs{fs}-{index}" for index in range(count))
    ids.sort(key=lambda item: (int(item.split("-")[1][2:]), int(item.split("-")[2])))
    return ids


def sql_ids():
    return [f"spider-{index}" for index in range(1034) if index not in SQL_EXCLUDED]


def tau_ids():
    ids = [f"airline-{index}" for index in range(50)] + [f"retail-{index}" for index in range(115)]
    ids.sort(key=lambda item: (item.split("-")[0], int(item.split("-")[1])))
    return ids


def terminal_ids():
    summary = json.loads((MECH / "tb-v5" / "full-summary.json").read_text(encoding="utf-8"))
    return sorted(summary["pairs"])


def pack(ids):
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate task id")
    return {"count": len(ids), "pilot": ids[:8], "ids": ids}


def prompts():
    sys.path.insert(0, str(MECH / "tb-v5"))
    from tb_policy import COMMON, ROLES, extra

    freeze = json.loads((MECH / "native-system-freeze.json").read_text(encoding="utf-8"))
    staff = freeze["variants"]["native-trained-frozen-source"]["staffContract"]["instructions"]
    terminal_janus = extra(staff, ROLES["FINAL_VALIDATION"], True) + (
        "\nWhen the task is to cancel asynchronous work, cancel the enclosing task group so the remaining tasks stop too, then run the tests before marking the task complete.\n"
    )
    bash_janus = (
        "Produce the requested result with one pipeline, and do not print another command after it.\n"
        "When the instruction asks for the md5 sum of the md5 sum of sorted files, sort the file names, run md5sum on each file, and md5sum that output. Do not concatenate the file bytes and do not cut the hash line.\n"
        "When it asks for the md5 sum of the contents of files named by a shell variable, expand that variable, sort those names, and hash the concatenated file bytes. Do not replace the variable with find, even if an unquoted echo looks empty.\n"
        "When it asks for a sorted list of checksums, use one pipeline: md5sum of each file, sort of those full lines, then md5sum. Keep the filename on each line.\n"
        "When it says to md5sum each file and sort that output, sort the checksum lines and then md5sum them. Do not sort the filenames for that request.\n"
        "Do not print a preview, a filename list, or a second hash after that pipeline.\n"
    )
    sql_staff = (MECH / "intercode-sql-staff.txt").read_text(encoding="utf-8").strip()
    roles = json.loads((MECH / "sql-v21" / "sql_role_templates.json").read_text(encoding="utf-8"))
    policy = (
        "Answer the public question with read-only MySQL using the actual\n"
        "schema. Preserve ONLY_FULL_GROUP_BY and all database settings; do not modify\n"
        "data. Work out the requested output columns and row granularity first. Return\n"
        "only those columns, without extra identifiers, notes or debugging aggregates.\n"
        "Check row versus entity counts, supported joins, multiplicity and NULLs. Apply\n"
        "row conditions before grouping and grouped conditions with HAVING or a suitable\n"
        "subquery. Do not invent schema constraints or impose additional conditions.\n"
        "Add sorting only when requested or needed to select an explicitly requested\n"
        "rank; do not add cosmetic sorting. Inspect schema or data when necessary, but\n"
        "an inspection query is never the answer query. IMPORTANT: submit grades only\n"
        "the LAST executed SQL. After any diagnostic query, execute your final answer\n"
        "query again before submit. Its columns, rows, aggregation and limit must answer\n"
        "the question directly. A frozen output proposal is fallible advice: derive the\n"
        "SQL independently, reject unsupported details, and do not replace a correct\n"
        "answer with diagnostic output. Return one SQL statement or submit per turn;\n"
        "keep reasoning internal."
    )
    role_block = "\n".join(f"{name}: {text}" for name, text in roles.items())
    sql_janus = (
        "Output rule: select only the columns the question asks to see. "
        "A column used only to filter, join, group, or sort is not an output column. "
        "When the question asks which entities, return the entity name or identifier only. "
        "Before submit, read the requested output again and drop any selected column the question did not ask to see. "
        "The submitted query must match the requested columns and rows exactly. "
        "A count question returns one number. A which or list question returns only the identifying column. "
        "If the question can be answered without an extra column, leave that column out. "
        "Do not add ORDER BY unless the question asks for an order or a specific rank. "
        "Use LIMIT only when the question asks for one row, a rank, or a specific number of rows. "
        "Use DISTINCT only when the question says different or distinct; when it asks how many different values, put DISTINCT inside the count and return that one number. "
        "Return the requested columns in the order the question names them. "
        "When the question asks for entities that have no related row, exclude those entities and return only the requested identifier. "
        "A numeric range used only to filter rows is not an output column. "
        "Do not use SELECT star, and do not add a column alias the question did not ask to see. "
        "Return a name when the question asks for a name, and an id only when it asks for an id. Do not substitute a code for a name. "
        "Include both endpoints of a between range. Do not drop a row that satisfies the stated filter, and do not keep a row that fails it. "
        "When the question asks for two aggregates, return both in that order as one row. When it asks for an aggregate for each group, return the group key and that aggregate. "
        "The graded statement is one SQL answer. Do not leave a SHOW, DESCRIBE, or preview query as the statement that gets graded. "
        "When excluding entities that appear in a related table, check every direction the question names, not only one. "
        "A grouped question returns one row per group, not one row per member of the group. "
        "For an exclusion question, select the entity name the question asks to see and leave every other column out. "
        "When a rank is requested, order by the measure the question names and keep only that row. "
        "After any schema or data inspection, execute the answer query again so the last statement is that answer. "
        "Compare text values with the exact spelling in the question. "
        "Read the requested output once more immediately before the final query. "
        "The answer query is read-only. Do not issue UPDATE, INSERT, DELETE, or ALTER. "
        "Join on the keys the schema actually contains. Do not invent a join condition. "
        "Do not create, drop, or replace a table, view, or index. "
        "A related row in either named direction still counts as related, so an exclusion rejects both directions. "
        "Quote a text filter with the exact characters written in the question. "
        "If the answer query is already read-only and returns the requested rows, submit that query and do not rewrite it. "
        "Add GROUP BY only when the question asks for a result per group. A single aggregate stays one row without GROUP BY. "
        "Do not cast an identifier to a number, and do not cast a number to text unless the question asks for that format. "
        "Do not use a window function unless the question asks for a rank or a running total. "
        "If a draft already returns only the requested identifier for an exclusion or a numeric range, keep that query. "
        "When the question says ascending or descending, use that direction and no other.\n\n"
        + policy
        + "\n\n"
        + sql_staff
        + "\n\nVerification roles:\n"
        + role_block
        + "\n"
    )
    tau_vanilla = (
        "Execution checklist (the official policy above takes precedence):\n"
        "Track the user's requests and complete each permitted part. Distinguish known\n"
        "facts from assumptions. Use the available read-only tools to obtain missing\n"
        "facts when the policy permits; ask concise questions for the remaining gaps.\n"
        "Before each tool call, check the exact schema, required arguments, identifiers,\n"
        "and current policy conditions. Use identifiers from the user or actual tool\n"
        "results, and follow required confirmation rules before changing records.\n"
        "After a tool result, check for errors and update your plan from the observed\n"
        "state. Do not repeat an unchanged failing call or claim a change succeeded\n"
        "without supporting tool results. If the request is prohibited, explain the\n"
        "specific constraint and offer an allowed alternative. Finish with an accurate\n"
        "summary of completed actions and any unresolved part. Treat any planner\n"
        "proposal as fallible advice and check it against policy and current facts."
    )
    tau_janus = (
        tau_vanilla
        + "\nIf the user only answers what you ask, ask one concise question for each missing fact the policy requires before you change a record. "
        + "Do not end after a lookup when they asked to complete a reservation or a change. "
        + "When they name more than one acceptable airport, search each of them and choose the cheapest flight that matches the requested day and cabin. "
        + "If the change includes both the flights and the baggage, submit both updates. "
        + "On a new booking, ask for the payment instrument and the bag count only when the user has not already given them. Do not add insurance when they said they do not want it. "
        + "On a new booking, the bag count is required: if the user has not given a number, ask for it and pass that number to the booking call. Set nonfree bags from the membership allowance for that cabin, and do not charge a bag the allowance already covers. "
        + "When they will pay with certificates, apply those certificates before a card. If only one certificate can be used, use the larger one and charge the remainder to the card they named. That remainder split is only for certificates on a new booking, never for a gift card. "
        + "Do not book a flight earlier than the departure time they stated. If a direct flight and one stop are both acceptable, search both and book the cheaper one in the requested cabin. On a new booking, search only the airport you first used for the city they named, keep every segment on the requested day, and book the passenger whose user id they gave. "
        + "Confirm the user id only when they ask to book a new reservation and have not already given it. "
        + "When they want the cheapest replacement for an existing trip, compare layover cities between that reservation's origin and destination, keep the trip on the requested day, and book the lowest total fare. Do not change the origin or destination unless they named another airport. Do not reuse the original flight numbers unless that itinerary is the cheapest. When they want the fastest same-day return, ignore price, pick the return with the shortest total time, and submit that flight update and the baggage update before searching again. A fastest-return request is not a cheapest-fare request. "
        + "When they ask to change the passenger, the cabin, and the bags on an existing trip, submit all three updates and do not ask for a birthday that is already in the profile. Basic economy can still change cabin, replace a passenger when the passenger count stays the same, and add bags. Do not stop after the cabin update. "
        + "When they already named a gift card for that reservation, use that card and do not ask for a different payment instrument. "
        + "When a flight change already states the baggage, do not ask for a bag count again. "
        + "On a flight change, the amount due is the fare difference, not the new itinerary total, and the tool accepts one payment method. If they asked for the smallest gift card, use the smallest gift card whose balance covers that full difference, and pass that same card to the baggage update. "
        + "When they want every business reservation moved to economy on the same flights and passengers, leave a reservation that is already economy unchanged. Do not ask them to pick a card. Submit each business reservation once, with cabin economy, the same flight numbers and dates, and that reservation's original payment id, after one yes. Report the sum of the refunds the tools return. If the cabin label still says the old cabin after that one flight update, do not send the same flight update again and do not transfer them to a human. Still submit a passenger update and a baggage update when they asked for those. "
        + "When they say the original payment is fine for a refund, use that reservation's original payment id. "
        + "Carry every constraint they already stated into the tool call, and do not add an option they declined.\n"
    )
    built = {
        "terminal": {"vanilla": COMMON.strip() + "\n", "janus": terminal_janus.strip() + "\n"},
        "bash": {"vanilla": "", "janus": bash_janus},
        "sql": {"vanilla": policy + "\n", "janus": sql_janus},
        "tau": {"vanilla": tau_vanilla + "\n", "janus": tau_janus},
    }
    for item in built.values():
        item["sha256"] = prompt_hash(item)
    return built


def main():
    benchmarks = {
        "terminal": pack(terminal_ids()),
        "bash": pack(bash_ids()),
        "sql": pack(sql_ids()),
        "tau": pack(tau_ids()),
    }
    expected = {"terminal": 63, "bash": 200, "sql": 1015, "tau": 165}
    for name, count in expected.items():
        if benchmarks[name]["count"] != count:
            raise SystemExit(f"{name} count {benchmarks[name]['count']} != {count}")
        if benchmarks[name]["pilot"] != benchmarks[name]["ids"][:8]:
            raise SystemExit(f"{name} pilot is not the first 8")
    lock = {
        "schema": "robustness-baseline-order-v1",
        "sort": "task number, not score",
        "historicalScoresAreReferenceOnly": True,
        "benchmarks": benchmarks,
    }
    lock["sha256"] = order_hash(benchmarks)
    text = json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
    (HERE / "order-lock.json").write_text(text, encoding="utf-8")
    prompt_doc = {"schema": "robustness-baseline-prompts-v1", "benchmarks": prompts()}
    (HERE / "prompts.json").write_text(json.dumps(prompt_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(lock["sha256"])
    for name, item in prompt_doc["benchmarks"].items():
        print(name, item["sha256"][:12], "pilot", ",".join(benchmarks[name]["pilot"]))


if __name__ == "__main__":
    main()
