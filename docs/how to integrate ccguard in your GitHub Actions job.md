# How to integrate ccguard in your CircleCI job

## Limitations

At the moment, [CircleCI does not expose the base branch of the PR being processed](https://ideas.circleci.com/ideas/CCI-I-894).
ccguard assumes then that the base branch is `origin/master`, and determines which reference to use on the base of the common history between `HEAD` and `origin/master`.
As pointed out by a comment on the Idea, a transitory solution would be to use [this orb](https://github.com/NarrativeScience/circleci-orb-ghpr), specifying `--target-branch ${GITHUB_PR_BASE_BRANCH:-origin/master}`. The two sample workflows include it.
Otherwise, you could adopt a more aggressive behavior `--target-branch HEAD` that compares the current CC to the previous commit.

## Common

Set two environment variables

```sh
# the public address of your ccguard server
ccguard_server_address=https://ccguard.your.domain
# you should have setup this same token when preparing ccguard_server
ccguard_token=azoudcodbqzypfuazêofvpzkecnaio
```

## python 3 workflow

```yaml
      - name: Upload coverage
        run: |
          git fetch --prune --unshallow
          ccguard --debug --html coverage.xml --adapter web --target-branch origin/${{ github.base_ref }} --branch {{ github.ref }}

        env:
          ccguard_server_address: ${{ secrets.ccguard_server_address }}
          ccguard_token: ${{ secrets.ccguard_token }}

      - uses: actions/upload-artifact@v1
        with:
          name: coverage-html
          path: cc.html

      - uses: actions/upload-artifact@v1
        continue-on-error: true
        with:
          name: coverage-diff-html
          path: diff.html
```

## _I don't want install python3_ workflow

```yaml
      - name: Upload coverage
        run: |
          curl https://raw.githubusercontent.com/nilleb/ccguard/master/ccguard/ccguard.sh -o ccguard.sh
          bash ccguard.sh coverage.xml

        env:
          ccguard_server_address: ${{ secrets.ccguard_server_address }}
          ccguard_token: ${{ secrets.ccguard_token }}
```
