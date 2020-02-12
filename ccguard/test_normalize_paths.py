import io
from .ccguard import normalize_report_paths, GitAdapter

REPOSITORY = "."
REPORT = "ccguard/test_data/paths.xml"


def test_relativize():
    with open(REPORT, "rb") as report_fd:
        report = io.BytesIO(report_fd.read())
    sources = GitAdapter(REPOSITORY).get_root_path()

    xml = normalize_report_paths(report, sources)

    ccsource = xml.xpath('/coverage/sources/source[@class="ccguard-meta-sources-root"]')
    # a <source>, with a particular class has been added
    assert ccsource
    # the <source> element has the repository root as value
    assert sources in ccsource[0].text

    filenames = xml.xpath("packages/package/classes/class/@filename")

    # even "gone" files appear in the report
    assert len(filenames) == 3

    for filename in filenames:
        # paths are now all relative
        assert filename.startswith("ccguard/")
