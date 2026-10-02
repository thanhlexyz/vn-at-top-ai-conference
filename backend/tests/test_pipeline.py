"""Checks of the rules that decide what is counted. Run with `make test` (no network, no login)."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_site_data as build  # noqa: E402
import common  # noqa: E402
import fetch_accepted  # noqa: E402
import fetch_openreview  # noqa: E402
import find_candidates  # noqa: E402
from common import (classify_status, in_vietnam, name_key, norm_name, norm_title, openreview_venue,  # noqa: E402
                    same_institution, virtual_track, vn_institution)


class Labels(unittest.TestCase):
    def test_outcomes(self):
        cases = [
            ("ICLR 2025 Poster", "ICLR.cc/2025/Conference", "accepted"),
            ("ICLR 2023 notable top 25%", "ICLR.cc/2023/Conference", "accepted"),
            ("NeurIPS 2022 Accept", "NeurIPS.cc/2022/Conference", "accepted"),
            ("Submitted to ICLR 2025", "ICLR.cc/2025/Conference/Rejected_Submission", "rejected"),
            ("ICLR 2022 Submitted", "ICLR.cc/2022/Conference", "rejected"),  # once misread as accepted
            ("ICLR 2026 Conference Withdrawn Submission", "ICLR.cc/2026/Conference/Withdrawn_Submission", "withdrawn"),
            ("ICLR 2026 Conference Desk Rejected Submission", "ICLR.cc/2026/Conference/Desk_Rejected_Submission",
             "desk_rejected"),
            ("", "", "unknown"),
        ]
        for venue, venueid, want in cases:
            self.assertEqual(classify_status(venue, venueid), want, venue)

    def test_outcome_from_invitation_and_decision(self):
        self.assertEqual(classify_status(invitations=["ICLR.cc/2020/Conference/-/Withdrawn_Submission"]), "withdrawn")
        self.assertEqual(classify_status(invitations=["ICLR.cc/2021/Conference/-/Desk_Rejected_Submission"]),
                         "desk_rejected")
        self.assertEqual(classify_status(decision="Reject"), "rejected")
        self.assertEqual(classify_status(decision="Accept (Spotlight)"), "accepted")

    def test_openreview_venue(self):
        cases = {
            "ICLR.cc/2026/Conference/-/Submission": ("iclr", 2026, "main"),
            "ICLR.cc/2021/Conference/-/Blind_Submission": ("iclr", 2021, "main"),
            "ICLR.cc/2026/Workshop/TSALM/-/Submission": ("iclr", 2026, "workshop"),
            "ICLR.cc/2024/TinyPapers/-/Submission": ("iclr", 2024, "tiny_papers"),
            "NeurIPS.cc/2025/Datasets_and_Benchmarks_Track/-/Submission": ("neurips", 2025, "datasets_benchmarks"),
            "NeurIPS.cc/2023/Track/Datasets_and_Benchmarks/-/Submission": ("neurips", 2023, "datasets_benchmarks"),
            "NeurIPS.cc/2026/Evaluations_and_Datasets_Track/-/Submission": ("neurips", 2026, "datasets_benchmarks"),
            "ICML.cc/2025/Position_Paper_Track/-/Submission": ("icml", 2025, "position"),
            "thecvf.com/CVPR/2025/Conference/-/Submission": ("cvpr", 2025, "main"),
        }
        for invitation, want in cases.items():
            self.assertEqual(openreview_venue([invitation]), want, invitation)
        self.assertIsNone(openreview_venue(["TMLR/-/Submission"], ""))
        self.assertEqual(openreview_venue([], "ICLR.cc/2022/Conference"), ("iclr", 2022, "main"))

    def test_virtual_site_tracks(self):
        g = "https://openreview.net/group?id="
        self.assertEqual(virtual_track("T", g + "NeurIPS.cc/2025/Conference", "{location} Poster", True), "main")
        self.assertEqual(virtual_track("T", g + "NeurIPS.cc/2025/Datasets_and_Benchmarks_Track", "", True),
                         "datasets_benchmarks")
        self.assertEqual(virtual_track("T", g + "NeurIPS.cc/2025/Position_Paper_Track", "", True), "position")
        self.assertEqual(virtual_track("Position: stop", g + "ICML.cc/2024/Conference", "", True), "position")
        self.assertEqual(virtual_track("T", None, "Findings Poster", True), "findings")
        self.assertEqual(virtual_track("T", "TMLR-123", "", True), "journal")
        self.assertEqual(virtual_track("T", None, "", True), "other")  # a session container, not a paper
        self.assertEqual(virtual_track("T", None, None, False), "main")  # 2020-21 lists carry no source


class Names(unittest.TestCase):
    def test_names(self):
        self.assertEqual(norm_name("Nguyễn Phi-Lê "), "nguyen phi le")
        self.assertEqual(norm_name("Đàm Quang Tuấn"), "dam quang tuan")
        self.assertEqual(name_key("Ngo Van Linh"), name_key("Linh Ngo Van"))
        self.assertEqual(name_key("Khoa D. Doan"), name_key("Doan Khoa"))
        self.assertEqual(norm_title("ES³: A {Study} of 360° — Models"), norm_title("es3 a study of 360 models"))

    def test_vietnamese_institutions(self):
        short = lambda a: (vn_institution(a) or (None, None))[1]  # noqa: E731
        self.assertEqual(short("School of ICT, Hanoi University of Science and Technology"), "HUST")
        self.assertEqual(short("Hanoi University of Science"), "VNU-HUS")
        self.assertEqual(short("VinUniversity; Nanyang Technological University"), "VinUni")
        self.assertEqual(short("Ho Chi Minh city University of Science, Vietnam National University"), "HCMUS")
        # look-alikes abroad
        for foreign in ["HUST", "Beijing University of Posts and Telecommunications", "Vinci4D",
                        "UiT The Arctic University of Norway", "Carnegie Mellon University", ""]:
            self.assertIsNone(vn_institution(foreign), foreign)

    def test_same_institution(self):
        person = {"institution": "Hanoi University of Science and Technology", "institution_short": "HUST"}
        self.assertTrue(same_institution("VinUniversity; Hanoi University of Science and Technology", person))
        self.assertFalse(same_institution("VinAI Research", person))
        self.assertFalse(same_institution("", person))

    def test_only_while_in_vietnam(self):
        self.assertFalse(in_vietnam({"vn_since": 2024}, 2023))
        self.assertTrue(in_vietnam({"vn_since": 2024}, 2024))
        self.assertTrue(in_vietnam({"vn_since": None}, 2020))


class Sources(unittest.TestCase):
    def test_bibtex(self):
        self.assertEqual(fetch_accepted.debib(r"Luong, {\DJ}o{\`a}n Minh"), "Luong, Đoàn Minh")
        self.assertEqual(fetch_accepted.debib(r"Nguy{\~{\^e}}n"), "Nguyễn")
        self.assertEqual(fetch_accepted.debib(r"{E}com{S}cript: a \textit{x} \& y"), "EcomScript: a x & y")
        bib = ('@inproceedings{a-2025,\n    title = "A {T}itle",\n    author = {Fosse, Lo{\\"i}c  and\n      Ta, Hoang},\n'
               '    month = jul,\n    url = "https://aclanthology.org/2025.acl-long.1/"\n}\n')
        (paper,) = fetch_accepted.parse_acl_bib(2025, bib)
        self.assertEqual(paper["title"], "A Title")
        self.assertEqual([a["name"] for a in paper["authors"]], ["Loïc Fosse", "Hoang Ta"])
        self.assertEqual(paper["url"], "https://aclanthology.org/2025.acl-long.1/")

    def test_list_without_a_schedule_is_provisional(self):
        paper = {"name": "P", "authors": [{"fullname": "X"}]}
        self.assertTrue(fetch_accepted.is_provisional(json.dumps({"results": [paper]})))
        self.assertFalse(fetch_accepted.is_provisional(json.dumps({"results": [dict(paper, starttime="2025-12-03")]})))
        # a schedule for a few sessions only: the list is still being filled
        partly = [dict(paper, starttime="2026-12-03")] + [paper] * 9
        self.assertTrue(fetch_accepted.is_provisional(json.dumps({"results": partly})))

    def test_virtual_site_listing(self):
        src = "https://openreview.net/group?id=NeurIPS.cc/2025/"
        rows = [
            {"name": "Paper A", "authors": [{"fullname": "X Y", "institution": "VinUniversity"}], "decision": "Accept (poster)",
             "sourceurl": src + "Conference", "event_type": "Poster", "paper_url": "https://openreview.net/forum?id=abc"},
            {"name": "Paper A", "authors": [{"fullname": "X Y", "institution": "VinUniversity"}], "decision": "Accept (oral)",
             "sourceurl": src + "Conference", "event_type": "Oral", "paper_url": ""},
            {"name": "Paper B", "authors": [{"fullname": "X Y", "institution": ""}], "decision": "Accept",
             "sourceurl": src + "Datasets_and_Benchmarks_Track", "event_type": "Poster", "paper_url": ""},
        ]
        papers = fetch_accepted.parse_virtual("neurips", 2025, json.dumps({"results": rows}))
        self.assertEqual(sorted((p["title"], p["track"], p["pres"], p["forum"]) for p in papers),
                         [("Paper A", "main", "oral", "abc"), ("Paper B", "datasets_benchmarks", "", "")])


class FacultyPages(unittest.TestCase):
    faculty = [{"institution_short": "VinUni", "name": "Doan Dang Khoa", "rank": "Assistant Professor"},
               {"institution_short": "VNU-UET", "name": "Tạ Việt Cường", "rank": "Lecturer with PhD"},
               {"institution_short": "HCMUT", "name": "Tran Tuan Anh", "rank": "Lecturer with PhD"}]

    def match(self, forms, institutions):
        m = find_candidates.faculty_match(forms, institutions, self.faculty)
        return (m[0]["name"], m[1]) if m else None

    def test_name_orders_and_initials(self):
        self.assertEqual(self.match(["Khoa D Doan", "Khoa Doan"], {"VinUni"}), ("Doan Dang Khoa", "likely"))
        self.assertEqual(self.match(["Khoa Doan"], {"VinUni"}), ("Doan Dang Khoa", "possible"))
        self.assertEqual(self.match(["Cuong Viet Ta"], {"VNU-UET"}), ("Tạ Việt Cường", "exact"))
        self.assertEqual(self.match(["Cuong Viet Ta"], {"VNU"}), ("Tạ Việt Cường", "exact"))  # VNU is the parent
        self.assertIsNone(self.match(["Khoa X Doan"], {"VinUni"}))  # the initial fits no listed word

    def test_same_name_at_another_university_is_not_matched(self):
        self.assertIsNone(self.match(["Anh T Tran", "Anh Tran"], {"VinAI"}))
        self.assertEqual(self.match(["Anh T Tran"], {"HCMUT"}), ("Tran Tuan Anh", "likely"))


class FakeNote:
    def __init__(self, id, content, forum=None, invitations=None, invitation=None):
        self.id, self.forum, self.content = id, forum or id, content
        if invitations is not None:
            self.invitations = invitations
        if invitation is not None:
            self.invitation = invitation


class OpenReviewFetch(unittest.TestCase):
    """fetch_person against stand-ins shaped like the two OpenReview API versions."""

    def test_fetch_person(self):
        profile = types.SimpleNamespace(id="~A_B1", content={
            "names": [{"fullname": "A B", "username": "~A_B1"}, {"fullname": "B A", "username": "~B_A1"}],
            "history": [{"position": "Lecturer", "start": 2024, "end": None,
                         "institution": {"name": "Hanoi University of Science and Technology", "domain": "hust.edu.vn"}}]})
        v2_notes = [
            FakeNote("f1", {"title": {"value": "New paper"}, "venue": {"value": "Submitted to ICLR 2026"},
                            "venueid": {"value": "ICLR.cc/2026/Conference/Rejected_Submission"},
                            "authors": {"value": ["A B", "C D"]}, "authorids": {"value": ["~A_B1", "~C_D1"]}},
                     invitations=["ICLR.cc/2026/Conference/-/Submission"]),
            FakeNote("r1", {"title": {"value": "a review"}}, forum="f1", invitations=["ICLR.cc/2026/Conference/-/Review"]),
            FakeNote("t1", {"title": {"value": "Journal paper"}, "venue": {"value": "TMLR"}, "venueid": {"value": "TMLR"}},
                     invitations=["TMLR/-/Submission"]),
        ]
        v1_notes = [FakeNote("f0", {"title": "Old paper", "authors": ["B A"], "authorids": ["~B_A1"]},
                             invitation="ICLR.cc/2021/Conference/-/Blind_Submission")]
        decision = FakeNote("d0", {"decision": "Reject"}, forum="f0",
                            invitation="ICLR.cc/2021/Conference/Paper7/-/Decision")
        v2 = types.SimpleNamespace(get_profile=lambda pid: profile,
                                   get_all_notes=lambda content: v2_notes if content["authorids"] == "~A_B1" else [])
        v1 = types.SimpleNamespace(get_all_notes=lambda content=None, forum=None: [decision] if forum else (
            v1_notes if content["authorids"] == "~B_A1" else []))
        person = {"slug": "a-b", "name": "A B", "openreview_ids": ["~A_B1"]}
        data = fetch_openreview.fetch_person(v2, v1, person)

        self.assertEqual(data["profile_ids"], ["~A_B1", "~B_A1"])  # both usernames of the profile are queried
        self.assertEqual(sorted(n["forum"] for n in data["notes"]), ["f0", "f1"])  # review and TMLR paper dropped
        old = next(n for n in data["notes"] if n["forum"] == "f0")
        self.assertEqual(old["decision"], "Reject")  # read from the Decision reply
        self.assertEqual(fetch_openreview.vietnam_post(data["profiles"][0])["position"], "Lecturer")
        json.dumps(data)  # must be serializable as it is


class Counting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raw = Path(self.tmp.name)
        self._saved = build.OPENREVIEW_RAW
        build.OPENREVIEW_RAW = self.raw
        self.addCleanup(setattr, build, "OPENREVIEW_RAW", self._saved)
        self.person = {"slug": "a-b", "name": "A B", "variants": ["a b", "b a"], "vn_since": 2024,
                       "institution": "Hanoi University of Science and Technology", "institution_short": "HUST",
                       "openreview_ids": ["~A_B1"], "to_confirm": ""}
        hust = "Hanoi University of Science and Technology"

        def paper(venue, year, title, aff, track="main", forum="", name="A B", topic="", extra=()):
            return {"venue": venue, "year": year, "track": track, "title": title, "forum": forum, "pres": "",
                    "url": "u", "source": "s", "topic": topic,
                    "authors": [{"name": name, "aff": aff}, {"name": "C D", "aff": "MIT"}, *extra]}

        student = {"name": "E F", "aff": hust}
        vinai = {"name": "G H", "aff": "VinAI Research, Cornell University"}
        self.accepted = [
            paper("iclr", 2025, "Accepted at ICLR", hust, forum="acc1", topic="Deep Learning->Algorithms"),
            paper("icml", 2025, "Own institution", hust, topic="Theory->Learning Theory", extra=[student, vinai]),
            paper("icml", 2025, "Other Vietnamese institution", "VinAI Research"),
            paper("acl", 2025, "No affiliation in source", ""),
            paper("icml", 2025, "Namesake abroad", "Google"),
            paper("neurips", 2025, "A benchmark", hust, track="datasets_benchmarks"),
            paper("icml", 2022, "Before the move", hust),
        ]
        for a in self.accepted[3]["authors"]:  # the ACL Anthology gives names only
            a["aff"] = ""
        coverage = [{"venue": v, "year": y, "papers": 1} for v in common.VENUE_KEYS for y in common.YEARS]
        self.acc = build.Accepted(self.accepted, coverage)

    def records(self, notes, decisions=None):
        (self.raw / "a-b.json").write_text(json.dumps({"notes": notes, "queried_ids": ["~A_B1"],
                                                       "fetched_at": "2026-10-01T00:00:00"}))
        queue, self.warnings, skipped = [], [], []
        recs, source, _, stale = build.person_records(self.person, self.acc, {}, decisions or {}, queue,
                                                      self.warnings, skipped)
        self.assertEqual((source, stale), ("openreview", False))
        counted, excluded = build.apply_rules(self.person, recs)
        return counted, excluded, queue, skipped

    def test_rules(self):
        def note(forum, title, year, venue="", venueid="", decision=""):
            return {"forum": forum, "title": title, "venue": venue, "venueid": venueid, "decision": decision,
                    "invitations": [f"ICLR.cc/{year}/Conference/-/Submission"], "authors": ["A B", "C D"]}

        notes = [
            note("acc1", "Accepted at ICLR", 2025, "ICLR 2025 Poster", "ICLR.cc/2025/Conference"),
            note("rej1", "Rejected at ICLR", 2025, "Submitted to ICLR 2025", "ICLR.cc/2025/Conference/Rejected_Submission"),
            note("wd1", "Withdrawn from ICLR", 2026, "ICLR 2026 Conference Withdrawn Submission",
                 "ICLR.cc/2026/Conference/Withdrawn_Submission"),
            note("old1", "Rejected before the move", 2021, decision="Reject"),
            note("unk1", "No decision on record", 2024),
            {"forum": "ws1", "title": "A workshop paper", "venue": "ICLR 2025 Workshop X Poster", "decision": "",
             "venueid": "ICLR.cc/2025/Workshop/X", "invitations": ["ICLR.cc/2025/Workshop/X/-/Submission"], "authors": []},
        ]
        counted, excluded, queue, skipped = self.records(notes)
        got = {r["title"]: (r["venue"], r["status"]) for r in counted}
        self.assertEqual(got, {
            "Accepted at ICLR": ("iclr", "accepted"),
            "Rejected at ICLR": ("iclr", "rejected"),
            "Withdrawn from ICLR": ("iclr", "withdrawn"),
            "No decision on record": ("iclr", "rejected"),  # inferred, and marked as such
            "Own institution": ("icml", "accepted"),
        })
        self.assertTrue(next(r for r in counted if r["title"] == "No decision on record")["note"])
        self.assertEqual({r["title"] for r in excluded}, {"A benchmark", "Rejected before the move", "Before the move"})
        self.assertTrue(any("check vn_since" in w for w in self.warnings))  # HUST on a 2022 paper, vn_since 2024
        self.assertEqual({q["title"] for q in queue}, {"Other Vietnamese institution", "No affiliation in source"})
        self.assertEqual(len(skipped), 1)  # the namesake at Google is neither counted nor queued

        totals = build.tally(counted)["iclr"]
        self.assertEqual((totals["submitted"], totals["accepted"], totals["not_accepted"]), (4, 1, 3))

    def test_review_answers(self):
        yes = {("a-b", "acl", "2025", common.norm_title("No affiliation in source")): "yes",
               ("a-b", "icml", "2025", common.norm_title("Other Vietnamese institution")): "no"}
        counted, _, queue, _ = self.records([], yes)
        self.assertIn("No affiliation in source", {r["title"] for r in counted})
        self.assertNotIn("Other Vietnamese institution", {r["title"] for r in counted})
        self.assertEqual(queue, [])

    def test_coauthors_and_topics(self):
        counted, _, _, _ = self.records([], {("a-b", "acl", "2025", common.norm_title("No affiliation in source")): "yes"})
        c = build.collaboration(self.person, counted)
        # three accepted papers with 1, 3 and 1 co-authors; the ACL one has no affiliations
        self.assertEqual((c["papers"], c["avg_coauthors"], c["distinct_coauthors"]), (3, "1.7", 3))
        self.assertEqual((c["min_coauthors"], c["max_coauthors"]), (1, 3))
        self.assertEqual((c["papers_with_affiliations"], c["avg_foreign"]), (2, "1.0"))  # only C D at MIT is foreign
        self.assertEqual((c["elsewhere"], c["elsewhere_abroad"], c["elsewhere_vietnam"]), (2, 1, 1))  # C D, G H
        self.assertEqual((c["papers_with_topic"], c["topic_areas"]), (2, 2))

    def own(self, venue, year, title, role="own", track="main", authors=("A B", "C D"), owner="A B"):
        return {"venue": venue, "year": year, "title": title, "track": track, "role": role, "owner": owner,
                "authors": list(authors), "source_url": "https://example.org/page", "label": "their own page"}

    def test_personal_pages(self):
        coverage = [dict(c, provisional=(c["venue"], c["year"]) == ("neurips", 2026)) for c in self.acc.coverage]
        self.accepted.append({"venue": "cvpr", "year": 2026, "track": "main", "title": "Signed with another name",
                              "forum": "", "pres": "", "url": "u", "source": "s", "topic": "",
                              "authors": [{"name": "B. Another", "aff": ""}]})
        self.acc = build.Accepted(self.accepted, coverage)
        (self.raw / "a-b.json").write_text(json.dumps({"notes": [], "queried_ids": ["~A_B1"]}))
        rows = [
            self.own("neurips", 2026, "Announced last week"),            # list not complete yet: counted, unofficial
            self.own("neurips", 2025, "Only on the page"),               # complete list without it: not counted
            self.own("acl", 2025, "No affiliation in source"),           # confirms a name-only match, no review needed
            self.own("cvpr", 2026, "Signed with another name"),          # official paper under an unknown name form
            self.own("neurips", 2026, "With a colleague", role="coauthor", owner="X Y", authors=("X Y", "B A")),
            self.own("cvpr", 2026, "Signed with another name", role="coauthor", owner="X Y"),
            self.own("neurips", 2026, "A dataset", track="datasets_benchmarks"),
        ]
        queue, warnings, skipped = [], [], []
        recs, _, _, _ = build.person_records(self.person, self.acc, {}, {}, queue, warnings, skipped, rows)
        counted, excluded = build.apply_rules(self.person, recs)
        got = {r["title"]: bool(r.get("unofficial")) for r in counted}
        self.assertEqual(got["Announced last week"], True)
        self.assertEqual(got["With a colleague"], True)
        self.assertEqual(got["No affiliation in source"], False)
        self.assertEqual(got["Signed with another name"], False)
        self.assertNotIn("Only on the page", got)
        self.assertTrue(any("Only on the page" in w and "not counted" in w for w in warnings))
        self.assertNotIn("No affiliation in source", {q["title"] for q in queue})  # no longer needs a yes
        self.assertEqual([r["title"] for r in excluded if r.get("unofficial")], ["A dataset"])
        t = build.tally(counted)["neurips"]
        self.assertEqual((t["accepted"], t["official"], t["own_page"]), (2, 0, 2))
        colleague = next(r for r in counted if r["title"] == "With a colleague")
        self.assertIn("page of X Y", colleague["match"])
        self.assertEqual(colleague["self"], 1)                            # 'B A' is a name form of this person

    def test_colleague_page_does_not_settle_an_official_paper(self):
        self.accepted.append({"venue": "cvpr", "year": 2026, "track": "main", "title": "Signed with another name",
                              "forum": "", "pres": "", "url": "u", "source": "s", "topic": "",
                              "authors": [{"name": "B. Another", "aff": ""}]})
        self.acc = build.Accepted(self.accepted, self.acc.coverage)
        (self.raw / "a-b.json").write_text(json.dumps({"notes": [], "queried_ids": ["~A_B1"]}))
        row = self.own("cvpr", 2026, "Signed with another name", role="coauthor", owner="X Y")
        queue, warnings = [], []
        recs, _, _, _ = build.person_records(self.person, self.acc, {}, {}, queue, warnings, [], [row])
        self.assertNotIn("Signed with another name", {r["title"] for r in recs})
        asked = [q for q in queue if q["title"] == "Signed with another name"]
        self.assertEqual(len(asked), 1)
        self.assertIn("named as co-author on the page of X Y", asked[0]["reason"])
        key = ("a-b", "cvpr", "2026", common.norm_title("Signed with another name"))
        recs, _, _, _ = build.person_records(self.person, self.acc, {}, {key: "yes"}, [], [], [], [row])
        self.assertIn("Signed with another name", {r["title"] for r in recs})

    def test_unknown_start_year_does_not_pull_in_papers_from_abroad(self):
        newcomer = dict(self.person, vn_since=None)
        (self.raw / "a-b.json").write_text(json.dumps({"notes": [], "queried_ids": ["~A_B1"]}))
        rows = [self.own("icml", 2025, "Namesake abroad")]               # the official list shows A B at Google
        warnings, skipped = [], []
        recs, _, _, _ = build.person_records(newcomer, self.acc, {}, {}, [], warnings, skipped, rows)
        self.assertNotIn("Namesake abroad", {r["title"] for r in recs})
        settled = dict(self.person, vn_since=2024)                        # with a start year the year rule decides
        recs, _, _, _ = build.person_records(settled, self.acc, {}, {}, [], [], [], rows)
        self.assertIn("Namesake abroad", {r["title"] for r in recs})

    def test_paper_in_the_record_of_a_colleague(self):
        colleague = dict(self.person, slug="c-d", name="C D", variants=["c d"], openreview_ids=["~C_D1"])
        note = {"forum": "w1", "title": "Withdrawn together", "venue": "ICLR 2026 Conference Withdrawn Submission",
                "venueid": "ICLR.cc/2026/Conference/Withdrawn_Submission", "decision": "",
                "invitations": ["ICLR.cc/2026/Conference/-/Submission"], "authors": ["C D", "A B"],
                "authorids": ["~C_D1", "~A_B1"]}
        (self.raw / "c-d.json").write_text(json.dumps({"notes": [note], "queried_ids": ["~C_D1"],
                                                       "profile_ids": ["~C_D1"]}))
        # the submission carries this person's profile ID: counted without asking
        shared = build.shared_notes([self.person, colleague], {})
        self.assertEqual([(b["owner"], b["exact"]) for b in shared["a-b"]], [("C D", True)])
        recs, source, _, _ = build.person_records(self.person, self.acc, {}, {}, [], [], [], (), shared["a-b"])
        self.assertEqual([(r["title"], r["status"], r["borrowed"]) for r in recs if r["venue"] == "iclr"
                          and r["year"] == 2026], [("Withdrawn together", "withdrawn", True)])
        self.assertEqual(source, "none")

        # a different profile ID under the same name is somebody else
        other = dict(self.person, openreview_ids=["~A_B9"])
        self.assertEqual(build.shared_notes([other, colleague], {})["a-b"], [])

        # no profile ID known for this person: the name alone waits for a yes
        unknown = dict(self.person, openreview_ids=[])
        shared = build.shared_notes([unknown, colleague], {})
        self.assertEqual([b["exact"] for b in shared["a-b"]], [False])
        queue = []
        recs, _, _, _ = build.person_records(unknown, self.acc, {}, {}, queue, [], [], (), shared["a-b"])
        self.assertNotIn("Withdrawn together", {r["title"] for r in recs})
        self.assertIn("Withdrawn together", {q["title"] for q in queue})
        yes = {("a-b", "iclr", "2026", common.norm_title("Withdrawn together")): "yes"}
        recs, _, _, _ = build.person_records(unknown, self.acc, {}, yes, [], [], [], (), shared["a-b"])
        self.assertIn("Withdrawn together", {r["title"] for r in recs})

    def test_stricter_institution_counts(self):
        hust = {"institution": "Hanoi University of Science and Technology", "institution_short": "HUST"}
        def rec(title, affs, status="accepted"):
            return {"venue": "icml", "year": 2025, "title": title, "status": status,
                    "people": [{"name": f"P{i}", "aff": a} for i, a in enumerate(affs)]}
        h = hust["institution"]
        a = build.authorship([rec("mostly", [h, h, "MIT"]), rec("half", [h, "MIT"]), rec("first only", [h, "MIT", "MIT"]),
                              rec("last only", ["MIT", "MIT", h]), rec("no affiliations", ["", ""]),
                              rec("rejected", [h, h], "rejected")], hust)
        self.assertEqual((a["majority"]["total"], a["first_author"]["total"], a["judged"], a["unknown"]), (1, 3, 4, 1))
        self.assertEqual(a["majority"]["venues"]["icml"], 1)

    def test_blog_figures(self):
        import charts
        svg = charts.pies("x", [("ICLR", [("s1", "accepted", 6), ("not", "rejected", 29)])])
        self.assertEqual((svg.count("<path"), "6 (17%)" in svg, "29 (83%)" in svg), (2, True, True))
        svg = charts.stacked_rows("x", [("A B", [1, 0, 2.5]), ("C D", [0, 0, 0])], [("s1", "a"), ("s2", "b"), ("s3", "c")])
        self.assertEqual(svg.count("<path"), 2)
        self.assertIn(">3.5<", svg)
        svg = charts.lines("x", [2025, 2026], [("v1", "ICLR", [1, 3]), ("v2", "ACL", [0, 2])])
        self.assertEqual((svg.count("<polyline"), svg.count("<circle"), "ACL 2026: 2" in svg), (2, 4, True))

    def test_one_coauthor_under_two_spellings(self):
        keys = build.distinct_people(["Bui T Duc", "Bui Trong Duc", "Duc Bui Trong", "Bui Van Duc", "Khoa D. Doan",
                                      "Doan Khoa"])
        self.assertEqual(keys["Bui T Duc"], keys["Bui Trong Duc"])      # an initial stands for the full word
        self.assertEqual(keys["Bui Trong Duc"], keys["Duc Bui Trong"])  # word order does not matter
        self.assertNotEqual(keys["Bui Trong Duc"], keys["Bui Van Duc"])
        self.assertEqual(keys["Khoa D. Doan"], keys["Doan Khoa"])

    def test_same_paper_with_a_changed_title(self):
        self.assertTrue(build.same_paper("UniCon: unified framework for contrastive multimodal alignment",
                                         "UniCon: Unified Framework for Efficient Contrastive Alignment via Kernels"))
        self.assertFalse(build.same_paper("A study of X", "A study of Y and much more besides, really"))

    def test_self_reported_file(self):
        path = self.raw / "self_reported.csv"
        path.write_text("professor,venue,year,title,track,coauthors,announced,source_url,fetched,note\n"
                        "c-d,neurips,2026,Joint paper,,A B; E F,,https://example.org,2026-09-30,\n"
                        "c-d,neurips,2026,,,,5,https://example.org,2026-09-30,five papers\n", encoding="utf-8")
        saved, build.SELF_REPORTED = build.SELF_REPORTED, path
        self.addCleanup(setattr, build, "SELF_REPORTED", saved)
        roster = [dict(self.person, approved="yes"),
                  {"slug": "c-d", "name": "C D", "variants": ["c d"], "approved": "yes"}]
        papers, announced = build.load_self_reported(roster)
        self.assertEqual([(r["role"], r["track"], r["year"]) for r in papers["c-d"]], [("own", "main", 2026)])
        self.assertEqual([(r["role"], r["owner"]) for r in papers["a-b"]], [("coauthor", "C D")])  # named on C D's page
        self.assertEqual(announced["c-d"][("neurips", 2026)]["announced"], "5")

    def test_later_acceptance(self):
        self.accepted.append({"venue": "neurips", "year": 2026, "track": "main", "title": "Twice Submitted", "forum": "",
                              "pres": "", "url": "u", "source": "s", "topic": "",
                              "authors": [{"name": "A B", "aff": self.person["institution"]}]})
        self.acc = build.Accepted(self.accepted, self.acc.coverage)
        notes = [{"forum": "r1", "title": "Twice submitted", "venue": "Submitted to ICLR 2026", "decision": "",
                  "venueid": "ICLR.cc/2026/Conference/Rejected_Submission", "authors": [],
                  "invitations": ["ICLR.cc/2026/Conference/-/Submission"]},
                 {"forum": "r2", "title": "Never seen again", "venue": "Submitted to ICLR 2026", "decision": "",
                  "venueid": "ICLR.cc/2026/Conference/Rejected_Submission", "authors": [],
                  "invitations": ["ICLR.cc/2026/Conference/-/Submission"]}]
        counted, _, _, _ = self.records(notes)
        build.mark_later_acceptance(counted, self.acc)
        later = {r["title"]: r["later"] for r in counted if r["status"] == "rejected"}
        self.assertEqual(later, {"Twice submitted": "NeurIPS 2026", "Never seen again": ""})

    def test_projection(self):
        def year(y, accepted, iclr_accepted, iclr_not, counts=True):
            v = {k: {"accepted": 0, "not_accepted": 0} for k in common.VENUE_KEYS}
            v["iclr"] = {"accepted": iclr_accepted, "not_accepted": iclr_not}
            return {"year": y, "counts": counts, "accepted": accepted, "venues": v}

        prof = {"name": "A B", "iclr_complete": True, "venues": {"iclr": {"submitted": 9, "accepted": 1}},
                "years": [year(2023, 5, 0, 0, counts=False), year(2024, 2, 0, 2), year(2025, 3, 1, 2)]}
        p = build.projection(prof)
        self.assertEqual((p["basis"], p["ratio"]), ("own", "5.0"))  # (9 + 1) / (1 + 1)
        # 2024: 2 accepted elsewhere stand for 2 x 4 = 8 papers that were not accepted, plus 2 known at ICLR
        self.assertEqual([(r["estimated"], r["total"]) for r in p["rows"] if r["counts"]], [("8", "12"), ("8", "13")])
        self.assertFalse(p["rows"][0]["counts"])  # a year before the move to Vietnam is left out
        self.assertIn("<svg", p["svg"])
        self.assertIn("2024: 2 accepted", p["svg"])

        none_accepted = dict(prof, venues={"iclr": {"submitted": 2, "accepted": 0}})
        self.assertEqual(build.projection(none_accepted)["ratio"], "3.0")  # stays finite without an acceptance
        no_iclr = dict(prof, venues={"iclr": {"submitted": 0, "accepted": 0}},
                       years=[year(2024, 2, 0, 0), year(2025, 3, 0, 0)])
        p = build.projection(no_iclr)  # no ICLR papers at all: nothing is added
        self.assertEqual((p["basis"], p["ratio"], p["estimated"], p["total"]), ("none", "1.0", "0", "5"))
        unknown = dict(prof, iclr_complete=False)  # OpenReview record not fetched: nothing is added either
        self.assertEqual(build.projection(unknown)["estimated"], "0")

    def test_accepted_list_overrides_a_misread_label(self):
        notes = [{"forum": "acc1", "title": "Accepted at ICLR", "venue": "Submitted to ICLR 2025", "venueid": "",
                  "decision": "", "invitations": ["ICLR.cc/2025/Conference/-/Submission"], "authors": []}]
        counted, _, _, _ = self.records(notes)
        self.assertEqual([r["status"] for r in counted if r["title"] == "Accepted at ICLR"], ["accepted"])


if __name__ == "__main__":
    unittest.main()
