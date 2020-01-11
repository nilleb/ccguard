# code coverage

## monolith: compute code coverage on search, eventstream, mlearning

```sh
pipenv shell
pytest server/search server/eventstream --cov=server/search --cov=server/eventstream --cov=server/mlearning
```

## idea

compute the code coverage
define a format to express code coverage

- json
- xml

deserialize the code coverage information

for each mesurable object in the challenger,

- compute the path
- read the coverage value
- save both to a dictionary

for each mesurable object in the reference,

- compute the path
- read the coverage value
- get the corresponding value in the challenger

- if the value does not exist, then we have no coverage for this item
  - has it been deleted?
  - has it been excluded from coverage?
- else (if the value exists)
  - v(challenger) >= v(reference) => OK
  - v(challenger) < v(reference) => NOK (raise an exception)

display the relative variation in code coverage

cnbR, cnbC = cumulated number of blocks in the reference/challenger
covcnbR, covcnbC = cumulated number of covered blocks in the reference/challenger

compute the diff blocks
deleted blocks improve the code coverage
added blocks shall be considered in regard of their code coverage
given a code coverage threshold, added blocks shall at least present this CC threshold

## about the git history

### table schema: timestamped_coverage_{repository_id}

commit_id | collected_at | coverage_data

commit id is a string, max length equal to the commit id length
coverage data is a blob

```SQL
create database if not exists `ccguard`;

USE `ccguard`;

SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;

CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}` (
  `commit_id` varchar(40) NOT NULL,
  `collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `coverage_data` BLOB NOT NULL default '',
   PRIMARY KEY  (`commit_id`)
);
```


### get the repository ID

```py
repositoryID = get_output("git rev-list --max-parents=0 HEAD")
```

### get the last 100 commit IDs

```py
commits = get_output("git rev-list --max-count=100 HEAD").split("\n")
```

### get the next 100 commits

```py
commits = get_output("git rev-list --skip=100 --max-count=100 HEAD").split("\n")
```

### is there any data in the database

```SQL
SELECT commit_id FROM timestamped_coverage_{repository_id}
```

### get the commits for which the code coverage is present

```SQL
SELECT commit_id FROM timestamped_coverage_{repository_id}
WHERE commit_id IN ({commits})
```

use a set to store the returned IDs
now read the commits list in order and get the first one in the set

if no data is available, repeat with the next 100 commits

```py
import shlex
import subprocess
import sqlite3

conn = sqlite3.connect('ccguard.db')

def get_output(command, working_folder=None):
    try:
        return subprocess.check_output(shlex.split(command), cwd=working_folder)
    except OSError:
        print('Command being executed: {}'.format(command))
        raise

def get_repository_id(repository_folder=None):
    return get_output("git rev-list --max-parents=0 HEAD", working_folder=repository_folder).trim()

def iter_git_commits(repository_folder=None):
    count = 0
    while commits:
        skip = "--skip={}".format(100 * count) if count else ""
        command = "git rev-list {} --max-count=100 HEAD".format(skip)
        commits = get_output(command, working_folder=repository_folder).split("\n")
        yield commits

def get_cc_commits(repository_id):
    commits_query = "SELECT commit_id FROM timestamped_coverage_{repository_id}".format(repository_id=repository_id)
    return set(conn.execute(commits_query))

def get_cc_data(repository_id, commit_id):
    query = 'SELECT coverage_data FROM timestamped_coverage_{repository_id}' +
            'WHERE commit_id="{}"'.format(repository_id=repository_id, commit_id=commit_id)
    return conn.execute(query)

def create_table(repository_id):
    ddl = """create database if not exists `ccguard`;

USE `ccguard`;

SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;

CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}` (
  `commit_id` varchar(40) NOT NULL,
  `collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `coverage_data` BLOB NOT NULL default '',
   PRIMARY KEY  (`commit_id`)
);
    """
    statement = ddl.format(repository_id)
    conn.execute(statement)

def determine_parent_commit(iter_callable):
    for commits_chunk in iter_callable():
            for commit in commits_chunk:
                if commit in db_commits:
                    return commit

def main():
    repository_id = get_repository_id(".")
    create_table(repository_id)
    db_commits = yield get_cc_commits()
    most_recent_commit_with_data = None
    commit_id = determine_parent_commit(iter_git_commits)
    cc_reference_data = get_cc_data(repository_id, commit_id)

```
