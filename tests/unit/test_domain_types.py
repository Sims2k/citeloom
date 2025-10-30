from src.domain.types import ProjectId, CiteKey, PageSpan, SectionPath


def test_project_id_value():
    p = ProjectId("citeloom/clean-arch")
    assert p.value == "citeloom/clean-arch"


def test_citekey_value():
    c = CiteKey("clean-arch-2025")
    assert c.value == "clean-arch-2025"


def test_pagespan_optional():
    s1 = PageSpan((1, 3))
    s2 = PageSpan(None)
    assert s1.value == (1, 3)
    assert s2.value is None


def test_section_path_sequence():
    sp = SectionPath(["Intro", "Scope"])
    assert list(sp.parts) == ["Intro", "Scope"]
