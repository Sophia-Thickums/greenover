#!/usr/bin/env bash
# The exact terminal session the demo video records. Deterministic, no network, no GPU.
cd "$(dirname "$0")/falsegreen-repo"

banner() { printf '\n\033[1;36m$\033[0m \033[1m%s\033[0m\n' "$1"; sleep 1.8; }

clear
printf '\033[1mFalse Green\033[0m — does your monitoring actually monitor?\n'
sleep 3.5

banner "git clone https://github.com/Sophia-Thickums/greenover"
printf '\033[2mCloning into greenover...\033[0m\n'; sleep 1.2
printf 'remote: Enumerating objects: 42, done.\n'; sleep 0.5
printf 'Receiving objects: 100%% (42/42), 24.18 KiB | 3.02 MiB/s, done.\n'; sleep 1.2

banner "cd greenover && python3 -m falsegreen --selftest"
python3 -m falsegreen --selftest
sleep 3.5

banner "python3 -m falsegreen --demo"
python3 -m falsegreen --demo
sleep 3.5

banner "python3 audit_reference_pipelines.py"
python3 audit_reference_pipelines.py
sleep 4.0

printf '\n\033[1;32mgreen over nothing, on every pattern that ships.\033[0m\n'
printf '\033[2mgithub.com/Sophia-Thickums/greenover\033[0m\n'
sleep 4.0
