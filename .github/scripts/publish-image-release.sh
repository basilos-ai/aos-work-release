#!/usr/bin/env bash
set -euo pipefail
case "$COMPONENT" in
  workbench-backend) key=WORKBENCH_VERSION ;;
  workbench-frontend) key=WORKBENCH_FRONTEND_VERSION ;;
  workbench-runtime) key=RUNTIME_VERSION ;;
  *) exit 2 ;;
esac
[[ "$IMAGE_TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ && "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ && "$SOURCE_RUN" =~ ^[0-9]+$ ]]
case "${IMAGE_TAG,,}" in latest|dev) exit 2 ;; esac
export GH_REPO=basilos-ai/aos-work-release
root=$PWD
# A compare-and-swap ref serializes publishers running in different repositories.
lock_ref=refs/heads/automation/image-release-lock
owner=$(git -c user.name=github-actions -c user.email=github-actions@users.noreply.github.com \
  commit-tree HEAD^{tree} -p HEAD -m "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$SOURCE_RUN attempt $GITHUB_RUN_ATTEMPT")
release_lock() {
  git push --force-with-lease="$lock_ref:$owner" origin ":$lock_ref"
}
deadline=$((SECONDS + 600))
until git push --force-with-lease="$lock_ref:" origin "$owner:$lock_ref"; do
  # Retry contention only. Authentication and transport errors must surface.
  git ls-remote --exit-code origin "$lock_ref" >/dev/null || exit 1
  (( SECONDS < deadline )) || { echo 'Timed out waiting for release lock' >&2; exit 1; }
  sleep 5
done
trap release_lock EXIT
trap 'exit 1' TERM INT
work=$(mktemp -d)
previous=$work/previous
out=$work/output
mkdir "$previous"
gh api "repos/$GH_REPO/releases/latest" > "$previous/release.json"
base=$(jq -er .tag_name "$previous/release.json")
[[ "$base" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$ ]]
git fetch --tags origin
event="Image build: $COMPONENT/$SOURCE_RUN $SOURCE_SHA $IMAGE_TAG"
if git log -1 --format=%H --fixed-strings --grep="$event" "refs/tags/$base" | grep -q .; then
  echo "This build is already included in $base."
  exit 0
fi
current=$(git show "refs/tags/$base:.env.workbench" | sed -n "s/^$key=//p")
if [[ "$current" == "$IMAGE_TAG" ]]; then echo "$COMPONENT already uses $IMAGE_TAG."; exit 0; fi
# Dispatch runs may reach the shared queue out of order. Keep the newer build of this component.
last_run=$(git log -1 --format=%s --grep="^Image build: $COMPONENT/" "refs/tags/$base" | sed -E 's@^Image build: [^/]+/([0-9]+) .*@\1@')
if [[ -n "$last_run" ]] && (( 10#$last_run > 10#$SOURCE_RUN )); then echo 'Superseded by a newer build.'; exit 0; fi

# Reuse an unpublished tag left by an interrupted upload if its parent is still the latest release.
tag=
while read -r candidate; do
  [[ -n "$candidate" && "$(git show -s --format=%s "$candidate")" == "$event" ]] || continue
  if [[ "$(git rev-parse "$candidate^")" == "$(git rev-parse "$base^{commit}")" ]]; then tag=$candidate; break; fi
done < <(git tag --list 'v20*' --sort=-v:refname)
if [[ -z "$tag" ]]; then
  day=$(TZ=Asia/Shanghai date +v%Y.%m.%d)
  tag=$day
  i=0
  while git show-ref --verify --quiet "refs/tags/$tag"; do i=$((i+1)); tag=$day.$i; done
fi
# Refuse unrecognized attachment layouts instead of silently dropping files.
jq -e '([.assets[].name] | sort) == (["deploy.sh","deploy.tar","deploy.tar.gz","SHA256SUMS"] | sort)' "$previous/release.json" >/dev/null
gh release download "$base" --dir "$previous" -p deploy.sh -p deploy.tar.gz -p SHA256SUMS
git worktree add --detach "$work/tree" "refs/tags/$base"
python3 "$root/.github/scripts/prepare-image-release.py" "$work/tree" "$previous" "$out" "$COMPONENT" "$IMAGE_TAG" "$tag"
(cd "$out" && sha256sum -c SHA256SUMS && bash -n deploy.sh)
cd "$work/tree"
git add -- .env.workbench deploy.sh README.md
if git show-ref --verify --quiet "refs/tags/$tag"; then
  git diff --cached --quiet "$tag" --
else
  git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' commit -m "$event"
  git tag "$tag"
  git push origin "refs/tags/$tag"
fi
if ! gh release view "$tag" --json isDraft --jq .isDraft > "$work/draft"; then
  gh release create "$tag" --verify-tag --draft --title "$(cat "$out/title")" --notes-file "$out/notes.md"
else
  [[ "$(cat "$work/draft")" == true ]] || { echo 'Release already published; refusing to overwrite it.' >&2; exit 1; }
fi
gh release upload "$tag" "$out"/{deploy.sh,deploy.tar,deploy.tar.gz,SHA256SUMS} --clobber
# Check what GitHub actually stored before exposing the draft as Latest.
gh release view "$tag" --json assets > "$work/remote-assets.json"
for asset in deploy.sh deploy.tar deploy.tar.gz SHA256SUMS; do
  digest=$(sha256sum "$out/$asset" | cut -d' ' -f1)
  jq -e --arg name "$asset" --arg digest "sha256:$digest" \
    '[.assets[] | select(.name == $name and .digest == $digest)] | length == 1' "$work/remote-assets.json" >/dev/null
done
[[ "$(gh api "repos/$GH_REPO/releases/latest" --jq .tag_name)" == "$base" ]]
gh release edit "$tag" --draft=false --latest
gh release view "$tag" --json url --jq .url >> "$GITHUB_STEP_SUMMARY"
