# Fetches 9D's dated timetable (with substitutions and events) from Viimsi Kool's public Edupage
# for yesterday .. +13 days and writes live.json for the app. Run by .github/workflows/live.yml.
import json, re, urllib.request, datetime, zoneinfo

BASE = "https://viimsi.edupage.org/timetable/server/"
CLASS_ID = "-290"  # 9D
MY_GROUPS = {"", "Terve klass", "mat5", "IK6", "VK4", "T1", "käs"}
NAMES = {
    "Inglise keel (A-võõrkeel)": "Inglise keel", "Vene keel (B-võõrkeel)": "Vene keel",
    "Saksa keel (B-võõrkeel)": "Saksa keel", "Käsitöö- kodundus/tehnoloogiaõpetus": "Käsitöö",
    "Liikumisõpetus": "Kehaline", "Ühiskonnaõp": "Ühiskonnaõpetus", "Klassijuhataja": "Klassijuhataja tund",
}

def call(path, func, args):
    body = json.dumps({"__args": [None] + args, "__gsh": "00000000"}).encode()
    req = urllib.request.Request(f"{BASE}{path}?__func={func}", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["r"]

def main():
    today = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Tallinn")).date()
    year = today.year if today.month >= 8 else today.year - 1
    viewer = call("ttviewer.js", "getTTViewerData", [year])
    tt_num = viewer["regular"]["default_num"]
    tables = {t["id"]: {r["id"]: r for r in t["data_rows"]}
              for t in call("regulartt.js", "regularttGetData", [tt_num])["dbiAccessorRes"]["tables"]}
    subj = lambda i: NAMES.get(tables["subjects"].get(i, {}).get("name", ""), tables["subjects"].get(i, {}).get("name", "?"))
    teacher = lambda i: re.sub(r"\s?[A-ZÕÄÖÜ]$", "", tables["teachers"].get(i, {}).get("short", ""))
    room = lambda i: tables["classrooms"].get(i, {}).get("short", "")

    start, end = today - datetime.timedelta(days=1), today + datetime.timedelta(days=13)
    r = call("currenttt.js", "curentttGetData", [{
        "year": year, "datefrom": str(start), "dateto": str(end), "table": "classes", "id": CLASS_ID,
        "showColors": True, "showIgroupsInClasses": False, "showOrig": True, "log_module": "CurrentTTView"}])

    days, events = {}, {}
    d = start
    while d <= end:
        if d.weekday() < 5:
            days[str(d)] = []
        d += datetime.timedelta(days=1)
    for x in r["ttitems"]:
        if x["type"] == "event":
            events.setdefault(x["date"], []).append({"name": x.get("name", ""), "start": x["starttime"], "end": x["endtime"]})
            continue
        if x["type"] != "card" or not x.get("subjectid"):
            continue
        if not set(x.get("groupnames") or [""]) & MY_GROUPS:
            continue
        days.setdefault(x["date"], []).append({
            "p": int(x["uniperiod"]) if str(x["uniperiod"]).isdigit() else 0,
            "subj": subj(x["subjectid"]),
            "teacher": ", ".join(teacher(t) for t in x.get("teacherids", [])),
            "room": ", ".join(room(c) for c in x.get("classroomids", [])),
            "start": x["starttime"], "end": x["endtime"],
            "changed": bool(x.get("changed")),
        })
    for v in days.values():
        v.sort(key=lambda l: l["start"])
    out = {"updated": datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Tallinn")).strftime("%Y-%m-%d %H:%M"),
           "days": days, "events": events}
    old = None
    try:
        old = json.load(open("live.json", encoding="utf8"))
    except Exception:
        pass
    # keep the file unchanged when only the timestamp would differ, so no empty commits
    if old and old.get("days") == days and old.get("events") == events:
        return
    json.dump(out, open("live.json", "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
