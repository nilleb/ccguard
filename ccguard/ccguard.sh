#!/bin/bash

# this script is supposed to be executed in a CI workflow

# Usage
#
# debug=True ccguard_token=aaaa ccguard_server_address=http://localhost:8910 ccguard.sh coverage.xml --hard-minimum 70 --tolerance 5 --target production

# ARGUMENTS PARSING
debug=${debug:-False}
base_branch=${GITHUB_PR_BASE_BRANCH:-origin/master}
coverage_xml=${COVERAGE_XML:-coverage.xml}
tolerance=${ccguard_tolerance:-0}
hard_minimum=${ccguard_hard_minimum:-0}
ccguard_server_address=${ccguard_server_address:-http://localhost:5000}

while [ "$1" != "" ]; do
    case $1 in
        --target-branch )       shift
                                base_branch=$1
                                ;;
        --tolerance )           shift
                                tolerance=$1
                                ;;
        --hard-minimum )        shift
                                hard_minimum=$1
                                ;;
        * )                     coverage_xml=$1
                                ;;
    esac
    shift
done

# ARGUMENTS VALIDATION
if [[ ! -f "$coverage_xml" ]]; then
    echo "fatal: $coverage_xml does not exist"
    exit 255
else
    echo "Processing $coverage_xml..."
fi

# MAIN LOGIC
repository_id=`git rev-list --max-parents=0 HEAD`
commit_id=`git rev-parse HEAD`
common_ancestor=`git merge-base ${base_branch} HEAD`
git rev-list ${common_ancestor} --max-count=100 > refs.txt

echo "Current commit ID: $commit_id"
echo "Common ancestor: $common_ancestor"

set -eu

## Upload current commit data
upload_url=${ccguard_server_address}/api/v1/references/${repository_id}/${commit_id}/data

if [[ $debug == "True" ]]; then
    echo "curl -T ${coverage_xml} -H \"Content-Type: application/xml\" -X PUT $upload_url -H \"authorization: ${ccguard_token}\""
fi

curl -s -T ${coverage_xml} -H "Content-Type: application/xml" -X PUT $upload_url -H "authorization: ${ccguard_token}"
echo ""
echo "successfully uploaded reference"

## Ask the server to choose the best reference given the local history
choose_url=${ccguard_server_address}/api/v1/references/${repository_id}/choose

if [[ $debug == "True" ]]; then
    echo "curl --data-binary @refs.txt -H \"Content-Type: text/plain\" -X POST $choose_url -o /tmp/ccguard-ref.txt -s -w \"%{http_code}\n\""
fi;

http_status=`curl --data-binary @refs.txt -H "Content-Type: text/plain" -X POST $choose_url -o /tmp/ccguard-ref.txt -s -w "%{http_code}\n"`

if [[ $http_status != "200" ]]; then
    echo "warning: no upstream reference matches common ancestor history."
    exit 0
fi

ref=`cat /tmp/ccguard-ref.txt`
rm /tmp/ccguard-ref.txt

if [[ $ref == $commit_id ]]; then
    echo "exiting: already on the latest reference"
    exit 0
fi

## Ask the server to compare the current coverage data to the reference
comparison_url="${ccguard_server_address}/api/v1/references/${repository_id}/${ref}..${commit_id}/comparison?tolerance=${tolerance}&hard_minimum=${hard_minimum}"

if [[ $debug == "True" ]]; then
    echo $ref
    echo "curl -X GET $comparison_url -o /tmp/ccguard-comparison.txt -s -w \"%{http_code}\n\""
fi

http_status=`curl -X GET $comparison_url -o /tmp/ccguard-comparison.txt -s -w "%{http_code}\n"`

if [[ $http_status != "200" ]]; then
    echo "fatal: term in comparison $ref..$commit_id not found"
    exit 255
fi

status=`cat /tmp/ccguard-comparison.txt`

if [[ "$status" -gt "0" ]]; then
    echo "fatal: the code coverage has not improved."
else
    echo "Congratulations! You have improved the code coverage!"
fi

rm /tmp/ccguard-comparison.txt

exit $status
