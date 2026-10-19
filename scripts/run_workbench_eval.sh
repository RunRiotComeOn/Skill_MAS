#!/usr/bin/env bash
# Evaluate a skill (or the single-agent baseline) on WorkBench.
# Run from the parent of Skill_MAS/:
#   bash Skill_MAS/scripts/run_workbench_eval.sh <name> single
#   bash Skill_MAS/scripts/run_workbench_eval.sh <name> skill Skill_MAS/init_skill/SKILL.md
set -u
PACKAGE_ROOT="$(pwd)"
export PYTHONPATH="${PACKAGE_ROOT}:${PACKAGE_ROOT}/Skill_MAS/dataset"
mkdir -p results/wb
python Skill_MAS/dataset/workbench/run_eval.py --mode "$2" ${3:+--skill "$3"} \
  --n-per-domain "${N_PER_DOMAIN:-30}" --seed "${SEED:-0}" --max-concurrency "${MAX_CONCURRENCY:-8}" \
  --out "results/wb/$1" > "results/wb/$1.log" 2>&1
