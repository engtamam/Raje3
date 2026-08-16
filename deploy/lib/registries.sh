# shellcheck shell=sh
#
# /etc/rancher/k3s/registries.yaml has TWO authors, and each used to write the whole file (ل-5).
#
#   install.sh  writes `configs: "ghcr.io":` — the credential without which the eighteen private
#               platform images cannot be pulled at all.
#   registry.sh writes `mirrors: "127.0.0.1:PORT":` and its `configs:` entry — the node-local
#               mirror the fast ship path pulls from.
#
# Both used `cat >` / `tee`, so whichever ran last erased the other and then restarted k3s so the
# loss took effect. The symptom is an ImagePullBackOff that reads like a broken registry rather
# than a file that was overwritten, and it went in both directions depending on the order the
# operator happened to use.
#
# THE UNIT IS THE ENTRY, NOT THE SECTION — because `configs:` is co-owned: ghcr's credential and
# the local mirror's `insecure_skip_verify` are two entries under the same key. A helper that
# replaced whole sections would have let the same overwrite back in through the smaller door.
#
#   registries_entry <file> <section> <key> <<'YAML'
#     "127.0.0.1:5055":
#       endpoint:
#         - "http://127.0.0.1:5055"
#   YAML
#
# Any existing entry under <section> whose key matches <key> is replaced; every other entry, under
# this section or any other, survives verbatim. A missing file is an empty one.
#
# It is awk over an indentation shape, not a YAML library, because it runs on the node where
# nothing richer than a POSIX shell is promised. The shape it handles is the one these two scripts
# write: a top-level `key:` in column 1, entries indented two spaces, their contents deeper.

registries_entry() {
  _re_file="$1"; _re_section="$2"; _re_key="$3"
  _re_body="$(cat)"
  _re_tmp="${_re_file}.merging.$$"

  [ -f "$_re_file" ] || : > "$_re_file"

  # 1. everything except the named entry, with the section header kept if it has other entries
  awk -v section="$_re_section" -v key="$_re_key" '
    # A top-level key opens a section and closes the previous one.
    /^[^[:space:]#]/ {
      hdr = $0; sub(/:.*/, "", hdr)
      insec = (hdr == section)
      drop = 0
      print
      next
    }
    # An entry header inside the section we are editing: two spaces, then the key.
    insec && /^  [^[:space:]]/ {
      ent = $0
      sub(/^  /, "", ent); sub(/:.*/, "", ent); gsub(/"/, "", ent)
      # QUOTES OFF BOTH SIDES. Callers name the entry as it is written — `"ghcr.io"` — and
      # stripping them from only one side made every comparison false: a re-run appended a SECOND
      # ghcr entry instead of replacing the first, and a rotated token then sat below the stale one
      # in a file where the first occurrence wins.
      # (No apostrophes in here: the awk program is inside a single-quoted shell string.)
      want = key; gsub(/"/, "", want)
      drop = (ent == want)
    }
    !drop { print }
  ' "$_re_file" > "$_re_tmp"

  # 2. the section header, if the file did not already have one
  grep -q "^${_re_section}:" "$_re_tmp" || printf '%s:\n' "$_re_section" >> "$_re_tmp"

  # 3. the entry itself, appended under its section — which requires the section to be last, so
  #    the block is re-emitted in full rather than spliced. Two sections, both rewritten this way,
  #    stay legal YAML because a top-level key may appear only once and this never duplicates one.
  awk -v section="$_re_section" -v body="$_re_body" '
    /^[^[:space:]#]/ {
      hdr = $0; sub(/:.*/, "", hdr)
      if (insec) { printf "%s\n", body; insec = 0 }
      insec = (hdr == section)
      print
      next
    }
    { print }
    END { if (insec) printf "%s\n", body }
  ' "$_re_tmp" > "$_re_tmp.2"

  chmod 600 "$_re_tmp.2" 2>/dev/null || true
  mv "$_re_tmp.2" "$_re_file"
  rm -f "$_re_tmp"
}
