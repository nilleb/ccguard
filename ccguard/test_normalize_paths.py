import io
from lxml import etree as ET
from .ccguard import normalize_report_paths, GitAdapter

REPOSITORY = "."
REPORT = "ccguard/test_data/paths.xml"


def test_relativize_same_machine():
    with open(REPORT, "rb") as report_fd:
        report = io.BytesIO(report_fd.read())

    sources = GitAdapter(REPOSITORY).get_root_path()

    tree = ET.parse(report)
    xml = tree.getroot()
    sources_node = xml.xpath("/coverage/sources/source")[0]
    sources_node.text = "{}/ccguard".format(sources)
    report.truncate(0)
    tree.write(report)
    report.seek(0, 0)

    assert report

    xml = normalize_report_paths(report, sources).getroot()

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


def test_relativize_other_machine():
    with open(REPORT, "rb") as report_fd:
        report = io.BytesIO(report_fd.read())

    sources = GitAdapter(REPOSITORY).get_root_path()

    tree = ET.parse(report)
    xml = tree.getroot()
    sources_node = xml.xpath("/coverage/sources/source")[0]
    sources_node.text = "/usr/local/sources/ccguard/ccguard".format(sources)
    report.truncate(0)
    tree.write(report)
    report.seek(0, 0)

    xml = normalize_report_paths(report, sources).getroot()

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
