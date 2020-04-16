import os
import lxml.etree as ET
from ccguard import ccguard_convert


def test_convert_go_xml():
    path = "ccguard/test_data/convert/go-coverage.txt"
    outpath = "{}.xml".format(os.path.splitext(path)[0])
    ccguard_convert.main([path, "-if", "go", "-of", "xml", "-o", outpath])
    assert os.path.exists(outpath)
    xml = ET.parse(outpath).getroot()
    assert float(xml.get("line-rate"))


def test_exclusions():
    path = "ccguard/test_data/convert/go-coverage.txt"
    (
        report,
        rate,
        covered,
        total,
        packages,
        packages_coverage,
        files,
        file_coverage,
    ) = ccguard_convert.convert_golang_report(
        path, config={"convert.exclusions.go": ["**/config/default.go"]}
    )
    assert not [fp for fp in files if "default.go" in fp]
