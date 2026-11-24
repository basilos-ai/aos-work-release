#!/bin/sh
# POSIX sh launcher for the pinned official AOS quick installer.
set -eu

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

valid_domain() {
    [ "${#1}" -le 253 ] || return 1
    printf '%s\n' "$1" | LC_ALL=C awk '
      /[^a-z0-9.-]/ || !/\./ {exit 1}
      {n=split($0,a,"."); for(i=1;i<=n;i++)
        if(length(a[i])<1 || length(a[i])>63 || a[i] ~ /^-/ || a[i] ~ /-$/) exit 1}
      /^[0-9.]+$/ {exit 1}
      /\.(local|localhost|test|invalid)$/ {exit 1}'
}

ask_domain() {
    while :; do
        printf '%s: ' "$1" >/dev/tty
        IFS= read -r domain </dev/tty || die 'Cannot read domain from terminal.'
        domain=$(printf '%s' "$domain" | tr '[:upper:]' '[:lower:]')
        if valid_domain "$domain"; then printf '%s\n' "$domain"; return; fi
        printf 'Enter a public DNS name only, without https://, port or path.\n' >/dev/tty
    done
}

main() {
    [ "$(id -u)" = 0 ] || die 'Run with: curl -fsSL URL | sudo sh'
    [ "$(uname -s)" = Linux ] || die 'Linux is required.'
    grep -Eq '^ID=(ubuntu|debian|"ubuntu"|"debian")$' /etc/os-release ||
        die 'Ubuntu or Debian is required.'
    [ -d /run/systemd/system ] || die 'systemd must be running.'

    version=v2026.11.24-quick-install-preview.1
    digest=dcef9452a473c5bf62cf85d72eb2d1115b2c72486ca0a7bef33de5028723d997
    url="https://github.com/basilos-ai/aos-work-release/releases/download/$version/deploy.sh"
    deploy_dir=/opt/aos-work
    [ "$#" -eq 0 ] || [ "$#" -eq 3 ] || die 'Usage: sh install-aos.sh [WORK_DOMAIN STUDIO_DOMAIN STORAGE_DOMAIN]'
    if [ "$#" -eq 3 ]; then
        work_domain=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
        studio_domain=$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')
        storage_domain=$(printf '%s' "$3" | tr '[:upper:]' '[:lower:]')
    else
        printf 'Enter three distinct domains pointing to this server. TCP 80/443 must be reachable.\n'
        work_domain=$(ask_domain 'AOS Work domain')
        studio_domain=$(ask_domain 'Studio domain')
        storage_domain=$(ask_domain 'Storage domain')
    fi
    for domain in "$work_domain" "$studio_domain" "$storage_domain"; do
        valid_domain "$domain" || die "Invalid domain: $domain"
        getent ahosts "$domain" >/dev/null || die "DNS lookup failed: $domain"
    done
    [ "$work_domain" != "$studio_domain" ] && [ "$work_domain" != "$storage_domain" ] &&
        [ "$studio_domain" != "$storage_domain" ] || die 'The three domains must be distinct.'

    for command in curl bash flock sha256sum; do
        command -v "$command" >/dev/null 2>&1 || die "Missing command: $command. Install curl, bash, util-linux and coreutils first."
    done
    [ ! -L "$deploy_dir" ] || die 'Deployment directory must not be a symlink.'
    mkdir -p "$deploy_dir"
    cd "$deploy_dir"
    exec 9> .launcher.lock
    flock -n 9 || die 'Another launcher is running.'
    umask 077
    tmp=$(mktemp -d "$deploy_dir/.launcher.XXXXXXXX")
    trap 'rm -rf -- "$tmp"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    printf 'AOS_WORK_DOMAIN=%s\nSTUDIO_DOMAIN=%s\nSTORAGE_DOMAIN=%s\n' \
        "$work_domain" "$studio_domain" "$storage_domain" > "$tmp/.env"

    [ ! -L .env ] && [ ! -L deploy.sh ] || die 'Configuration or installer is a symlink.'
    if [ -e .env ]; then
        cmp -s .env "$tmp/.env" || die "Existing configuration differs. Inspect $deploy_dir/.env before retrying."
    else
        # Existing deployment data must never be overwritten by this launcher.
        for existing in .aos-install .env.middleware .env.workbench .env.studio data compose workbench; do
            [ ! -e "$existing" ] && [ ! -L "$existing" ] || die "Existing deployment found: $deploy_dir/$existing"
        done
        mv "$tmp/.env" .env
    fi
    printf 'Downloading official installer %s ...\n' "$version"
    curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
        --retry 3 --connect-timeout 20 --max-time 300 "$url" -o "$tmp/deploy.sh"
    printf '%s  %s\n' "$digest" "$tmp/deploy.sh" | sha256sum -c -
    mv "$tmp/deploy.sh" deploy.sh
    chmod 600 .env deploy.sh
    printf 'Starting installation in %s ...\n' "$deploy_dir"
    if bash ./deploy.sh --quick-install; then
        printf '\nInstallation completed. Open https://%s\n' "$work_domain"
        printf 'Fresh-install administrator: admin / Admin@12345. Change the password after login.\n'
    else
        printf '\nInstallation failed. Resolve the error above, then rerun with the same domains.\n' >&2
        printf 'Deployment files are preserved in %s.\n' "$deploy_dir" >&2
        exit 1
    fi
}

main "$@"

