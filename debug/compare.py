import sys
from ccguard import has_better_coverage

from pycobertura import Cobertura, CoberturaDiff

reference = Cobertura(sys.argv[0])
challenger = Cobertura(sys.argv[1])
reference.line_rate()
challenger.line_rate()
diff = CoberturaDiff(reference, challenger)

for filename in diff.files():
    print("{}: {}".format(filename, diff.diff_total_misses(filename)))
    print(diff.cobertura1.missed_statements(filename))
    print(diff.cobertura2.missed_statements(filename))
