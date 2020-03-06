# this script is supposed to be executed in a CI workflow
# PARAMETERS
base_branch=${GITHUB_PR_BASE_BRANCH:-origin/master}
coverage_xml=${COVERAGE_XML:-coverage.xml}
tolerance=${ccguard_tolerance:-0}
hard_minimum=${ccguard_hard_minimum:-0}
ccguard_server_address=${ccguard_server_address:-http://localhost:5000}

while [ "$1" != "" ]; do
    case $1 in
        -t | --target-branch )  shift
                                base_branch=$1
                                ;;
        -f | --file )           shift
                                coverage_xml=$1
                                ;;
        -t | --tolerance )      shift
                                tolerance=$1
                                ;;
        -hm | --hard_minimum )  shift
                                hard_minimum=$1
                                ;;
        * )                     coverage_xml=$1
                                ;;
    esac
    shift
done


# MAIN LOGIC
repository_id=`git rev-list --max-parents=0 HEAD`
commit_id=`git rev-parse HEAD`
common_ancestor=`git merge-base ${base_branch} HEAD`
git rev-list ${common_ancestor} --max-count=100 > refs.txt

curl -d @${coverage_xml} -H "Content-Type: application/xml" -X PUT ${ccguard_server_address}/api/v1/references/${repository_id}/${commit_id}/data -H "authorization: ${ccguard_token}"
http_status=`curl --data-binary @refs.txt -H "Content-Type: text/plain" -X POST ${ccguard_server_address}/api/v1/references/${repository_id}/choose -o ref.txt -s -w "%{http_code}\n"`
if [[ $http_status == "200" ]]; then
    ref=`cat ref.txt`
    status = `curl -X GET ${ccguard_server_address}/api/v1/references/${repository_id}/${ref}/${commit_id}/compare?tolerance=${tolerance}&hard_minimum=${hard_minimum}`
    exit status
fi
