import re
import os
import time
import argparse
from collections import defaultdict
import lxml.etree as ET
from lxml import objectify
import ccguard
from pycobertura import Cobertura
from pycobertura.reporters import HtmlReporter


def convert_golang_report(report, log_function=print):
    # name.go:line.column,line.column numberOfStatements count

    pattern = (
        r"(?P<filename>.+):(?P<line_begins>[0-9]+)"
        r"\.(?P<column_begins>[0-9]+),(?P<line_ends>[0-9]+)"
        r"\.(?P<column_ends>[0-9]+) (?P<number_statements>[0-9]+) "
        r"(?P<count>[0-9]+)"
    )
    pattern = re.compile(pattern)

    files = defaultdict(lambda: defaultdict(int))
    with open(report) as report_fd:
        for line in report_fd:
            match = pattern.match(line)
            if not match:
                continue

            filename = match.group("filename")
            line_begins = int(match.group("line_begins"))
            # column_begins = match.group("column_begins")
            line_ends = int(match.group("line_ends"))
            # column_ends = match.group("column_ends")
            # number_statements = match.group("number_statements")
            count = int(match.group("count"))

            for lineno in range(line_begins, line_ends):
                files[filename][lineno] = max(count, files[filename][lineno])

    covered, total = 0, 0
    file_coverage = defaultdict(float)
    packages = defaultdict(list)
    packages_coverage = defaultdict(lambda: (0, 0, 0.0))
    for filename, lines in files.items():
        packages[os.path.dirname(filename)].append(filename)
        file_covered_lines = len([line for line, count in lines.items() if count])
        file_total_lines = float(len(lines))
        file_rate = file_covered_lines / file_total_lines
        file_coverage[filename] = file_rate
        covered += file_covered_lines
        total += len(lines)
        package_name = os.path.dirname(filename)
        prev_cov, prev_total, prev_rate = packages_coverage[package_name]
        packages_coverage[package_name] = (
            prev_cov + file_covered_lines,
            prev_total + file_total_lines,
            prev_rate + file_rate,
        )

    for filename, rate in file_coverage.items():
        log_function("- {:5.2f} {}".format(rate, filename))

    rate = covered / float(total) if total else 0.0
    log_function(
        "Lines covered/total (rate): {}/{} ({:5.2f})".format(covered, total, rate)
    )

    return (
        report,
        rate,
        covered,
        total,
        packages,
        packages_coverage,
        files,
        file_coverage,
    )


def serialize(
    report, rate, covered, total, packages, packages_coverage, files, file_coverage
):
    coverage = objectify.Element("coverage")
    coverage.set("branch-rate", "0")
    coverage.set("branches-covered", "0")
    coverage.set("branches-valid", "0")

    coverage.set("line-rate", str(rate))
    coverage.set("lines-covered", str(covered))
    coverage.set("lines-valid", str(total))
    coverage.set("timestamp", str(time.time()))
    coverage.set("version", "5.0.3")

    packages_elem = objectify.Element("packages")

    for package, filenames in packages.items():
        package_elem = objectify.Element("package")
        package_elem.set("name", package)
        package_elem.set("line-rate", str(packages_coverage[package][2]))
        package_elem.set("branch-rate", str(0))
        package_elem.set("complexity", str(0))
        classes_elem = objectify.Element("classes")
        for filename in filenames:
            class_elem = objectify.Element("class")
            class_elem.set("filename", filename)
            class_elem.set("name", os.path.basename(filename))
            class_elem.set("line-rate", str(file_coverage[filename]))
            class_elem.set("branch-rate", str(0))
            class_elem.set("complexity", str(0))
            lines_elem = objectify.Element("lines")
            for lineno, hits in files[filename].items():
                line_elem = objectify.Element("line")
                line_elem.set("number", str(lineno))
                line_elem.set("hits", str(hits))
                lines_elem.append(line_elem)
            class_elem.append(lines_elem)
            classes_elem.append(class_elem)

        package_elem.append(classes_elem)
        packages_elem.append(package_elem)

    coverage.append(packages_elem)

    source_elem = objectify.Element("source")
    source_elem["text"] = os.path.dirname(report)
    sources_elem = objectify.Element("sources")
    sources_elem.append(source_elem)
    coverage.append(sources_elem)

    objectify.deannotate(coverage, cleanup_namespaces=True, xsi_nil=True)
    return coverage


def write(dest, what):
    mode = "w" if isinstance(what, str) else "wb"
    with open(dest, mode) as fd:
        fd.write(what)

    print("The output has been written to {}".format(dest))


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Convert the input report to cobertura."
    )

    parser.add_argument(
        "report", help="The report to convert",
    )

    parser.add_argument(
        "-if",
        "--input-format",
        dest="input_format",
        help="The format of the input report. (Supported: go)",
    )

    parser.add_argument(
        "-of",
        "--output-format",
        dest="output_format",
        help="The format of the input report. (Supported: xml, html)",
        default="xml",
    )

    parser.add_argument(
        "-o", "--output", dest="output", help="The output file name (default: stdout)"
    )

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    xml = None
    if args.input_format == "go":
        xml = serialize(*convert_golang_report(args.report))
    if args.input_format == "xml":
        xml = ET.parse(args.report).getroot()
    if xml is None:
        print("fatal: nothing to do")
        return
    if args.output_format == "xml":
        if not args.output:
            print(ET.tostring(xml, pretty_print=True))
        else:
            write(args.output, ET.tostring(xml, pretty_print=True))
    elif args.output_format == "html":
        source = ccguard.GitAdapter(os.path.dirname(args.report) or ".").get_root_path()
        challenger = Cobertura(args.report, source=source)
        report = HtmlReporter(challenger)
        if not args.output:
            print(report.generate())
        else:
            write(args.output, report.generate())


if __name__ == "__main__":
    main()
