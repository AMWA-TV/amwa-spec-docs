#!/usr/bin/env bash
#
# Upload the built Zensical site to the AMWA web server using an atomic
# replacement under /var/www/$SPEC_SERVER/new/$SITE_NAME.

set -o errexit

for var in SSH_USER SSH_HOST SSH_PRIVATE_KEY SSH_KNOWN_HOSTS SPEC_SERVER SITE_NAME; do
    if [[ -z "${!var:-}" ]]; then
        echo "$var not set" >&2
        exit 1
    fi
done

# Keep values that become SSH arguments separate. In particular, a placeholder
# such as '-' in SSH_USER becomes an option-like target ("-@host").
if [[ "${SSH_USER:0:1}" == "-" || "${SSH_USER}" == *"@"* || "${SSH_USER}" == *" "* ]]; then
    echo "SSH_USER must be a username only (not '-', user@host, or an option)" >&2
    exit 1
fi
if [[ "${SSH_HOST:0:1}" == "-" || "${SSH_HOST}" == *"://"* || "${SSH_HOST}" == *"/"* || "${SSH_HOST}" == *"@"* || "${SSH_HOST}" == *" "* ]]; then
    echo "SSH_HOST must be a hostname only (not a URL, user@host, or an option)" >&2
    exit 1
fi

if [[ ! -d site ]]; then
    echo "error: ./site not found (run zensical build first)" >&2
    exit 1
fi

dest="/var/www/$SPEC_SERVER/new/$SITE_NAME"

if [[ -e .ssh ]]; then
    echo "Temp .ssh already exists: exiting for safety" >&2
    exit 1
fi

mkdir .ssh
chmod 700 .ssh
printf '%s\n' "$SSH_PRIVATE_KEY" > .ssh/id_rsa
chmod 600 .ssh/id_rsa
printf '%s\n' "$SSH_KNOWN_HOSTS" > .ssh/known_hosts
chmod 600 .ssh/known_hosts

cleanup() {
    rm -rf .ssh "${SITE_NAME}.tar.gz"
}
trap cleanup EXIT

tar_file="${SITE_NAME}.tar.gz"
tar -czf "$tar_file" site

ssh_options=(-i .ssh/id_rsa -o UserKnownHostsFile=.ssh/known_hosts)
ssh_target="$SSH_USER@$SSH_HOST"

ssh "${ssh_options[@]}" "$ssh_target" "mkdir -p /var/www/$SPEC_SERVER/new"
dest_new=$(ssh "${ssh_options[@]}" "$ssh_target" "mktemp -d $dest.XXXXXX")

if ! scp "${ssh_options[@]}" "$tar_file" "$ssh_target:$dest_new/"; then
    ssh "${ssh_options[@]}" "$ssh_target" "rm -rf '$dest_new'"
    exit 1
fi

ssh "${ssh_options[@]}" "$ssh_target" \
    "cd '$dest_new' && tar --strip-components=1 -xf '$tar_file'"
ssh "${ssh_options[@]}" "$ssh_target" \
    "if [ -e '$dest' ]; then mv '$dest' '$dest.old'; fi; mv '$dest_new' '$dest'; chmod 775 '$dest'; rm -rf '$dest.old'"

echo "Site is https://$SPEC_SERVER/new/$SITE_NAME"
