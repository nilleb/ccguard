# bash ccguard test plan

- [ ] Test the ccguard-server choose method (POST "/api/v1/references/<string:repository_id>/choose")
- [ ] Test the ccguard-server comparison method (GET "/api/v1/references/<string:repository_id>/<string:commit_id1>..<string:commit_id2>/comparison")
- [ ] test the ccguard.sh script
  - target branch
  - file
  - tolerance
  - hard-minimum
